# HealthSync case: starting point

The full assignment is in [ENUNCIADO.md](ENUNCIADO.md) (in Spanish, as written by the instructor). To work on this case, use `CASE=healthsync` in your `.env`.

## What the template provides and what the group builds

| Module (weight) | What the template provides | What the group builds |
|---|---|---|
| Registration and verification (20%) | Sign up with roles `patient` (active immediately) and `professional` (starts `pending`). Sign in and sign out, example directory and profile. Email sending to Mailpit. | Date of birth and professional card photo. Admin panel to approve or reject. Referrals and points. C++ validation bot. |
| Wearables (10%) | Data simulator (`/openmhealth/v1/dataPoints`) and example HTTP client. | Device linking, import and storage of metrics. |
| Virtual consultations (30%) | — | Directory, scheduling, credit charge, consent, clinical notes, history. |
| Scheduled alerts (30%) | Periodic C++ robot that calls `/api/internal/...`. | Thresholds, periodic evaluation, notifications to patient and professional. |
| Transfers (10%) | — | Balances and transfers between users. |

## Test accounts

Created by the `seed` service with the `SEED_PASSWORD` from `.env`:

| Role | Emails |
|---|---|
| admin | value of `ADMIN_EMAIL` (password `ADMIN_PASSWORD`) |
| patient | patient1@healthsync.test, patient2@healthsync.test |
| professional | professional1@healthsync.test, professional2@healthsync.test |

If you add roles, also add at least two accounts per role in `case.json`.

## Simulated external API

`GET {EXTERNAL_API_BASE_URL}/dataPoints?schema=<metric>&user=<id>&days=<1-30>`, with the `Authorization: Bearer <key>` header.

Available metrics: `heart-rate`, `step-count`, `oxygen-saturation`, `sleep-duration`. The series is deterministic per user and metric. About 5 % of the readings are out of range (for example 138 bpm or 86 % oxygen) so alerts can be tested.

The response follows a structure inspired by the Open mHealth schemas (`header` and `body`), but it is not an exact replica. The assignment mentions the public Open mHealth API; Open mHealth mainly publishes schema specifications, and it was not verified that a public service delivering real wearable data exists. That is why the simulator is the default source.
