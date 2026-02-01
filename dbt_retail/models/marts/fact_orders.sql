-- fact_orders.sql
-- Materialized: incremental (MERGE upsert on order_id)
-- Partition: order_date (DATE)
-- Cluster: store_key, product_id
--
-- The core fact table. One row per order line item.
-- Only processes new rows (order_date > max existing) on incremental runs.
-- Full refresh rebuilds the entire table.

{{ config(
    materialized='incremental',
    unique_key='order_id',
    partition_by={
        'field': 'order_date',
        'data_type': 'date',
        'granularity': 'day'
    },
    cluster_by=['store_key', 'product_id']
) }}

WITH enriched_orders AS (

    SELECT * FROM {{ ref('int_orders_enriched') }}

),

date_dim AS (

    SELECT * FROM {{ ref('dim_date') }}

),

final AS (

    SELECT
        o.order_id,
        o.customer_id,
        o.store_key,
        o.product_id,
        d.date_key,
        o.currency_code,
        o.quantity,
        o.unit_price_local,
        o.rate_to_usd,
        o.unit_price_usd,
        o.total_amount_usd,
        o.rate_is_stale,
        o.order_date,
        o.pipeline_run_id

    FROM enriched_orders o
    LEFT JOIN date_dim d
        ON o.order_date = d.full_date

    {% if is_incremental() %}
    WHERE o.order_date > (SELECT MAX(order_date) FROM {{ this }})
    {% endif %}

)

SELECT * FROM final
