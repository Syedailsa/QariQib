from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from db.supabase import supabase
from services.class_service import setup_class
from services.scheduler import schedule_class_jobs
from datetime import datetime

router = APIRouter(prefix='/api/v1/schedules', tags=['schedules'])


class ScheduleCreate(BaseModel):
    teacher_id: str
    student_ids: List[str]
    scheduled_start: str
    scheduled_end: str
    scheduled_duration_mins: int
    session_type: str = 'group'


class ScheduleUpdate(BaseModel):
    scheduled_start: Optional[str] = None
    scheduled_end: Optional[str] = None
    scheduled_duration_mins: Optional[int] = None
    session_type: Optional[str] = None


@router.get('')
def list_schedules():
    result = supabase.table('class_schedules') \
        .select('''
            *,
            teachers(id, full_name, email),
            class_students(
                id,
                zoom_registrant_id,
                zoom_join_url,
                students(id, full_name, email)
            ),
            alerts(id, alert_type, severity, is_resolved)
        ''') \
        .order('scheduled_start', desc=True) \
        .execute()
    return result.data


@router.get('/today')
def list_today_schedules():
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date()
    start = f'{today}T00:00:00+00:00'
    end = f'{today}T23:59:59+00:00'

    result = supabase.table('class_schedules') \
        .select('''
            *,
            teachers(id, full_name, email),
            class_students(
                id,
                zoom_registrant_id,
                zoom_join_url,
                students(id, full_name, email)
            )
        ''') \
        .gte('scheduled_start', start) \
        .lte('scheduled_start', end) \
        .order('scheduled_start') \
        .execute()
    return result.data


@router.get('/{schedule_id}')
def get_schedule(schedule_id: str):
    result = supabase.table('class_schedules') \
        .select('''
            *,
            teachers(id, full_name, email),
            class_students(
                id,
                zoom_registrant_id,
                zoom_join_url,
                students(id, full_name, email)
            ),
            attendance_records(*),
            alerts(*, teachers(id, full_name), students(id, full_name))
        ''') \
        .eq('id', schedule_id) \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail='Schedule not found')
    return result.data[0]


@router.post('')
def create_schedule(body: ScheduleCreate):
    teacher = supabase.table('teachers') \
        .select('*') \
        .eq('id', body.teacher_id) \
        .execute()

    if not teacher.data:
        raise HTTPException(status_code=404, detail='Teacher not found')

    if not teacher.data[0]['consent_given']:
        raise HTTPException(
            status_code=403,
            detail='Teacher has not given consent for monitoring'
        )

    schedule = supabase.table('class_schedules').insert({
        'teacher_id':               body.teacher_id,
        'scheduled_start':          body.scheduled_start,
        'scheduled_end':            body.scheduled_end,
        'scheduled_duration_mins':  body.scheduled_duration_mins,
        'session_type':             body.session_type,
        'status':                   'scheduled'
    }).execute()

    schedule_id = schedule.data[0]['id']

    for student_id in body.student_ids:
        supabase.table('class_students').insert({
            'schedule_id': schedule_id,
            'student_id':  student_id
        }).execute()

    try:
        meeting_id = setup_class(schedule_id)
    except Exception as e:
        print(f'[ERROR] Zoom setup failed for {schedule_id}: {e}')
        supabase.table('class_students').delete().eq('schedule_id', schedule_id).execute()
        supabase.table('class_schedules').delete().eq('id', schedule_id).execute()
        raise HTTPException(status_code=503, detail=f'Failed to create Zoom meeting: {str(e)}')

    # Queue Celery tasks in a daemon thread so the HTTP response is never delayed
    # by broker connection latency or a slow/down Redis instance.
    import threading
    def _queue_tasks():
        try:
            scheduled_start_dt = datetime.fromisoformat(body.scheduled_start.replace('Z', '+00:00'))
            schedule_class_jobs(schedule_id, scheduled_start_dt)
        except Exception as e:
            print(f'[WARNING] Failed to queue Celery tasks for {schedule_id}: {e}', flush=True)
    threading.Thread(target=_queue_tasks, daemon=True).start()

    return {
        'schedule_id':    schedule_id,
        'zoom_meeting_id': meeting_id,
        'message':        'Class scheduled and Zoom meeting created'
    }


