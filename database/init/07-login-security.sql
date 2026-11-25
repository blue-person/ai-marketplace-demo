-- Counter of failed logins for each email and the sessions that live in the server.

-- One row for each email that failed, whether the account exists or not, so a lock does not reveal accounts
CREATE TABLE login_throttle (
    email_hash   CHAR(64)          NOT NULL PRIMARY KEY,
    failures     SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    -- How many times the email was locked since its last good login or unlock
    lock_level   TINYINT UNSIGNED  NOT NULL DEFAULT 0,
    locked_until TIMESTAMP         NULL,
    updated_at   TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT ck_login_throttle_lock CHECK ((lock_level > 0) = (locked_until IS NOT NULL)),
    INDEX ix_login_throttle_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The id of a session is a random value and only its hash is stored, like the API keys
CREATE TABLE sessions (
    id_hash       CHAR(64)        NOT NULL PRIMARY KEY,
    account_id    BIGINT UNSIGNED NOT NULL,
    created_at    TIMESTAMP(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    -- Microseconds, because a request in the same second as the last one would change no row
    last_seen_at  TIMESTAMP(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    revoked_at    TIMESTAMP(6)    NULL,
    CONSTRAINT fk_sessions_account FOREIGN KEY (account_id) REFERENCES accounts (id),
    INDEX ix_sessions_account (account_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
