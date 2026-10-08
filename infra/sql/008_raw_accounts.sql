CREATE TABLE raw.accounts (
    account_id INT NOT NULL, -- business key from source 
    account_version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, -- account version key
    currency_id INT NOT NULL, -- currency identifier from source
    customer_id INT NOT NULL, -- customer identifier from source
    registered_at_dt DATE NOT NULL, -- date when account was registred
    created_at_dt TIMESTAMPTZ NOT NULL, -- created at timestamp
    updated_at_dt TIMESTAMPTZ NOT NULL, -- updated at ts
    inserted_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- time when record got into raw
    ingestion_run_id UUID NOT NULL -- ingestion run id
); -- grain: One row per observed version of source.accounts