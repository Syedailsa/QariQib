# services/attendance.py
from datetime import datetime, timezone
from db.supabase import supabase
from services.alerts import create_alert, resolve_alert, THRESHOLDS
from services.schedule import get_schedule
import re


def parse_dt(dt_str: str) -> datetime:
    dt_str = dt_str.replace('Z', '+00:00')
    dt_str = re.sub(
        r'(\d{2}:\d{2}:\d{2})\.(\d+)([+-]\d{2}:\d{2})',
        lambda m: f"{m.group(1)}.{m.group(2)[:6].ljust(6, '0')}{m.group(3)}",
        dt_str
    )
    return datetime.fromisoformat(dt_str)


def minutes_since(dt_str: str) -> float:
    return (datetime.now(timezone.utc) - parse_dt(dt_str)).total_seconds() / 60


def get_teacher_by_email(email: str):
    result = supabase.table('teachers').select('*').eq('email', email).execute()
    return result.data[0] if result.data else None


def get_student_enrollment_by_registrant(registrant_id: str, schedule_id: str):
    result = supabase.table('class_students') \
        .select('*, students(*)') \
        .eq('zoom_registrant_id', registrant_id) \
        .eq('schedule_id', schedule_id) \
        .execute()
    return result.data[0] if result.data else None


def resolve_absence(schedule_id: str, participant_id: str):
    """Mark absence as resolved when participant joins late."""
    supabase.table('absences').update({
        'resolved':    True,
        'resolved_at': datetime.now(timezone.utc).isoformat()
    }).eq('schedule_id', schedule_id) \
      .eq('participant_id', participant_id) \
      .eq('resolved', False) \
      .execute()
    print(f'[ABSENCE RESOLVED] participant {participant_id} joined', flush=True)


def on_participant_joined(payload: dict):
    obj = payload['object']
    zoom_meeting_id = str(obj['id'])
    participant = obj['participant']
    join_time = participant.get('join_time') or datetime.now(timezone.utc).isoformat()
    registrant_id = participant.get('registrant_id', '')
    participant_email = participant.get('email', '')

    print(f'[DEBUG] email: "{participant_email}" | registrant_id: "{registrant_id}"', flush=True)

    schedule = get_schedule(zoom_meeting_id)
    if not schedule:
        print(f'[SKIP] No schedule for meeting {zoom_meeting_id}', flush=True)
        return

    if schedule['status'] in ('completed', 'missed'):
        print(f'[SKIP] Meeting already {schedule["status"]} — stale webhook ignored', flush=True)
        return

    mins_late = minutes_since(schedule['scheduled_start'])

    if registrant_id:
        # Student
        enrollment = get_student_enrollment_by_registrant(registrant_id, schedule['id'])
        if not enrollment:
            print(f'[UNKNOWN] Unregistered student: registrant_id="{registrant_id}"')
            return

        student = enrollment['students']
        participant_id = student['id']
        name = student['full_name']
        participant_type = 'student'
        absent_alert_type = 'student_absent'

    else:
        # Teacher/host
        teacher = get_teacher_by_email(participant_email)
        if not teacher:
            print(f'[UNKNOWN] Host not found in teachers: {participant_email}')
            return

        participant_id = teacher['id']
        name = teacher['full_name']
        participant_type = 'teacher'
        absent_alert_type = 'teacher_absent'

    # Idempotency check — must run BEFORE any writes so Zoom retries are fully blocked
    existing_record = supabase.table('attendance_records') \
        .select('id') \
        .eq('schedule_id', schedule['id']) \
        .eq('participant_id', participant_id) \
        .is_('leave_time', 'null') \
        .execute()

    if existing_record.data:
        print(f'[SKIP] Duplicate join event for {participant_id} — already has open record', flush=True)
        return

    # Resolve any existing absence record and alert
    resolve_absence(schedule['id'], participant_id)
    resolve_alert(schedule['id'], absent_alert_type)

    # Determine status and create late/absent alerts
    if participant_type == 'student':
        if mins_late > THRESHOLDS['student_absent_mins']:
            create_alert(
                schedule_id=schedule['id'],
                alert_type='participant_late',
                student_id=participant_id,
                notes=f'{name} (Student) joined {mins_late:.1f} mins late — was marked absent'
            )
            status = 'late'
        elif mins_late > THRESHOLDS['participant_late_mins']:
            create_alert(
                schedule_id=schedule['id'],
                alert_type='participant_late',
                student_id=participant_id,
                notes=f'{name} (Student) joined {mins_late:.1f} mins after scheduled start'
            )
            status = 'late'
        else:
            status = 'present'
    else:
        if mins_late > THRESHOLDS['teacher_absent_mins']:
            create_alert(
                schedule_id=schedule['id'],
                alert_type='teacher_late',
                teacher_id=participant_id,
                notes=f'{name} (Teacher) joined {mins_late:.1f} mins late — was marked absent'
            )
            status = 'late'
        elif mins_late > THRESHOLDS['teacher_late_mins']:
            create_alert(
                schedule_id=schedule['id'],
                alert_type='teacher_late',
                teacher_id=participant_id,
                notes=f'{name} (Teacher) joined {mins_late:.1f} mins after scheduled start'
            )
            status = 'late'
        else:
            status = 'present'

    result = supabase.table('attendance_records').insert({
        'schedule_id':      schedule['id'],
        'participant_type': participant_type,
        'participant_id':   participant_id,
        'join_time':        join_time,
        'status':           status
    }).execute()

    if not result.data:
        print(f'[ATTENDANCE ERROR] Insert returned no data for {participant_type} {participant_id} — check table constraints', flush=True)
    else:
        print(f'[JOINED] {participant_type} {name} → {status}', flush=True)


