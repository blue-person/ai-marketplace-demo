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

The C++ worker does not connect to the database. On a timer it asks the backend for the pending registrations, decides which ones have a complete profile and asks the backend to approve each one. The profile is complete when the organization and the country are present. The robot has an account with the role `bot` and signs in with the API key of that account, which is sent in the `Authorization` header. The key is read from `WORKER_API_KEY`, and the seed stores only its hash. The backend applies the permission policy to every call, so the robot can list the pending registrations and approve the ones with a complete profile, and every other action gets a 403. The approvals are saved with the id of the robot in `reviewed_by`. An administrator can suspend the account of the robot from the panel, and from then on the backend answers 401 to its key. The interval is set by `WORKER_INTERVAL_SECONDS`. The log lines carry one of the levels `DEBUG`, `INFO`, `WARN` or `ERROR`, and `LOG_LEVEL` sets the lowest one that is written, with `INFO` by default. Warnings and errors go to the error output.

## Backend

Each area of the API is a Flask blueprint registered in `backend/app/__init__.py`, and its file is named `routes_<area>.py`. The shared helpers are `config.py`, which reads the environment and `cases/marketplace/case.json`, and `db.py`, which opens one database connection for each request and provides the transactions. They also include `passwords.py`, which hashes and checks passwords and is the only file that knows the hashing library, `security.py`, which reads the signed in account from the database on each request, checks API keys and provides the `login_required` and `api_key_required` decorators, `rbac.py`, which holds the permission policy and is the only file that knows the authorization library, `mail.py` for email and `external_api.py` for the AI service. The registration module adds `registration.py`, which holds the approval, the rejection, the referral bonus and the profile check, `api_keys.py`, which creates and hashes the keys, `email_address.py` and `countries.py`, which are the only files that know the validation libraries, `accounts.py`, which lists the accounts, suspends or reactivates them and keeps at least one active administrator, and `routes_admin.py` for the administrator panel. The routes under `/api/internal` in `routes_internal.py` are only for the robots, and nginx answers 404 to them from outside. Finally, `seed.py` creates the admin, the test accounts and two pending registrations, and prints the API key of each active account.

## Data

The table `accounts` stores the name, email, password hash, role, status and balance of each user. The status can be `pending`, `active`, `rejected` or `suspended`. At registration it is set to `pending` when the role requires approval in `case.json` and to `active` otherwise. The admin panel and the robot change it afterwards through `registration.py`, which also saves who reviewed the account and creates its referral code and its API key. An administrator can also move an account between `active` and `suspended`, and each change is added to the table `account_status_changes`. The tables `transfers` and `ledger_entries` hold the credit transfers and the append-only list of every balance change. New tables go in numbered files in `database/init`, and those files run only when the database volume is created.

Every write goes through `transaction()` in `db.py`, which commits at the end of the block and rolls back on any error. A function that can meet a deadlock is wrapped with `retry_on_deadlock`. The reasons are in the decision "Transaction helper, retries and credit transfers" of `DECISIONS.md`.

## Frontend

The Vue application is in `frontend/src`. Each page is a file in `views`, the routes are defined in `router/index.js` and `api.js` wraps the calls to the backend. The signed in user is kept in the browser by `session.js`.

This description matches the code today and has to be revised whenever a module is added.
