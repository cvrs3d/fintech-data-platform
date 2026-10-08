# Problem

Created a raw layer for observed versions of accounts 

# Grain

On row per observed vesrion of an account

# Boudaries

Full read with `fetchall()` from source, single ingestion worker(process), single transaction on run, conflicts stop the ingestion, no quarantine layer
We check buisness fields
On coflict with customer_id we raise an error

# Test scenarios 

1. First run 
    Expected: Two consecutive runs with no error 
    Actual: First run saved all rows, second one skipped them, SUCCESS
2. Mocking changes inside buisness attributes (registred_at)
    Expected: Success, single row being re-saved 
    Actual: SUCCESS saved 1 row skipped other
