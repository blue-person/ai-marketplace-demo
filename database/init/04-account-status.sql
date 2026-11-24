-- Record of who suspended or reactivated an account. Rows are only added.

CREATE TABLE account_status_changes (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_id   BIGINT UNSIGNED NOT NULL,
    changed_by   BIGINT UNSIGNED NOT NULL,
    from_status  ENUM('active', 'suspended') NOT NULL,
    to_status    ENUM('active', 'suspended') NOT NULL,
    created_at   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_status_changes_account FOREIGN KEY (account_id) REFERENCES accounts (id),
    CONSTRAINT fk_status_changes_admin FOREIGN KEY (changed_by) REFERENCES accounts (id),
    CONSTRAINT ck_status_changes_different CHECK (from_status <> to_status),
    INDEX ix_status_changes_account (account_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
