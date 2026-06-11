import sys
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from webhooks.zoom import router as zoom_router
from routers.teachers_route import router as teachers_router
from routers.students_route import router as students_router
from routers.schedules_route import router as schedules_router
from routers.alerts_route import router as alerts_router
from routers.oauth_route import router as oauth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-queue tasks for any active classes that have no Celery tasks in Redis.
    # Non-fatal: if the broker is down at startup, log and continue — the app
    # must start even if Celery is temporarily unreachable.
    try:
        from services.scheduler import recover_missing_tasks
        recover_missing_tasks()
    except Exception as e:
        print(f'[STARTUP WARNING] Could not recover Celery tasks: {e}', flush=True)
    yield


app = FastAPI(
    title='QaraQib API',
    version='1.0.0',
    docs_url='/api/docs',
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:3000',
        'https://zoom.us',           
        'https://marketplace.zoom.us'
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(oauth_router) 
app.include_router(zoom_router)
app.include_router(teachers_router)
app.include_router(students_router)
app.include_router(schedules_router)
app.include_router(alerts_router)

@app.get('/health')
async def health_check():
    return {'status': 'ok', 'service': 'qaraqib-api'}