#!/bin/bash
# Creates the MySQL user of the application with only the privileges it needs.
# It runs after the .sql files, so every table already exists, and only when the volume is first created.
# The entrypoint of the image sources this file, so everything runs in a subshell and its options do not leak out.

(
    set -euo pipefail

    # Refuse values that would break the statements below
    if [[ ! "${DB_USER:-}" =~ ^[A-Za-z0-9_]+$ ]]; then
        echo "DB_USER must be set and use only letters, numbers and underscores" >&2
        exit 1
    fi
    if [[ -z "${DB_PASSWORD:-}" || "$DB_PASSWORD" == *"'"* || "$DB_PASSWORD" == *'\'* ]]; then
        echo "DB_PASSWORD must be set and must not contain quotes or backslashes" >&2
        exit 1
    fi

    # Tables that are only appended to get no UPDATE, so a row cannot be changed after it is written
    mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" <<SQL
CREATE USER '${DB_USER}'@'%' IDENTIFIED BY '${DB_PASSWORD}';
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.accounts TO '${DB_USER}'@'%';
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.api_keys TO '${DB_USER}'@'%';
GRANT SELECT, INSERT, UPDATE ON ${MYSQL_DATABASE}.agents TO '${DB_USER}'@'%';
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.transfers TO '${DB_USER}'@'%';
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.ledger_entries TO '${DB_USER}'@'%';
GRANT SELECT, INSERT ON ${MYSQL_DATABASE}.audit_events TO '${DB_USER}'@'%';
SQL
)
