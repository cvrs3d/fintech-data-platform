import psycopg
import os 
import dotenv 
import uuid

def with_connection(f):
    def with_connection_(*args, **kwargs):
        dotenv.load_dotenv()
        dbname = os.environ["POSTGRES_DB"]
        user = os.environ["POSTGRES_USER"]
        password = os.environ["POSTGRES_PASSWORD"]

        cnn = psycopg.connect(
            host="127.0.0.1",
            port=5432,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5,
        )
        try:
            rv = f(cnn, *args, **kwargs)
        except Exception:
            cnn.rollback()
            raise
        else:
            cnn.commit() # or maybe not
        finally:
            cnn.close()

        return rv

    return with_connection_

@with_connection
def ingestion(cnn):
    
    ingestion_run_id = uuid.uuid4()

    with cnn.cursor() as cur:
        
        cur.execute("SELECT entry_id, transaction_id, account_id, amount, created_at_dt, executed_at_dt FROM source.entries")
        source_rows = cur.fetchall()

        for source_row in source_rows:
            source_entry_id = source_row[0]
            cur.execute("SELECT entry_id, transaction_id, account_id, amount, created_at_dt, executed_at_dt FROM raw.entries WHERE entry_id=%s", (source_entry_id,))
            raw_row = cur.fetchone()

            if raw_row is None:
                cur.execute(
                    """
                    INSERT INTO raw.entries (
                        entry_id,
                        transaction_id,
                        account_id,
                        amount,
                        created_at_dt,
                        executed_at_dt,
                        ingestion_run_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (*source_row, ingestion_run_id),
                )
            elif source_row == raw_row:
                # Same data
                continue
            else:
                raise ValueError(f"Conflicting entry. Entry ID: {source_entry_id}")

if __name__ == "__main__":
    ingestion()