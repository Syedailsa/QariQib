# QaraQib — Frontend

Admin dashboard for the QaraQib Quran academy class monitoring system. Displays live class status, attendance records, and alerts. Connects to the FastAPI backend via REST.

---

## Tech Stack

| Library | Purpose |
|---|---|
| `next` 16.x | React framework (App Router) |
| `react` 19.x | UI |
| `@tanstack/react-query` 5.x | Server state — fetching, caching, auto-refresh |
| `axios` 1.x | HTTP client (configured in `lib/api.ts`) |
| `date-fns` 4.x | Date formatting |
| `typescript` 5.x | Type safety |
| `tailwindcss` 4.x | Installed but not used — all styling is inline |

---

## File Structure

```
frontend/
├── app/
│   ├── layout.tsx                       # Root layout — wraps with <Providers>
│   ├── page.tsx                         # Redirects / → /dashboard
│   ├── providers.tsx                    # React Query client (30s stale, 30s refetch)
│   └── dashboard/
│       ├── layout.tsx                   # Sidebar nav (Overview, Schedules, Teachers, Students, Alerts)
│       ├── error.tsx                    # Error boundary — catches crashes, shows clean UI instead of red screen
│       ├── page.tsx                     # Today's overview: stats + today's classes + active alerts
│       ├── alerts/
│       │   └── page.tsx                 # All alerts — toggle active/resolved, resolve button, 15s refresh
│       ├── teachers/
│       │   └── page.tsx                 # Teacher list + add teacher + consent toggle
│       ├── students/
│       │   └── page.tsx                 # Student list + add student
│       └── schedules/
│           ├── page.tsx                 # All schedules grouped by date, delete with confirm modal
│           ├── new/
│           │   └── page.tsx             # Create class form (teacher + students + time)
│           └── [id]/
│               ├── page.tsx             # Class detail: attendance, enrolled students, alerts
│               └── edit/
│                   └── page.tsx         # Edit scheduled class time/duration
│
└── lib/
    ├── api.ts                           # All API calls (axios wrappers for every endpoint)
    └── time.ts                          # formatTime(), formatDateTime(), formatDateHeader() — null-safe
```

---

## Error Handling Rules

Every page follows the same pattern to avoid crashes and blank screens:

1. **Error boundary** — `app/dashboard/error.tsx` catches any unhandled React error anywhere in the dashboard. Instead of the Next.js red screen, the admin sees "Something went wrong" with a "Try Again" button. Live classes are completely unaffected (server-side, no dependency on the UI).

2. **`isError` on every query** — All `useQuery` calls expose `isError`. If the backend is down or returns 5xx, the page shows a readable message ("Failed to load schedules. Check your backend connection.") instead of silently showing empty lists.

3. **Null-safe data access** — Alert objects from the API can have either `teachers` or `students` populated, never both. All access uses optional chaining: `a.students?.full_name ?? 'Unknown'` to prevent crashes if a related record was deleted.

4. **`isLoading` vs `isError` vs empty** — Every list section has three distinct states: loading spinner, error message, and empty-state message. The admin always knows which state they're in.

5. **Mutation errors** — All mutations (`useMutation`) have `onError` handlers that surface the backend's `detail` message to the user (e.g., "Teacher has not given consent", "Failed to delete").

---

## Page-by-Page Flow

### `/dashboard` — Today's Overview
- 4 stat cards: Total Classes Today, Live Now, Completed, Unresolved Alerts
- Left panel: today's classes list with status badges, click to go to detail
- Right panel: first 8 active alerts with severity color coding
- Backend: `GET /api/v1/schedules/today` + `GET /api/v1/alerts`
- Shows error message per panel if either request fails

### `/dashboard/schedules` — All Schedules
- All classes grouped by date, sorted newest first
- Card color: yellow (scheduled), green (live/completed), red (missed)
- Alert count badge (🔔 N alerts) shows unresolved alerts per class — pulled from the list API
- Actual duration diff shown on completed classes (red if short, green if over)
- Edit (✏️) and Delete (🗑️) buttons only appear on `scheduled` classes — live/completed classes cannot be accidentally deleted from the UI
- Delete shows a confirmation modal; on failure the modal stays open with an inline error message
- Auto-refreshes every 30 seconds

