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

_HANDLERS = {
    'meeting.started':            on_meeting_started,
    'meeting.ended':              on_meeting_ended,
    'meeting.participant_joined': on_participant_joined,
    'meeting.participant_left':   on_participant_left,
}


def _dispatch(event: str, payload: dict):
    """Process a Zoom webhook event. Runs in a background task after 200 is sent."""
    try:
        handler = _HANDLERS.get(event)
        if handler:
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
