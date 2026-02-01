-- stg_exchange_rates.sql
-- Materialized: view
--
-- Cleans exchange rate records.
-- Deduplicates to one rate per currency per day (latest fetch wins).

WITH source AS (

    SELECT * FROM {{ source('raw', 'raw_exchange_rates') }}

),

deduplicated AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY currency_code, rate_date
            ORDER BY fetched_at DESC
        ) AS _row_num

    FROM source

),

cleaned AS (

    SELECT
        UPPER(TRIM(currency_code))          AS currency_code,
        CAST(rate_to_usd AS FLOAT64)        AS rate_to_usd,
        UPPER(TRIM(base_currency))          AS base_currency,
        CAST(rate_date AS DATE)             AS rate_date,
        CAST(fetched_at AS TIMESTAMP)       AS fetched_at,
        pipeline_run_id

    FROM deduplicated
    WHERE _row_num = 1

)

SELECT * FROM cleaned
