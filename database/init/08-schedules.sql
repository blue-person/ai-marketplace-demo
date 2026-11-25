-- Scheduled executions of the agents, recurring or conditional, that the dispatch robot launches.
-- Every time is read from the clock of MySQL, never from the robot or the backend.

CREATE TABLE scheduled_executions (
    id                    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    account_id            BIGINT UNSIGNED  NOT NULL,
    agent_id              BIGINT UNSIGNED  NOT NULL,
    kind                  ENUM('recurring', 'conditional') NOT NULL,
    prompt                VARCHAR(2000)    NOT NULL,
    -- Only a recurring schedule has an interval, from 5 minutes to 30 days
    interval_seconds      INT UNSIGNED     NULL,
    -- Only a conditional schedule has a threshold of balance and a cooldown between launches
    threshold_usd         DECIMAL(12,4)    NULL,
    cooldown_seconds      INT UNSIGNED     NULL,
    status                ENUM('active', 'paused', 'cancelled') NOT NULL DEFAULT 'active',
    -- Who paused it, and only a paused schedule has one
    pause_reason          ENUM('owner', 'admin', 'failures') NULL,
    -- The schedule is due when this time has passed and the claim of a launch moves it forward
    next_run_at           TIMESTAMP        NOT NULL,
    consecutive_failures  TINYINT UNSIGNED NOT NULL DEFAULT 0,
    last_run_at           TIMESTAMP        NULL,
    last_outcome          ENUM('completed', 'failed', 'not_enough_balance', 'agent_unavailable') NULL,
    -- The execution of the last launch, and a launch without balance or agent has none
    last_execution_id     BIGINT UNSIGNED  NULL,
    created_at            TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_scheduled_account FOREIGN KEY (account_id) REFERENCES accounts (id),
    CONSTRAINT fk_scheduled_agent FOREIGN KEY (agent_id) REFERENCES agents (id),
    CONSTRAINT fk_scheduled_execution FOREIGN KEY (last_execution_id) REFERENCES executions (id),
    CONSTRAINT ck_scheduled_kind CHECK (
        (kind = 'recurring' AND interval_seconds IS NOT NULL AND threshold_usd IS NULL AND cooldown_seconds IS NULL)
        OR (kind = 'conditional' AND interval_seconds IS NULL AND threshold_usd IS NOT NULL AND cooldown_seconds IS NOT NULL)
    ),
    CONSTRAINT ck_scheduled_interval CHECK (interval_seconds IS NULL OR interval_seconds BETWEEN 300 AND 2592000),
    CONSTRAINT ck_scheduled_threshold CHECK (threshold_usd IS NULL OR threshold_usd > 0),
    CONSTRAINT ck_scheduled_cooldown CHECK (cooldown_seconds IS NULL OR cooldown_seconds BETWEEN 600 AND 2592000),
    CONSTRAINT ck_scheduled_pause CHECK ((status = 'paused') = (pause_reason IS NOT NULL)),
    CONSTRAINT ck_scheduled_failures CHECK (consecutive_failures <= 3),
    CONSTRAINT ck_scheduled_last CHECK (
        (last_run_at IS NULL) = (last_outcome IS NULL)
        AND (last_execution_id IS NULL OR last_outcome IN ('completed', 'failed'))
    ),
    INDEX ix_scheduled_due (status, next_run_at),
    INDEX ix_scheduled_account (account_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
