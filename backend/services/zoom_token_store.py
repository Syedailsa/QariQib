import json
import time
import httpx
import base64
from core.config import settings
from core.redis_client import redis_client

TOKEN_KEY = "zoom:oauth:tokens"


def get_access_token() -> str | None:
    raw = redis_client.get(TOKEN_KEY)
    if raw:
        data = json.loads(raw)
        if time.time() < data["expires_at"]:
            return data["access_token"]
    return _fetch_new_token()


def _fetch_new_token() -> str | None:
    credentials = f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    response = httpx.post(
        "https://zoom.us/oauth/token",
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "account_credentials",
            "account_id": settings.ZOOM_ACCOUNT_ID,
        },
    )

    if response.status_code != 200:
        print(f"[TOKEN STORE] Failed to fetch token: {response.text}", flush=True)
        return None

    token_data = response.json()
    access_token = token_data["access_token"]
    expires_in = token_data["expires_in"]

    redis_client.set(TOKEN_KEY, json.dumps({
        "access_token": access_token,
        "expires_at": time.time() + expires_in - 60,
    }))
    print("[TOKEN STORE] New token fetched and cached.", flush=True)
    return access_token
