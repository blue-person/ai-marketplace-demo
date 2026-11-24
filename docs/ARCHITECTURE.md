# Architecture

This document describes how the parts of the system are connected and which part handles each task. It covers the structure that exists today and the credit transfers, so the other modules still to be built are not included. The list of services and the way to start them are in the README.

## Request flow

The browser sends every request to `web`, where nginx returns the Vue application and forwards the requests whose path begins with `/api` to the Flask backend. The backend applies the business rules, sends emails to Mailpit and calls `mock-api` whenever it needs the AI service.

```
browser -> web (nginx) -> backend (Flask) -> db (MySQL)
                                          -> mailpit (email)
                                          -> mock-api (AI service)
worker (C++) -> backend /api/internal
```

Two parts connect to the database. The backend does it for every request, and the `seed` script does it directly at startup, before the backend begins to answer. The browser also reaches Mailpit on port 8025, and Docker publishes the MySQL port 3306 on the host, so the database is reachable from outside the internal network. That mapping comes from the template and is still to be reviewed.

## The robot

The C++ worker does not connect to the database. It calls the paths under `/api/internal` on a timer and identifies itself with a shared token in the `X-Internal-Token` header, so every decision stays in the Python code and the robot acts only on the answers it receives. Today it requests the accounts pending approval and writes them to its log, and the interval is set by `WORKER_INTERVAL_SECONDS`.

## Backend

Each area of the API is a Flask blueprint registered in `backend/app/__init__.py`, and its file is named `routes_<area>.py`. The shared helpers are `config.py`, which reads the environment and `cases/marketplace/case.json`, and `db.py`, which opens one database connection for each request and provides the transactions. They also include `passwords.py`, which hashes and checks passwords and is the only file that knows the hashing library, `security.py`, which provides the `login_required` and `role_required` decorators, `mail.py` for email and `external_api.py` for the AI service. Finally, `seed.py` creates the admin and the test accounts.

## Data

The table `accounts` stores the name, email, password hash, role, status and balance of each user. The status can be `pending`, `active`, `rejected` or `suspended`. At registration it is set to `pending` when the role requires approval in `case.json` and to `active` otherwise. No code changes it afterwards, because the admin panel that will do so has not been built. The tables `transfers` and `ledger_entries` hold the credit transfers and the append-only list of every balance change. New tables go in numbered files in `database/init`, and those files run only when the database volume is created.

Every write goes through `transaction()` in `db.py`, which commits at the end of the block and rolls back on any error. A function that can meet a deadlock is wrapped with `retry_on_deadlock`. The reasons are in the decision "Transaction helper, retries and credit transfers" of `DECISIONS.md`.

## Frontend

The Vue application is in `frontend/src`. Each page is a file in `views`, the routes are defined in `router/index.js` and `api.js` wraps the calls to the backend. The signed in user is kept in the browser by `session.js`.

This description matches the code today and has to be revised whenever a module is added.
