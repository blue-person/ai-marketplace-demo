-- Base schema shared by both cases.
-- This script runs automatically ONLY when the database volume is created
-- for the first time. If you change it, recreate the volume:
--     docker compose down -v && docker compose up --build
--
-- Add the tables of your modules in new files in this folder,
-- for example 02-modules.sql (they run in alphabetical order).

CREATE TABLE IF NOT EXISTS accounts (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(120)  NOT NULL,
    email          VARCHAR(254)  NOT NULL,
    password_hash  VARCHAR(255)  NOT NULL,
    -- Valid roles depend on the case: see cases/<case>/case.json
    role           VARCHAR(30)   NOT NULL,
    status         ENUM('pending', 'active', 'rejected', 'suspended') NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_accounts_email UNIQUE (email),
    INDEX ix_accounts_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
