# services/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timezone, timedelta
from db.supabase import supabase
from services.alerts import create_alert, THRESHOLDS

scheduler = BackgroundScheduler(timezone='UTC')


# ─── Job Functions ───────────────────────────────────────────

def check_teacher_absent(schedule_id: str):
    """
    Fires 7 mins after scheduled start.
    If teacher has no attendance record → fire teacher_absent alert.
    """
    print(f'[SCHEDULER] Checking teacher absent for schedule {schedule_id}')

    # Check if teacher has joined
    schedule = supabase.table('class_schedules') \
        .select('*, teachers(*)') \
        .eq('id', schedule_id) \
        .execute()

    if not schedule.data:
        return

    schedule = schedule.data[0]

    # If meeting never started or already completed — skip
    if schedule['status'] not in ('live', 'scheduled'):
        print(f'[SCHEDULER] Schedule {schedule_id} status is {schedule["status"]} — skipping')
        return

    teacher = schedule['teachers']

    # Check if teacher attendance record exists
    attendance = supabase.table('attendance_records') \
        .select('id') \
        .eq('schedule_id', schedule_id) \
        .eq('participant_type', 'teacher') \
        .execute()

    if attendance.data:
        print(f'[SCHEDULER] Teacher already joined — no absent alert needed')
        return

    # Teacher hasn't joined — fire alert
    create_alert(
        schedule_id=schedule_id,
        alert_type='teacher_absent',
        teacher_id=teacher['id'],
        notes=f'Teacher did not join {THRESHOLDS["teacher_absent_mins"]} mins after scheduled start'
    )
    print(f'[SCHEDULER] teacher_absent alert fired for schedule {schedule_id}')


def check_student_absents(schedule_id: str):
    """
    Fires 10 mins after scheduled start.
    For each registered student with no attendance record → fire student_absent alert.
    """
    print(f'[SCHEDULER] Checking student absents for schedule {schedule_id}')

    schedule = supabase.table('class_schedules') \
        .select('id, status') \
        .eq('id', schedule_id) \
        .execute()

    if not schedule.data:
        return

    if schedule.data[0]['status'] not in ('live', 'scheduled'):
        return

    # Get all enrolled students
    enrollments = supabase.table('class_students') \
        .select('*, students(*)') \
        .eq('schedule_id', schedule_id) \
        .execute()

    for enrollment in enrollments.data:
        student = enrollment['students']

        # Check if this student has an attendance record
        attendance = supabase.table('attendance_records') \
            .select('id') \
            .eq('schedule_id', schedule_id) \
            .eq('participant_id', student['id']) \
            .execute()

        if attendance.data:
            continue  # Student already joined

        # Student hasn't joined — fire alert
        create_alert(
            schedule_id=schedule_id,
            alert_type='student_absent',
            student_id=student['id'],
            notes=f'{student["full_name"]} did not join {THRESHOLDS["student_absent_mins"]} mins after scheduled start'
        )
        print(f'[SCHEDULER] student_absent alert fired for {student["full_name"]}')


def check_empty_class(schedule_id: str):
    """
    Fires 15 mins after scheduled start.
    If no participants currently in meeting → fire empty_class alert.
    """
    print(f'[SCHEDULER] Checking empty class for schedule {schedule_id}')

    schedule = supabase.table('class_schedules') \
        .select('id, status') \
        .eq('id', schedule_id) \
        .execute()

    if not schedule.data:
        return

    if schedule.data[0]['status'] != 'live':
        print(f'[SCHEDULER] Meeting not live — skipping empty class check')
        return

    # Check for any open attendance records (participants still in meeting)
    active = supabase.table('attendance_records') \
        .select('id') \
        .eq('schedule_id', schedule_id) \
        .is_('leave_time', 'null') \
        .execute()

    if active.data:
        print(f'[SCHEDULER] {len(active.data)} participants still in meeting — no empty class alert')
        return

    create_alert(
        schedule_id=schedule_id,
        alert_type='empty_class',
        notes=f'No participants in meeting for {THRESHOLDS["empty_class_mins"]} mins'
    )
    print(f'[SCHEDULER] empty_class alert fired for schedule {schedule_id}')


# ─── Schedule Jobs ───────────────────────────────────────────

