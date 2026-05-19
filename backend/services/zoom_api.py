# services/zoom_api.py
import httpx
import base64
from datetime import datetime, timezone
from core.config import settings

ZOOM_API_BASE = 'https://api.zoom.us/v2'


def get_access_token() -> str:
    credentials = f'{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}'
    encoded = base64.b64encode(credentials.encode()).decode()

    response = httpx.post(
        f'https://zoom.us/oauth/token?grant_type=account_credentials&account_id={settings.ZOOM_ACCOUNT_ID}',
        headers={'Authorization': f'Basic {encoded}'}
    )
    response.raise_for_status()
    return response.json()['access_token']


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
        json=payload
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
        json=payload
    )
    
    # Print full error for debugging
    if response.status_code != 201:
        print(f'[ZOOM ERROR] Status: {response.status_code}')
        print(f'[ZOOM ERROR] Body: {response.text}')
    
    response.raise_for_status()
    return response.json()


def get_registrants(meeting_id: str) -> list:
    """
    Returns list of all registrants for a meeting.
    """
    response = httpx.get(
        f'{ZOOM_API_BASE}/meetings/{meeting_id}/registrants',
        headers=get_headers()
    )
    response.raise_for_status()
    return response.json().get('registrants', [])