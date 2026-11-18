from dataclasses import dataclass
from uuid import UUID
from collections.abc import Callable
import psycopg
import logging
from datetime import datetime

@dataclass
class RunStats:
    rows_read: int = 0
    rows_saved: int = 0
    rows_skipped: int = 0


@dataclass
class RunContext:
    ingestion_run_id: UUID
    stats: RunStats


def run_pipeline(name: str,
                connection_factory: Callable[[], psycopg.Connection],
                time_function: Callable[[], datetime],
                uuid_gen: Callable[[], UUID],
                pipeline: Callable[[psycopg.Connection, RunContext], None],
                on_failure: Callable[[psycopg.Connection, RunContext, Exception], None] | None = None) -> None :
    run_context = RunContext(
        ingestion_run_id=uuid_gen(),
        stats=RunStats()
    )

    connection = connection_factory()
    try:
        with connection.cursor() as cur:
            cur.execute("""INSERT INTO ops.ingestion_runs (
                ingestion_run_id,
                run_status,
                rows_read,
                rows_saved,
                rows_skipped,
                pipeline_name,
                start_time_dt
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)""", (
                    run_context.ingestion_run_id,
                    "RUNNING",
                    run_context.stats.rows_read,
                    run_context.stats.rows_saved,
                    run_context.stats.rows_skipped,
                    name,
                    time_function()))
            connection.commit()
            try:
                pipeline(connection, run_context)
                cur.execute(
                    """
                    UPDATE ops.ingestion_runs
                    SET run_status = 'SUCCESS',
                        rows_read = %s,
                        rows_saved = %s,
                        rows_skipped = %s,
                        end_time_dt = %s
                    WHERE ingestion_run_id = %s
                    """,
                    (
                        run_context.stats.rows_read,
                        run_context.stats.rows_saved,
                        run_context.stats.rows_skipped,
                        time_function(),
                        run_context.ingestion_run_id,
                    ),
                )
                connection.commit()
            except Exception as main_error:
                try:
                    connection.rollback()
                    with connection.transaction():
                        if on_failure is not None:
                            try:
                                with connection.transaction():
                                    on_failure(connection, run_context, main_error)
                            except Exception as quarantine_exception:
                                logging.error(
                                    "Quarantine pipeline failed: pipeline_name: %s run_uuid: %s error: %s",
                                    name, run_context.ingestion_run_id, type(quarantine_exception).__name__
                                )
                        cur.execute("""UPDATE ops.ingestion_runs
                        SET run_status = 'FAILED',
                        rows_saved = 0,
                        rows_skipped = %s,
                        rows_read = %s,
                        end_time_dt = %s,
                        error_cause = %s
                        WHERE ingestion_run_id = %s""", (
                            run_context.stats.rows_skipped,
                            run_context.stats.rows_read,
                            time_function(),
                            str(main_error),
                            run_context.ingestion_run_id,))
                except Exception as inner_error:
                    logging.error(
                        "Audit pipeline failed: " \
                        " pipeline_name: %s" \
                        " run_uuid: %s" \
                        " error: %s",
                        name, run_context.ingestion_run_id, type(inner_error).__name__
                    )
                raise
    finally:
        connection.close()
