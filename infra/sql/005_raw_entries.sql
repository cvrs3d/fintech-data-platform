CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE raw.entries (
    entry_id INT PRIMARY KEY, -- pk
    transaction_id UUID NOT NULL, -- buisness transaction number
    account_id INT NOT NULL, -- money entry account 
    amount NUMERIC(18, 2) NOT NULL, -- amount of entry
    created_at_dt TIMESTAMPTZ  NOT NULL, -- created in db at timestamp
    executed_at_dt TIMESTAMPTZ NOT NULL, -- date when transaction was executed by bank
    inserted_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- first row insertion into raw table
    ingestion_run_id UUID NOT NULL -- ingestion run id
);