"""
services/rtms.py — Zoom RTMS WebSocket connection manager

Flow:
  meeting.rtms_started webhook fires
    → start_rtms_session Celery task calls connect_rtms()
      → connect signaling WebSocket
        → complete HAND_SHAKE_REQ / HAND_SHAKE_RESP
          → receive video media server URL
            → connect video media WebSocket
              → same handshake
                → receive binary H.264 frames
                  → sample 1 frame / 5s per participant
                    → run vision inference inline
                      → write alerts to Supabase
"""

import asyncio
import base64
import hashlib
import hmac as hmac_lib
import json
import time
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor

from core.config import settings
from core.redis_client import redis_client

# ─── Config ───────────────────────────────────────────────────────────────────
FRAME_SAMPLE_INTERVAL = 5   # seconds between samples per participant
QUEUE_DEPTH_LIMIT     = 200  # drop frames if more than this many queued
HANDSHAKE_TIMEOUT     = 15   # seconds to wait for each WS message

# ─── HMAC helper ──────────────────────────────────────────────────────────────

def _compute_signature(meeting_uuid: str, stream_id: str) -> str:
    """
    Zoom RTMS handshake signature.
    key = client_secret
    msg = client_id,meeting_uuid,stream_id
    """
    key = settings.ZOOM_CLIENT_SECRET.encode()
    msg = f'{settings.ZOOM_CLIENT_ID},{meeting_uuid},{stream_id}'.encode()
    return hmac_lib.new(key=key, msg=msg, digestmod=hashlib.sha256).hexdigest()


# ─── Signaling handshake ──────────────────────────────────────────────────────

async def _signaling_handshake(ws, meeting_id: str, meeting_uuid: str,
                               stream_id: str) -> str:
    """
    Complete RTMS signaling handshake.
    Zoom RTMS requires the CLIENT to speak first by sending a HAND_SHAKE_REQ.
    Zoom then responds with HAND_SHAKE_RESP + media URLs.
    Returns the video media server URL on success, empty string on failure.
    """
    # Client sends first — msg_type 1 = SIGNALING_HAND_SHAKE_REQ
    signature = _compute_signature(meeting_uuid, stream_id)

    await ws.send(json.dumps({
        'msg_type':         1,
        'protocol_version': 1,
        'meeting_uuid':     meeting_uuid,
        'rtms_stream_id':   stream_id,
        'sequence':         0,
        'signature':        signature,
    }))
    print(f'[RTMS] Sent SIGNALING_HAND_SHAKE_REQ (msg_type=1) for meeting={meeting_id}', flush=True)

    raw = await asyncio.wait_for(ws.recv(), timeout=HANDSHAKE_TIMEOUT)
    msg = json.loads(raw)
    print(f'[RTMS] Signaling response: {msg}', flush=True)

    # msg_type 2 = SIGNALING_HAND_SHAKE_RESP
    if msg.get('msg_type') != 2:
        print(f'[RTMS] Expected msg_type=2 (RESP), got: {msg.get("msg_type")}', flush=True)
        return ''

    if msg.get('status_code', -1) != 0:
        print(f'[RTMS] Handshake rejected — status={msg.get("status_code")}', flush=True)
        return ''

    # Extract video URL — Zoom may nest it differently, handle both formats
    server_urls = (
        msg.get('media_server', {}).get('server_urls') or
        msg.get('server_urls') or
        {}
    )
    if isinstance(server_urls, dict):
        video_url = server_urls.get('video') or server_urls.get('all', '')
    else:
        video_url = str(server_urls)

    return video_url


# ─── Media handshake ──────────────────────────────────────────────────────────

