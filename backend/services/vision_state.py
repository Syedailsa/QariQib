"""
services/vision_state.py — Redis state + alert threshold logic

Tracks per-participant vision state in Redis during a live RTMS session.
Writes alerts to Supabase when thresholds are crossed.

Redis key schema (all keys expire 2h after creation):
  rtms:{meeting_id}:{zoom_user_id}:participant      → JSON {db_id, type, name}  ← written by attendance.py
  rtms:{meeting_id}:{participant_id}:cam_off_since  → float timestamp
  rtms:{meeting_id}:{participant_id}:cam_alerted    → '1'
  rtms:{meeting_id}:{participant_id}:face_off_since → float timestamp
  rtms:{meeting_id}:{participant_id}:face_alerted   → '1'
  rtms:{meeting_id}:{participant_id}:phone_count    → int
  rtms:{meeting_id}:{participant_id}:phone_last_ts  → float timestamp
"""

import json
import time
from datetime import datetime, timezone
from core.redis_client import redis_client
from db.supabase import supabase

# ─── Alert thresholds ─────────────────────────────────────────────────────────
CAMERA_OFF_SECS     = 25      # seconds continuous before camera-off alert (300 for production)
PHONE_CONSEC_NEEDED = 4       # consecutive frames with phone before a strike
FACE_CONSEC_NEEDED  = 4       # consecutive frames with no face before alert
PHONE_GAP_SECS      = 1 * 60  # minimum gap between consecutive phone strikes
KEY_TTL             = 7200    # Redis key TTL: 2 hours

_PHONE_SEVERITY = {1: 'low', 2: 'medium', 3: 'high'}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _k(meeting_id: str, participant_id: str, field: str) -> str:
    return f'rtms:{meeting_id}:{participant_id}:{field}'


def _get_schedule_id(meeting_id: str) -> str | None:
    result = supabase.table('class_schedules') \
        .select('id') \
        .eq('zoom_meeting_id', meeting_id) \
        .execute()
    return result.data[0]['id'] if result.data else None


def _resolve_participant(
    meeting_id: str, zoom_user_id: str, participant_type: str
) -> tuple[str | None, str | None, str]:
    """
    Returns (teacher_id, student_id, label) for alert inserts.

    Primary path  : Redis cache written by attendance.on_participant_joined.
    Teacher fallback: query class_schedules directly — always reliable since
                      schedule.teacher_id is a FK set at creation time.
    Student fallback: no DB path without zoom_user_id mapping, so label only.
    All exceptions are caught — never blocks an alert from being written.
    """
    # ── Primary: Redis cache ──────────────────────────────────────────────────
    try:
        raw = redis_client.get(f'rtms:{meeting_id}:{zoom_user_id}:participant')
        if raw:
            data  = json.loads(raw)
            db_id = data.get('db_id')
            ptype = data.get('type', participant_type)
            name  = data.get('name', ptype.capitalize())
            label = f'{name} ({ptype.capitalize()})'
            if ptype == 'teacher':
                return db_id, None, label
            return None, db_id, label
    except Exception as e:
        print(f'[VISION STATE] Redis participant lookup failed: {e}', flush=True)

    # ── Fallback for teachers via stored teacher_zoom_id ─────────────────────
    # Zoom does NOT send participant_type in RTMS video frames — it always
    # defaults to 'student'. Instead, attendance.py stores a separate key
    # with the teacher's zoom_user_id when they join via webhook.
    try:
        stored = redis_client.get(f'rtms:{meeting_id}:teacher_zoom_id')
        if stored and stored == zoom_user_id:
            rows = supabase.table('class_schedules') \
                .select('teacher_id, teachers(full_name)') \
                .eq('zoom_meeting_id', meeting_id) \
                .execute()
            if rows.data:
                row        = rows.data[0]
                teacher_id = row.get('teacher_id')
                name       = (row.get('teachers') or {}).get('full_name', 'Teacher')
                return teacher_id, None, f'{name} (Teacher)'
    except Exception as e:
        print(f'[VISION STATE] Teacher zoom_id fallback failed: {e}', flush=True)

    # ── Final fallback: alert still fires, just without a name badge ──────────
    return None, None, 'Participant'


def _write_alert(
    schedule_id: str, alert_type: str, severity: str, notes: str,
    teacher_id: str | None = None, student_id: str | None = None,
):
    """
    Write alert to Supabase.
    camera_off and face_not_visible are deduplicated per participant — only one
    active alert per (schedule, type, participant) at a time.
    Phone alerts always write — each strike is a separate record.
    """
    if alert_type in ('camera_off', 'face_not_visible'):
        q = supabase.table('alerts') \
            .select('id') \
            .eq('schedule_id', schedule_id) \
            .eq('alert_type', alert_type) \
            .eq('is_resolved', False)
        if teacher_id:
            q = q.eq('teacher_id', teacher_id)
        elif student_id:
            q = q.eq('student_id', student_id)
        if q.execute().data:
            return  # already active for this participant

    row = {
        'schedule_id': schedule_id,
        'alert_type':  alert_type,
        'severity':    severity,
        'notes':       notes,
        'is_resolved': False,
    }
    if teacher_id:
        row['teacher_id'] = teacher_id
    if student_id:
        row['student_id'] = student_id

    supabase.table('alerts').insert(row).execute()
    print(f'[VISION ALERT] {alert_type} ({severity}) — schedule={schedule_id}', flush=True)


