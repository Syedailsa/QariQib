from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from db.supabase import supabase
from services.class_service import setup_class

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
            )
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
            alerts(*)
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

    meeting_id = setup_class(schedule_id)

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

    updates = {k: v for k, v in body.dict().items() if v is not None}
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

    return result.data[0]