### `/dashboard/schedules/new` — Create Class
- Left column: radio select teacher (warns if consent not given), datetime pickers, auto-calculated duration display
- Right column: checkbox select students (multiple allowed)
- **Duration is auto-calculated** from start/end times — no manual input. Shown as a read-only field that updates live
- **Minimum 15 minutes enforced** — if the window is under 15 mins the duration field turns red with an inline "⚠ Minimum 15 mins" warning and submission is blocked
- Client-side validation: teacher required, at least one student required, both times required, end > start, duration ≥ 15 mins
- On submit: local datetime converted to ISO UTC string → `POST /api/v1/schedules`
- On success: redirects to the new class detail page

### `/dashboard/schedules/[id]` — Class Detail
- Header: teacher name, status badge, scheduled vs actual duration with diff
- Attendance panel: join/leave times and status (present / late / early_departure) per participant
- Students panel: enrolled students with Zoom join links (links hidden once class is missed or completed)
- Alerts panel: all alerts for this class, resolve button on unresolved ones
- **Polling**: auto-refreshes every 15 seconds **only when status is `live` or `scheduled`** — stops polling once the class is `completed` or `missed` to avoid unnecessary API calls

### `/dashboard/schedules/[id]/edit` — Edit Class
- Pre-filled with current start/end times (converted from UTC to local datetime-local format)
- Duration is auto-calculated from the times — same rule as create: minimum 15 mins enforced with inline warning
- Only available for `scheduled` classes — shows a clear message and Go Back button if the class is live/completed/missed
- On save: validates duration ≥ 15 mins, then `PATCH /api/v1/schedules/:id` → backend revokes old Celery tasks and re-queues at new time, updates Zoom meeting

### `/dashboard/alerts` — All Alerts
- Toggle between active and resolved alerts
- Each alert shows: type, severity badge, person badge (teacher/student), notes, trigger time, link to class detail
- Resolve button → `POST /api/v1/alerts/:id/resolve`
- Auto-refreshes every 15 seconds

### `/dashboard/teachers` — Teachers
- List all active teachers with consent status
- Add teacher form: name, email, phone, Zoom User ID (Zoom User ID should be the teacher's Zoom email address)
- Consent toggle per teacher — teacher must have `consent_given = true` before classes can be scheduled for them

### `/dashboard/students` — Students
- List all active students
- Add student form: name, email, parent name, parent email, parent phone

---

## State Management

All server state goes through **React Query**:

| Query key | Refetch interval | Reason |
|---|---|---|
| `['today-schedules']` | 30s (global default) | Overview page |
| `['schedules']` | 30s | Schedule list |
| `['alerts', showResolved]` | 15s | Alerts page |
| `['schedule', id]` | 15s when live/scheduled, off otherwise | Class detail — stops when done |

Mutations (`useMutation`) invalidate relevant query keys on success so the UI updates immediately without a full page reload.

---

## API Client (`lib/api.ts`)

Single axios instance pointing to `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

Exports one function per backend operation:
- `getTeachers`, `createTeacher`, `updateConsent`
- `getStudents`, `createStudent`
- `getSchedules`, `getTodaySchedules`, `getSchedule`, `createSchedule`, `updateSchedule`, `deleteSchedule`
- `getAlerts`, `resolveAlert`

---

## `lib/time.ts` — Null-Safe Formatters

All three functions accept `string | null | undefined` and return `'—'` for missing values instead of crashing:

- `formatTime(utcString)` — `02:55 PM`
- `formatDateTime(utcString)` — `May 21, 2026, 02:55 PM`
- `formatDateHeader(utcString)` — `Thursday, May 21, 2026`

---

## Environment Variables (`.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Running Locally

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The FastAPI backend must be running on port 8000 first.
