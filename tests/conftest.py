import pytest
from pytest import MonkeyPatch
import uuid
from ingestion.infra import create_connection, utc_now

@pytest.fixture(autouse=True)
def test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_DB", "fintech_test")

    with create_connection() as conn:
        result = conn.execute("SELECT current_database()").fetchone()
        if result != ("fintech_test",):
            raise RuntimeError(f"Expected fintech_test, got {result!r}")


@pytest.fixture
def one_currency() -> None:
    with create_connection() as conn:
        result = conn.execute("SELECT current_database()").fetchone()
        if result != ("fintech_test",):
            raise RuntimeError
        with conn.cursor() as curr:
            curr.execute("""
                TRUNCATE TABLE raw.currency, source.entries, source.accounts, source.currency
                """)
            curr.execute(""" 
                INSERT INTO source.currency (currency_id, currency_code, registered_at_dt)
                VALUES(%s, %s, DATE '2026-01-01')
            """, (1, "EUR"))
            curr.execute("""INSERT INTO raw.currency (currency_id, currency_code, registered_at_dt, updated_at_dt, created_at_dt, ingestion_run_id)
            SELECT currency_id, currency_code, registered_at_dt, updated_at_dt, created_at_dt, %s FROM source.currency""",(uuid.uuid4(),))
    return

@pytest.fixture
def one_account_version():

    with create_connection() as conn:
        result = conn.execute("SELECT current_database()").fetchone()
        if result != ("fintech_test",):
            raise RuntimeError
        with conn.cursor() as curr:
            curr.execute("""
                TRUNCATE TABLE raw.accounts,
                source.account_history,
                source.entries, 
                source.accounts, 
                source.customers,
                source.currency
            """)
            curr.execute(""" 
                INSERT INTO source.currency (currency_id, currency_code, registered_at_dt)
                VALUES(%s, %s, DATE '2026-01-01')
            """, (1, "EUR"))
            curr.execute("INSERT INTO source.customers (customer_id, first_name, last_name, birth_date, registered_at_dt) VALUES(" \
            "%s, %s, %s, DATE '1990-01-01', DATE '2026-01-01')", (1, "John", "Doe"))
            curr.execute("INSERT INTO source.accounts (account_id, currency_id, customer_id, registered_at_dt) VALUES (" \
            "%s, %s, %s, DATE '2026-01-01')", (1, 1, 1))

            curr.execute("""
                SELECT source_account_version_id
                FROM source.account_history
                WHERE account_id = 1
            """)
            versions = curr.fetchall()
            assert len(versions) == 1, f"Expected one source version, got {len(versions)}"
            version_id = versions[0][0]

            curr.execute("SELECT COUNT(*) FROM raw.accounts")
            assert curr.fetchone() == (0,), "Expected empty raw.accounts before ingestion"


    yield version_id
        

