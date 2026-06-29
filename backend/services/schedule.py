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
    obj = payload['object']
    zoom_meeting_id = str(obj['id'])
    start_time = obj['start_time']

    schedule = get_schedule(zoom_meeting_id)
    if not schedule:
        print(f'[SKIP] No schedule for meeting {zoom_meeting_id}', flush=True)
        return

    if schedule['status'] in ('live', 'completed', 'missed'):
        print(f'[SKIP] Schedule {schedule["id"]} already {schedule["status"]} — duplicate event ignored', flush=True)
        return

    supabase.table('class_schedules').update({
        'status':       'live',
        'actual_start': start_time
    }).eq('id', schedule['id']).execute()

    print(f'[MEETING STARTED] Schedule {schedule["id"]} is now live', flush=True)

    # Trigger RTMS stream — without this call Zoom never fires meeting.rtms_started
    try:
        import httpx
        from services.zoom_api import get_headers
        resp = httpx.post(
            f'https://api.zoom.us/v2/meetings/{zoom_meeting_id}/rtms/start',
            headers=get_headers(),
            timeout=10.0,
        )
        if resp.is_success:
            print(f'[RTMS] Stream start requested for meeting {zoom_meeting_id}', flush=True)
        else:
            print(f'[RTMS] Stream start failed: {resp.status_code} {resp.text}', flush=True)
    except Exception as e:
        print(f'[RTMS] Failed to start stream: {e}', flush=True)


def on_meeting_ended(payload: dict):
    obj = payload['object']
    zoom_meeting_id = str(obj['id'])
    end_time = obj.get('end_time') or datetime.now(timezone.utc).isoformat()

    schedule = get_schedule(zoom_meeting_id)
    if not schedule:
        return

    if schedule['status'] == 'completed':
        print(f'[SKIP] Schedule {schedule["id"]} already completed — duplicate event ignored', flush=True)
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

    # Only alert absent students if the class ran long enough that students
    # had a fair chance to join. If the teacher ended the class before the
    # absent threshold (e.g. after 2 mins), it is the teacher's fault — the
    # ETA task will already see status=completed and skip, which is correct.
    # We only need this safety net when the class DID run past the threshold
    # but the ETA task hasn't fired yet (race condition at exactly 8 mins).
    _alert_absent_students_if_fair(schedule['id'], actual_duration)

    # Delete the Zoom meeting so the host cannot restart it after class ends
    try:
        import httpx
        from services.zoom_api import get_headers
        httpx.delete(
            f'https://api.zoom.us/v2/meetings/{zoom_meeting_id}',
            headers=get_headers()
        )
        print(f'[ZOOM] Meeting {zoom_meeting_id} deleted after completion', flush=True)
    except Exception as e:
        print(f'[ZOOM] Failed to delete meeting after completion: {e}', flush=True)

    print(f'[MEETING ENDED] actual: {actual_duration} mins, diff: {duration_diff} mins', flush=True)


def _alert_absent_students_if_fair(schedule_id: str, actual_duration_mins):
    """
    Create student_absent alerts at completion time ONLY if the class ran
    at least as long as the student_absent threshold.

    Rule: if actual_duration < student_absent_mins, students didn't have
    a fair window to join — no absent alert (teacher ended it too early).
    The teacher already gets an early_departure alert via on_participant_left.

    This function is a safety net for the race condition where the meeting
    ends right around the 8-min mark before the ETA Celery task fires.
    create_alert() is idempotent so duplicates from the Celery task are safe.
    """
    from services.alerts import create_alert, THRESHOLDS

    if actual_duration_mins is None or actual_duration_mins < THRESHOLDS['student_absent_mins']:
        print(
            f'[MEETING ENDED] class ran {actual_duration_mins} mins '
            f'(< {THRESHOLDS["student_absent_mins"]} min threshold) — '
            f'no student absent alerts (teacher ended early)', flush=True
        )
        return

    enrollments = supabase.table('class_students') \
        .select('*, students(*)') \
        .eq('schedule_id', schedule_id) \
        .execute()

    absent_count = 0
    for enrollment in (enrollments.data or []):
        student = enrollment['students']

        joined = supabase.table('attendance_records') \
            .select('id') \
            .eq('schedule_id', schedule_id) \
            .eq('participant_id', student['id']) \
            .execute()

        if joined.data:
            continue

        existing_absence = supabase.table('absences') \
            .select('id') \
            .eq('schedule_id', schedule_id) \
            .eq('participant_id', student['id']) \
            .eq('resolved', False) \
            .execute()
        if not existing_absence.data:
            supabase.table('absences').insert({
                'schedule_id':      schedule_id,
                'participant_type': 'student',
                'participant_id':   student['id'],
                'marked_at':        datetime.now(timezone.utc).isoformat(),
                'resolved':         False
            }).execute()

        create_alert(
            schedule_id=schedule_id,
            alert_type='student_absent',
            student_id=student['id'],
            notes=f'{student["full_name"]} (Student) did not attend (class ran {actual_duration_mins} mins)'
        )
        absent_count += 1

    if absent_count:
        print(f'[MEETING ENDED] {absent_count} student(s) marked absent at completion', flush=True)
