import asyncio
import hmac
import hashlib
import json
import traceback
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from core.config import settings
from services.schedule import on_meeting_started, on_meeting_ended
from services.attendance import on_participant_joined, on_participant_left

router = APIRouter(prefix='/api/v1/webhooks', tags=['webhooks'])

# Live RTMS tasks: meeting_id → asyncio.Task (in-process, same event loop as FastAPI)
_rtms_tasks: dict[str, asyncio.Task] = {}


async def _on_rtms_started(payload: dict):
    # Confirmed Zoom RTMS payload (flat, not nested inside 'object'):
    # { "meeting_id": 85416038689, "meeting_uuid": "...",
    #   "rtms_stream_id": "...", "server_urls": "wss://..." }
    meeting_id    = str(payload.get('meeting_id', ''))
    meeting_uuid  = payload.get('meeting_uuid', '')
    signaling_url = payload.get('server_urls', '')
    stream_id     = payload.get('rtms_stream_id', '')

    print(f'[RTMS] meeting.rtms_started  meeting={meeting_id} '
          f'uuid={meeting_uuid!r} stream={stream_id!r} url={signaling_url!r}', flush=True)

    if not signaling_url:
        print('[RTMS] No signaling URL in payload — skipping', flush=True)
        return

    # Cache uuid→id so rtms_stopped (which only carries uuid) can resolve it
    if meeting_uuid and meeting_id:
        from core.redis_client import redis_client
        redis_client.setex(f'rtms:uuid:{meeting_uuid}', 7200, meeting_id)

    from services.rtms import connect_rtms

    task = asyncio.create_task(
        connect_rtms(meeting_id, meeting_uuid, signaling_url, stream_id),
        name=f'rtms-{meeting_id}',
    )
    _rtms_tasks[meeting_id] = task
    task.add_done_callback(lambda t: _rtms_tasks.pop(meeting_id, None))
    print(f'[RTMS] Asyncio task created for meeting={meeting_id}', flush=True)


async def _on_rtms_stopped(payload: dict):
    print(f'[RTMS] meeting.rtms_stopped  full payload: {json.dumps(payload)}', flush=True)
    meeting_uuid = payload.get('meeting_uuid', '')
    meeting_id   = str(payload.get('meeting_id', ''))

    # rtms_stopped payload has no meeting_id — look it up from the uuid we cached
    if not meeting_id and meeting_uuid:
        from core.redis_client import redis_client
        cached = redis_client.get(f'rtms:uuid:{meeting_uuid}')
        if cached:
            meeting_id = cached.decode() if isinstance(cached, bytes) else str(cached)

    print(f'[RTMS] Stopping session for meeting={meeting_id}', flush=True)

    task = _rtms_tasks.pop(meeting_id, None)
    if task and not task.done():
        task.cancel()


def _on_rtms_interrupted(payload: dict):
    meeting_id = str(payload.get('meeting_id', ''))
    print(f'[RTMS] Stream interrupted for meeting={meeting_id} — Zoom will auto-resume', flush=True)


_HANDLERS = {
    'meeting.started':            on_meeting_started,
    'meeting.ended':              on_meeting_ended,
    'meeting.participant_joined': on_participant_joined,
    'meeting.participant_left':   on_participant_left,
    'meeting.rtms_started':       _on_rtms_started,
    'meeting.rtms_interrupted':   _on_rtms_interrupted,
    'meeting.rtms_stopped':       _on_rtms_stopped,
}


async def _dispatch(event: str, payload: dict):
    """Process a Zoom webhook event. Runs in a background task after 200 is sent."""
    try:
        handler = _HANDLERS.get(event)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
        else:
            print(f'[UNHANDLED] {event}', flush=True)
    except Exception as e:
        print(f'[WEBHOOK ERROR] event={event} error={e}', flush=True)
        traceback.print_exc()


@router.post('/zoom')
async def zoom_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    body = json.loads(raw_body)
    event = body.get('event', '')

    # URL validation — Zoom expects the token back immediately, no sig check needed
    if event == 'endpoint.url_validation':
        plain_token = body['payload']['plainToken']
        encrypted = hmac.new(
            key=settings.ZOOM_WEBHOOK_SECRET_TOKEN.encode('utf-8'),
            msg=plain_token.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        return JSONResponse(content={
            'plainToken':     plain_token,
            'encryptedToken': encrypted
        })

    # Verify the request came from Zoom — reject anything without a valid signature
    timestamp = request.headers.get('x-zm-request-timestamp', '')
    signature = request.headers.get('x-zm-signature', '')
    message = f'v0:{timestamp}:{raw_body.decode()}'
    expected = 'v0=' + hmac.new(
        key=settings.ZOOM_WEBHOOK_SECRET_TOKEN.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        print('[WEBHOOK] Rejected — invalid signature', flush=True)
        return JSONResponse(status_code=401, content={'error': 'Invalid signature'})

    payload = body.get('payload', {})
    print(f'[WEBHOOK] Received: {event}', flush=True)

    # Return 200 to Zoom immediately — BEFORE processing.
    # Any exception during processing is logged but cannot cause a retry.
    background_tasks.add_task(_dispatch, event, payload)

    return JSONResponse(content={'status': 'ok'})
