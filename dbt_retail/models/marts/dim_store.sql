-- dim_store.sql
-- Materialized: table (full refresh — small table)
--
-- Store dimension derived from distinct store_key values in orders.
-- In production you'd source this from a master data system; here we
-- derive synthetic attributes from the key pattern.

WITH distinct_stores AS (

    SELECT DISTINCT store_key
    FROM {{ ref('stg_orders') }}
    WHERE store_key IS NOT NULL

),

enriched AS (

    SELECT
        store_key,
        CONCAT('Store ', store_key)           AS store_name,
        -- Derive deterministic but realistic attributes from the key
        CASE MOD(ABS(FARM_FINGERPRINT(store_key)), 5)
            WHEN 0 THEN 'New York'
            WHEN 1 THEN 'London'
            WHEN 2 THEN 'Tokyo'
            WHEN 3 THEN 'São Paulo'
            WHEN 4 THEN 'Sydney'
        END                                     AS city,
        CASE MOD(ABS(FARM_FINGERPRINT(store_key)), 5)
            WHEN 0 THEN 'North America'
            WHEN 1 THEN 'Europe'
            WHEN 2 THEN 'Asia Pacific'
            WHEN 3 THEN 'Latin America'
            WHEN 4 THEN 'Asia Pacific'
        END                                     AS region,
        CASE MOD(ABS(FARM_FINGERPRINT(store_key)), 5)
            WHEN 0 THEN 'US'
            WHEN 1 THEN 'GB'
            WHEN 2 THEN 'JP'
            WHEN 3 THEN 'BR'
            WHEN 4 THEN 'AU'
        END                                     AS country

    FROM distinct_stores

)

SELECT * FROM enriched
