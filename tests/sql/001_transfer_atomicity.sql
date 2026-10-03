BEGIN;
INSERT INTO source.entries (entry_id, transaction_id, account_id, amount, executed_at_dt)
VALUES (
    3,
    'ATOMIC_FAIL',
    1,
    -50,
    NOW()
);
INSERT INTO source.entries (entry_id, transaction_id, account_id, amount, executed_at_dt)
VALUES (
    4,
    'ATOMIC_FAIL',
    2,
    0,
    NOW()
);
COMMIT;