# Testing ingestion into the raw layer 

# Problem

When we ingest data into the raw layer it should be the same data. Ingestion itself must be idempotent. 

# Test scenarios 

Boundries: Full read with `fetchall()` from source, single ingestion worker(process), single transaction on run, conflicts stop the ingestion, no quarantine layer

1. First ingestion into raw.entries
    Expected: No errors. Full ingestion. 
    Actual: 10 out of 10 rows were ingested successfully
2. Repeated ingestion of the same data 
    Expected: No new data in raw. Same checksum
    Actual: Same checksum and row count. No errors
3. Rollback aftem internal error (simulated), second attempt after resolving error
    Expected: Same checksum, no new data. After second attempt - new checksum ,new data
    Actual: Function raised error, no new data arrived. Checksum is the same. After second atempt with resolved issue, new data arrived and checksum was different from previous run.
4. Conflict between source and raw data contents
    Expected: Same checksum, raised error, no new data or updated data in raw
    Actual:  Same checksum, raised error, no new data or updated data in raw