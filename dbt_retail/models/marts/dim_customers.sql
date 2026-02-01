-- dim_customers.sql
-- Materialized: table (full refresh — small table)
--
-- SCD Type 1: always reflects the latest customer state.
-- Enriched with order stats from int_customer_segments.

SELECT
    customer_id,
    name,
    email,
    city,
    country,
    signup_date,
    customer_segment,
    total_orders,
    lifetime_value_usd,
    first_order_date,
    last_order_date,
    days_since_last_order

FROM {{ ref('int_customer_segments') }}
