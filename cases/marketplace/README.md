# AI Agent Marketplace case: starting point

The full assignment is in [ENUNCIADO.md](ENUNCIADO.md) (in Spanish, as written by the instructor). To work on this case, use `CASE=marketplace` in your `.env`.

## What the template provides and what the group builds

| Module (weight) | What the template provides | What the group builds |
|---|---|---|
| Registration and verification (20%) | Sign up with roles `developer` and `company` (both start `pending`). Sign in and sign out, example directory and profile. Email sending to Mailpit. | Admin panel for approval. API key generation and delivery. Referrals with credit. C++ approval bot. |
| Agent catalog (10%) | — | Publication, admin approval and visibility. |
| Agent execution (30%) | OpenRouter-compatible simulator (`/chat/completions`, `/models`) and example HTTP client. | API key authentication, per-execution charge, history. |
| Scheduled executions (30%) | Periodic C++ robot that calls `/api/internal/...`. | Recurring and conditional scheduling, dispatch. |
| Transfers (10%) | — | Balances and transfers between users. |

## Test accounts

Created by the `seed` service with the `SEED_PASSWORD` from `.env`:

| Role | Emails |
|---|---|
| admin | value of `ADMIN_EMAIL` (password `ADMIN_PASSWORD`) |
| developer | dev1@marketplace.test, dev2@marketplace.test |
| company | company1@marketplace.test, company2@marketplace.test |
| bot | approval.robot@marketplace.test, which cannot sign in and uses the key of `WORKER_API_KEY` |
| pending | pending.complete@marketplace.test, which the robot approves, and pending.incomplete@marketplace.test, which waits for an administrator |

If you add roles, also add at least two accounts per role in `case.json`.

## Simulated external API

- `GET {EXTERNAL_API_BASE_URL}/models`: list of simulated models with prices.
- `POST {EXTERNAL_API_BASE_URL}/chat/completions` with `{"model": "...", "messages": [...]}`: replies in the OpenRouter format (OpenAI compatible).

Both require the `Authorization: Bearer <key>` header. Available models: `simulated/echo-1`, `simulated/summary-1` and `simulated/slow-1` (takes 5 seconds, useful to test timeouts).

**Using real OpenRouter (optional):** set `EXTERNAL_API_BASE_URL=https://openrouter.ai/api/v1` and your own `EXTERNAL_API_KEY` in `.env`. The real API charges per use, so the delivery to the auditor group must work with the simulator.
