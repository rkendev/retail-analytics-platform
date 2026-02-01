-- int_customer_segments.sql
-- Materialized: ephemeral
--
-- Enriches customer records with aggregated order stats for segmentation.

WITH customers AS (

    SELECT * FROM {{ ref('stg_customers') }}

),

order_stats AS (

    SELECT
        customer_id,
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(total_amount_usd)    AS lifetime_value_usd,
        MIN(order_date)          AS first_order_date,
        MAX(order_date)          AS last_order_date

    FROM {{ ref('int_orders_enriched') }}
    GROUP BY customer_id

),

enriched AS (

    SELECT
        c.*,
        COALESCE(os.total_orders, 0)             AS total_orders,
        COALESCE(os.lifetime_value_usd, 0.0)     AS lifetime_value_usd,
        os.first_order_date,
        os.last_order_date,
        DATE_DIFF(CURRENT_DATE(), os.last_order_date, DAY) AS days_since_last_order

    FROM customers c
    LEFT JOIN order_stats os
        ON c.customer_id = os.customer_id

)

SELECT * FROM enriched
