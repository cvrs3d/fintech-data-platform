from collections.abc import Iterator
import uuid

import pytest

from ingestion.infra import create_connection


def _reset_test_tables() -> None:
    with create_connection() as conn:
        target = conn.execute("SELECT current_database()").fetchone()
        if target != ("fintech_test",):
            raise RuntimeError(f"Refusing to reset tables in {target!r}")

        conn.execute("""
            TRUNCATE source.entries, source.accounts, source.account_history,
                     source.customers, source.currency, raw.accounts,
                     raw.currency, quarantine.currency, ops.ingestion_runs
        """)


@pytest.fixture(autouse=True)
def test_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("POSTGRES_DB", "fintech_test")
    _reset_test_tables()
    try:
        yield
    finally:
        _reset_test_tables()


@pytest.fixture
def source_currency(test_database: None) -> None:
    with create_connection() as conn:
        conn.execute("""
            INSERT INTO source.currency (
                currency_id, currency_code, registered_at_dt
            )
            VALUES (1, 'EUR', DATE '2026-01-01')
        """)


@pytest.fixture
def one_currency(source_currency: None) -> None:
    with create_connection() as conn:
        conn.execute("""
            INSERT INTO raw.currency (
                currency_id, currency_code, registered_at_dt,
                updated_at_dt, created_at_dt, ingestion_run_id
            )
            SELECT currency_id, currency_code, registered_at_dt,
                   updated_at_dt, created_at_dt, %s
            FROM source.currency
            WHERE currency_id = 1
        """, (uuid.uuid4(),))


@pytest.fixture
def one_account_version(source_currency: None) -> int:
    with create_connection() as conn:
        conn.execute("""
            INSERT INTO source.customers (
                customer_id, first_name, last_name, birth_date, registered_at_dt
            )
            VALUES (1, 'John', 'Doe', DATE '1990-01-01', DATE '2026-01-01')
        """)
        conn.execute("""
            INSERT INTO source.accounts (
                account_id, currency_id, customer_id, registered_at_dt
            )
            VALUES (1, 1, 1, DATE '2026-01-01')
        """)
        rows = conn.execute("""
            SELECT source_account_version_id
            FROM source.account_history
            WHERE account_id = 1
        """).fetchall()
        assert len(rows) == 1
        return rows[0][0]
