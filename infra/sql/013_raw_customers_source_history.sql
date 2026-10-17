ALTER TABLE raw.customers 
ADD COLUMN source_customer_version_id BIGINT UNIQUE,
ADD COLUMN source_effective_from_dt TIMESTAMPTZ;