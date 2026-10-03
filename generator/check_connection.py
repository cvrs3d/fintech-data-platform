import psycopg
import dotenv
import os

def main():
    dotenv.load_dotenv()

    dbname = os.environ["POSTGRES_DB"]
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]

    
    with psycopg.connect(
        host="127.0.0.1",
        port=5432,
        dbname=dbname,
        user=user,
        password=password,
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user;")
            record = cur.fetchone()

    print(record)

if __name__ == "__main__":
	main()