# routers/alerts.py
from fastapi import APIRouter, HTTPException
from db.supabase import supabase
from datetime import datetime, timezone

router = APIRouter(prefix='/api/v1/alerts', tags=['alerts'])


@router.get('')
def list_alerts(resolved: bool = False):
    result = supabase.table('alerts') \
        .select('''
            *,
            class_schedules(id, scheduled_start, scheduled_end),
            teachers(id, full_name, email),
            students(id, full_name, email)
        ''') \
        .eq('is_resolved', resolved) \
        .order('triggered_at', desc=True) \
        .execute()
    return result.data


@router.post('/{alert_id}/resolve')
def resolve_alert(alert_id: str):
    result = supabase.table('alerts').update({
        'is_resolved': True,
        'resolved_at': datetime.now(timezone.utc).isoformat()
    }).eq('id', alert_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail='Alert not found')
    return result.data[0]