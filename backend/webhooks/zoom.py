import hmac
import hashlib
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from core.config import settings
from services.schedule import on_meeting_started, on_meeting_ended
from services.attendance import on_participant_joined, on_participant_left

router = APIRouter(prefix='/api/v1/webhooks', tags=['webhooks'])


@router.post('/zoom')
async def zoom_webhook(request: Request):
    try:
        body = await request.json()
        event = body.get('event')

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

        payload = body.get('payload', {})
        print(f'[WEBHOOK] {event}')

        handlers = {
            'meeting.started':             on_meeting_started,
            'meeting.ended':               on_meeting_ended,
            'meeting.participant_joined':  on_participant_joined,
            'meeting.participant_left':    on_participant_left,
        }

        handler = handlers.get(event)
        if handler:
            handler(payload)
        else:
            print(f'[UNHANDLED] {event}')

        return JSONResponse(content={'status': 'ok'})
    

    except Exception as e:
        print(f'[ERROR] {e}')
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={'error': str(e)})