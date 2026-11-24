-- Catalog of the agents that developers publish and administrators review.

CREATE TABLE agents (
    id                BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    developer_id      BIGINT UNSIGNED NOT NULL,
    name              VARCHAR(100)    NOT NULL,
    description       VARCHAR(1000)   NOT NULL,
    price_usd         DECIMAL(12,2)   NOT NULL,
    category          VARCHAR(30)     NOT NULL,
    -- Stored and shown to the owner and the administrators, and the backend never calls it
    test_endpoint     VARCHAR(500)    NOT NULL,
    model             VARCHAR(100)    NOT NULL,
    status            ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    -- A key of the list of reasons of the backend and only a rejected agent has one
    rejection_reason  VARCHAR(40)     NULL,
    reviewed_by       BIGINT UNSIGNED NULL,
    reviewed_at       TIMESTAMP       NULL,
    created_at        TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_agents_developer FOREIGN KEY (developer_id) REFERENCES accounts (id),
    CONSTRAINT fk_agents_reviewer FOREIGN KEY (reviewed_by) REFERENCES accounts (id),
    CONSTRAINT ck_agents_price CHECK (price_usd > 0),
    CONSTRAINT ck_agents_reason CHECK ((status = 'rejected') = (rejection_reason IS NOT NULL)),
    CONSTRAINT uq_agents_developer_name UNIQUE (developer_id, name),
    INDEX ix_agents_status (status, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
