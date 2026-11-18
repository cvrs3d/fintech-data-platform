import os
from functools import wraps
from datetime import datetime, timezone
import dotenv
import psycopg

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def create_connection() -> psycopg.Connection:
    dotenv.load_dotenv()

    return psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
        autocommit=False,
    )


def with_connection(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        connection = create_connection()

        try:
            return func(connection, *args, **kwargs)
        finally:
            connection.close()

    return wrapper