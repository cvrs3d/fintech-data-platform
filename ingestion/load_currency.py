import uuid
from infra import utc_now, create_connection
import psycopg
from runtime import RunContext, run_pipeline

class CurrencyCodeChanged(ValueError):
    def __init__(self, currency_id: int, original_code: str, incoming_code: str) -> None:
        self.currency_id = currency_id
        self.original_code = original_code
        self.incoming_code = incoming_code
        super().__init__(f"CURRENCY_CODE_CHANGED: currency_id={currency_id}, original={original_code}, incoming={incoming_code}")

def write_currency_quarantine(connection: psycopg.Connection, context: RunContext, exp: Exception) -> None:
    if not isinstance(exp, CurrencyCodeChanged):
        return
    with connection.cursor() as cur:
        record = (exp.currency_id, exp.original_code, exp.incoming_code, "CURRENCY_CODE_CHANGED", context.ingestion_run_id)
        cur.execute("""
            INSERT INTO quarantine.currency (
                currency_id,
                currency_original_code,
                currency_incoming_code,
                reason,
                ingestion_run_id
            )
            VALUES (%s, %s, %s, %s, %s)
        """, record)


def currency_ingestion(cnn: psycopg.Connection, context: RunContext) -> None:
    with cnn.cursor() as cur:
        cur.execute("""
            SELECT
            currency_id,
            currency_code,
            registered_at_dt,
            updated_at_dt,
            created_at_dt
            FROM source.currency
        """)
        source_rows = cur.fetchall()
        context.stats.rows_read = len(source_rows)

        for source_row in source_rows:
            source_currency_id = source_row[0]
            cur.execute("""
            SELECT
            currency_id,
            currency_code,
            registered_at_dt,
            updated_at_dt,
            created_at_dt
            FROM raw.currency
            WHERE currency_id = %s
            """, (source_currency_id, ))
            raw_row = cur.fetchone()
            if raw_row is not None and source_row[0:2] == raw_row[0:2]:
                context.stats.rows_skipped += 1
                continue
            if raw_row is not None and raw_row[1] != source_row[1]:
                raise CurrencyCodeChanged(
                    currency_id=source_currency_id,
                    original_code=raw_row[1],
                    incoming_code=source_row[1])

            cur.execute("""
            INSERT INTO raw.currency (
            currency_id,
            currency_code,
            registered_at_dt,
            updated_at_dt,
            created_at_dt,
            ingestion_run_id)
            VALUES (%s, %s, %s, %s, %s, %s)""", (*source_row, context.ingestion_run_id))
            context.stats.rows_saved += 1


if __name__ == "__main__":
    run_pipeline(
        name="source_currency_to_raw",
        connection_factory=create_connection,
        time_function=utc_now,
        uuid_gen=uuid.uuid4,
        pipeline=currency_ingestion,
        on_failure=write_currency_quarantine,
    )
