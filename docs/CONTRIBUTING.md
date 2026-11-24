# Contributing

These rules guide changes to the code. They come from the course requirements and from weaknesses found in the starter template, so they are conventions of the team and not a copy of an external standard. The template code still breaks some of them, and correcting that comes before any new module is built.

## Security

Structured Query Language (SQL) statements should use placeholders instead of string formatting, because text typed by a user then stays as data and cannot change the meaning of the query. For the same reason, responses should list the fields they return one by one and avoid returning a whole database row, so that values such as the password hash do not reach the browser.

Every route that is not public should check the role and the owner of the data on the server. Hiding a button in the interface changes only what the user sees and does not stop a direct request. Real keys and the `.env` file should stay out of the repository, and the example file holds only `change-me` values. All data in the seed and in the tests should be invented.

## Code

Names, comments, routes, tables and interface text are written in English. Variables and functions use `snake_case`, constants use `SNAKE_CASE` and classes use `PascalCase`, which keeps the code consistent as the course rubric asks. Each area of the API lives in its own `routes_<area>.py` blueprint, and the business rules belong there and not in the views. A function whose purpose is not obvious carries a short comment that explains why it exists.

Any change of balance should run in a single transaction that locks the rows involved, so that two simultaneous requests cannot spend the same money. The robot should reach the backend only through `/api/internal` and send the shared token on every call.

## Before delivering

The project should be started from scratch with `docker compose down -v` followed by `docker compose up --build`, and the main flows should be checked on that clean start. The file `docs/ENTREGA.md` has to describe the real state of each module. The ZIP is built with `python scripts/package.py --group NAME`, which prints the fingerprint to register on the platform.
