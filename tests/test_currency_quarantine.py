import uuid

import psycopg

from ingestion.infra import create_connection, utc_now
from ingestion.runtime import RunContext, run_pipeline
from ingestion.load_currency import (
    CurrencyCodeChanged,
    currency_ingestion,
    write_currency_quarantine,
)


def test_currency_quarantine(one_currency) -> None:
    test_run_id = uuid.uuid4()

    # Выбираем существующую валюту и свободный тестовый код.
    with create_connection() as connection:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT s.currency_id, s.currency_code
                FROM source.currency AS s
                JOIN raw.currency AS r
                    ON s.currency_id = r.currency_id
                WHERE s.currency_code = r.currency_code
                ORDER BY s.currency_id
                LIMIT 1
            """)
            row = cur.fetchone()
            assert row is not None, "No matching source/RAW currency"

            currency_id, original_code = row

            cur.execute("SELECT currency_code FROM source.currency")
            used_codes = {row[0] for row in cur.fetchall()}

            incoming_code = next(
                (
                    code
                    for code in ("XTS", "XXX", "ZZZ")
                    if code not in used_codes
                ),
                None,
            )
            assert incoming_code is not None, "No free test currency code"

    def change_code_then_load(
        connection: psycopg.Connection,
        context: RunContext,
    ) -> None:
        with connection.cursor() as cur:
            cur.execute("""
                UPDATE source.currency
                SET currency_code = %s
                WHERE currency_id = %s
                  AND currency_code = %s
            """, (incoming_code, currency_id, original_code))

            assert cur.rowcount == 1, "Test currency was not updated"

        # Без commit: загрузчик видит изменение на том же соединении.
        currency_ingestion(connection, context)

    expected_message = (
        f"CURRENCY_CODE_CHANGED: currency_id={currency_id}, "
        f"original={original_code}, incoming={incoming_code}"
    )

    try:
        run_pipeline(
            name="test_currency_quarantine",
            connection_factory=create_connection,
            time_function=utc_now,
            uuid_gen=lambda: test_run_id,
            pipeline=change_code_then_load,
            on_failure=write_currency_quarantine,
        )
    except CurrencyCodeChanged as error:
        assert error.currency_id == currency_id
        assert error.original_code == original_code
        assert error.incoming_code == incoming_code
        assert str(error) == expected_message
    else:
        raise AssertionError("Expected CurrencyCodeChanged was not raised")

    # Проверяем только сохранённое состояние через новое соединение.
    with create_connection() as connection:
        with connection.cursor() as cur:
            cur.execute("""
                SELECT currency_code
                FROM source.currency
                WHERE currency_id = %s
            """, (currency_id,))
            assert cur.fetchone() == (original_code,), (
                "Source change was not rolled back"
            )

            cur.execute("""
                SELECT currency_code
                FROM raw.currency
                WHERE currency_id = %s
            """, (currency_id,))
            assert cur.fetchone() == (original_code,), (
                "Original RAW currency changed"
            )

            cur.execute("""
                SELECT COUNT(*)
                FROM raw.currency
                WHERE ingestion_run_id = %s
            """, (test_run_id,))
            assert cur.fetchone() == (0,), "Partial RAW inserts persisted"

            cur.execute("""
                SELECT run_status, rows_saved, error_cause
                FROM ops.ingestion_runs
                WHERE ingestion_run_id = %s
            """, (test_run_id,))
            assert cur.fetchall() == [
                ("FAILED", 0, expected_message)
            ], "Unexpected audit state"

            cur.execute("""
                SELECT
                    currency_id,
                    currency_original_code,
                    currency_incoming_code,
                    reason
                FROM quarantine.currency
                WHERE ingestion_run_id = %s
            """, (test_run_id,))
            assert cur.fetchall() == [
                (
                    currency_id,
                    original_code,
                    incoming_code,
                    "CURRENCY_CODE_CHANGED",
                )
            ], "Unexpected quarantine record"

    print(f"Currency quarantine test passed: {test_run_id}")


if __name__ == "__main__":
    test_currency_quarantine()