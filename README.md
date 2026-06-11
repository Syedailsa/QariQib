# QaraQib — Islamic Online Education Platform

AI-powered Zoom class monitoring backend. Tracks attendance, detects phone usage, monitors camera/face presence, and fires real-time alerts — all from live Zoom video using RTMS (Real-Time Media Streaming).

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| AI Vision | YOLOv8n (phone detection) + MediaPipe BlazeFace (face detection) |
| Live Video | Zoom RTMS WebSocket |
| Background Jobs | Celery + Celery Beat |
| Cache / State | Upstash Redis |
| Database | Supabase (PostgreSQL) |
| Zoom API | OAuth 2.0 + Zoom REST API v2 |

---

## Project Structure

```
QaraQib/
├── backend/
│   ├── main.py                        # FastAPI app entry point, CORS, lifespan
│   ├── celery_app.py                  # Celery + Beat config, Redis broker, beat schedule
│   ├── pyproject.toml                 # Python dependencies (uv)
│   │
│   ├── core/
│   │   ├── config.py                  # All env vars via pydantic-settings
│   │   └── redis_client.py            # Single Redis connection (used everywhere)
│   │
│   ├── db/
│   │   └── supabase.py                # Single Supabase client (used everywhere)
│   │
│   ├── routers/
│   │   ├── alerts_route.py            # GET/PATCH alerts (read + resolve)
│   │   ├── oauth_route.py             # GET /oauth/callback — Zoom OAuth token exchange
│   │   ├── schedules_route.py         # CRUD for class schedules
│   │   ├── students_route.py          # Student management
│   │   └── teachers_route.py          # Teacher management
│   │
│   ├── webhooks/
│   │   └── zoom.py                    # Receives all Zoom webhook events, verifies HMAC
│   │
│   ├── services/
│   │   ├── alerts.py                  # create_alert() / resolve_alert() with dedup
│   │   ├── attendance.py              # participant_joined / participant_left handlers
│   │   ├── class_service.py           # Creates Zoom meeting + registers all participants
│   │   ├── rtms.py                    # Full RTMS WebSocket lifecycle (handshake, frame loop, keep-alives)
│   │   ├── schedule.py                # meeting.started / meeting.ended handlers
│   │   ├── scheduler.py               # Queue / revoke / recover Celery ETA tasks
│   │   ├── vision.py                  # YOLOv8n + MediaPipe inference on a single frame
│   │   ├── vision_state.py            # Per-participant Redis state machine → fires alerts
│   │   ├── zoom_api.py                # Zoom REST API calls (create, register, delete meeting)
│   │   └── zoom_token_store.py        # OAuth token save/get/refresh (Redis-backed)
│   │
│   ├── tasks/
│   │   └── absence.py                 # Celery tasks: teacher_absent, student_absent, empty_class, missed_classes
│   │
│   └── test_vision.py                 # Dev script: offline vision model validator (not part of server)
│
└── frontend/                          # Next.js dashboard
```

---

## Environment Variables

Create `backend/.env`:

```env
# General
ENV=development
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key

# Redis (Upstash or local)
REDIS_URL=rediss://default:password@host:6380

# Zoom App
ZOOM_CLIENT_ID=your-zoom-client-id
ZOOM_CLIENT_SECRET=your-zoom-client-secret
ZOOM_WEBHOOK_SECRET_TOKEN=your-webhook-secret
ZOOM_REDIRECT_URI=https://your-domain.com/oauth/callback

# Optional (not actively used)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
SENDGRID_API_KEY=
SENTRY_DSN=
```

---

## Running the Project

Three separate terminal processes are required. All commands run from the `backend/` directory.

### Terminal 1 — FastAPI Server

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

Handles all HTTP requests, Zoom webhooks, and RTMS WebSocket connections (asyncio tasks run inside this process).

### Terminal 2 — Celery Worker

```bash
cd backend
uv run celery -A celery_app worker --loglevel=info --pool=solo
```

