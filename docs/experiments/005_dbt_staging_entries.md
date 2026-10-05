# Testing dbt 

# Problem

We need dbt to build DWH layers for us automatically and run sql tests against data

# Boudaries 

We are creating one view and we have 5 tests to check 

# Setting up
First install postgresql adapter for dbt 

```bash
uv add dbt-postgres
uv run dbt --version
```
Then we have files dbt/dbt_project.yml and dbt/profiles.yml,  dbt/models/staging/_sources.yml 

Testing connection with debug
```bash
uv run --env-file .env dbt debug \
  --project-dir dbt \
  --profiles-dir dbt
```
Then parse project with parse 

```bash
uv run --env-file .env dbt parse \
  --project-dir dbt \
  --profiles-dir dbt
```
Then we have dbt/models/staging/_models.yml
After performed checks we build our project

```bash
uv run --env-file .env dbt build \
  --project-dir dbt \
  --profiles-dir dbt \
  --select stg_entries
```


# Tests

1. Standard build
    Expected: All 4 tests passed, view is created
    Actual: Successfull build, view created 4 of 4 tests passed 

2. Run with WHERE entry_id <> 1 inside view creation  
    Expected: FAIL 1 
    Actual: Build shown 1 failed test, fixing the issue doesn't rollback the view we should build again
    After deleting where clause we performed another build with PASS=5 ERROR=0 result