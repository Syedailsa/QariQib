import uuid
from celery import shared_task
from datetime import datetime, timezone
from db.supabase import supabase
from services.alerts import create_alert, THRESHOLDS

# ─── Deterministic Task ID helpers ───────────────────────────────────────────
_NS_TEACHER = uuid.UUID('a1a1a1a1-0001-0001-0001-000000000001')
_NS_STUDENT  = uuid.UUID('a2a2a2a2-0002-0002-0002-000000000002')
_NS_EMPTY    = uuid.UUID('a3a3a3a3-0003-0003-0003-000000000003')


def get_task_ids(schedule_id: str) -> dict:
    return {
        'teacher': str(uuid.uuid5(_NS_TEACHER, schedule_id)),
        'student': str(uuid.uuid5(_NS_STUDENT,  schedule_id)),
        'empty':   str(uuid.uuid5(_NS_EMPTY,    schedule_id)),
    }


def _mark_absent(schedule_id: str, participant_type: str, participant_id: str):
    existing = supabase.table('absences') \
        .select('id') \
        .eq('schedule_id', schedule_id) \
        .eq('participant_id', participant_id) \
        .eq('resolved', False) \
        .execute()
    if not existing.data:
        supabase.table('absences').insert({
            'schedule_id':      schedule_id,
            'participant_type': participant_type,
            'participant_id':   participant_id,
            'marked_at':        datetime.now(timezone.utc).isoformat(),
            'resolved':         False
        }).execute()
        print(f'[ABSENT] {participant_type} {participant_id} marked absent', flush=True)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def check_teacher_absent(self, schedule_id: str):
    print(f'[TASK] check_teacher_absent for {schedule_id}', flush=True)

    result = supabase.table('class_schedules') \
        .select('*, teachers(*)') \
        .eq('id', schedule_id) \
        .execute()

    if not result.data:
        print(f'[TASK] schedule {schedule_id} not found — skipping', flush=True)
        return

    schedule = result.data[0]

    if schedule['status'] not in ('live', 'scheduled'):
        print(f'[TASK] check_teacher_absent: status={schedule["status"]} — skipping', flush=True)
        return

    teacher = schedule['teachers']

    already_joined = supabase.table('attendance_records') \
        .select('id') \
        .eq('schedule_id', schedule_id) \
        .eq('participant_type', 'teacher') \
        .execute()

    if already_joined.data:
        print(f'[TASK] Teacher already joined — no alert', flush=True)
        return

    _mark_absent(schedule_id, 'teacher', teacher['id'])
    create_alert(
        schedule_id=schedule_id,
        alert_type='teacher_absent',
        teacher_id=teacher['id'],
        notes=f'{teacher["full_name"]} (Teacher) did not join {THRESHOLDS["teacher_absent_mins"]} mins after scheduled start'
    )
    print(f'[TASK] teacher_absent alert created for {teacher["full_name"]}', flush=True)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def check_student_absents(self, schedule_id: str):
    print(f'[TASK] check_student_absents for {schedule_id}', flush=True)

    result = supabase.table('class_schedules') \
        .select('id, status') \
        .eq('id', schedule_id) \
        .execute()

    if not result.data:
        print(f'[TASK] schedule {schedule_id} not found — skipping', flush=True)
        return

    status = result.data[0]['status']
    if status not in ('live', 'scheduled'):
        print(f'[TASK] check_student_absents: status={status} — skipping', flush=True)
        return

    enrollments = supabase.table('class_students') \
        .select('*, students(*)') \
        .eq('schedule_id', schedule_id) \
        .execute()

    print(f'[TASK] checking {len(enrollments.data)} enrolled student(s)', flush=True)

    for enrollment in enrollments.data:
        student = enrollment['students']

        already_joined = supabase.table('attendance_records') \
            .select('id') \
            .eq('schedule_id', schedule_id) \
            .eq('participant_id', student['id']) \
            .execute()

        if already_joined.data:
            print(f'[TASK] {student["full_name"]} already has record — no absent alert', flush=True)
            continue

        _mark_absent(schedule_id, 'student', student['id'])
        create_alert(
            schedule_id=schedule_id,
            alert_type='student_absent',
            student_id=student['id'],
            notes=f'{student["full_name"]} (Student) did not join {THRESHOLDS["student_absent_mins"]} mins after scheduled start'
        )
        print(f'[TASK] student_absent alert created for {student["full_name"]}', flush=True)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def check_empty_class(self, schedule_id: str):
    print(f'[TASK] check_empty_class for {schedule_id}', flush=True)

    result = supabase.table('class_schedules') \
        .select('id, status') \
        .eq('id', schedule_id) \
        .execute()

    if not result.data or result.data[0]['status'] != 'live':
        print(f'[TASK] check_empty_class: not live — skipping', flush=True)
        return

    still_present = supabase.table('attendance_records') \
        .select('id') \
        .eq('schedule_id', schedule_id) \
        .is_('leave_time', 'null') \
        .execute()

    if still_present.data:
        print(f'[TASK] {len(still_present.data)} participant(s) still present — no empty alert', flush=True)
        return

    create_alert(
        schedule_id=schedule_id,
        alert_type='empty_class',
        notes=f'No participants in meeting {THRESHOLDS["empty_class_mins"]} mins after start'
    )
    print(f'[TASK] empty_class alert created for {schedule_id}', flush=True)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, retry_backoff=True)
