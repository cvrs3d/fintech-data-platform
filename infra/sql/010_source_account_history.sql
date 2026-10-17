CREATE TABLE source.account_history (
    source_account_version_id BIGINT
        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id INT NOT NULL,
    currency_id INT NOT NULL,
    customer_id INT NOT NULL,
    registered_at_dt DATE NOT NULL,
    created_at_dt TIMESTAMPTZ NOT NULL,
    updated_at_dt TIMESTAMPTZ NOT NULL,
    effective_from_dt TIMESTAMPTZ NOT NULL,
    recorded_at_dt TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION source.log_account_version()
RETURNS trigger
AS $$
BEGIN
    INSERT INTO source.account_history (
        account_id,
        currency_id,
        customer_id,
        registered_at_dt,
        created_at_dt,
        updated_at_dt,
        effective_from_dt
    )
    VALUES (
        NEW.account_id,
        NEW.currency_id,
        NEW.customer_id,
        NEW.registered_at_dt,
        NEW.created_at_dt,
        NEW.updated_at_dt,
        clock_timestamp()
    );

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER acc_insert_hist
    AFTER INSERT ON source.accounts
    FOR EACH ROW
    EXECUTE FUNCTION source.log_account_version();

CREATE TRIGGER acc_update_hist
    AFTER UPDATE ON source.accounts
    FOR EACH ROW
    WHEN (
        ROW(OLD.currency_id, OLD.customer_id, OLD.registered_at_dt)
        IS DISTINCT FROM
        ROW(NEW.currency_id, NEW.customer_id, NEW.registered_at_dt)
    )
    EXECUTE FUNCTION source.log_account_version();

-- Initial snapshot
INSERT INTO source.account_history (
    account_id,
    currency_id,
    customer_id,
    registered_at_dt,
    created_at_dt,
    updated_at_dt,
    effective_from_dt
)
SELECT
    account_id,
    currency_id,
    customer_id,
    registered_at_dt,
    created_at_dt,
    updated_at_dt,
    clock_timestamp()
FROM source.accounts;