import psycopg
from uuid import UUID, uuid4
from datetime import datetime, timezone
from decimal import Decimal
import dotenv
import os

def create_transfer(
    from_account_id: int,
    to_account_id: int,
    amount: Decimal,
    idempotency_key: UUID, 
) -> UUID:

        if not amount.is_finite():
            raise ValueError("Amount must be finite")
        
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if amount.as_tuple().exponent < -2:
            raise ValueError("Amount must have at most two decimal places")

        if from_account_id == to_account_id:
            raise ValueError("Accounts must be different")

        transaction_id = uuid4()

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
                cur.execute("SELECT account_id, currency_id FROM source.accounts WHERE account_id=%s", (from_account_id,))
                record1 = cur.fetchone()
                cur.execute("SELECT account_id, currency_id FROM source.accounts WHERE account_id=%s", (to_account_id,))
                record2 = cur.fetchone()
                    
                if record1 is None:
                    raise ValueError("Source account does not exist")

                if record2 is None:
                    raise ValueError("Destination account does not exist")

                if record1[1] != record2[1]:
                    raise ValueError("Account currencies must match")

                cur.execute("""INSERT INTO source.transfer_requests ( 
                    idempotency_key,
                    transaction_id, 
                    from_account_id, 
                    to_account_id, 
                    amount 
                ) 
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                RETURNING transaction_id;""", (
                    idempotency_key,
                    transaction_id, 
                    from_account_id,
                    to_account_id,
                    amount
                ))
                transfer_req = cur.fetchone()
                if transfer_req is None:
                    cur.execute("""SELECT from_account_id, to_account_id, amount, transaction_id
                        FROM source.transfer_requests
                        WHERE idempotency_key=%s""", (idempotency_key,))
                    result = cur.fetchone()
                    if result[0] == from_account_id and result[1] == to_account_id and result[2] == amount:
                        transaction_id = result[3]
                    else:
                        raise ValueError("Key is already in use with different parameters. Cannot change existing request.")
                else:
                    dt = datetime.now(timezone.utc)
                    cur.execute("INSERT INTO source.entries (transaction_id, account_id, amount, executed_at_dt) VALUES (%s, %s, %s, %s)", 
                    (transaction_id, from_account_id, -amount, dt))
                    cur.execute("INSERT INTO source.entries (transaction_id, account_id, amount, executed_at_dt) VALUES (%s, %s, %s, %s)", 
                    (transaction_id, to_account_id, amount, dt))
        
        return transaction_id
            


