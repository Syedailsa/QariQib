# QaraQib — Backend

Quran academy class monitoring system. Schedules Zoom classes, tracks real-time attendance via Zoom webhooks, and fires alerts when teachers or students are absent, late, or leave early.

---

## Architecture

```
Frontend (Next.js)
      │  REST API calls
      ▼
FastAPI  ──────────────────────────────► Supabase (all DB reads/writes)
      │
      │  on class create / edit / delete
      │  queues ETA tasks in daemon thread
      ▼
Redis (Upstash — TLS rediss://)
      │  stores timed tasks until fire time
      │  Beat fires check_missed_classes every 15 min
      ▼
Celery Worker
      │  runs absence checks at scheduled times
      ▼
Supabase  (writes alerts, attendance records, updates class status)

Zoom API ──► POST /api/v1/webhooks/zoom
                 │  signature verified (HMAC-SHA256)
                 │  returns 200 immediately → BackgroundTask processes
                 ▼
            attendance_records + alerts tables
```

---

## Tech Stack

| Library | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server |
| `supabase` (Python SDK) | All database operations |
| `celery` 5.3 | Distributed background task queue |
| `redis` 5.0 | Celery broker + result backend (Upstash) |
| `gevent` | High-concurrency worker pool (production) |
| `httpx` | Calling Zoom REST API (HTTP/1.1, 30s timeout) |
| `pydantic` 2.x | Request/response validation |
| `pydantic-settings` | Typed `.env` config via `core/config.py` |

---

## File Structure

```
backend/
├── main.py                  # FastAPI app, lifespan (recover_missing_tasks on startup)
├── celery_app.py            # Celery + Beat config, Upstash Redis connection
├── Procfile                 # Process reference for Railway/Heroku
├── supervisord.conf         # Production process manager config (Linux VPS)
├── requirements.txt
│
├── core/
│   └── config.py            # Pydantic Settings — reads all env vars
│
├── db/
│   └── supabase.py          # Supabase client (HTTP/1.1 forced to prevent concurrency errors)
│
├── routers/
│   ├── schedules_route.py   # CRUD for class schedules + Zoom + Celery orchestration
│   ├── teachers_route.py    # Teacher CRUD + consent toggle
│   ├── students_route.py    # Student CRUD
│   └── alerts_route.py      # List alerts, resolve alert
│
├── services/
│   ├── class_service.py     # setup_class(): creates Zoom meeting, registers participants
│   ├── zoom_api.py          # Zoom Server-to-Server OAuth, meeting/registrant API calls
│   ├── schedule.py          # on_meeting_started(), on_meeting_ended() webhook handlers
│   ├── attendance.py        # on_participant_joined(), on_participant_left() webhook handlers
│   ├── alerts.py            # create_alert(), resolve_alert(), THRESHOLDS, ALERT_SEVERITY
│   └── scheduler.py         # schedule_class_jobs(), revoke_class_jobs(), recover_missing_tasks()
│
├── tasks/
│   └── absence.py           # 4 Celery tasks + get_task_ids() UUID helper
│
└── webhooks/
    └── zoom.py              # Zoom webhook router — verifies signature, routes to handlers
```

---

## Complete Request Flow

### 1. Creating a Class — `POST /api/v1/schedules`

1. Validates teacher exists and has `consent_given = true`
2. Inserts row into `class_schedules` (status: `scheduled`)
3. Inserts one row per student into `class_students`
4. `setup_class()` calls Zoom API:
   - Creates a scheduled Zoom meeting (registration required, auto-approve)
   - Stores the host join URL on the `teachers` row
   - Registers each student → stores `zoom_registrant_id` + `zoom_join_url` on `class_students`
5. `schedule_class_jobs()` runs in a **daemon thread** — broker latency never blocks the HTTP response

### 2. The 3 ETA Celery Tasks

| Task | Fires at | What it checks |
|---|---|---|
| `check_teacher_absent` | scheduled_start + 8 min | No attendance record for teacher → HIGH alert |
| `check_student_absents` | scheduled_start + 8 min | No attendance record per student → MEDIUM alert each |
| `check_empty_class` | scheduled_start + 10 min | No one still present in meeting → HIGH alert |

