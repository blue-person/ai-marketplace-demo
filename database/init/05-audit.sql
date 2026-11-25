-- Record of who did what, when and to whom. Rows are only added.

CREATE TABLE audit_events (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    created_at    TIMESTAMP(3)    NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    category      ENUM('authn', 'authz', 'registration', 'account', 'credit', 'agent', 'execution') NOT NULL,
    action        VARCHAR(50)     NOT NULL,
    outcome       ENUM('success', 'failure') NOT NULL,
    -- Empty when nobody is signed in, for example a failed login
    actor_id      BIGINT UNSIGNED NULL,
    -- Empty when the action does not act on an account
    target_id     BIGINT UNSIGNED NULL,
    -- The email that was typed when the account does not exist
    target_label  VARCHAR(254)    NULL,
    -- Old and new values, never passwords, hashes or API keys
    details       JSON            NULL,
    CONSTRAINT fk_audit_actor FOREIGN KEY (actor_id) REFERENCES accounts (id),
    CONSTRAINT fk_audit_target FOREIGN KEY (target_id) REFERENCES accounts (id),
    INDEX ix_audit_category (category, id),
    INDEX ix_audit_actor (actor_id, id),
    INDEX ix_audit_target (target_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
