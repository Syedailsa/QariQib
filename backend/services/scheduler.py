from datetime import datetime, timezone, timedelta
from db.supabase import supabase
from services.alerts import THRESHOLDS


def schedule_class_jobs(schedule_id: str, scheduled_start: datetime):
    """
    Queue the 3 absence-check tasks for a class.
    All three use deterministic UUIDs derived from schedule_id, so calling
    this twice for the same class is safe — revoke the old ones first.
    """
    # Must import celery_app FIRST — this sets it as current_app so that
    # @shared_task functions below bind to our Redis-backed app, not Celery's
    # default AMQP app (which points to localhost:5672 and doesn't exist here).
    from celery_app import celery_app  # noqa: F401
    from tasks.absence import check_teacher_absent, check_student_absents, check_empty_class, get_task_ids

    task_ids = get_task_ids(schedule_id)

    teacher_time = scheduled_start + timedelta(minutes=THRESHOLDS['teacher_absent_mins'])
    student_time = scheduled_start + timedelta(minutes=THRESHOLDS['student_absent_mins'])
    empty_time   = scheduled_start + timedelta(minutes=THRESHOLDS['empty_class_mins'])

    # apply_async with eta: fires at that datetime
    # If the datetime is already in the past, Celery executes it immediately
    # task_id pins the Celery task to a known UUID so we can revoke it later
    check_teacher_absent.apply_async(
        args=[schedule_id],
        eta=teacher_time,
        task_id=task_ids['teacher']
    )
    check_student_absents.apply_async(
        args=[schedule_id],
        eta=student_time,
        task_id=task_ids['student']
    )
    check_empty_class.apply_async(
        args=[schedule_id],
        eta=empty_time,
        task_id=task_ids['empty']
    )

    print(f'[CELERY] Queued 3 tasks for schedule {schedule_id}')
    print(f'  teacher_absent  @ {teacher_time.isoformat()}')
    print(f'  student_absents @ {student_time.isoformat()}')
    print(f'  empty_class     @ {empty_time.isoformat()}')


def revoke_class_jobs(schedule_id: str):
    """
    Cancel pending absence-check tasks for a class.
    Called before delete or reschedule so stale tasks don't fire.
    terminate=False means: if a task is currently running, let it finish —
    just don't re-queue it after. We don't want to abruptly kill a running check.
    """
    from celery_app import celery_app
    from tasks.absence import get_task_ids

    task_ids = get_task_ids(schedule_id)

    for name, task_id in task_ids.items():
        celery_app.control.revoke(task_id, terminate=False)
        print(f'[CELERY] Revoked {name} task {task_id}')


def recover_missing_tasks():
    """
    Called once on FastAPI startup.
    Finds any active classes whose tasks were never queued — this happens on
    first deploy after migration, or if Redis data was wiped.
    Revokes first (no-op if tasks don't exist) then re-schedules to be safe.
    """
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')

    active = supabase.table('class_schedules') \
        .select('id, scheduled_start, status') \
        .in_('status', ['scheduled', 'live']) \
        .gt('scheduled_end', now) \
        .execute()

    recovered = 0
    for s in (active.data or []):
        try:
            scheduled_start = datetime.fromisoformat(
                s['scheduled_start'].replace('Z', '+00:00')
            )
            # Do NOT revoke here — revoking then re-queuing the same deterministic UUID
            # adds the ID to Celery's revoke list, which then discards the re-queued task.
            # Tasks are idempotent (each checks status before acting), so re-queuing
            # a task that already exists in Redis is safe — only one will do real work.
            schedule_class_jobs(s['id'], scheduled_start)
            recovered += 1
        except Exception as e:
            print(f'[STARTUP] Failed to queue tasks for schedule {s["id"]}: {e}', flush=True)

    print(f'[STARTUP] Ensured tasks exist for {recovered} active schedule(s)', flush=True)