Task IDs are **deterministic UUIDs** via `uuid.uuid5(namespace, schedule_id)` — same schedule always produces the same task IDs so they can be revoked by ID without querying the DB.

Each task re-checks `status` before acting. If the class is already `completed` or `missed`, the task skips silently — no duplicate alerts.

### 3. Zoom Webhooks — `POST /api/v1/webhooks/zoom`

**All requests are signature-verified** using `x-zm-signature` + `x-zm-request-timestamp` headers (HMAC-SHA256). Invalid signatures return 401 immediately.

Every valid event gets a `200 OK` response **before** any processing — Zoom never sees a slow handler and never retries due to a processing error. Actual work runs in a FastAPI `BackgroundTask`.

| Event | Handler | Action |
|---|---|---|
| `meeting.started` | `on_meeting_started` | status → `live`, records `actual_start` |
| `meeting.participant_joined` | `on_participant_joined` | Writes `attendance_records` row, resolves existing absence alert, creates `teacher_late` or `participant_late` alert if joining late |
| `meeting.participant_left` | `on_participant_left` | Updates `leave_time` + `duration_mins`, creates `early_departure` alert if left >6 min before scheduled end |
| `meeting.ended` | `on_meeting_ended` | status → `completed`, calculates `actual_duration_mins` + `duration_diff_mins`, deletes the Zoom meeting |

**Identity resolution:**
- Teacher identified by `email` field in the webhook payload
- Students identified by `registrant_id` (set at registration time, unique per meeting)

**Race condition — `meeting.ended` vs `meeting.participant_left`:**
When the teacher ends the meeting, Zoom fires both events almost simultaneously. `on_participant_left` does **not** skip on `status='completed'` — it falls through to the attendance record check so `early_departure` fires correctly even if `meeting.ended` was processed first.

### 4. Student Absent Alerts — Fair Threshold Rule

At meeting end, `_alert_absent_students_if_fair()` is called:
- If `actual_duration_mins >= 8` (the `student_absent_mins` threshold): students who never joined get `student_absent` alerts
- If `actual_duration_mins < 8`: **no student absent alerts** — the teacher ended the class too early and it is not the students' fault

This applies at both `meeting.ended` time and when the Celery `check_student_absents` task fires. If the class is already `completed` or `missed` when the task fires, the task skips.

### 5. Alert Idempotency

`create_alert()` runs a `SELECT` before every `INSERT`:
- If an unresolved alert of the same `(schedule_id, alert_type, participant_id)` already exists → skip, print `[ALERT SKIP]`
- This prevents duplicates from Zoom webhook retries, Celery retries, and the race condition at meeting end

### 6. Celery Beat — Every 15 Minutes

`check_missed_classes` runs on a schedule:
- Finds any `scheduled` or `live` class whose `scheduled_end` has passed
- Sets status → `missed`
- Deletes the Zoom meeting via API
- Creates `teacher_absent` alerts for teachers who never joined
- Creates `student_absent` alerts for students who never joined (checked against `attendance_records`, not just whether an alert exists)

### 7. Editing a Class — `PATCH /api/v1/schedules/:id`

- Only allowed when status is `scheduled`
- If `scheduled_start` changes: revokes old ETA tasks in a daemon thread → re-queues at the new time
- Updates the Zoom meeting time/duration via Zoom API

### 8. Deleting a Class — `DELETE /api/v1/schedules/:id`

Order matters — tasks revoked **before** DB deletion so no task fires into a deleted schedule:
1. Revoke Celery tasks (wrapped in try/except — if Redis is unreachable, deletion continues)
2. Delete Zoom meeting via API
3. Delete `attendance_records`, `alerts`, `absences`, `class_students`
4. Delete `class_schedules`

### 9. FastAPI Startup — `recover_missing_tasks()`

