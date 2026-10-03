# Transfer atomicity check 

1) In tests/sql/001_transfer_atomicity.sql we checked transfer atomicity for further work with transfer entries 

2) To fail commit we on purpose generated amount check by assigning 0 to amount column

3) Expected: No entry with transaction_id='ATOMIC_FAIL'
   Actual: Commit failed no rows where added.

4) INSERT 0 1 just means how many row where processed by db engine (1) and Object id which is almost always 0. It does not guarantee data ingestion.