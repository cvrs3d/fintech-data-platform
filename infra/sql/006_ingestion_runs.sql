CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE ops.ingestion_runs (
    ingestion_run_id UUID PRIMARY KEY,
    run_status VARCHAR(10) NOT NULL CHECK (run_status IN ('SUCCESS', 'RUNNING', 'FAILED')),
    rows_read INT NOT NULL DEFAULT 0 CHECK (rows_read >= 0), -- Rows read from source
    rows_saved INT NOT NULL DEFAULT 0 CHECK (rows_saved >= 0), -- Rows that were saved into raw for the first time 
    rows_skipped INT NOT NULL DEFAULT 0 CHECK (rows_skipped >= 0), -- Skipped similar rows
    error_cause  TEXT,
    pipeline_name VARCHAR(150) NOT NULL,
    start_time_dt TIMESTAMPTZ NOT NULL,
    end_time_dt TIMESTAMPTZ
);