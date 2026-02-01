-- tests/assert_positive_revenue.sql
-- Fails if any order has negative total revenue in USD.

SELECT order_id, total_amount_usd
FROM {{ ref('fact_orders') }}
WHERE total_amount_usd < 0
