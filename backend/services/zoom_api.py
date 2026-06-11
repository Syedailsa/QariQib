# services/zoom_api.py
import httpx
from datetime import datetime, timezone
from services.zoom_token_store import get_access_token
from core.config import settings

ZOOM_API_BASE = 'https://api.zoom.us/v2'


def get_headers() -> dict:
    token = get_access_token()
    if not token:
        raise RuntimeError(
            '[ZOOM] No valid OAuth token available. Re-authorise at: '
            f'https://zoom.us/oauth/authorize?response_type=code'
            f'&client_id={settings.ZOOM_CLIENT_ID}'
            f'&redirect_uri={settings.ZOOM_REDIRECT_URI}'
            f'&scope=meeting:write:meeting'
        )
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }


def create_meeting(topic: str, start_time: datetime, duration_mins: int,
                   alternative_host_email: str = '') -> dict:
    """
    Creates a Zoom meeting under the academy's authorized account (me).
    alternative_host_email: teacher's Zoom account email — makes the meeting
    appear in their Zoom schedule and lets them start/host it themselves.
    """
    payload = {
        'topic': topic,
        'type': 2,  # scheduled meeting
        'start_time': start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'duration': duration_mins,
        'timezone': 'UTC',
        'settings': {
            'registration_type': 1,
            'approval_type': 0,
            'registrants_email_notification': True,
            'waiting_room': False,
            'join_before_host': True,   # alt host can start without admin
            'alternative_hosts': alternative_host_email,
            'alternative_hosts_email_notification': True,
        }
    }

    response = httpx.post(
        f'{ZOOM_API_BASE}/users/me/meetings',
        headers=get_headers(),
        json=payload,
        timeout=30.0
    )
    if not response.is_success:
        print(f'[ZOOM] create_meeting failed — status={response.status_code}')
        print(f'[ZOOM] error body: {response.text}')
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