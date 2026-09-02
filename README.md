# College Event Resource Allocation System (CERAS)   

A Flask + SQLAlchemy + SQLite web portal for campus event and resource management featuring **Role-Based Access Control (RBAC)** across 2 dedicated roles, **Session-Based Authentication (Login & Student Signup)**, **Interactive 7-Day Visual Booking Schedule Calendar**, and an **All-or-Nothing Resource Allocation Engine** with   conflict detection and alternative suggestions.

---

## 🛡️ Role-Based Access Control (2 Dedicated Roles)

### 1. Administrator (`admin`)
- **Reviews Pending Resource Requests**: Full approval and rejection decision controls with custom feedback reasons and single-allocation cancellation.
- **Manages Campus Facilities Equipment**: Add, edit, activate, and deactivate college facilities, laboratories, and AV equipment.
- **Manages Registered User Accounts & Roles**: Accesses the Admin User Management panel to promote/demote users (`admin` $\leftrightarrow$ `student_organiser`) and toggle account active status.

### 2. Student Organiser (`student_organiser`)
- **Creates & Manages Campus Events**: Create, edit, and manage department/club events.
- **Submits Multi-Item Resource Allocation Requests**: Bundle multi-item hardware & room requests (e.g. 1x Auditorium + 2x Microphones + 1x 4K Projector) with all-or-nothing allocation guarantees.
- **7-Day Visual Booking Schedule Calendar**: Explores confirmed daily time slots and checks resource availability in real-time.

---

## 🔑 Default Seed Credentials for Quick Testing

| Role | Email | Password | Assigned Name / Department |
| :--- | :--- | :--- | :--- |
| **🛡️ Administrator** | `admin@college.edu` | `admin123` | Dr. Eleanor Vance (Campus Administration) |
| **   Student Organiser** | `alex.cs@college.edu` | `student123` | Alex Rivera (Computer Science Society) |
| **   Student Organiser** | `sarah.arts@college.edu` | `student123` | Sarah Chen (Fine Arts & Cultural Club) |

> *Tip: The login page includes 1-click Quick Demo buttons for instant evaluation.*

---

## Tech Stack

Python 3.10+, Flask, Flask-SQLAlchemy, Werkzeug, SQLite, Jinja2, Tailwind CSS, vanilla JS, Inter & Outfit Google Fonts.

## Project Structure

```
college-resource-system/
├── app/
│   ├── __init__.py          # App factory, blueprints & context processors
│   ├── extensions.py        # SQLAlchemy db instance
│   ├── models.py            # User, Event, Resource, ResourceRequest, Allocation
│   ├── utils.py             # Auth decorators (@login_required, @admin_required) & helpers
│   ├── routes/
│   │   ├── auth.py          # Login, Student Signup, Logout & Demo Logins
│   │   ├── admin_users.py   # Admin User & Role management
│   │   ├── calendar.py      # 7-Day Visual Booking Schedule Matrix
│   │   ├── dashboard.py     # Role-aware dashboard (Admin & Student views)
│   │   ├── events.py        # Create/edit/cancel/filter events with user ownership
│   │   ├── resources.py     # Facilities management (Admin RBAC restricted)
│   │   └── requests.py      # Multi-item requests, Admin approval/rejection, Live availability
│   ├── services/
│   │   └── booking_service.py   # Conflict detection, suitability, alternatives, all-or-nothing allocation
│   └── templates/           # Jinja2 templates with modern university portal theme
├── config.py
├── run.py                   # Entry point
├── seed.py                  # Seeds users, resources, events & allocations
├── requirements.txt
├── .env.example
└── .gitignore
```

## 1. Installation & Running

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env

# 3. Initialize & Seed database with demo accounts and data
python seed.py

