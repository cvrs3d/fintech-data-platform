# Testing ingestion tracking

# Problem 

For analytical and audit purpose we have to save information about our previous pipeline runs 

# Boundaries 

We do not assume any network partitions or unexpected process termination, otherwise there may remain RUNNING pipelines in db

# Test scenarios 

1. Simple first run on ingested data
    Expected: Write history row with all rows counted as read and skipped
    Actual: Successfull write into the ops.igestion_runs with all rows in rows_read and skipped
2. Run with simulated error 
    Expected: Raising error, writing history row with Falied state with rows_saved = 0, rows_skipped = 12
    Actual: Error raised, new record with failed state, rows_saved = 0, rows_skipped = 12
3. Rerun with issue fixed
    Expected: New record with status SUCCESS and only new rows count in rows_saved, previous rows in rows_skipped
    Actual: Successfull run with row count in saved read skipped same as expected