def check_missed_classes(self):
    """Fired by Celery Beat every 15 minutes."""
    print('[TASK] check_missed_classes running...', flush=True)

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')

    missed_scheduled = supabase.table('class_schedules') \
        .select('*, teachers(*)') \
        .eq('status', 'scheduled') \
        .lt('scheduled_end', now) \
        .execute()

    missed_live = supabase.table('class_schedules') \
        .select('*, teachers(*)') \
        .eq('status', 'live') \
        .lt('scheduled_end', now) \
        .execute()

    all_missed = (missed_scheduled.data or []) + (missed_live.data or [])
    print(f'[TASK] Found {len(all_missed)} missed class(es)', flush=True)

    if not all_missed:
        return

    for schedule in all_missed:
        supabase.table('class_schedules').update({
            'status': 'missed'
        }).eq('id', schedule['id']).execute()

        zoom_meeting_id = schedule.get('zoom_meeting_id')
        if zoom_meeting_id:
            try:
                import httpx
                from services.zoom_api import get_headers
                httpx.delete(
                    f'https://api.zoom.us/v2/meetings/{zoom_meeting_id}',
                    headers=get_headers()
                )
                print(f'[ZOOM] Meeting {zoom_meeting_id} deleted — class missed', flush=True)
            except Exception as e:
                print(f'[ZOOM] Failed to delete meeting: {e}', flush=True)

        teacher = schedule['teachers']

        existing = supabase.table('alerts').select('id') \
            .eq('schedule_id', schedule['id']) \
            .eq('alert_type', 'teacher_absent').execute()

        if not existing.data:
            _mark_absent(schedule['id'], 'teacher', teacher['id'])
            create_alert(
                schedule_id=schedule['id'],
                alert_type='teacher_absent',
                teacher_id=teacher['id'],
                notes=f'{teacher["full_name"]} (Teacher) — class was never started'
            )

        enrollments = supabase.table('class_students') \
            .select('*, students(*)') \
            .eq('schedule_id', schedule['id']).execute()

        for enrollment in enrollments.data:
            student = enrollment['students']

            # Only alert for students who never joined at all
            already_joined = supabase.table('attendance_records') \
                .select('id') \
                .eq('schedule_id', schedule['id']) \
                .eq('participant_id', student['id']) \
                .execute()

            if already_joined.data:
                continue

            create_alert(
                schedule_id=schedule['id'],
                alert_type='student_absent',
                student_id=student['id'],
                notes=f'{student["full_name"]} (Student) — class was never conducted'
            )

        print(f'[TASK] Processed missed class {schedule["id"]}', flush=True)
