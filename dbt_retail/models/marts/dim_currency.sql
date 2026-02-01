-- dim_currency.sql
-- Materialized: table (full refresh — small table)
--
-- One row per currency code with the most recent exchange rate.

WITH latest_rates AS (

    SELECT
        currency_code,
        rate_to_usd,
        rate_date,
        ROW_NUMBER() OVER (
            PARTITION BY currency_code
            ORDER BY rate_date DESC
        ) AS _row_num

    FROM {{ ref('stg_exchange_rates') }}

)

SELECT
    currency_code,
    rate_to_usd AS latest_rate_to_usd,
    rate_date   AS rate_as_of

FROM latest_rates
WHERE _row_num = 1
