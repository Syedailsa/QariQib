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
    'grace_period_mins':     5,   # no alerts in first 5 mins for anyone
    'teacher_absent_mins':   7,   # background job fires teacher_absent
    'empty_class_mins':      15,  # background job fires empty_class
    'participant_late_mins': 5,   # student late after 5 mins
    'student_absent_mins':   10,  # background job fires student_absent
    'early_departure_mins':  8,   # leaving before last 8 mins
}


def create_alert(schedule_id: str, alert_type: str,
                 teacher_id: str = None, student_id: str = None,
                 notes: str = None):
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
    print(f'[ALERT] {alert_type} → schedule {schedule_id}')


def resolve_alert(schedule_id: str, alert_type: str):
    supabase.table('alerts').update({
        'is_resolved': True,
        'resolved_at': datetime.now(timezone.utc).isoformat()
    }).eq('schedule_id', schedule_id) \
      .eq('alert_type', alert_type) \
      .eq('is_resolved', False) \
      .execute()