def on_participant_left(payload: dict):
    obj = payload['object']
    zoom_meeting_id = str(obj['id'])
    participant = obj['participant']
    leave_time = participant.get('leave_time') or datetime.now(timezone.utc).isoformat()
    registrant_id = participant.get('registrant_id', '')
    participant_email = participant.get('email', '')

    schedule = get_schedule(zoom_meeting_id)
    if not schedule:
        print(f'[SKIP] No schedule for meeting {zoom_meeting_id}', flush=True)
        return

    # Only hard-skip for 'missed' — 'completed' can race with this event:
    # meeting.ended fires first → status='completed' → then participant_left arrives.
    # The attendance record check below handles truly stale webhooks for completed meetings.
    if schedule['status'] == 'missed':
        print(f'[SKIP] Meeting missed — stale webhook ignored', flush=True)
        return

    if registrant_id:
        enrollment = get_student_enrollment_by_registrant(registrant_id, schedule['id'])
        if not enrollment:
            print(f'[SKIP] Unknown registrant left: {registrant_id}')
            return
        participant_id = enrollment['students']['id']
        participant_name = enrollment['students']['full_name']
        participant_type = 'student'
    else:
        teacher = get_teacher_by_email(participant_email)
        if not teacher:
            print(f'[SKIP] Unknown host left: {participant_email}')
            return
        participant_id = teacher['id']
        participant_name = teacher['full_name']
        participant_type = 'teacher'

    attendance = supabase.table('attendance_records') \
        .select('*') \
        .eq('schedule_id', schedule['id']) \
        .eq('participant_id', participant_id) \
        .is_('leave_time', 'null') \
        .execute()

    if not attendance.data:
        print(f'[SKIP] No open attendance record for {participant_id}')
        return

    record = attendance.data[0]
    join_dt = parse_dt(record['join_time'])
    leave_dt = parse_dt(leave_time)
    duration_mins = int((leave_dt - join_dt).total_seconds() / 60)

    scheduled_end = parse_dt(schedule['scheduled_end'])
    mins_before_end = (scheduled_end - leave_dt).total_seconds() / 60
    status = record['status']

    if mins_before_end > THRESHOLDS['early_departure_mins']:
        status = 'early_departure'
        # FIX: was previously broken for students (student_id was always None)
        create_alert(
            schedule_id=schedule['id'],
            alert_type='early_departure',
            teacher_id=participant_id if participant_type == 'teacher' else None,
            student_id=participant_id if participant_type == 'student' else None,
            notes=f'{participant_name} ({participant_type.title()}) left {mins_before_end:.1f} mins before class ended'
        )

    supabase.table('attendance_records').update({
        'leave_time':    leave_time,
        'duration_mins': duration_mins,
        'status':        status
    }).eq('id', record['id']).execute()

    print(f'[LEFT] {participant_type} {participant_name} → {duration_mins} mins → {status}', flush=True)