ALTER TABLE raw.accounts 
ADD COLUMN source_account_version_id  BIGINT UNIQUE ,
ADD COLUMN source_effective_from_dt TIMESTAMPTZ;