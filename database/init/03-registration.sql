-- Profile, referrals, review data and API keys of the registration module.

ALTER TABLE accounts
    ADD COLUMN organization      VARCHAR(100)    NULL,
    ADD COLUMN country           CHAR(2)         NULL,
    ADD COLUMN referral_code     VARCHAR(32)     NULL,
    ADD COLUMN referred_by       BIGINT UNSIGNED NULL,
    ADD COLUMN reviewed_at       TIMESTAMP       NULL,
    ADD COLUMN reviewed_by       BIGINT UNSIGNED NULL,
    ADD COLUMN rejection_reason  VARCHAR(30)     NULL,
    ADD CONSTRAINT uq_accounts_referral_code UNIQUE (referral_code),
    ADD CONSTRAINT fk_accounts_referred_by FOREIGN KEY (referred_by) REFERENCES accounts (id),
    ADD CONSTRAINT fk_accounts_reviewed_by FOREIGN KEY (reviewed_by) REFERENCES accounts (id);

-- One row per account, so the database itself allows only one valid key at a time
CREATE TABLE api_keys (
    account_id  BIGINT UNSIGNED PRIMARY KEY,
    key_hash    CHAR(64)        NOT NULL,
    key_prefix  CHAR(8)         NOT NULL,
    created_at  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_api_keys_account FOREIGN KEY (account_id) REFERENCES accounts (id),
    CONSTRAINT uq_api_keys_hash UNIQUE (key_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The unique key lets the database refuse a second bonus for the same referred account
ALTER TABLE ledger_entries
    MODIFY COLUMN entry_type ENUM('seed_credit', 'transfer_out', 'transfer_in', 'referral_bonus') NOT NULL,
    ADD COLUMN referred_account_id BIGINT UNSIGNED NULL,
    ADD CONSTRAINT fk_ledger_referred FOREIGN KEY (referred_account_id) REFERENCES accounts (id),
    ADD CONSTRAINT uq_ledger_referred UNIQUE (referred_account_id);
