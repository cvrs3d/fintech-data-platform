CREATE TABLE raw.currency (
    currency_id INT PRIMARY KEY,
    currency_code VARCHAR(3) UNIQUE NOT NULL,
    registered_at_dt DATE NOT NULL,
    updated_at_dt TIMESTAMPTZ NOT NULL,
    created_at_dt TIMESTAMPTZ NOT NULL,
    inserted_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    ingestion_run_id UUID NOT NULL
);

CREATE SCHEMA IF NOT EXISTS quarantine;

CREATE TABLE quarantine.currency (
    quarantine_currency_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    currency_id INT NOT NULL,
    currency_original_code VARCHAR(3) NOT NULL,
    currency_incoming_code VARCHAR(3) NOT NULL,
    reason TEXT NOT NULL,
    ingestion_run_id UUID NOT NULL,
    detected_at_td TIMESTAMPTZ DEFAULT NOW() NOT NULL
);