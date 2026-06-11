"""
services/vision_state.py — Redis state + alert threshold logic

Tracks per-participant vision state in Redis during a live RTMS session.
Writes alerts to Supabase when thresholds are crossed.

Redis key schema (all keys expire 2h after creation):
  rtms:{meeting_id}:{participant_id}:cam_off_since   → float timestamp
  rtms:{meeting_id}:{participant_id}:cam_alerted     → '1'
  rtms:{meeting_id}:{participant_id}:face_off_since  → float timestamp
  rtms:{meeting_id}:{participant_id}:face_alerted    → '1'
  rtms:{meeting_id}:{participant_id}:phone_count     → int
  rtms:{meeting_id}:{participant_id}:phone_last_ts   → float timestamp
"""

import time
from core.redis_client import redis_client
from db.supabase import supabase

# ─── Alert thresholds ─────────────────────────────────────────────────────────
CAMERA_OFF_SECS  = 25         # 25 seconds continuous before alert (testing)
FACE_ABSENT_SECS = 25         # 25 seconds continuous before alert (testing)
PHONE_GAP_SECS   = 3  * 60   # minimum gap between consecutive phone strikes
KEY_TTL          = 7200       # Redis key TTL: 2 hours

_PHONE_SEVERITY = {1: 'low', 2: 'medium', 3: 'high'}
_PHONE_TYPE     = {1: 'phone_detected', 2: 'phone_detected', 3: 'phone_detected'}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _k(meeting_id: str, participant_id: str, field: str) -> str:
    return f'rtms:{meeting_id}:{participant_id}:{field}'


def _get_schedule_id(meeting_id: str) -> str | None:
    result = supabase.table('class_schedules') \
        .select('id') \
        .eq('zoom_meeting_id', meeting_id) \
        .execute()
    return result.data[0]['id'] if result.data else None


def _write_alert(schedule_id: str, alert_type: str, severity: str, notes: str):
    """
    Write alert to Supabase.
    For camera_off and face_not_visible: deduplicate — only one active alert per type.
    For phone alerts: always write (each strike is a separate alert).
    """
    if alert_type in ('camera_off', 'face_not_visible'):
        existing = supabase.table('alerts') \
            .select('id') \
            .eq('schedule_id', schedule_id) \
            .eq('alert_type', alert_type) \
            .eq('is_resolved', False) \
            .execute()
        if existing.data:
            return  # already active

    supabase.table('alerts').insert({
        'schedule_id': schedule_id,
        'alert_type':  alert_type,
        'severity':    severity,
        'notes':       notes,
        'is_resolved': False,
    }).execute()

    print(f'[VISION ALERT] {alert_type} ({severity}) — schedule={schedule_id}', flush=True)


# ─── Public API ───────────────────────────────────────────────────────────────

def process_result(meeting_id: str, participant_id: str,
                   participant_type: str, result) -> None:
    """
    Called after each vision inference.
    Updates Redis state and fires Supabase alerts when thresholds are crossed.
    Thread-safe: each Redis operation is atomic.
    """
    schedule_id = _get_schedule_id(meeting_id)
    if not schedule_id:
        print(f'[VISION STATE] No schedule for meeting {meeting_id}', flush=True)
        return

    now   = time.time()
    label = participant_type.capitalize()

    # ── Camera off ────────────────────────────────────────────────────────────
    if not result.camera_on:
        k_since   = _k(meeting_id, participant_id, 'cam_off_since')
        k_alerted = _k(meeting_id, participant_id, 'cam_alerted')

        if not redis_client.exists(k_since):
            redis_client.setex(k_since, KEY_TTL, str(now))

        since = float(redis_client.get(k_since) or now)

        if now - since >= CAMERA_OFF_SECS and not redis_client.exists(k_alerted):
            _write_alert(
                schedule_id, 'camera_off', 'medium',
                f'{label} camera has been off for 5+ minutes.'
            )
            redis_client.setex(k_alerted, KEY_TTL, '1')
    else:
        # Camera back on — reset clock and allow re-alerting
        redis_client.delete(_k(meeting_id, participant_id, 'cam_off_since'))
        redis_client.delete(_k(meeting_id, participant_id, 'cam_alerted'))

    # ── Face not visible (camera ON but no face detected) ─────────────────────
    if result.camera_on and not result.face_visible:
        k_since   = _k(meeting_id, participant_id, 'face_off_since')
        k_alerted = _k(meeting_id, participant_id, 'face_alerted')

        if not redis_client.exists(k_since):
            redis_client.setex(k_since, KEY_TTL, str(now))

        since = float(redis_client.get(k_since) or now)

        if now - since >= FACE_ABSENT_SECS and not redis_client.exists(k_alerted):
            _write_alert(
                schedule_id, 'face_not_visible', 'medium',
                f'{label} face has not been visible for 5+ minutes '
                f'(camera is on but no face detected).'
            )
            redis_client.setex(k_alerted, KEY_TTL, '1')
    elif result.face_visible:
        redis_client.delete(_k(meeting_id, participant_id, 'face_off_since'))
        redis_client.delete(_k(meeting_id, participant_id, 'face_alerted'))

    # ── Phone detected ────────────────────────────────────────────────────────
    if not result.phone_detected:
        return

    k_count   = _k(meeting_id, participant_id, 'phone_count')
    k_last_ts = _k(meeting_id, participant_id, 'phone_last_ts')

    count   = int(redis_client.get(k_count)   or 0)
    last_ts = float(redis_client.get(k_last_ts) or 0)

    # Don't count rapid back-to-back detections as separate strikes
    if count > 0 and now - last_ts < PHONE_GAP_SECS:
        return

    count += 1
    redis_client.setex(k_count,   KEY_TTL, str(count))
    redis_client.setex(k_last_ts, KEY_TTL, str(now))

    strike    = min(count, 3)
    severity  = _PHONE_SEVERITY[strike]
    atype     = _PHONE_TYPE[strike]
    notes     = (
        f'{label} phone detected — strike {count}/3.'
        if count < 3 else
        f'{label} phone detected — 3rd strike, persistent usage confirmed.'
    )

    _write_alert(schedule_id, atype, severity, notes)
