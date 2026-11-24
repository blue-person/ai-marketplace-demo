# AI Agent Marketplace

This project is a web platform where developers publish artificial intelligence (AI) agents and companies run them and pay for each use. It was built for the Software Security course, so its code is meant to be read, tested and audited by another group and later corrected by its own team.

## Current status

The starter base works, and it includes sign up, sign in, a searchable directory, an editable profile, test emails, a call to a simulated external AI service and a C++ robot that runs on a timer. The business modules, namely the admin approval panel, the agent catalog, agent execution, scheduled executions and credit transfers, have not been built yet. This document describes only what exists today and will grow as each module is completed.

## Services

The application runs as seven services under Docker Compose, which are described in the following table.

| Service | Technology | What it does |
|---|---|---|
| `web` | nginx, Vue 3, Bootstrap 5 | Serves the interface and forwards the requests that start with `/api` to the backend |
| `backend` | Python 3.13, Flask, gunicorn | Applies the business rules and exposes the REST application programming interface (API) |
| `db` | MySQL 8.4 | Stores the data |
| `worker` | C++17, libcurl | Calls the backend on a timer |
| `mailpit` | Mailpit | Receives every email the application sends and keeps it locally, so nothing reaches a real address |
| `mock-api` | Flask | Simulates the OpenRouter AI service, which avoids real keys and costs |
| `seed` | Same image as the backend | Runs once at startup to create the admin and the test accounts |

## Requirements

Docker Engine with Compose v2 (or Docker Desktop) and about 4 GB of free disk space are enough to run the project. On Linux, the Docker commands must start with `sudo` when the user does not belong to the `docker` group.

The Python parts are managed with [uv](https://docs.astral.sh/uv/). The `backend` and `mock-api` folders each have their own `pyproject.toml` and `uv.lock`, and the Docker images install exactly what the lock files list. Working on the code outside Docker, or building the delivery ZIP with `uv run scripts/package.py --group NAME`, needs only `uv`, because it downloads the right Python version by itself.

## Quick start

To start, copy the example settings and replace every `change-me` value with a secret of your own. Then build and start the services.

```bash
cp .env.example .env
docker compose up --build
```

When the build ends, the application is available at `http://localhost:8080` and the captured emails at `http://localhost:8025`.

## Test accounts

The admin signs in with `admin@template.test` and the password stored in `ADMIN_PASSWORD`. The four test accounts share the password stored in `SEED_PASSWORD`. They are `dev1@marketplace.test` and `dev2@marketplace.test` for developers, and `company1@marketplace.test` and `company2@marketplace.test` for companies.

## Useful commands

Four commands cover most of the daily work.

```bash
docker compose logs -f backend                   # read the logs of one service
docker compose up --build                        # rebuild after changing code
docker compose down -v                           # delete all data to start clean
docker compose exec db mysql -u root -p app      # open a MySQL console
```

## Documentation

The structure of the code is explained in `docs/ARCHITECTURE.md`, the rules for changing it are in `docs/CONTRIBUTING.md` and the technical decisions with their sources are in `docs/DECISIONS.md`. The delivery sheet in `docs/ENTREGA.md` records the accounts, the status of each module and the known limits, while `docs/GUIA_AUDITOR.md` explains how the auditor group starts the application. These last two files are written in Spanish, as the course provides them.

## Common problems

If a port is already in use, change the number on the left of the matching `ports` entry in `docker-compose.yml`. A change in a `.sql` file appears only after `docker compose down -v`, because those scripts run when the database volume is first created. When the `seed` service fails, its log is available with `docker compose logs seed`.
