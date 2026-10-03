BEGIN;
INSERT INTO source.entries (transaction_id, account_id, amount, executed_at_dt)
VALUES (
    '3ef2db84-fc26-4249-956e-26f0a7f9ab41',
    1,
    -50,
    NOW()
);
INSERT INTO source.entries (transaction_id, account_id, amount, executed_at_dt)
VALUES (
    '3ef2db84-fc26-4249-956e-26f0a7f9ab41',
    2,
    0,
    NOW()
);
COMMIT;