-- stg_supplier_catalog.sql
-- Materialized: view
--
-- Cleans supplier catalog records from CSV file drops.

WITH source AS (

    SELECT * FROM {{ source('raw', 'raw_supplier_catalog') }}

),

cleaned AS (

    SELECT
        CAST(product_id AS INT64)       AS product_id,
        TRIM(product_name)              AS product_name,
        TRIM(category)                  AS category,
        TRIM(subcategory)               AS subcategory,
        TRIM(brand)                     AS brand,
        CAST(supplier_id AS INT64)      AS supplier_id,
        CAST(unit_cost AS FLOAT64)      AS unit_cost,
        source_file,
        pipeline_run_id

    FROM source
    WHERE product_id IS NOT NULL

)

SELECT * FROM cleaned
