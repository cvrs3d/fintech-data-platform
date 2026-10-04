CREATE TABLE source.transfer_requests (
    idempotency_key UUID PRIMARY KEY,
    transaction_id UUID NOT NULL,
    from_account_id INT NOT NULL,
    to_account_id INT NOT NULL CHECK(from_account_id<>to_account_id),
    amount DECIMAL(18,2) NOT NULL CHECK(amount > 0.00),
    created_at_dt TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_transfer_requests_transaction_id UNIQUE (transaction_id),
    FOREIGN KEY (from_account_id) REFERENCES source.accounts(account_id),
    FOREIGN KEY (to_account_id) REFERENCES source.accounts(account_id)
);