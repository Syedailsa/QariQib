import httpx
from supabase import create_client, Client
from core.config import settings

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)

try:
    _old = supabase.postgrest.session
    supabase.postgrest.session = httpx.Client(
        http2=False,
        base_url=str(_old.base_url),
        headers=dict(_old.headers),
        timeout=30.0
    )
except Exception:
    pass