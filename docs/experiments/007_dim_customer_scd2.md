# Created dim customer table with scd2 

# Problem 

Our analysts need a reliable way to analyze historical customer data
Data engineers need a way to automatically create and adjust dimension
We used dbt for SCD2 type table dim_customer

# Grain
One row describes one observed version inside raw

# SCD2 intervals

[valid_from, valid_to) 

# Boundaries

customer_keys are preserved after build only if the same RAW is present

# Test scenarios 

1. Experiment where we create is_current=false with valid_to 
    Expected: 2 tests will fail
    Actual: Failed to tests
    With restored pipeline all 8 tests passed 
    


