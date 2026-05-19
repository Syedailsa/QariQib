# services/schedule.py
from datetime import datetime, timezone
from db.supabase import supabase


def get_schedule(zoom_meeting_id: str):
    result = supabase.table('class_schedules') \
        .select('*') \
        .eq('zoom_meeting_id', zoom_meeting_id) \
        .execute()
    return result.data[0] if result.data else None


def on_meeting_started(payload: dict):
    from services.scheduler import schedule_class_jobs
    obj = payload['object']
    zoom_meeting_id = str(obj['id'])
    start_time = obj['start_time']

    schedule = get_schedule(zoom_meeting_id)
    if not schedule:
        print(f'[SKIP] No schedule for meeting {zoom_meeting_id}')
        return

    # Skip if already processed — live or completed
    if schedule['status'] in ('live', 'completed', 'missed'):
        print(f'[SKIP] Schedule {schedule["id"]} already {schedule["status"]} — duplicate event ignored')
        return

    supabase.table('class_schedules').update({
        'status':       'live',
        'actual_start': start_time
    }).eq('id', schedule['id']).execute()

    print(f'[MEETING STARTED] Schedule {schedule["id"]} is now live')

    scheduled_start = datetime.fromisoformat(
        schedule['scheduled_start'].replace('Z', '+00:00')
    )
    schedule_class_jobs(schedule['id'], scheduled_start)


def on_meeting_ended(payload: dict):
    obj = payload['object']
    zoom_meeting_id = str(obj['id'])
    end_time = obj.get('end_time') or datetime.now(timezone.utc).isoformat()

    schedule = get_schedule(zoom_meeting_id)
    if not schedule:
        return

    actual_start = schedule.get('actual_start')
    actual_duration = None
    duration_diff = None

    if actual_start:
        start_dt = datetime.fromisoformat(actual_start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        actual_duration = int((end_dt - start_dt).total_seconds() / 60)
        duration_diff = actual_duration - schedule['scheduled_duration_mins']

    supabase.table('class_schedules').update({
        'status':               'completed',
        'actual_end':           end_time,
        'actual_duration_mins': actual_duration,
        'duration_diff_mins':   duration_diff
    }).eq('id', schedule['id']).execute()

    print(f'[MEETING ENDED] actual: {actual_duration} mins, diff: {duration_diff} mins')