# 4. Run the development server
python run.py
```

The app is served at **http://localhost:5000**.


## 2. Database Setup

This project uses SQLite with Flask-SQLAlchemy's `db.create_all()`, invoked
automatically:
- Every time the app starts (`create_app()` calls `db.create_all()` inside
  an app context), and
- Explicitly via `python init_db.py` or `python seed.py`.

This means **no separate migration step is required to get started** — the
schema is created directly from the models in `app/models.py`. The database
file is `app.db` in the project root (path configurable via `DATABASE_URL`
in `.env`).

If you extend the schema later, we recommend adding
[Flask-Migrate](https://flask-migrate.readthedocs.io/) (Alembic) for proper
versioned migrations — the model layer is already structured to support that
with just `flask db init/migrate/upgrade`.

`seed.py` additionally inserts sample resources (auditoriums, labs,
projectors, microphones, a camera, and one deliberately inactive resource)
plus one demo event, so you can exercise every feature immediately.

## 3. How Conflict Detection Works

Every confirmed resource assignment is stored as a row in the `allocations`
table (`resource_id`, `event_id`, `start_time`, `end_time`, `status`).

Before any resource is assigned, `booking_service.is_resource_available()`
checks for existing **active** (`status == "Allocated"`) allocations of that
same resource whose time window overlaps the requested window, using the
standard interval-overlap test:

```
existing.start_time < new.end_time  AND  new.start_time < existing.end_time
```

This correctly:
- **Rejects** overlapping bookings (e.g. existing 10am–2pm vs. new 12pm–4pm).
- **Allows** back-to-back bookings (existing 10am–2pm, new 2pm–4pm) because
  the intervals don't actually overlap.
- Ignores allocations that have been cancelled, so cancelling a booking
  immediately frees that resource for other requests.

This check runs entirely on the backend inside `find_suitable_candidates()`
and `process_resource_request()` — it cannot be bypassed from the UI.

## 4. How Alternative Resources Are Selected

When a request item can't be satisfied by its preferred resource (or by any
match at all), `suggest_alternatives()` searches for other resources that
are simultaneously:

1. **The same resource type** (a microphone is never offered as an
   alternative to a projector).
2. **Active** (`is_active == True`).
3. **Capacity-sufficient**, if a minimum capacity was specified (or was
   auto-derived from the event's expected attendance for
   Auditorium/Laboratory requests).
4. **Free at the requested time window** (same overlap check as above).

Matching candidates are sorted by capacity ascending (best-fit first) so a
200-person event isn't handed a 500-seat auditorium when a closer-fitting
200-seat hall is free, then the top matches are returned as suggestions.
This is the same underlying function used both to fully satisfy a request
automatically and to generate "here's what else is available" suggestions
when a request can't be filled — so the suggestions the admin/organizer sees
are always resources that genuinely would have worked.

## 5. Approval & Allocation Workflow

- **Resources** are booked at the *type* level (e.g. "1x Auditorium, 1x
  Projector, 2x Microphone") rather than requiring the organizer to know
  exact inventory. Optionally, an organizer can name a **preferred specific
  resource** per line item (e.g. "Hall A" specifically); if that resource is
  unavailable or unsuitable, the system automatically tries other resources
  of the same type instead.
- On **Approve**, `process_resource_request()`:
  1. Builds an in-memory allocation *plan* for every item (no DB writes yet).
  2. If **any** item cannot be fully satisfied, the whole plan is discarded,
     the request is marked `Rejected` with a reason (including any partial
     alternative suggestions found), and **zero** allocations are written.
     This satisfies the "all-or-nothing" requirement: if Auditorium and
     Projector are available but Microphone is not, none of the three get
     allocated.
  3. If every item can be satisfied, all `Allocation` rows are created and
     committed together inside a single SQLAlchemy transaction
     (`db.session.commit()` at the end; `db.session.rollback()` on any
     unexpected exception), so a crash mid-write can never leave a partial
     allocation behind.
- **Cancelling** a request (or an individual allocation, or the parent
  event) flips the relevant `Allocation.status` to `Cancelled`, which
  immediately excludes it from future conflict checks — releasing the
  resource.

Status flow: `Pending → Approved (Allocated)` or `Pending → Rejected`, with
`Cancelled` reachable from either `Pending` or `Approved`.

## 6. Validation & Error Handling

- All forms validate on the backend (never trust client-side only): required
  fields, non-negative attendance, valid date/time parsing, start < end,
  capacity required for Auditorium/Laboratory resources, valid
  status/type/resource selections.
- Validation failures re-render the form with the entered values preserved
  and clear flash-message errors — no exceptions bubble up to the user.
- A global Flask error handler catches any unhandled exception, rolls back
  the DB session, logs the real error server-side, and shows a generic
  friendly error page — **Python tracebacks are never shown to users**
  (this holds even with `FLASK_DEBUG=0`, which is the default).
- Inactive resources are filtered out at the query level everywhere
  (`Resource.is_active == True`), so they can never be selected for
  allocation, only reactivated by an admin.

## 7. Important Assumptions

- **Single-admin model**: there's no login/auth system in this assignment
  build — anyone using the app can act as organizer or approver. Adding
  Flask-Login with role-based access (organizer vs. admin) would be the
  natural next step for production use.
- **Resource requests are type + quantity based** (e.g. "2x Microphone")
  rather than requiring the organizer to hand-pick every individual unit,
  matching the assignment's own example ("Auditorium, Projector, 2
  Microphones"). A specific preferred resource can optionally be named per
  line item.
- **Capacity requirement for halls** defaults to the event's expected
  attendance when the organizer doesn't specify a minimum capacity
  explicitly, since that's the natural real-world rule ("hall must fit the
  crowd").
- **Capacity is only meaningful for Auditorium/Laboratory** types in this
  build; Projector/Microphone/Camera/Computer resources are tracked
  individually (e.g. "Microphone 1", "Microphone 2") rather than by a
  numeric capacity.
- Timestamps are stored naively (no timezone) for simplicity, consistent
  across the whole app — fine for a single-college deployment; a
  multi-timezone deployment would want timezone-aware datetimes.
- `db.create_all()` is used instead of a formal migration tool to keep setup
  to a single command for evaluation purposes; see the migrations note in
  the Database Setup section above.

## 8. Manual Test Checklist (already verified during development)

- Overlapping booking on the same resource is rejected; back-to-back
  bookings (end time == next start time) are allowed.
- A hall with capacity < event attendance is correctly excluded and an
  alternative of adequate capacity is suggested if one exists.
- Requesting a Projector where only Microphones are active correctly
  fails ("wrong type" is never treated as a valid alternative).
- A multi-item request where one item can't be satisfied results in
  zero allocations for the entire request (all-or-nothing), and the
  request is auto-rejected with a reason.
- Cancelling an approved request (or a single allocation, or the parent
  event) releases the resource(s) so they immediately become available
  again for other requests.
- Deactivated resources are excluded from search results and cannot be
  allocated until reactivated.
