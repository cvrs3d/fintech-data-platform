CREATE TABLE raw.customers (
    customer_id INT NOT NULL, -- business key 
    customer_version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL, -- first name of a client should be long in case of nation specific long name like african
    last_name VARCHAR(50) NOT NULL, -- last name
    birth_date DATE NOT NULL, -- birth date
    death_date DATE , -- date of death
    registered_at_dt DATE NOT NULL, -- date of client registration 
    updated_at_dt TIMESTAMPTZ NOT NULL, -- time when client was updated 
    created_at_dt TIMESTAMPTZ NOT NULL, -- time when client record was published in the system
    inserted_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- first row insertion into raw table
    ingestion_run_id UUID NOT NULL -- ingestion run id

); -- grain: One row per one version of certain customer

CREATE INDEX IF NOT EXISTS idx_raw_customers 
ON raw.customers (customer_id, customer_version_id);