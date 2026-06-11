import httpx
import base64
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from core.config import settings
from services.zoom_token_store import save_tokens

router = APIRouter(prefix="/oauth", tags=["OAuth"])

ZOOM_CLIENT_ID = settings.ZOOM_CLIENT_ID
ZOOM_CLIENT_SECRET = settings.ZOOM_CLIENT_SECRET
ZOOM_REDIRECT_URI = settings.ZOOM_REDIRECT_URI


@router.get("/callback")
async def oauth_callback(code: str = Query(...), state: str = Query(None)):
    """
    Zoom redirects here after user authorizes the app.
    Exchange the authorization code for access + refresh tokens.
    """
    credentials = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://zoom.us/oauth/token",
            headers={
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": ZOOM_REDIRECT_URI,
            },
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Token exchange failed: {response.text}",
        )

    token_data = response.json()

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    if not access_token or not refresh_token:
        raise HTTPException(
            status_code=500,
            detail="Zoom returned incomplete token data",
        )

    save_tokens(access_token, refresh_token, expires_in)

    print(f"[OAUTH] Token obtained. Expires in {expires_in}s", flush=True)

    return JSONResponse(content={
        "status": "authorized",
        "expires_in": expires_in,
    })