-- stg_orders.sql
-- Materialized: view (always fresh from source)
--
-- Cleans and deduplicates raw order records:
--   • Casts types explicitly (no implicit coercion)
--   • Deduplicates by order_id — keeps the latest updated_at (CDC logic)
--   • Filters out future-dated orders as a safety net
WITH source AS (
    SELECT * FROM {{ source('raw', 'raw_orders') }}
),
deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY COALESCE(updated_at, order_date) DESC
        ) AS _row_num
    FROM source
),
cleaned AS (
    SELECT
        CAST(order_id AS INT64)               AS order_id,
        CAST(customer_id AS INT64)             AS customer_id,
        CAST(product_id AS INT64)              AS product_id,
        CAST(quantity AS INT64)                AS quantity,
        CAST(unit_price_local AS FLOAT64)      AS unit_price_local,
        UPPER(TRIM(currency_code))             AS currency_code,
        CAST(order_date AS TIMESTAMP)          AS order_date,
        TRIM(store_key)                        AS store_key,
        COALESCE(cdc_operation, 'I')           AS cdc_operation,
        COALESCE(updated_at, order_date)       AS updated_at,
        pipeline_run_id
    FROM deduplicated
    WHERE _row_num = 1
      AND CAST(order_date AS DATE) <= CURRENT_DATE()
      AND COALESCE(cdc_operation, 'I') != 'D'
)
SELECT * FROM cleaned
