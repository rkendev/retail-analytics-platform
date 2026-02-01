-- dim_products.sql
-- Materialized: table (full refresh — small table)

SELECT
    product_id,
    product_name,
    category,
    subcategory,
    brand,
    supplier_id,
    unit_cost

FROM {{ ref('stg_products') }}
