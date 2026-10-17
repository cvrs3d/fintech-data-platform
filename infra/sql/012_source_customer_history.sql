CREATE TABLE source.customer_history (
    source_customer_version_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id INT NOT NULL,
    first_name VARCHAR(50) NOT NULL, -- first name of a client should be long in case of nation specific long name like african
    last_name VARCHAR(50) NOT NULL, -- last name
    birth_date DATE NOT NULL, -- birth date
    death_date DATE CHECK(birth_date <= death_date), -- date of death
    registered_at_dt DATE NOT NULL, -- date of client registration 
    updated_at_dt TIMESTAMPTZ NOT NULL, -- time when client was updated 
    created_at_dt TIMESTAMPTZ NOT NULL, -- time when client record was published in the system
    effective_from_dt TIMESTAMPTZ NOT NULL,
    recorded_at_dt TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION source.log_customer_version() 
RETURNS trigger 
AS $$
BEGIN
    INSERT INTO source.customer_history (
        customer_id, 
        first_name,
        last_name,
        birth_date,
        death_date,
        registered_at_dt,
        updated_at_dt,
        created_at_dt,
        effective_from_dt
    ) VALUES (
        NEW.customer_id,
        NEW.first_name,
        NEW.last_name,
        NEW.birth_date,
        NEW.death_date,
        NEW.registered_at_dt,
        NEW.updated_at_dt,
        NEW.created_at_dt,
        clock_timestamp()
    );

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER cust_insert_hist 
    AFTER INSERT ON source.customers 
    FOR EACH ROW 
    EXECUTE FUNCTION source.log_customer_version();

CREATE TRIGGER cust_update_hist
    AFTER UPDATE ON source.customers 
    FOR EACH ROW 
    WHEN (
        ROW(OLD.first_name, OLD.last_name, OLD.birth_date, OLD.death_date, OLD.registered_at_dt)
        IS DISTINCT FROM 
        ROW(NEW.first_name, NEW.last_name, NEW.birth_date, NEW.death_date, NEW.registered_at_dt)
    )
    EXECUTE FUNCTION source.log_customer_version();

-- Initial snapshot 
INSERT INTO source.customer_history (
    customer_id, 
    first_name,
    last_name,
    birth_date,
    death_date,
    registered_at_dt,
    updated_at_dt,
    created_at_dt,
    effective_from_dt
) SELECT 
    customer_id, 
    first_name,
    last_name,
    birth_date,
    death_date,
    registered_at_dt,
    updated_at_dt,
    created_at_dt,
    clock_timestamp()
FROM source.customers;