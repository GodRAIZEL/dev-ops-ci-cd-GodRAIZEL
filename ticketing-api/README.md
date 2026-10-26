# Event Ticketing & Seat Reservation API

Ticket **HS-2026-0872** · Halcyon Systems · Django 5 + Django REST Framework + PostgreSQL

A containerised backend microservice for venues, events, seats and bookings, with JWT
authentication, role-based permissions, a standardised JSON error schema, OpenAPI docs,
a `/health/` probe and a GitHub Actions pipeline (lint → test → Docker build).

## Quick start (docker-compose)

```bash
cp .env.example .env        # optional; sensible dev defaults exist
docker-compose up --build   # or: docker compose up --build
```

The `web` container waits for PostgreSQL to be healthy, applies migrations, then serves on
<http://localhost:8000>.

| URL | Purpose |
|---|---|
| `/health/` | database connectivity, uptime, service status (200 / 503) |
| `/api/docs/` | Swagger UI (`/api/redoc/` for ReDoc, `/api/schema/` for raw OpenAPI) |
| `/admin/` | Django admin |

Create an admin (API admins have `role = admin`; superusers also count as admins):

```bash
docker-compose exec web python manage.py createsuperuser
```

### Local run without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate          # SQLite unless POSTGRES_DB is set
python manage.py runserver
```

## Domain model

```
User (role: admin|user) ──< Booking >──< Seat >── Event >── Venue
                                │                    └──<>── Tag   (many-to-many)
                                └── Event
```

* **Venue** – name, city, capacity (unique per name+city)
* **Event** – venue FK, start time, base price, status (`draft|published|cancelled`), M2M **Tag**
* **Seat** – event FK, section/row/number (unique per event), price, status (`available|booked`)
* **Booking** – user FK, event FK, **M2M seats**, status (`pending|confirmed|cancelled`), total

Business rules: only published, future events can be booked; max 10 seats per booking;
seats are locked with `SELECT ... FOR UPDATE` inside a transaction so two users can never
book the same seat; cancelling (or an admin deleting) a booking releases its seats;
seat blocks cannot exceed venue capacity.

## Roles & permissions

| Resource | Standard user | Admin |
|---|---|---|
| Venues, tags, events, seats | read | full CRUD (+ `POST /events/{id}/generate-seats/`) |
| Draft events | hidden | visible |
| Bookings | create, list/retrieve **own**, cancel own | everything; `PATCH` status; delete |

## Error schema

Every error (validation, auth, 404, 409, 405, unexpected 500, even unknown URLs) is:

```json
{"error": {"code": "validation_error", "message": "Request validation failed.",
           "status": 400, "details": {"capacity": ["Ensure this value is greater than or equal to 1."]}}}
```

Codes: `validation_error`, `unauthorized`, `permission_denied`, `not_found`,
`method_not_allowed`, `conflict` (taken seats, invalid status transition, deleting
referenced records), `server_error`. `details` appears only for validation errors.

## cURL walkthrough

```bash
BASE=http://localhost:8000

# 1. register + log in
curl -s -X POST $BASE/api/auth/register/ -H 'Content-Type: application/json' \
  -d '{"username":"alice","email":"alice@example.com","password":"Str0ng-Passw0rd!x"}'
TOKEN=$(curl -s -X POST $BASE/api/auth/token/ -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"Str0ng-Passw0rd!x"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access"])')
AUTH="Authorization: Bearer $TOKEN"

# 2. health (no auth)
curl -s $BASE/health/

# 3. as an ADMIN token: create venue, event, seats
curl -s -X POST $BASE/api/venues/ -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"name":"Grand Hall","city":"Johannesburg","capacity":200}'
curl -s -X POST $BASE/api/events/ -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"venue":1,"title":"Jazz Night","starts_at":"2030-01-15T19:00:00Z","base_price":"150.00"}'
curl -s -X POST $BASE/api/events/1/generate-seats/ -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"section":"A","rows":3,"seats_per_row":10}'

# 4. as any user: browse and book
curl -s "$BASE/api/events/?starts_after=2029-01-01T00:00:00Z&ordering=starts_at" -H "$AUTH"
curl -s "$BASE/api/seats/?event=1&status=available" -H "$AUTH"
curl -s -X POST $BASE/api/bookings/ -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"event":1,"seat_ids":[1,2]}'
curl -s -X POST $BASE/api/bookings/1/cancel/ -H "$AUTH"

# 5. admin: confirm a booking
curl -s -X PATCH $BASE/api/bookings/1/ -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"status":"confirmed"}'
```

## Database index reasoning

Indexes are tied to the queries the API actually runs:

| Index | Serves | Why |
|---|---|---|
| `Event(starts_at)` | default listing order, `starts_after/before` range filters | range scans + ordered pagination without a sort |
| `Event(venue, starts_at)` | "events at venue X, soonest first" | equality column first, range/sort column second |
| `Event(status, starts_at)` | listing published events (members always exclude drafts) | low-cardinality status first, then date order |
| `Seat(event, status)` | `seats?event=&status=available`, `seats_available` count | the hottest path: "what is still free for this event?" |
| `Seat UNIQUE(event, section, row, number)` | integrity + lookups by exact seat | prevents duplicate seats at the DB level; its index also covers `event`-only lookups |
| `Booking(user, status)` | "my bookings", filtered by status | every non-admin booking list is scoped by user |
| `Booking(event, status)` | admin views of an event's bookings, delete-protection checks | |
| `Booking.reference` (unique) | public lookup by UUID, no guessable ids | |
| `Venue.city`, `User.role` | city filtering; role checks | cheap single-column indexes on filter columns |
| `Venue UNIQUE(name, city)`, `Tag.name` unique | integrity | |

Composite indexes put equality columns before range/sort columns. I deliberately did **not**
index `Seat.price`, `Event.description` or other rarely filtered columns: every extra index
slows the write-heavy seat/booking paths.

## Testing & CI

```bash
pip install -r requirements-dev.txt
pytest                      # fails below 90% coverage (see pytest.ini)
flake8 .
```

`.github/workflows/ci.yml` runs on every push/PR: **lint** (flake8) → **test** (pytest against a
temporary PostgreSQL service container, `--cov-fail-under=90`) → **build** the Docker image.
On `main`, if `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` secrets are set, the image is also pushed.

## Submission checklist

- [ ] GitHub repo link: https://github.com/GodRAIZEL/dev-ops-ci-cd-GodRAIZEL
- [ ] Swagger: `http://localhost:8000/api/docs/`
