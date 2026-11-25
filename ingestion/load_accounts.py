import uuid

import psycopg

from infra import create_connection, utc_now
from runtime import RunContext, run_pipeline


BATCH_SIZE = 256
VERSIONS = """
    SELECT h.account_id, h.currency_id, h.customer_id, h.registered_at_dt,
           h.created_at_dt, h.updated_at_dt, h.source_account_version_id,
           h.effective_from_dt, r.source_account_version_id IS NOT NULL,
           count(*) OVER ()
    FROM source.account_history h
    LEFT JOIN raw.accounts r USING (source_account_version_id)
    ORDER BY h.source_account_version_id
"""
OWNERS = """
    SELECT DISTINCT ON (account_id) account_id, customer_id
    FROM raw.accounts
    WHERE account_id = ANY(%s)
    ORDER BY account_id, account_version_id DESC
"""
INSERT = """
    INSERT INTO raw.accounts (
        account_id, currency_id, customer_id, registered_at_dt, created_at_dt,
        updated_at_dt, source_account_version_id, source_effective_from_dt, ingestion_run_id
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
"""


def account_ingestion(cnn: psycopg.Connection, context: RunContext) -> None:
    with cnn.cursor() as cur:
        # Serialize RAW writers before taking the source/RAW cursor snapshot.
        # Ordinary readers remain free to query the last committed state.
        cur.execute("LOCK TABLE raw.accounts IN SHARE ROW EXCLUSIVE MODE")
        with cnn.cursor(name="account_versions") as versions:
            versions.execute(VERSIONS)
            while batch := versions.fetchmany(BATCH_SIZE):
                context.stats.rows_read = batch[0][-1]
                accounts = {row[0] for row in batch if not row[-2]}
                owners = {}
                if accounts:
                    cur.execute(OWNERS, (sorted(accounts),))
                    owners = dict(cur.fetchall())

                for row in batch:
                    if row[-2]:
                        context.stats.rows_skipped += 1
                        continue
                    account_id, _, customer_id = row[:3]
                    original = owners.setdefault(account_id, customer_id)
                    if original != customer_id:
                        raise ValueError(
                            f"Account {account_id}: customer_id changed "
                            f"from {original} to {customer_id}"
                        )
                    cur.execute(INSERT, (*row[:8], context.ingestion_run_id))
                    context.stats.rows_saved += 1


if __name__ == "__main__":
    run_id = uuid.uuid4()
    print(f"source_accounts_to_raw ingestion_run_id={run_id}", flush=True)
    run_pipeline(
        name="source_accounts_to_raw",
        connection_factory=create_connection,
        time_function=utc_now,
        uuid_gen=lambda: run_id,
        pipeline=account_ingestion,
    )
