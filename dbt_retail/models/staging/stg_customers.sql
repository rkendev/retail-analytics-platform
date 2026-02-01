-- stg_customers.sql
-- Materialized: view
--
-- Cleans and deduplicates customer records.
-- Keeps the most recently updated record per customer_id.

WITH source AS (

    SELECT * FROM {{ source('raw', 'raw_customers') }}

),

deduplicated AS (

    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY signup_date DESC
        ) AS _row_num

    FROM source

),

cleaned AS (

    SELECT
        CAST(customer_id AS INT64)    AS customer_id,
        TRIM(name)                    AS name,
        LOWER(TRIM(email))            AS email,
        TRIM(city)                    AS city,
        UPPER(TRIM(country))          AS country,
        CAST(signup_date AS DATE)     AS signup_date,
        TRIM(customer_segment)        AS customer_segment

    FROM deduplicated
    WHERE _row_num = 1

)

SELECT * FROM cleaned