Runs the absence check tasks:
- `check_teacher_absent` — fires at `scheduled_start + 8 min`
- `check_student_absents` — fires at `scheduled_start + 8 min`
- `check_empty_class` — fires at `scheduled_start + 10 min`

Use `--pool=solo` on Windows (avoids multiprocessing issues). On Linux/macOS use `--pool=prefork` or omit the flag.

### Terminal 3 — Celery Beat (Periodic Scheduler)

```bash
cd backend
uv run celery -A celery_app beat --loglevel=info
```

Runs `check_missed_classes` every 15 minutes — catches classes that were never started.

---

## One-Time Zoom OAuth Setup

Before the server can create any Zoom meetings, you must authorize it once:

1. Start the FastAPI server (Terminal 1)
2. Open in browser:
   ```
   https://zoom.us/oauth/authorize?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI
   ```
3. Authorize → Zoom redirects to `/oauth/callback?code=...`
4. The server exchanges the code for tokens and saves them to Redis
5. Tokens auto-refresh — you only need to do this once per Redis wipe

---

## Complete System Flow

### Step 1 — First-Time OAuth
```
Browser → https://zoom.us/oauth/authorize?client_id=...
  → Zoom redirects: GET /oauth/callback?code=...
    → oauth_route.py exchanges code for access + refresh tokens
      → zoom_token_store.py saves tokens to Redis (key: zoom:oauth:tokens)
        → zoom_api.py uses this token for every Zoom REST call
          → token auto-refreshes when expired
```

### Step 2 — Admin Creates a Class
```
POST /api/v1/schedules
  → inserts class_schedules row (status='scheduled')
  → inserts class_students rows (one per student)
  → setup_class() [class_service.py]
      → zoom_api.create_meeting() → Zoom meeting created
      → zoom_api.register_participant() for teacher → join URL stored
      → zoom_api.register_participant() for each student → join URL + registrant_id stored
      → zoom_meeting_id stored on class_schedules
  → schedule_class_jobs() [scheduler.py]
      → queues 3 Celery ETA tasks:
          check_teacher_absent  → start + 8 min
          check_student_absents → start + 8 min
          check_empty_class     → start + 10 min
```

### Step 3 — Teacher Starts the Meeting
```
Zoom webhook: meeting.started
  → on_meeting_started() [schedule.py]
      → class_schedules: status = 'live', actual_start = now

Zoom webhook: meeting.rtms_started
  → _on_rtms_started() [zoom.py]
      → caches rtms:uuid:{uuid} → meeting_id in Redis
      → asyncio.create_task(connect_rtms(...))   ← fires instantly, no Celery
```

### Step 4 — Live RTMS Vision Monitoring
```
connect_rtms() [rtms.py] — runs as asyncio task inside FastAPI's event loop
  → connects to Zoom signaling WebSocket (ping_interval=None)
  → sends SIGNALING_HAND_SHAKE_REQ (msg_type=1) + HMAC signature
  → receives video media server URL
  → connects to Zoom media WebSocket
  → sends MEDIA_DATA_HAND_SHAKE_REQ (msg_type=3)
  → sends CLIENT_READY_ACK (msg_type=7) → Zoom starts sending frames

Two background tasks run concurrently:
  _drain_sig(sig_ws)         → reads signaling channel, replies msg_type 13 to keep-alives
  _proactive_keepalive(ws)   → sends msg_type 12 every 20s on media channel (prevents timeout)

Frame loop (media WebSocket):
  msg_type 12 → reply 13 (keep-alive)
  msg_type 15 → VIDEO FRAME:
      base64 decode → JPEG bytes
      sample 1 frame per participant every 10 seconds
      cv2.imdecode → numpy array
      run_in_executor → _run_vision_on_frame() in ThreadPoolExecutor (non-blocking)
          analyze_frame() [vision.py]:
              mean brightness < 30 → camera_on = False, skip inference
              YOLOv8n(frame) → phone detected? (COCO class 67, conf >= 0.35)
              MediaPipe BlazeFace → face visible? (conf >= 0.50)
              returns VisionResult(camera_on, face_visible, phone_detected, phone_confidence)
          process_result() [vision_state.py]:
              Camera off → Redis timer → if continuous > 5 min → camera_off alert (medium)
              Face absent (camera on) → Redis timer → if continuous > 5 min → face_not_visible alert (medium)
              Phone detected → gap check (3 min between strikes):
                  strike 1 → phone_detected (low)
                  strike 2 → phone_detected (medium)
                  strike 3 → phone_detected (high)
```

