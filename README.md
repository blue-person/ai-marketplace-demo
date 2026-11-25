# AI Agent Marketplace

This project is a web platform where developers publish artificial intelligence (AI) agents and companies run them and pay for each use. It was built for the Software Security course, so its code is meant to be read, tested and audited by another group and later corrected by its own team.

## Current status

The base works, and it includes sign up with a profile and a referral code, sign in, the approval of accounts by an administrator or by a C++ robot that has an account of its own, the suspension and reactivation of accounts by an administrator, API keys sent by email, referral bonuses, credit transfers with a ledger, a catalog of agents that developers publish and administrators review, the execution of agents with a charge, a refund when the AI service fails, a history and a split of each payment between the developer and the platform, an audit log that an administrator reads in the panel, a searchable directory, an editable profile, test emails and a call to a simulated external AI service. Scheduled executions have not been built yet. This document describes only what exists today and will grow as each module is completed.

## Services

The application runs as seven services under Docker Compose, which are described in the following table.

| Service | Technology | What it does |
|---|---|---|
| `web` | nginx, Vue 3, Bootstrap 5 | Serves the interface and forwards the requests that start with `/api` to the backend |
| `backend` | Python 3.13, Flask, gunicorn | Applies the business rules and exposes the REST application programming interface (API) |
| `db` | MySQL 8.4 | Stores the data |
| `worker` | C++17, libcurl | Reads the pending registrations on a timer and approves the ones with a complete profile through the backend |
| `mailpit` | Mailpit | Receives every email the application sends and keeps it locally, so nothing reaches a real address |
| `mock-api` | Flask | Simulates the OpenRouter AI service, which avoids real keys and costs |
| `seed` | Same image as the backend | Runs once at startup to create the admin and the test accounts |

## Requirements

Docker Engine with Compose v2 (or Docker Desktop) and about 4 GB of free disk space are enough to run the project. On Linux, the Docker commands must start with `sudo` when the user does not belong to the `docker` group.

The Python parts are managed with [uv](https://docs.astral.sh/uv/). The `backend` and `mock-api` folders each have their own `pyproject.toml` and `uv.lock`, and the Docker images install exactly what the lock files list. Working on the code outside Docker, or building the delivery ZIP with `uv run scripts/package.py --group NAME`, needs only `uv`, because it downloads the right Python version by itself.

## Quick start

To start, copy the example settings and replace every `change-me` value with a secret of your own. The value of `WORKER_API_KEY` is the API key of the approval robot, and it needs at least 32 characters, for example `mk_` followed by the output of `openssl rand -hex 24`. The values `DB_USER` and `DB_PASSWORD` define the MySQL user that the application uses, which is created the first time the database starts. Then build and start the services.

```bash
cp .env.example .env
docker compose up --build
```

When the build ends, the application is available at `http://localhost:8080` and the captured emails at `http://localhost:8025`.

## Test accounts

The admin signs in with `admin@template.test` and the password stored in `ADMIN_PASSWORD`. The four test accounts share the password stored in `SEED_PASSWORD`. They are `dev1@marketplace.test` and `dev2@marketplace.test` for developers, and `company1@marketplace.test` and `company2@marketplace.test` for companies. The seed also creates the account of the approval robot, which cannot sign in, and two pending registrations. One has a complete profile and the robot approves it in its first cycle, and the other has no profile and waits for an administrator. The seed also creates the account of the platform, which receives its share of each execution and cannot sign in or be suspended, and three finished executions that show a paid run, a run that failed and was refunded and a free run of an agent by its own developer. The seed also creates five example agents, three approved, one pending and one rejected, so the catalog and the review tab of the panel have data from the start. A developer publishes from the page Agents, an administrator approves or rejects from the tab Agents of the panel, and every signed in person reads the approved agents in the catalog.

## Running an agent

A developer or a company can run an approved agent from the page Executions of the interface, or with the API key of the account. The request needs an `Idempotency-Key` header with a UUID, so a retry of the same request returns the saved result and does not charge a second time. The same key with another prompt answers 422, and the same key while the first request still runs answers 409. The price is charged first, the AI service is called afterwards, and the payment of 80 percent to the developer and 20 percent to the platform happens only when the answer arrives. When the service fails the price returns to the balance through a new entry of the ledger. A developer runs the own agents for free. The example below uses the key that `docker compose logs seed` prints for `company1@marketplace.test`.

```bash
curl -X POST http://localhost:8080/api/agents/1/executions \
  -H "Authorization: Bearer $API_KEY" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize this text in one line."}'
```

The prompt can have up to 2000 characters. The history is read with `GET /api/executions` and one execution with `GET /api/executions/<id>`. A developer reads the earnings of the own agents with `GET /api/agents/mine/executions`, and an administrator reads the amounts of all the executions with `GET /api/admin/executions`.

## Useful commands

Four commands cover most of the daily work.

```bash
docker compose logs -f backend                   # read the logs of one service
docker compose up --build                        # rebuild after changing code
docker compose down -v                           # delete all data to start clean
docker compose exec db mysql -u root -p app      # open a MySQL console
```

## Documentation

The structure of the code is explained in `docs/ARCHITECTURE.md`, the rules for changing it are in `docs/CONTRIBUTING.md`, the way tests are chosen and written is in `docs/TESTS.md` and the technical decisions with their sources are in `docs/DECISIONS.md`. The delivery sheet in `docs/ENTREGA.md` records the accounts, the status of each module and the known limits, while `docs/GUIA_AUDITOR.md` explains how the auditor group starts the application. These last two files are written in Spanish, as the course provides them.

## Common problems

If a port is already in use, change the number on the left of the matching `ports` entry in `docker-compose.yml`. A change in a `.sql` file appears only after `docker compose down -v`, because those scripts run when the database volume is first created. For the same reason, a change of `DB_USER` or `DB_PASSWORD` after the first start needs `docker compose down -v` as well. When the `seed` service fails, its log is available with `docker compose logs seed`.