async def _media_handshake(ws, meeting_uuid: str, stream_id: str) -> bool:
    """Complete RTMS media server handshake. Client speaks first.
    msg_type 3 = MEDIA_DATA_HAND_SHAKE_REQ, 4 = MEDIA_DATA_HAND_SHAKE_RESP.
    media_type 2 = VIDEO only (audio/transcript/deskshare not needed).
    """
    signature = _compute_signature(meeting_uuid, stream_id)

    await ws.send(json.dumps({
        'msg_type':         3,
        'protocol_version': 1,
        'meeting_uuid':     meeting_uuid,
        'rtms_stream_id':   stream_id,
        'sequence':         0,
        'signature':        signature,
        'media_type':       2,
    }))
    print(f'[RTMS] Sent MEDIA_DATA_HAND_SHAKE_REQ (msg_type=3)', flush=True)

    raw = await asyncio.wait_for(ws.recv(), timeout=HANDSHAKE_TIMEOUT)
    msg = json.loads(raw)
    print(f'[RTMS] Media handshake response: {msg}', flush=True)

    return msg.get('status_code', -1) == 0 or msg.get('msg_type') == 4


# ─── Frame processing ─────────────────────────────────────────────────────────

def _run_vision_on_frame(meeting_id: str, participant_id: str,
                         participant_type: str, frame: np.ndarray):
    """
    Runs synchronously in a thread pool executor.
    Calls vision inference and updates Redis state + alerts.
    """
    try:
        from services.vision import analyze_frame, VisionResult
        from services.vision_state import process_result

        if redis_client.exists(f'rtms:{meeting_id}:{participant_id}:cam_muted'):
            result = VisionResult(
                camera_on=False, face_visible=False,
                phone_detected=False, phone_confidence=0.0, mean_brightness=0.0,
            )
        else:
            result = analyze_frame(frame)

        print(f'[VISION] meeting={meeting_id} participant={participant_id} '
              f'camera={result.camera_on} face={result.face_visible} '
              f'phone={result.phone_detected}(conf={result.phone_confidence:.2f})', flush=True)
        process_result(
            meeting_id=meeting_id,
            participant_id=participant_id,
            participant_type=participant_type,
            result=result,
        )
    except Exception as e:
        print(f'[VISION] Error for {participant_id}: {e}', flush=True)


# ─── Main entry point ─────────────────────────────────────────────────────────

