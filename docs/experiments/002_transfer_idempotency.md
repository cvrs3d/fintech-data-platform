# Transfer idempotecy problem 

## Problem 

What should happen when somehow system will get multiple requests from a single client to perform same transfer?

## Solution 

We create idempotency key on client side and then store it in base with references for the entries. 
When system will get a request of transfer, it will perform check (INSERT) for the transfer request and decide what to do.

## Testing scenarios 

1. Creating two identical requests 
    Expected behavior: First one will create entries and the second one will just return UUID of existing transfer
    Actual: Two entries are created and second request returned same UUID.
2. Creating two identical requests concurrently
    Expected behavior: First one will create entries and the second one will just return UUID of existing transfer
    Actual: Two entries are created and second request returned same UUID.
3. Does the system perform roll back on key whe error happens between entries? 
    Expected: Raise RuntimeError, with no entries with attempted key
    Actual: No entries for that key.
