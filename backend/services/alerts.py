from datetime import datetime, timezone
from db.supabase import supabase

ALERT_SEVERITY = {
    'teacher_absent':   'high',
    'empty_class':      'high',
    'teacher_late':     'medium',
    'student_absent':   'medium',
    'early_departure':  'medium',
    'participant_late': 'low',
}

THRESHOLDS = {
    'grace_period_mins':     5,
    'teacher_absent_mins':   8,
    'teacher_late_mins':     5,
    'empty_class_mins':      10,
    'participant_late_mins': 5,
    'student_absent_mins':   8,
    'early_departure_mins':  6,
}


def create_alert(schedule_id: str, alert_type: str,
                 teacher_id: str = None, student_id: str = None,
                 notes: str = None):
    # Idempotency guard — never create duplicate active alerts for the same
    # schedule + type + participant. Zoom retries and Celery retries both call
    # this; without the guard every retry spawns a new alert row.
    query = supabase.table('alerts').select('id') \
        .eq('schedule_id', schedule_id) \
        .eq('alert_type', alert_type) \
        .eq('is_resolved', False)
    if teacher_id:
        query = query.eq('teacher_id', teacher_id)
    if student_id:
        query = query.eq('student_id', student_id)
    if query.execute().data:
        print(f'[ALERT SKIP] Duplicate {alert_type} suppressed for schedule {schedule_id}', flush=True)
        return

    supabase.table('alerts').insert({
        'schedule_id':  schedule_id,
        'alert_type':   alert_type,
        'severity':     ALERT_SEVERITY[alert_type],
        'teacher_id':   teacher_id,
        'student_id':   student_id,
        'triggered_at': datetime.now(timezone.utc).isoformat(),
        'is_resolved':  False,
        'notes':        notes
    }).execute()
    print(f'[ALERT] {alert_type} → schedule {schedule_id}', flush=True)


def resolve_alert(schedule_id: str, alert_type: str):
    supabase.table('alerts').update({
        'is_resolved': True,
        'resolved_at': datetime.now(timezone.utc).isoformat()
    }).eq('schedule_id', schedule_id) \
      .eq('alert_type', alert_type) \
      .eq('is_resolved', False) \
      .execute()
