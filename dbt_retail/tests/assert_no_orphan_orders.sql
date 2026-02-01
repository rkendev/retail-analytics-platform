-- tests/assert_no_orphan_orders.sql
-- Fails if any fact_orders row references a customer not in dim_customers.

SELECT f.order_id, f.customer_id
FROM {{ ref('fact_orders') }} f
LEFT JOIN {{ ref('dim_customers') }} c
    ON f.customer_id = c.customer_id
WHERE c.customer_id IS NULL