def schedule_class_jobs(schedule_id: str, scheduled_start: datetime):
    """
    Called when a meeting starts.
    Schedules all background check jobs relative to scheduled_start.
    """
    now = datetime.now(timezone.utc)

    # Teacher absent check — 7 mins after scheduled start
    teacher_absent_time = scheduled_start + timedelta(
        minutes=THRESHOLDS['teacher_absent_mins']
    )
    if teacher_absent_time > now:
        scheduler.add_job(
            check_teacher_absent,
            trigger=DateTrigger(run_date=teacher_absent_time),
            args=[schedule_id],
            id=f'teacher_absent_{schedule_id}',
            replace_existing=True
        )
        print(f'[SCHEDULER] teacher_absent job scheduled for {teacher_absent_time}')
    else:
        # Scheduled start was in the past — run immediately
        check_teacher_absent(schedule_id)

    # Student absent check — 10 mins after scheduled start
    student_absent_time = scheduled_start + timedelta(
        minutes=THRESHOLDS['student_absent_mins']
    )
    if student_absent_time > now:
        scheduler.add_job(
            check_student_absents,
            trigger=DateTrigger(run_date=student_absent_time),
            args=[schedule_id],
            id=f'student_absent_{schedule_id}',
            replace_existing=True
        )
        print(f'[SCHEDULER] student_absent job scheduled for {student_absent_time}')
    else:
        check_student_absents(schedule_id)

    # Empty class check — 15 mins after scheduled start
    empty_class_time = scheduled_start + timedelta(
        minutes=THRESHOLDS['empty_class_mins']
    )
    if empty_class_time > now:
        scheduler.add_job(
            check_empty_class,
            trigger=DateTrigger(run_date=empty_class_time),
            args=[schedule_id],
            id=f'empty_class_{schedule_id}',
            replace_existing=True
        )
        print(f'[SCHEDULER] empty_class job scheduled for {empty_class_time}')
    else:
        check_empty_class(schedule_id)

def check_missed_classes():
    """
    Runs every 15 mins.
    Finds classes that never started and marks them missed.
    """
    print(f'[SCHEDULER] Checking for missed classes...')
    now = datetime.now(timezone.utc).isoformat()

    # Find all scheduled classes where end time has passed
    missed = supabase.table('class_schedules') \
        .select('*, teachers(*)') \
        .eq('status', 'scheduled') \
        .lt('scheduled_end', now) \
        .execute()

    if not missed.data:
        print(f'[SCHEDULER] No missed classes found')
        return

    for schedule in missed.data:
        print(f'[SCHEDULER] Missed class detected: {schedule["id"]}')

        # Mark as missed
        supabase.table('class_schedules').update({
            'status': 'missed'
        }).eq('id', schedule['id']).execute()

        teacher = schedule['teachers']

        # Fire teacher_absent alert if not already fired
        existing_alert = supabase.table('alerts') \
            .select('id') \
            .eq('schedule_id', schedule['id']) \
            .eq('alert_type', 'teacher_absent') \
            .execute()

        if not existing_alert.data:
            create_alert(
                schedule_id=schedule['id'],
                alert_type='teacher_absent',
                teacher_id=teacher['id'],
                notes=f'Class was never started — marked as missed'
            )

        # Fire student_absent for all enrolled students
        enrollments = supabase.table('class_students') \
            .select('*, students(*)') \
            .eq('schedule_id', schedule['id']) \
            .execute()

        for enrollment in enrollments.data:
            student = enrollment['students']

            existing_student_alert = supabase.table('alerts') \
                .select('id') \
                .eq('schedule_id', schedule['id']) \
                .eq('alert_type', 'student_absent') \
                .eq('student_id', student['id']) \
                .execute()

            if not existing_student_alert.data:
                create_alert(
                    schedule_id=schedule['id'],
                    alert_type='student_absent',
                    student_id=student['id'],
                    notes=f'{student["full_name"]} — class was never conducted'
                )

        print(f'[SCHEDULER] Schedule {schedule["id"]} marked missed, alerts fired')

def start_scheduler():
    """Call this instead of scheduler.start() directly."""
    from apscheduler.triggers.interval import IntervalTrigger

    # Missed class check — runs every 15 mins
    scheduler.add_job(
        check_missed_classes,
        trigger=IntervalTrigger(minutes=15),
        id='missed_class_check',
        replace_existing=True
    )

    scheduler.start()
    print('[SCHEDULER] Started — missed class check every 15 mins')