### Step 5 — Participants Join / Leave
```
Zoom webhook: meeting.participant_joined
  → on_participant_joined() [attendance.py]
      → identify: teacher (by email) or student (by registrant_id)
      → calculate minutes_late since scheduled_start
      → resolve any open teacher_absent / student_absent alert
      → fire teacher_late or participant_late alert if late
      → insert attendance_records row (status: present / late)

Zoom webhook: meeting.participant_left
  → on_participant_left() [attendance.py]
      → calculate mins_before_end
      → if left > 6 min before end → early_departure alert (medium)
      → update attendance_records: leave_time, duration_mins, status
```

### Step 6 — Celery Absence Checks
```
check_teacher_absent (fires at scheduled_start + 8 min):
  → no attendance_record for teacher? → teacher_absent alert (high)

check_student_absents (fires at scheduled_start + 8 min):
  → each enrolled student with no attendance_record → student_absent alert (medium)

check_empty_class (fires at scheduled_start + 10 min):
  → zero open attendance_records → empty_class alert (high)

check_missed_classes (Celery Beat, every 15 min):
  → classes past scheduled_end still 'scheduled'/'live' → mark 'missed', delete Zoom meeting
```

### Step 7 — Meeting Ends
```
Zoom webhook: meeting.ended
  → on_meeting_ended() [schedule.py]
      → status = 'completed', actual_end + duration stored
      → safety net: fire student_absent for anyone who never joined (if class ran >= 8 min)
      → zoom_api.delete_meeting() → prevents host from restarting

Zoom webhook: meeting.rtms_stopped
  → _on_rtms_stopped() [zoom.py]
      → asyncio task cancelled → CancelledError in connect_rtms
      → finally block: deletes all rtms:{meeting_id}:* Redis keys
```

---

## Alert Types

| Alert | Severity | Trigger |
|---|---|---|
| `teacher_absent` | high | No teacher at start + 8 min |
| `empty_class` | high | No one in meeting at start + 10 min |
| `teacher_late` | medium | Teacher joined but was late |
| `student_absent` | medium | Student never joined |
| `early_departure` | medium | Left > 6 min before class end |
| `participant_late` | low | Joined after grace period |
| `camera_off` | medium | Camera continuously off for 5 min |
| `face_not_visible` | medium | Camera on but no face for 5 min |
| `phone_detected` | low/medium/high | Phone seen (escalates per strike) |

---

## Zoom RTMS — Key Details

- **data_opt: 3** = `VIDEO_SINGLE_ACTIVE_STREAM` — only the active speaker's video is streamed. This is a Zoom platform constraint, not a code choice.
- **Keep-alive**: Zoom sends `msg_type: 12` (JSON in binary frame). Must respond `msg_type: 13` on both channels. Client must also proactively send `msg_type: 12` every 20s or the stream times out (`stop_reason: 19`).
- **HMAC signature**: `HMAC-SHA256(key=client_secret, msg=client_id,meeting_uuid,stream_id)`
- **Frame format**: JPEG, base64-encoded inside the `content.data` field of `msg_type: 15`

---

## Testing Vision Models Offline

```bash
cd backend
python test_vision.py path/to/screenshot.jpg
python test_vision.py path/to/screenshot.jpg --phone-conf 0.25 --face-conf 0.50
```

Outputs annotated images to `Pic_output/` showing bounding boxes for phone and face detections.
