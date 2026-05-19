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
    result = supabase.table('teachers') \
        .select('*') \
        .eq('email', email) \
        .execute()
    return result.data[0] if result.data else None


def get_student_enrollment_by_registrant(registrant_id: str, schedule_id: str):
    result = supabase.table('class_students') \
        .select('*, students(*)') \
        .eq('zoom_registrant_id', registrant_id) \
        .eq('schedule_id', schedule_id) \
        .execute()
    return result.data[0] if result.data else None


def on_participant_joined(payload: dict):
    obj = payload['object']
    zoom_meeting_id = str(obj['id'])
    participant = obj['participant']
    join_time = participant.get('join_time') or datetime.now(timezone.utc).isoformat()
    registrant_id = participant.get('registrant_id', '')
    participant_email = participant.get('email', '')

    print(f'[DEBUG] email: "{participant_email}" | registrant_id: "{registrant_id}"')

    schedule = get_schedule(zoom_meeting_id)
    if not schedule:
        print(f'[SKIP] No schedule for meeting {zoom_meeting_id}')
        return

    if schedule['status'] in ('completed', 'missed'):
        print(f'[SKIP] Meeting already {schedule["status"]} — stale webhook ignored')
        return

    mins_late = minutes_since(schedule['scheduled_start'])

    if registrant_id:
        # Has registrant_id = always a student
        enrollment = get_student_enrollment_by_registrant(registrant_id, schedule['id'])

        if enrollment:
            student = enrollment['students']
            participant_type = 'student'
            participant_id = student['id']
            name = student['full_name']
        else:
            print(f'[UNKNOWN] Unregistered student: registrant_id="{registrant_id}"')
            participant_type = 'student'
            participant_id = None
            name = 'Unknown'

        if mins_late > THRESHOLDS['participant_late_mins']:
            create_alert(
                schedule_id=schedule['id'],
                alert_type='participant_late',
                student_id=participant_id,
                notes=f'Student joined {mins_late:.1f} mins after scheduled start'
            )
            status = 'late'
        else:
            status = 'present'

        print(f'[JOINED] student {name} → {status}')

    else:
        # No registrant_id = host = teacher
        teacher = get_teacher_by_email(participant_email)
        if not teacher:
            print(f'[UNKNOWN] Host not found in teachers: {participant_email}')
            return

        participant_type = 'teacher'
        participant_id = teacher['id']

        if mins_late > THRESHOLDS['teacher_absent_mins']:
            create_alert(
                schedule_id=schedule['id'],
                alert_type='teacher_late',
                teacher_id=teacher['id'],
                notes=f'Teacher joined {mins_late:.1f} mins after scheduled start'
            )
            resolve_alert(schedule['id'], 'teacher_absent')

        status = 'late' if mins_late > THRESHOLDS['teacher_absent_mins'] else 'present'
        print(f'[JOINED] teacher {teacher["email"]} → {status}')

    supabase.table('attendance_records').insert({
        'schedule_id':      schedule['id'],
        'participant_type': participant_type,
        'participant_id':   participant_id,
        'join_time':        join_time,
        'status':           status
    }).execute()


def on_participant_left(payload: dict):
    obj = payload['object']
    zoom_meeting_id = str(obj['id'])
    participant = obj['participant']
    leave_time = participant.get('leave_time') or datetime.now(timezone.utc).isoformat()
    registrant_id = participant.get('registrant_id', '')
    participant_email = participant.get('email', '')

    schedule = get_schedule(zoom_meeting_id)
    if not schedule:
        print(f'[SKIP] No schedule for meeting {zoom_meeting_id}')
        return

    # Ignore stale events
    if schedule['status'] in ('completed', 'missed'):
        print(f'[SKIP] Meeting already {schedule["status"]} — stale webhook ignored')
        return

    teacher = None

    if registrant_id:
        # Student
        enrollment = get_student_enrollment_by_registrant(registrant_id, schedule['id'])
        if enrollment:
            participant_id = enrollment['students']['id']
            participant_type = 'student'
        else:
            print(f'[SKIP] Unknown registrant left: {registrant_id}')
            return
    else:
        # Teacher/host
        teacher = get_teacher_by_email(participant_email)
        if not teacher:
            print(f'[SKIP] Unknown host left: {participant_email}')
            return
        participant_id = teacher['id']
        participant_type = 'teacher'

    # Get open attendance record
    attendance = supabase.table('attendance_records') \
        .select('*') \
        .eq('schedule_id', schedule['id']) \
        .eq('participant_id', participant_id) \
        .is_('leave_time', 'null') \
        .execute()

    if not attendance.data:
        print(f'[SKIP] No open attendance record for participant_id {participant_id}')
        return

    attendance_record = attendance.data[0]

    join_dt = parse_dt(attendance_record['join_time'])
    leave_dt = parse_dt(leave_time)
    duration_mins = int((leave_dt - join_dt).total_seconds() / 60)

    scheduled_end = parse_dt(schedule['scheduled_end'])
    mins_before_end = (scheduled_end - leave_dt).total_seconds() / 60
    status = attendance_record['status']

    if mins_before_end > THRESHOLDS['early_departure_mins']:
        status = 'early_departure'
        create_alert(
            schedule_id=schedule['id'],
            alert_type='early_departure',
            teacher_id=teacher['id'] if teacher else None,
            student_id=None if teacher else participant_id,
            notes=f'Left {mins_before_end:.1f} mins before class ended'
        )

    supabase.table('attendance_records').update({
        'leave_time':    leave_time,
        'duration_mins': duration_mins,
        'status':        status
    }).eq('id', attendance_record['id']).execute()

    print(f'[LEFT] {participant_type} → {duration_mins} mins → {status}')