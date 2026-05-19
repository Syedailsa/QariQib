from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.scheduler import start_scheduler, scheduler
from webhooks.zoom import router as zoom_router
from routers.teachers_route import router as teachers_router
from routers.students_route import router as students_router
from routers.schedules_route import router as schedules_router
from routers.alerts_route import router as alerts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    scheduler.shutdown()
    print('[SCHEDULER] Stopped')


app = FastAPI(
    title='QaraQib API',
    version='1.0.0',
    docs_url='/api/docs',
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(zoom_router)
app.include_router(teachers_router)
app.include_router(students_router)
app.include_router(schedules_router)
app.include_router(alerts_router)

@app.get('/health')
async def health_check():
    return {'status': 'ok', 'service': 'qaraqib-api'}


# @app.post('/api/v1/test/setup-class/{schedule_id}')
# async def test_setup_class(schedule_id: str):
#     from services.class_service import setup_class
#     meeting_id = setup_class(schedule_id)
#     return {'meeting_id': meeting_id}


# @app.post('/api/v1/test/check-missed')
# async def test_check_missed():
#     from services.scheduler import check_missed_classes
#     check_missed_classes()
#     return {'status': 'done'}



# import requests

# url = "https://acleddata.com/oauth/token"

# data = {
#     "username": "bc240403442iub@vu.edu.pk",
#     "password": "iAhMagang.1996",
#     "grant_type": "password",
#     "client_id": "acled",
#     "scope": "authenticated"
# }

# response = requests.post(url, data=data)

# print(response.json())