# services/zoom_api.py
import httpx
import base64
from datetime import datetime, timezone, timedelta
from core.config import settings

ZOOM_API_BASE = 'https://api.zoom.us/v2'

_token_cache: dict = {'token': None, 'expires_at': datetime.min.replace(tzinfo=timezone.utc)}


def get_access_token() -> str:
    now = datetime.now(timezone.utc)
    if _token_cache['token'] and now < _token_cache['expires_at']:
        return _token_cache['token']

    credentials = f'{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}'
    encoded = base64.b64encode(credentials.encode()).decode()

    response = httpx.post(
        f'https://zoom.us/oauth/token?grant_type=account_credentials&account_id={settings.ZOOM_ACCOUNT_ID}',
        headers={'Authorization': f'Basic {encoded}'},
        timeout=15.0
    )
    response.raise_for_status()
    token = response.json()['access_token']

    # Zoom tokens are valid for 1 hour — cache for 55 min to avoid edge cases
    _token_cache['token'] = token
    _token_cache['expires_at'] = now + timedelta(minutes=55)
    print('[ZOOM] Access token refreshed')
    return token


def get_headers() -> dict:
    return {
        'Authorization': f'Bearer {get_access_token()}',
        'Content-Type': 'application/json'
    }


def create_meeting(teacher_zoom_user_id: str, topic: str,
                   start_time: datetime, duration_mins: int) -> dict:
    """
    Creates a Zoom meeting with registration enabled.
    Returns full meeting object including meeting ID and join URL.
    """
    payload = {
        'topic': topic,
        'type': 2,  # scheduled meeting
        'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'duration': duration_mins,
        'timezone': 'UTC',
        'settings': {
            'registration_type': 1,       # registration required
            'approval_type': 0,           # auto approve
            'registrants_email_notification': True,
            'waiting_room': False,        # disable waiting room for registered users
            'join_before_host': False,
        }
    }

    response = httpx.post(
        f'{ZOOM_API_BASE}/users/{teacher_zoom_user_id}/meetings',
        headers=get_headers(),
        json=payload,
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


def register_participant(meeting_id: str, first_name: str,
                            last_name: str, email: str) -> dict:
    payload = {
        'first_name': first_name,
        'last_name':  last_name,
        'email':      email
    }

    response = httpx.post(
        f'{ZOOM_API_BASE}/meetings/{meeting_id}/registrants',
        headers=get_headers(),
        json=payload,
        timeout=30.0
    )

    if response.status_code != 201:
        print(f'[ZOOM ERROR] Status: {response.status_code}')
        print(f'[ZOOM ERROR] Body: {response.text}')

    response.raise_for_status()
    return response.json()