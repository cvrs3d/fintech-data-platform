# Customer ingestion 

# Problem

We need to ingest customers into raw layer 

# Boudaries 

Only batch ingestion for now. 
Full scan.
No deletions.
Only observable changes.
Single loader. 


# Test scenarios 

1. Ingestion of customers and catching ingestion run result into ops.ingestion_runs
    Expected: Successfull run 2 saved 0 skipped 2 read
    Actual: 2 saved 2 read 0 skipped

2. Testing idempotency with the same data but second run
    Expected: Successfull idempotent run
    Actual: 0 saved, 2 read 2 skipped 

3. Changing data than while loading Doe → Smith → Doe 
    Expected: Succsessfull run
    Actual: We captured all state changes for the records. Changing timestamp does not create new state.