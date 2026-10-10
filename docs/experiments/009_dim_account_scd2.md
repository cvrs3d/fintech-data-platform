# Problem

We need to create SCD2 type table for staging layer, so we can run audit and analysis

# Grain 

One row per observed version of raw.accounts

# Info

account_key (PK) is derived from account_version_id 
intervals are derived from inserted_at_dt

# Tests

1. Staging.dim_account has exactly on row per current version for certain account
    Expected: PASS
    Actual: PASS
2. Staging.dim_account has valid interavals and does not violate rule valid_to is null -> is_current = true
    Expected: PASS
    Actual: PASS 