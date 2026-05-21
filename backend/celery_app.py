import ssl
from celery import Celery
from core.config import settings

celery_app = Celery(
    'qaraqib',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=['tasks.absence']   # tells Celery where to find our tasks
)

celery_app.conf.update(
    # Serialization — JSON is safe and readable
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # Always work in UTC
    timezone='UTC',
    enable_utc=True,

    # Task reliability settings
    task_track_started=True,       # marks task as STARTED before running (visible in monitoring)
    task_acks_late=True,           # only remove task from queue AFTER it finishes, not before
                                   # — if worker crashes mid-task, Redis re-queues it
    worker_prefetch_multiplier=1,  # each worker only picks up 1 task at a time from the queue
                                   # — critical for ETA tasks: prevents a worker from hoarding
                                   # future-dated tasks and blocking other workers from taking them

    broker_connection_retry_on_startup=True,
    redis_backend_use_ssl={'ssl_cert_reqs': ssl.CERT_NONE},
    broker_use_ssl={'ssl_cert_reqs': ssl.CERT_NONE},

    # Fail fast if Upstash is unreachable — prevents requests from hanging forever.
    # Without these, a refused/slow broker connection blocks the calling thread indefinitely.
    broker_transport_options={
        'socket_connect_timeout': 5,
        'socket_timeout': 10,
        'retry_on_timeout': False,
    },

    # Celery Beat — periodic tasks (replaces APScheduler's IntervalTrigger)
    beat_schedule={
        'check-missed-classes': {
            'task': 'tasks.absence.check_missed_classes',
            'schedule': 900.0,   # every 15 minutes (in seconds)
        }
    }
)
