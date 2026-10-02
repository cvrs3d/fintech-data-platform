-- DDL

CREATE SCHEMA IF NOT EXISTS source;


CREATE TABLE source.customers (
    customer_id INT PRIMARY KEY, -- business key 
    first_name VARCHAR(50) NOT NULL, -- first name of a client should be long in case of nation specific long name like african
    last_name VARCHAR(50) NOT NULL, -- last name
    birth_date DATE NOT NULL, -- birth date
    death_date DATE CHECK(birth_date <= death_date), -- date of death
    registered_at_dt DATE NOT NULL, -- date of client registration 
    updated_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- time when client was updated 
    created_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL -- time when client record was published in the system
);
CREATE TABLE source.currency (
    currency_id INT PRIMARY KEY,
    currency_code VARCHAR(3) UNIQUE NOT NULL,
    registered_at_dt DATE NOT NULL,
    updated_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL
);
CREATE TABLE source.accounts (
    account_id INT PRIMARY KEY, -- business key 
    currency_id INT NOT NULL, -- is foreign key  refrences source.currency
    customer_id INT NOT NULL, -- foreign key refernec source.customer
    registered_at_dt DATE NOT NULL, -- date when account was registred
    created_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- created at timestamp
    updated_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- updated at ts

    FOREIGN KEY (customer_id) REFERENCES source.customers(customer_id),
    FOREIGN KEY (currency_id) REFERENCES source.currency(currency_id)
);
-- Yes there will be no counterparty only entries on the one specific account 
CREATE TABLE source.entries (
    entry_id INT PRIMARY KEY, -- pk
    transaction_id VARCHAR(16) NOT NULL, -- buisness transaction number
    account_id INT NOT NULL, -- money entry account 
    amount NUMERIC(18, 2) NOT NULL CHECK(amount <> 0.00), -- amount of entry
    created_at_dt TIMESTAMPTZ DEFAULT NOW() NOT NULL, -- created in db at timestamp
    executed_at_dt TIMESTAMPTZ NOT NULL, -- date when transaction was executed by bank

    FOREIGN KEY (account_id) REFERENCES source.accounts(account_id)
);