Safety net for Redis wipes or first deploy after migration:
- Finds all active (`scheduled` / `live`) classes whose end time hasn't passed
- Re-queues their 3 ETA tasks (does NOT revoke first — revoking + re-queuing the same deterministic UUID adds it to Celery's revoke list)
- Non-fatal: if Redis is unreachable at startup, a warning is logged and the app starts anyway

---

## Alert Types

| Type | Severity | Trigger |
|---|---|---|
| `teacher_absent` | HIGH | Teacher not joined 8 min after start (or class missed entirely) |
| `empty_class` | HIGH | No participants in meeting 10 min after start |
| `teacher_late` | MEDIUM | Teacher joined between 5–8 min after start |
| `student_absent` | MEDIUM | Student not joined 8 min after start AND class ran ≥ 8 min |
| `early_departure` | MEDIUM | Participant left >6 min before scheduled end |
| `participant_late` | LOW | Student joined 5+ min after start |

Alerts are resolved automatically when a participant joins late (resolves their absent alert). Alerts can also be resolved manually via the dashboard.

---

## Key Design Decisions

**HTTP/1.1 on Supabase client (`db/supabase.py`)**
The Supabase Python SDK uses httpx with HTTP/2 by default. Under concurrent FastAPI threads, HTTP/2 stream multiplexing causes `RemoteProtocolError`. The postgrest session is patched to HTTP/1.1 at startup — must copy both `headers` (auth token) AND `base_url` (PostgREST endpoint).

**Daemon threads for Celery calls**
`schedule_class_jobs()` and `revoke_class_jobs()` in route handlers run in `threading.Thread(daemon=True)` — broker connection latency never blocks the HTTP response. The class creation returns `200` immediately even if Redis is slow.

**`celery_app` import order in `schedule_class_jobs`**
`from celery_app import celery_app` must be the first import inside `schedule_class_jobs`. This sets our Redis-backed app as `celery.current_app`. Without it, `@shared_task` functions bind to Celery's default AMQP app (localhost:5672) which doesn't exist.

**No `--reload` in production**
`uvicorn --reload` uses WatchFiles which can trigger false-positive restarts mid-request on Windows, killing workers and causing connection resets. Run without `--reload`.

---

## API Endpoints

```
GET    /api/v1/schedules              List all schedules (teacher, students, alerts)
GET    /api/v1/schedules/today        Today's schedules only
GET    /api/v1/schedules/:id          Single schedule with attendance + alerts
POST   /api/v1/schedules              Create schedule + Zoom meeting + queue tasks
PATCH  /api/v1/schedules/:id          Edit time/duration (reschedules tasks + Zoom)
DELETE /api/v1/schedules/:id          Delete class, Zoom meeting, all records

GET    /api/v1/teachers               List active teachers
POST   /api/v1/teachers               Add teacher
PATCH  /api/v1/teachers/:id/consent   Toggle monitoring consent

GET    /api/v1/students               List active students
POST   /api/v1/students               Add student

GET    /api/v1/alerts                 List alerts (?resolved=false)
POST   /api/v1/alerts/:id/resolve     Mark alert resolved

POST   /api/v1/webhooks/zoom          Zoom webhook receiver (signature verified)
GET    /health                        Health check
GET    /api/docs                      Swagger UI
```

---

## Environment Variables (`.env`)

```env
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
REDIS_URL=rediss://default:<password>@<host>.upstash.io:<port>
ZOOM_ACCOUNT_ID=
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
ZOOM_WEBHOOK_SECRET_TOKEN=
DATABASE_URL=              # Required by pydantic-settings (not used at runtime)
SECRET_KEY=                # Required by pydantic-settings
```

---

## ngrok with validated URL must be runnging its terminal

## Running Locally (3 terminals)

```bash
# Terminal 1 — FastAPI (NO --reload flag — causes false restarts on Windows)
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Celery worker (--pool=solo required on Windows)
cd backend
celery -A celery_app.celery_app worker --pool=solo --loglevel=info

# Terminal 3 — Celery Beat
cd backend
celery -A celery_app.celery_app beat --loglevel=info
```

Redis must be reachable (Upstash free tier — set `REDIS_URL=rediss://...` in `.env`).

If you see `[STARTUP WARNING] Could not recover Celery tasks` on startup, the worker is not yet running — start it and tasks will work fine.

## Production (Linux VPS)

Use `supervisord.conf` — manages all 3 processes with autorestart. Update the placeholder paths (`/path/to/venv`, `/path/to/backend`) before deploying.

```bash
# Worker uses gevent pool for high concurrency (100 simultaneous Supabase calls)
celery -A celery_app.celery_app worker --pool=gevent --concurrency=100 --loglevel=info
```

Run exactly **one** Beat process — multiple Beat instances duplicate periodic tasks. `supervisord` enforces this.
