-- int_orders_enriched.sql
-- Materialized: ephemeral (CTE — not persisted)
--
-- Enriches orders with:
--   • USD-converted amounts via exchange rates
--   • A stale-rate flag for orders where FX rate is > 1 day old

WITH orders AS (

    SELECT * FROM {{ ref('stg_orders') }}

),

exchange_rates AS (

    SELECT * FROM {{ ref('stg_exchange_rates') }}

),

enriched AS (

    SELECT
        o.order_id,
        o.customer_id,
        o.product_id,
        o.store_key,
        o.quantity,
        o.unit_price_local,
        o.currency_code,
        CAST(o.order_date AS DATE)                              AS order_date,
        o.pipeline_run_id,

        -- Exchange rate lookup
        COALESCE(ex.rate_to_usd, 1.0)                          AS rate_to_usd,
        o.unit_price_local * COALESCE(ex.rate_to_usd, 1.0)     AS unit_price_usd,
        o.quantity * o.unit_price_local * COALESCE(ex.rate_to_usd, 1.0)
                                                                AS total_amount_usd,

        -- Flag stale rates (no rate found for the exact order date)
        CASE
            WHEN ex.rate_to_usd IS NULL THEN TRUE
            ELSE FALSE
        END                                                     AS rate_is_stale

    FROM orders o
    LEFT JOIN exchange_rates ex
        ON o.currency_code = ex.currency_code
        AND CAST(o.order_date AS DATE) = ex.rate_date

)

SELECT * FROM enriched
