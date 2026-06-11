import json
import time
import httpx
import base64
from core.config import settings
from core.redis_client import redis_client 


TOKEN_KEY = "zoom:oauth:tokens"


def save_tokens(access_token: str, refresh_token: str, expires_in: int):
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": time.time() + expires_in - 60,  # 60s buffer before real expiry
    }
    redis_client.set(TOKEN_KEY, json.dumps(payload))
    print("[TOKEN STORE] Tokens saved to Redis.", flush=True)


def get_access_token() -> str | None:
    raw = redis_client.get(TOKEN_KEY)
    if not raw:
        return None
    data = json.loads(raw)
    # Token still valid
    if time.time() < data["expires_at"]:
        return data["access_token"]
    # Token expired — refresh it
    return _refresh_access_token(data["refresh_token"])


def _refresh_access_token(refresh_token: str) -> str | None:
    credentials = f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    response = httpx.post(
        "https://zoom.us/oauth/token",
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )

    if response.status_code != 200:
        print(f"[TOKEN STORE] Refresh failed: {response.text}", flush=True)
        return None

    token_data = response.json()
    save_tokens(
        token_data["access_token"],
        token_data["refresh_token"],
        token_data["expires_in"],
    )
    print("[TOKEN STORE] Token refreshed successfully.", flush=True)
    return token_data["access_token"]