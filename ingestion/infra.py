import psycopg
import os 
import dotenv 

def with_connection(f):
    def with_connection_(*args, **kwargs):
        dotenv.load_dotenv()
        dbname = os.environ["POSTGRES_DB"]
        user = os.environ["POSTGRES_USER"]
        password = os.environ["POSTGRES_PASSWORD"]

        cnn = psycopg.connect(
            host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=5,
        )
        try:
            return f(cnn, *args, **kwargs)
        finally:
            cnn.close()

    return with_connection_