@router.patch('/{schedule_id}')
def update_schedule(schedule_id: str, body: ScheduleUpdate):
    existing = supabase.table('class_schedules') \
        .select('status, zoom_meeting_id') \
        .eq('id', schedule_id) \
        .execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail='Schedule not found')

    if existing.data[0]['status'] != 'scheduled':
        raise HTTPException(
            status_code=400,
            detail=f'Cannot edit a class with status: {existing.data[0]["status"]}'
        )

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail='No fields to update')

    # Validate start before end
    if body.scheduled_start and body.scheduled_end:
        from datetime import datetime
        start_dt = datetime.fromisoformat(body.scheduled_start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(body.scheduled_end.replace('Z', '+00:00'))
        if end_dt <= start_dt:
            raise HTTPException(
                status_code=400,
                detail='End time must be after start time'
            )

    result = supabase.table('class_schedules') \
        .update(updates) \
        .eq('id', schedule_id) \
        .execute()

    # Update Zoom meeting
    try:
        import httpx
        from services.zoom_api import get_headers
        zoom_meeting_id = existing.data[0]['zoom_meeting_id']
        if zoom_meeting_id:
            update_payload = {}
            if body.scheduled_start:
                from datetime import datetime
                dt = datetime.fromisoformat(body.scheduled_start.replace('Z', '+00:00'))
                update_payload['start_time'] = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            if body.scheduled_duration_mins:
                update_payload['duration'] = body.scheduled_duration_mins
            if update_payload:
                httpx.patch(
                    f'https://api.zoom.us/v2/meetings/{zoom_meeting_id}',
                    headers=get_headers(),
                    json=update_payload
                )
                print(f'[ZOOM] Meeting {zoom_meeting_id} updated')
    except Exception as e:
        print(f'[ZOOM] Failed to update meeting: {e}')

    # If the start time changed, old ETA tasks would fire at the wrong time.
    # Revoke them and re-queue at the new time. Non-fatal: recover_missing_tasks
    # on next startup handles it if Celery/Redis is unavailable.
    if body.scheduled_start:
        import threading
        _new_start = body.scheduled_start
        def _reschedule():
            try:
                from services.scheduler import revoke_class_jobs, schedule_class_jobs
                new_start_dt = datetime.fromisoformat(_new_start.replace('Z', '+00:00'))
                revoke_class_jobs(schedule_id)
                schedule_class_jobs(schedule_id, new_start_dt)
            except Exception as e:
                print(f'[WARNING] Failed to reschedule Celery tasks for {schedule_id}: {e}', flush=True)
        threading.Thread(target=_reschedule, daemon=True).start()

    return result.data[0]

@router.delete('/{schedule_id}', status_code=204)
def delete_schedule(schedule_id: str):
    existing = supabase.table('class_schedules') \
        .select('status, zoom_meeting_id') \
        .eq('id', schedule_id) \
        .execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail='Schedule not found')

    # Cancel Celery tasks BEFORE deleting DB records — if we deleted first and
    # a task fired in the gap it would crash trying to query a deleted schedule
    try:
        from services.scheduler import revoke_class_jobs
        revoke_class_jobs(schedule_id)
    except Exception as e:
        print(f'[WARNING] Could not revoke Celery tasks for {schedule_id}: {e}', flush=True)

    zoom_meeting_id = existing.data[0].get('zoom_meeting_id')

    # Delete Zoom meeting if exists
    if zoom_meeting_id:
        try:
            import httpx
            from services.zoom_api import get_headers
            httpx.delete(
                f'https://api.zoom.us/v2/meetings/{zoom_meeting_id}',
                headers=get_headers()
            )
            print(f'[ZOOM] Meeting {zoom_meeting_id} deleted')
        except Exception as e:
            print(f'[ZOOM] Failed to delete meeting: {e}')

    # Delete related records first (foreign key constraints)
    supabase.table('attendance_records').delete().eq('schedule_id', schedule_id).execute()
    supabase.table('alerts').delete().eq('schedule_id', schedule_id).execute()
    supabase.table('absences').delete().eq('schedule_id', schedule_id).execute()
    supabase.table('class_students').delete().eq('schedule_id', schedule_id).execute()

    # Delete the schedule itself
    supabase.table('class_schedules').delete().eq('id', schedule_id).execute()

    return None