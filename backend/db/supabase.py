import httpx
from supabase import create_client, Client
from core.config import settings

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)

# Force HTTP/1.1 on the postgrest session to prevent RemoteProtocolError 500s.
# The Supabase sync client uses a shared httpx connection pool. Under HTTP/2,
# concurrent threads (FastAPI runs sync handlers in a thread pool) can corrupt
# the same connection stream. HTTP/1.1 connections are thread-independent.
# We must copy BOTH headers (auth token) and base_url (PostgREST endpoint)
# from the original session — missing either breaks all DB queries.
try:
    _old = supabase.postgrest.session
    supabase.postgrest.session = httpx.Client(
        http2=False,
        base_url=str(_old.base_url),
        headers=dict(_old.headers),
        timeout=30.0
    )
except Exception:
    pass  # SDK version doesn't expose .session — skip the patch