def _auto_resolve_vision_alert(
    schedule_id: str, alert_type: str,
    teacher_id: str | None = None, student_id: str | None = None,
):
    q = supabase.table('alerts') \
        .update({
            'is_resolved': True,
            'resolved_at': datetime.now(timezone.utc).isoformat()
        }) \
        .eq('schedule_id', schedule_id) \
        .eq('alert_type', alert_type) \
        .eq('is_resolved', False)
    if teacher_id:
        q = q.eq('teacher_id', teacher_id)
    elif student_id:
        q = q.eq('student_id', student_id)
    result = q.execute()
    if result.data:
        print(f'[AUTO-RESOLVE] {alert_type} resolved — schedule={schedule_id}', flush=True)


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

    now = time.time()
    teacher_id, student_id, label = _resolve_participant(
        meeting_id, participant_id, participant_type
    )

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
                f'{label} camera has been off for 5+ minutes.',
                teacher_id=teacher_id, student_id=student_id,
            )
            redis_client.setex(k_alerted, KEY_TTL, '1')
    else:
        # Camera back on — reset clock and allow re-alerting
        was_alerted = redis_client.exists(_k(meeting_id, participant_id, 'cam_alerted'))
        redis_client.delete(_k(meeting_id, participant_id, 'cam_off_since'))
        redis_client.delete(_k(meeting_id, participant_id, 'cam_alerted'))
        if was_alerted and (teacher_id or student_id):
            _auto_resolve_vision_alert(schedule_id, 'camera_off',
                                       teacher_id=teacher_id, student_id=student_id)

    # ── Face not visible (camera ON but no face detected) ─────────────────────
    # Requires FACE_CONSEC_NEEDED consecutive frames with no face before alerting.
    # A single missed frame (model miss, brief look-away) is ignored.
    k_face_consec  = _k(meeting_id, participant_id, 'face_consec')
    k_face_alerted = _k(meeting_id, participant_id, 'face_alerted')

    if result.camera_on and not result.face_visible:
        consec = int(redis_client.get(k_face_consec) or 0) + 1
        redis_client.setex(k_face_consec, KEY_TTL, str(consec))

        if consec >= FACE_CONSEC_NEEDED and not redis_client.exists(k_face_alerted):
            _write_alert(
                schedule_id, 'face_not_visible', 'medium',
                f'{label} face not visible for {FACE_CONSEC_NEEDED}+ consecutive frames '
                f'(camera is on but no face detected).',
                teacher_id=teacher_id, student_id=student_id,
            )
            redis_client.setex(k_face_alerted, KEY_TTL, '1')
    elif result.face_visible:
        was_alerted = redis_client.exists(k_face_alerted)
        redis_client.delete(k_face_consec)
        redis_client.delete(k_face_alerted)
        if was_alerted and (teacher_id or student_id):
            _auto_resolve_vision_alert(schedule_id, 'face_not_visible',
                                       teacher_id=teacher_id, student_id=student_id)

    # ── Phone detected ────────────────────────────────────────────────────────
    # Requires PHONE_CONSEC_NEEDED consecutive frames with phone before a strike.
    # Phone put down between frames resets the counter — brief appearances ignored.
    k_phone_consec = _k(meeting_id, participant_id, 'phone_consec')
    k_count        = _k(meeting_id, participant_id, 'phone_count')
    k_last_ts      = _k(meeting_id, participant_id, 'phone_last_ts')

    if result.phone_detected:
        consec = int(redis_client.get(k_phone_consec) or 0) + 1
        redis_client.setex(k_phone_consec, KEY_TTL, str(consec))

        if consec < PHONE_CONSEC_NEEDED:
            return  # not confirmed yet — need more consecutive frames

        count   = int(redis_client.get(k_count)   or 0)
        last_ts = float(redis_client.get(k_last_ts) or 0)

        if count > 0 and (now - last_ts) < PHONE_GAP_SECS:
            return  # within cooldown window — don't re-strike yet

        count += 1
        redis_client.setex(k_count,        KEY_TTL, str(count))
        redis_client.setex(k_last_ts,      KEY_TTL, str(now))
        redis_client.setex(k_phone_consec, KEY_TTL, '0')  # reset after strike

        strike   = min(count, 3)
        severity = _PHONE_SEVERITY[strike]
        notes    = (
            f'{label} phone detected — strike {count}/3.'
            if count < 3 else
            f'{label} phone detected — 3rd strike, persistent usage confirmed.'
        )
        _write_alert(schedule_id, 'phone_detected', severity, notes,
                     teacher_id=teacher_id, student_id=student_id)
    else:
        # No phone in this frame — break streak and reset strike history
        # so the next pickup is treated as a fresh incident (strike 1 again)
        redis_client.delete(k_phone_consec)
        redis_client.delete(k_count)
        redis_client.delete(k_last_ts)
