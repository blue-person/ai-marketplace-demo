-- Executions of the agents, their ledger entries and the protection of the platform account.

CREATE TABLE executions (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_id       BIGINT UNSIGNED NOT NULL,
    agent_id         BIGINT UNSIGNED NOT NULL,
    -- The developer of the agent when it ran, kept here so the earnings do not depend on later changes
    developer_id     BIGINT UNSIGNED NOT NULL,
    -- A UUID chosen by the client so a repeated request is never charged twice
    idempotency_key  CHAR(36)        NOT NULL,
    -- SHA-256 of the agent and the prompt, so the same key with another request is detected
    request_hash     CHAR(64)        NOT NULL,
    prompt           VARCHAR(2000)   NOT NULL,
    response         VARCHAR(4000)   NULL,
    cost_usd         DECIMAL(12,2)   NOT NULL,
    developer_share  DECIMAL(12,4)   NULL,
    platform_fee     DECIMAL(12,4)   NULL,
    status           ENUM('pending', 'completed', 'failed') NOT NULL DEFAULT 'pending',
    -- A key of the list of reasons of the backend and only a failed execution has one
    failure_reason   VARCHAR(40)     NULL,
    created_at       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at      TIMESTAMP       NULL,
    CONSTRAINT fk_executions_account FOREIGN KEY (account_id) REFERENCES accounts (id),
    CONSTRAINT fk_executions_agent FOREIGN KEY (agent_id) REFERENCES agents (id),
    CONSTRAINT fk_executions_developer FOREIGN KEY (developer_id) REFERENCES accounts (id),
    CONSTRAINT uq_executions_key UNIQUE (account_id, idempotency_key),
    CONSTRAINT ck_executions_cost CHECK (cost_usd >= 0),
    -- Only the developer of the agent runs it for free
    CONSTRAINT ck_executions_own CHECK ((account_id = developer_id) = (cost_usd = 0)),
    CONSTRAINT ck_executions_response CHECK ((status = 'completed') = (response IS NOT NULL)),
    CONSTRAINT ck_executions_reason CHECK ((status = 'failed') = (failure_reason IS NOT NULL)),
    CONSTRAINT ck_executions_finished CHECK ((status = 'pending') = (finished_at IS NULL)),
    -- The shares exist only in a completed execution that cost something and they add up to the cost
    CONSTRAINT ck_executions_shares CHECK (
        ((status = 'completed' AND cost_usd > 0) = (developer_share IS NOT NULL))
        AND ((developer_share IS NULL) = (platform_fee IS NULL))
        AND (developer_share IS NULL OR developer_share + platform_fee = cost_usd)
    ),
    INDEX ix_executions_account (account_id, id),
    INDEX ix_executions_developer (developer_id, id),
    INDEX ix_executions_status (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- Each kind of entry exists once for each execution, so a charge, a refund or a payment cannot repeat
ALTER TABLE ledger_entries
    MODIFY COLUMN entry_type ENUM(
        'seed_credit', 'transfer_out', 'transfer_in', 'referral_bonus',
        'agent_execution', 'agent_refund', 'agent_earning', 'platform_fee'
    ) NOT NULL,
    ADD COLUMN execution_id BIGINT UNSIGNED NULL,
    ADD CONSTRAINT fk_ledger_execution FOREIGN KEY (execution_id) REFERENCES executions (id),
    ADD CONSTRAINT uq_ledger_execution_type UNIQUE (execution_id, entry_type);

-- The platform account receives the share of the platform and it can never be suspended or changed of role
DELIMITER //
CREATE TRIGGER trg_accounts_protect_platform BEFORE UPDATE ON accounts
FOR EACH ROW
BEGIN
    IF OLD.role = 'system' AND (NEW.role <> OLD.role OR NEW.status <> OLD.status) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The platform account cannot be changed';
    END IF;
END//
DELIMITER ;
