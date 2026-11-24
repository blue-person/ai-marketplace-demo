# Project template: Software Security

Common starting point for the course's two cases: **HealthSync** and **AI Agent Marketplace**. It provides the base infrastructure defined in Docker Compose (web, backend, database, C++ robot, test mail and external API simulator) and usage examples for each piece of the stack. The business modules of each case are built by the group.

- Assignment and starting point of each case: [`cases/healthsync`](cases/healthsync/README.md) and [`cases/marketplace`](cases/marketplace/README.md).
- If you are the **auditor group** and received another group's ZIP: read [`GUIA_AUDITOR.md`](GUIA_AUDITOR.md).

**All pieces of the stack must be kept in your project**: Vue frontend served by nginx, Flask backend, MySQL, C++ robot, mail and external API consumption. You may modify, replace or extend the examples, but not remove a piece.

## Architecture

```
Browser ──► localhost:8080 ── web (nginx + Vue SPA) ──/api──► backend (Flask + gunicorn)
                                                                │      │       │
                                                               db   mailpit  mock-api
                                                            (MySQL)  (mail)  (simulated external API)
                                                                ▲
                                             worker (C++ robot) ┘ via /api/internal
```

| Service | Technology | Purpose |
|---|---|---|
| `web` | nginx 1.30 + Vue 3 + Bootstrap 5 | Serves the SPA and proxies `/api` to the backend. |
| `backend` | Python 3.13, Flask 3.1, gunicorn | REST API with the business logic. |
| `seed` | (same image as the backend) | Runs once at startup and creates the administrator and the test accounts. |
| `db` | MySQL 8.4 LTS | Database. |
| `worker` | C++17 + libcurl | Periodic robot. Calls the backend's `/api/internal/*`. |
| `mailpit` | Mailpit | Captures every email the application sends. Nothing leaves for the Internet. |
| `mock-api` | Flask | Simulates OpenRouter (marketplace) and Open mHealth-style wearable data (HealthSync). It is not part of your application: it stands for a third-party service. |

## Included examples

| Piece | Example | Where |
|---|---|---|
| Database | Sign up, sign in, directory with search, profile view and edit | `backend/app/routes_auth.py`, `routes_general.py` |
| External API | Query to the simulator from the dashboard | `backend/app/routes_general.py`, `external_api.py` |
| Mail | Registration confirmation email | `backend/app/mail.py` |
| C++ | Robot that lists accounts pending approval | `worker/src/robot.cpp`, `backend/app/routes_internal.py` |
| Vue | Navigation, forms, directory, dashboard | `frontend/src/` |

## Requirements

- Docker Desktop (Windows or macOS) or Docker Engine with the Compose v2 plugin (Linux). On Linux, run the commands with `sudo` if your user is not in the `docker` group.
- About 4 GB of free disk space (base images and libraries are downloaded).
- Python 3 on the machine, only for the `package.py` script. If you do not have it, see "Without Python" at the end.

Images are built on each person's machine, so they should work on Intel/AMD and ARM (Apple Silicon) processors.

## Quick start

```bash
# 1. Create the .env file (choose your case by editing CASE and replace every secret)
cp .env.example .env

# 2. Build and start everything
docker compose up --build

# 3. Open
#    Application:  http://localhost:8080
#    Emails:       http://localhost:8025
```

The administrator account and the password of the test accounts are in `.env`. The emails of each case's test accounts are in `cases/<case>/README.md`.

Useful commands:

| To | Command |
|---|---|
| See a service's logs | `docker compose logs -f backend` |
| Rebuild after changing code | `docker compose up --build` |
| Delete the data and start from scratch | `docker compose down -v` and then `docker compose up --build` |
| Open a MySQL console | `docker compose exec db mysql -u root -p app` |

## Structure

```
.env.example            Environment variables
docker-compose.yml      Definition of every service
ENTREGA.md              Sheet the group fills in before delivering (in Spanish)
GUIA_AUDITOR.md         Instructions for the group that receives the ZIP (in Spanish)
backend/app/
  __init__.py           App factory and error handling
  config.py             Configuration from environment variables
  db.py                 Database access functions
  security.py           login_required, role_required, current_user
  routes_auth.py        Sign up, sign in, sign out
  routes_general.py     Health, config, directory, profile, external API
  routes_internal.py    Endpoints for the robot
  mail.py               Email sending (to Mailpit)
  external_api.py       HTTP client
  seed.py               Seed data
cases/<case>/           case.json (roles, test accounts, API), ENUNCIADO.md (in Spanish), README.md
database/init/          SQL scripts run when the database is created
frontend/               Vue 3 SPA + nginx configuration
worker/                 C++ robot
mock-api/               External API simulator
scripts/                package.py
```

## How to extend the template

**New tables.** Create `database/init/02-modules.sql` (scripts run in alphabetical order). These scripts only run when the database volume is created, so after changing them run `docker compose down -v`.

**New endpoints.** Create a file `backend/app/routes_<module>.py` with a `Blueprint` and register it in `__init__.py`.

**Robots.** Add endpoints in `routes_internal.py` and call them from `run_cycle()` in `worker/src/robot.cpp`. If you need robots with different intervals (every minute and every second), duplicate the `worker` service in `docker-compose.yml` with another `WORKER_INTERVAL_SECONDS`.

**Views.** Add components in `frontend/src/views/` and routes in `frontend/src/router/index.js`. To develop the frontend with hot reload, start the rest with Docker and run `npm install` and `npm run dev` inside `frontend/` (opens at `http://127.0.0.1:5173`).

**Seed data.** Add in `backend/app/seed.py` the data the auditor group needs to test your modules: balances, agents, metrics, appointments.

## Delivery (phase 1)

1. Fill in `ENTREGA.md`.
2. Check that the application starts from scratch: `docker compose down -v && docker compose up --build`.
3. Build the ZIP: `python scripts/package.py --group group03`.
4. Upload the ZIP (`deliveries/*.zip`) to the platform and register the SHA-256 fingerprint the script prints.

The script excludes `.env`, `node_modules`, `dist`, `.git`, `.sandbox`, compiled files, PDFs, `TA.txt` and `CLAUDE.md`.

## Common problems

- **Port 8080, 8025 or 3306 is in use.** Change the left-hand port in the service's `ports` section of `docker-compose.yml`.
- **I changed a `.sql` file and it is not reflected.** The scripts in `database/init` only run when the volume is created: `docker compose down -v`.
- **The `seed` service fails.** Check `docker compose logs seed`.

## Without Python

You can use Docker's Python. On Linux, macOS or PowerShell, from the project root:

```bash
docker run --rm -v "${PWD}:/p" -w /p python:3.13-slim python scripts/package.py --group group03
```