async def connect_rtms(meeting_id: str, meeting_uuid: str,
                       signaling_url: str, stream_id: str = ''):
    """
    Called as an asyncio task from the webhook handler.
    Manages the full RTMS lifecycle for one meeting.
    Auth is via HMAC in the handshake message — no Authorization header needed.
    """
    import websockets

    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix=f'vision-{meeting_id}')
    stop_key         = f'rtms:stop:{meeting_id}'
    _cam_off_watchers: dict[str, asyncio.Task] = {}

    async def _camera_off_watcher(uid: str):
        """
        Fires a camera-off alert after CAMERA_OFF_SECS if the participant's
        camera is still muted. Runs as an asyncio task so it doesn' depend
        on frames arriving — Zoom stops sending video when camera is off.
        """
        from services.vision_state import CAMERA_OFF_SECS, process_result
        from services.vision import VisionResult
        try:
            await asyncio.sleep(CAMERA_OFF_SECS)
            if not redis_client.exists(f'rtms:{meeting_id}:{uid}:cam_muted'):
                return  # Camera came back on — nothing to do
            result = VisionResult(
                camera_on=False, face_visible=False,
                phone_detected=False, phone_confidence=0.0, mean_brightness=0.0,
            )
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                executor, process_result, meeting_id, uid, 'student', result
            )
        except asyncio.CancelledError:
            pass  # Camera came back on before threshold — expected
        finally:
            _cam_off_watchers.pop(uid, None)

    async def _drain_sig(ws, meeting_id: str):
        """Consume signaling-channel messages, respond to keep-alives, track camera state."""
        try:
            async for msg in ws:
                raw = msg if isinstance(msg, bytes) else msg.encode('utf-8')
                try:
                    d  = json.loads(raw)
                    mt = d.get('msg_type')
                    if mt == 12:
                        await ws.send(json.dumps({'msg_type': 13}))
                    elif mt == 6:
                        event      = d.get('event', {})
                        event_type = event.get('event_type')
                        parts      = event.get('participants', [])
                        if event_type == 9:   # PARTICIPANT_VIDEO_OFF
                            for p in parts:
                                uid = str(p.get('user_id', ''))
                                if not uid:
                                    continue
                                redis_client.setex(f'rtms:{meeting_id}:{uid}:cam_muted', 7200, '1')
                                k_since = f'rtms:{meeting_id}:{uid}:cam_off_since'
                                if not redis_client.exists(k_since):
                                    redis_client.setex(k_since, 7200, str(time.time()))
                                # Cancel any existing watcher and start fresh timer
                                old = _cam_off_watchers.pop(uid, None)
                                if old:
                                    old.cancel()
                                _cam_off_watchers[uid] = asyncio.create_task(
                                    _camera_off_watcher(uid)
                                )
                                print(f'[RTMS] Camera OFF: meeting={meeting_id} user={uid}', flush=True)
                        elif event_type == 8:  # PARTICIPANT_VIDEO_ON
                            for p in parts:
                                uid = str(p.get('user_id', ''))
                                if not uid:
                                    continue
                                redis_client.delete(f'rtms:{meeting_id}:{uid}:cam_muted')
                                redis_client.delete(f'rtms:{meeting_id}:{uid}:cam_off_since')
                                redis_client.delete(f'rtms:{meeting_id}:{uid}:cam_alerted')
                                task = _cam_off_watchers.pop(uid, None)
                                if task:
                                    task.cancel()
                                print(f'[RTMS] Camera ON: meeting={meeting_id} user={uid}', flush=True)
                except Exception:
                    pass
        except Exception:
            pass

    async def _proactive_keepalive(ws):
        """Send keep-alive request every 20s so Zoom doesn' time out the stream."""
        try:
            while True:
                await asyncio.sleep(20)
                await ws.send(json.dumps({'msg_type': 12}))
        except Exception:
            pass

    try:
        print(f'[RTMS] Connecting to signaling WS: {signaling_url}', flush=True)

        async with websockets.connect(
            signaling_url,
            ping_interval=None,  # Zoom uses JSON-level keep-alives; WS pings would timeout
            ping_timeout=None,
        ) as sig_ws:

            video_url = await _signaling_handshake(
                sig_ws, meeting_id, meeting_uuid, stream_id
            )
            if not video_url:
                return

            print(f'[RTMS] Video URL: {video_url}', flush=True)

            # CLIENT_READY_ACK and event subscription go on the signaling channel.
            # They survive media reconnections — sent once, not per-reconnect.
            await sig_ws.send(json.dumps({
                'msg_type':         7,
                'protocol_version': 1,
                'sequence':         0,
                'meeting_uuid':     meeting_uuid,
                'rtms_stream_id':   stream_id,
            }))
            print(f'[RTMS] Sent CLIENT_READY_ACK (msg_type=7) for meeting={meeting_id}', flush=True)

            await sig_ws.send(json.dumps({
                'msg_type': 5,
                'events': [
                    {'event_type': 8, 'subscribe': True},
                    {'event_type': 9, 'subscribe': True},
                ],
            }))
            print(f'[RTMS] Subscribed to camera ON/OFF events for meeting={meeting_id}', flush=True)

            sig_task    = asyncio.create_task(_drain_sig(sig_ws, meeting_id))
            last_sample: dict[str, float] = {}

            try:
                media_done = False
                while not media_done and not redis_client.exists(stop_key):
                    try:
                        async with websockets.connect(
                            video_url,
                            ping_interval=None,
                            max_size=10 * 1024 * 1024,
                        ) as media_ws:

                            ok = await _media_handshake(media_ws, meeting_uuid, stream_id)
                            if not ok:
                                print(f'[RTMS] Media handshake failed for {meeting_id}', flush=True)
                                media_done = True
                                break

                            print(f'[RTMS] Video stream live for meeting {meeting_id}', flush=True)
                            keepalive_task = asyncio.create_task(_proactive_keepalive(media_ws))
                            try:
                                async for message in media_ws:

                                    if redis_client.exists(stop_key):
                                        print(f'[RTMS] Stop signal — closing {meeting_id}', flush=True)
                                        media_done = True
                                        break

                                    raw = message if isinstance(message, bytes) else message.encode('utf-8')
                                    try:
                                        msg_dict = json.loads(raw)
                                    except Exception:
                                        continue

                                    mt = msg_dict.get('msg_type')

                                    if mt == 12:
                                        await media_ws.send(json.dumps({'msg_type': 13}))
                                        continue

                                    if mt in (7, 8, 9, 10):
                                        print(f'[RTMS] Stream stopped by Zoom (msg_type={mt})', flush=True)
                                        media_done = True
                                        break

                                    if mt != 15:
                                        continue

                                    content  = msg_dict.get('content', {})
                                    b64_data = content.get('data', '')
                                    if not b64_data:
                                        continue

                                    frame_bytes      = base64.b64decode(b64_data)
                                    participant_id   = str(content.get('user_id', 'unknown'))
                                    participant_type = content.get('participant_type', 'student')
                                    now              = time.time()

                                    if now - last_sample.get(participant_id, 0) < FRAME_SAMPLE_INTERVAL:
                                        continue

                                    last_sample[participant_id] = now

                                    arr   = np.frombuffer(frame_bytes, dtype=np.uint8)
                                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                                    if frame is None:
                                        print(f'[RTMS] cv2.imdecode failed: participant={participant_id} '
                                              f'len={len(frame_bytes)} header={frame_bytes[:4].hex()}', flush=True)
                                        continue

                                    print(f'[RTMS] Frame sampled: meeting={meeting_id} '
                                          f'participant={participant_id} size={frame.shape}', flush=True)

                                    loop = asyncio.get_running_loop()
                                    loop.run_in_executor(
                                        executor,
                                        _run_vision_on_frame,
                                        meeting_id, participant_id, participant_type, frame
                                    )

                            except websockets.exceptions.ConnectionClosed:
                                pass  # reconnect on next iteration
                            finally:
                                keepalive_task.cancel()

                        if not media_done and not redis_client.exists(stop_key):
                            print(f'[RTMS] Media WS closed — reconnecting for meeting {meeting_id}', flush=True)
                            await asyncio.sleep(1)

                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        if not media_done and not redis_client.exists(stop_key):
                            print(f'[RTMS] Media error ({e}) — reconnecting for meeting {meeting_id}', flush=True)
                            await asyncio.sleep(2)
                        else:
                            break
            finally:
                sig_task.cancel()

    except asyncio.CancelledError:
        print(f'[RTMS] Task cancelled for meeting {meeting_id}', flush=True)
    except asyncio.TimeoutError:
        print(f'[RTMS] Timeout for meeting {meeting_id}', flush=True)
    except Exception as e:
        import websockets
        if isinstance(e, websockets.exceptions.ConnectionClosedError):
            # Zoom force-closes the TCP connection when stopping a stream — expected
            print(f'[RTMS] Stream closed by Zoom for meeting {meeting_id}', flush=True)
        else:
            print(f'[RTMS] Error for meeting {meeting_id}: {e}', flush=True)
            import traceback
            traceback.print_exc()
    finally:
        executor.shutdown(wait=False)
        for task in list(_cam_off_watchers.values()):
            task.cancel()
        _cam_off_watchers.clear()
        redis_client.delete(stop_key)
        # Clean up all RTMS Redis state for this meeting
        for key in redis_client.scan_iter(f'rtms:{meeting_id}:*'):
            redis_client.delete(key)
        print(f'[RTMS] Session cleaned up for meeting {meeting_id}', flush=True)
