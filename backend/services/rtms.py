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
                  → sample 1 frame / 10s per participant
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
FRAME_SAMPLE_INTERVAL = 10   # seconds between samples per participant
QUEUE_DEPTH_LIMIT     = 200  # drop frames if more than this many queued
HANDSHAKE_TIMEOUT     = 15   # seconds to wait for each WS message

_executor = ThreadPoolExecutor(max_workers=4)


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
    media_type 32 = video (H.264).
    """
    signature = _compute_signature(meeting_uuid, stream_id)

    await ws.send(json.dumps({
        'msg_type':         3,
        'protocol_version': 1,
        'meeting_uuid':     meeting_uuid,
        'rtms_stream_id':   stream_id,
        'sequence':         0,
        'signature':        signature,
        'media_type':       32,
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
        from services.vision import analyze_frame
        from services.vision_state import process_result

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

    stop_key = f'rtms:stop:{meeting_id}'

    async def _drain_sig(ws):
        """Consume signaling-channel messages and respond to keep-alives."""
        try:
            async for msg in ws:
                raw = msg if isinstance(msg, bytes) else msg.encode('utf-8')
                try:
                    d = json.loads(raw)
                    if d.get('msg_type') == 12:
                        await ws.send(json.dumps({'msg_type': 13}))
                except Exception:
                    pass
        except Exception:
            pass

    async def _proactive_keepalive(ws):
        """Send keep-alive request every 20s so Zoom doesn't time out the stream."""
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

            async with websockets.connect(
                video_url,
                ping_interval=None,   # Zoom uses its own keep-alive (msg_type 12/13)
                max_size=10 * 1024 * 1024,
            ) as media_ws:

                ok = await _media_handshake(media_ws, meeting_uuid, stream_id)
                if not ok:
                    print(f'[RTMS] Media handshake failed for {meeting_id}', flush=True)
                    return

                # Signal to Zoom that we're ready — without this Zoom never sends frames
                await sig_ws.send(json.dumps({
                    'msg_type':         7,
                    'protocol_version': 1,
                    'sequence':         0,
                    'meeting_uuid':     meeting_uuid,
                    'rtms_stream_id':   stream_id,
                }))
                print(f'[RTMS] Sent CLIENT_READY_ACK (msg_type=7) for meeting={meeting_id}', flush=True)

                print(f'[RTMS] Video stream live for meeting {meeting_id}', flush=True)
                last_sample: dict[str, float] = {}

                # Keep both channels alive concurrently
                sig_task       = asyncio.create_task(_drain_sig(sig_ws))
                keepalive_task = asyncio.create_task(_proactive_keepalive(media_ws))
                try:
                    async for message in media_ws:

                        if redis_client.exists(stop_key):
                            print(f'[RTMS] Stop signal — closing {meeting_id}', flush=True)
                            break

                        raw = message if isinstance(message, bytes) else message.encode('utf-8')
                        try:
                            msg_dict = json.loads(raw)
                        except Exception:
                            continue

                        mt = msg_dict.get('msg_type')

                        # Keep-alive on media channel
                        if mt == 12:
                            await media_ws.send(json.dumps({'msg_type': 13}))
                            continue

                        if mt in (7, 8, 9, 10):
                            print(f'[RTMS] Stream stopped by Zoom (msg_type={mt})', flush=True)
                            break

                        # Skip non-video (audio=14, deskshare=16, transcript=17, etc.)
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
                            _executor,
                            _run_vision_on_frame,
                            meeting_id, participant_id, participant_type, frame
                        )
                finally:
                    sig_task.cancel()
                    keepalive_task.cancel()

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
        redis_client.delete(stop_key)
        # Clean up all RTMS Redis state for this meeting
        for key in redis_client.scan_iter(f'rtms:{meeting_id}:*'):
            redis_client.delete(key)
        print(f'[RTMS] Session cleaned up for meeting {meeting_id}', flush=True)
