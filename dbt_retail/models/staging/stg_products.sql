-- stg_products.sql
-- Materialized: view
--
-- Derives the product dimension from order + supplier catalog data.
-- Takes the most recent attributes per product_id.

WITH from_orders AS (

    SELECT DISTINCT
        CAST(product_id AS INT64) AS product_id,
        product_name,
        category,
        subcategory

    FROM {{ source('raw', 'raw_orders') }}
    WHERE product_id IS NOT NULL

),

from_supplier AS (

    SELECT
        CAST(product_id AS INT64) AS product_id,
        product_name,
        category,
        subcategory,
        brand,
        CAST(supplier_id AS INT64) AS supplier_id,
        CAST(unit_cost AS FLOAT64) AS unit_cost

    FROM {{ source('raw', 'raw_supplier_catalog') }}

),

combined AS (

    SELECT
        COALESCE(s.product_id, o.product_id) AS product_id,
        COALESCE(s.product_name, o.product_name) AS product_name,
        COALESCE(s.category, o.category) AS category,
        COALESCE(s.subcategory, o.subcategory) AS subcategory,
        s.brand,
        s.supplier_id,
        s.unit_cost

    FROM from_orders o
    FULL OUTER JOIN from_supplier s
        ON o.product_id = s.product_id

)

SELECT * FROM combined
