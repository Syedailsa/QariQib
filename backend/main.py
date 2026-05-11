from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings

app = FastAPI(
    title='QaraQib API',
    version='1.0.0',
    docs_url='/api/docs' if settings.ENV != 'production' else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS.split(','),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.get('/health')
async def health_check():
    return {'status': 'ok', 'service': 'qaraqib-api'}