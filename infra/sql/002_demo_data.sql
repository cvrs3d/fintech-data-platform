
-- DML

INSERT INTO source.customers (
    customer_id, first_name, last_name, birth_date, registered_at_dt
)
VALUES (
    1, 'John', 'Doe', DATE '1993-01-01', CURRENT_DATE
);
INSERT INTO source.customers (
    customer_id, first_name, last_name, birth_date, registered_at_dt
)
VALUES (
    2, 'Sarah', 'Doe', DATE '1993-01-01', CURRENT_DATE
);
INSERT INTO source.currency (
    currency_id, currency_code, registered_at_dt
)
VALUES (
    1, 'EUR', CURRENT_DATE
);

INSERT INTO source.accounts (account_id, currency_id, customer_id, registered_at_dt)
VALUES (
    1, 1, 1, CURRENT_DATE
);

INSERT INTO source.accounts (account_id, currency_id, customer_id, registered_at_dt)
VALUES (
    2, 1, 2, CURRENT_DATE
);

BEGIN TRANSACTION;

INSERT INTO source.entries (entry_id, transaction_id, account_id, amount, executed_at_dt)
VALUES (
    1, 'DUMMY', 1, -100, NOW()
);
INSERT INTO source.entries (entry_id, transaction_id, account_id, amount, executed_at_dt)
VALUES (
    2, 'DUMMY', 2, 100, NOW()
);
COMMIT;