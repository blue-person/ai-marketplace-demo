# Contributing

These rules guide changes to the code. They come from the course requirements and from weaknesses found in the starter template, so they are conventions of the team and not a copy of an external standard. The template code still breaks some of them, and correcting that comes before any new module is built.

## Security

Structured Query Language (SQL) statements should use placeholders instead of string formatting, because text typed by a user then stays as data and cannot change the meaning of the query. For the same reason, responses should list the fields they return one by one and avoid returning a whole database row, so that values such as the password hash do not reach the browser.

Every route that is not public should check the role and the owner of the data on the server. Hiding a button in the interface changes only what the user sees and does not stop a direct request. Real keys and the `.env` file should stay out of the repository, and the example file uses `change-me` in place of every secret. All data in the seed and in the tests should be invented.

## Code

Names, comments, routes, tables and interface text are written in English. Variables and functions use `snake_case`, constants use `SNAKE_CASE` and classes use `PascalCase`, which keeps the code consistent as the course rubric asks. Each area of the API lives in its own `routes_<area>.py` blueprint, and the business rules belong there and not in the views. Comments are written in English, on their own line and in a single line, without a final period. A blank line separates each comment from the line before it, except for the first comment of a file. Docstrings, decoration comments and comments that describe a whole file are not used. The imports go under the section comments `# Import libraries` and `# Import modules`, and the constants go under `# Constants`, without a comment on each one. Every definition has a comment even when it looks obvious, and so does any step that is hard to understand at first glance. Any other line is left without a comment.

Python files are indented with tabs and formatted with Ruff, whose settings are in `ruff.toml`. Running `ruff format` before each commit keeps the style uniform, and the tool is installed once with `uv tool install ruff`. Dependencies are added with `uv add` inside `backend` or `mock-api`, and the generated `pyproject.toml` and `uv.lock` are committed together, so the files are never edited by hand.

The Vue and JavaScript files follow the same rule and are formatted with Prettier, whose settings are in `frontend/.prettierrc.json`. Running `npm run format` inside `frontend` before each commit applies the style, and `npm run format:check` only verifies it.

Any change of balance should run in a single transaction that locks the rows involved, so that two simultaneous requests cannot spend the same money. The robot should reach the backend only through `/api/internal` and send the shared token on every call.

## Before delivering

The project should be started from scratch with `docker compose down -v` followed by `docker compose up --build`, and the main flows should be checked on that clean start. The file `docs/ENTREGA.md` has to describe the real state of each module. The ZIP is built with `uv run scripts/package.py --group NAME`, which prints the fingerprint to register on the platform.
