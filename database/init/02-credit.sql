-- Credit of each account, its transfers and the append-only ledger.

ALTER TABLE accounts
    ADD COLUMN balance DECIMAL(12,4) NOT NULL DEFAULT 0.0000,
    ADD CONSTRAINT ck_accounts_balance CHECK (balance >= 0);

CREATE TABLE transfers (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    from_account_id  BIGINT UNSIGNED NOT NULL,
    to_account_id    BIGINT UNSIGNED NOT NULL,
    amount           DECIMAL(12,4)   NOT NULL,
    created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_transfers_from FOREIGN KEY (from_account_id) REFERENCES accounts (id),
    CONSTRAINT fk_transfers_to FOREIGN KEY (to_account_id) REFERENCES accounts (id),
    CONSTRAINT ck_transfers_amount CHECK (amount > 0),
    CONSTRAINT ck_transfers_accounts CHECK (from_account_id <> to_account_id),
    INDEX ix_transfers_to (to_account_id, created_at),
    INDEX ix_transfers_from (from_account_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE ledger_entries (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_id   BIGINT UNSIGNED NOT NULL,
    amount       DECIMAL(12,4)   NOT NULL,
    entry_type   ENUM('seed_credit', 'transfer_out', 'transfer_in') NOT NULL,
    transfer_id  BIGINT UNSIGNED NULL,
    created_at   TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ledger_account FOREIGN KEY (account_id) REFERENCES accounts (id),
    CONSTRAINT fk_ledger_transfer FOREIGN KEY (transfer_id) REFERENCES transfers (id),
    CONSTRAINT ck_ledger_amount CHECK (amount <> 0),
    CONSTRAINT uq_ledger_transfer_type UNIQUE (transfer_id, entry_type),
    INDEX ix_ledger_account (account_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
