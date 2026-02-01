# Data Dictionary

Gold-layer star schema tables in BigQuery `marts` dataset.

## fact_orders

| Column | Type | Nullable | Description | Source |
|--------|------|----------|-------------|--------|
| order_id | INT64 | No | Unique order identifier from POS system | CDC simulator |
| customer_id | INT64 | No | FK to dim_customers | CDC simulator |
| store_key | STRING | No | FK to dim_store | CDC simulator |
| product_id | INT64 | No | FK to dim_products | CDC simulator |
| date_key | INT64 | No | FK to dim_date (YYYYMMDD format) | Derived |
| currency_code | STRING | No | FK to dim_currency (ISO 4217) | CDC simulator |
| quantity | INT64 | No | Number of units in this order | CDC simulator |
| unit_price_local | FLOAT64 | No | Price per unit in local currency | CDC simulator |
| rate_to_usd | FLOAT64 | No | Exchange rate applied (local → USD) | Exchange Rates API |
| unit_price_usd | FLOAT64 | No | unit_price_local × rate_to_usd | Derived |
| total_amount_usd | FLOAT64 | No | quantity × unit_price_usd | Derived |
| rate_is_stale | BOOL | No | TRUE if FX rate was not found for exact date | Derived |
| order_date | DATE | No | Date the order was placed | CDC simulator |
| pipeline_run_id | STRING | No | UUID of the pipeline run that loaded this row | Pipeline |

**Partition:** `order_date` (DATE, daily)
**Cluster:** `store_key`, `product_id`

## dim_customers

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| customer_id | INT64 | No | Primary key |
| name | STRING | No | Full name |
| email | STRING | No | Email address |
| city | STRING | Yes | City |
| country | STRING | No | ISO 3166-1 alpha-2 country code |
| signup_date | DATE | Yes | Account creation date |
| customer_segment | STRING | No | Bronze / Silver / Gold / Platinum |
| total_orders | INT64 | No | Lifetime order count |
| lifetime_value_usd | FLOAT64 | No | Sum of all order totals in USD |
| first_order_date | DATE | Yes | Earliest order |
| last_order_date | DATE | Yes | Most recent order |
| days_since_last_order | INT64 | Yes | Recency metric |

## dim_products

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| product_id | INT64 | No | Primary key |
| product_name | STRING | No | Display name |
| category | STRING | No | Top-level category |
| subcategory | STRING | No | Sub-category |
| brand | STRING | Yes | Brand name (from supplier catalog) |
| supplier_id | INT64 | Yes | FK to supplier (from catalog) |
| unit_cost | FLOAT64 | Yes | Wholesale cost (from catalog) |

## dim_date

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| date_key | INT64 | No | PK — YYYYMMDD integer |
| full_date | DATE | No | Calendar date |
| year | INT64 | No | 4-digit year |
| quarter | INT64 | No | 1-4 |
| month | INT64 | No | 1-12 |
| month_name | STRING | No | Full month name |
| week_of_year | INT64 | No | ISO week number |
| day_of_month | INT64 | No | 1-31 |
| day_of_week | INT64 | No | 1 (Sun) - 7 (Sat) |
| day_name | STRING | No | Full day name |
| is_weekend | BOOL | No | TRUE for Saturday/Sunday |

## dim_currency

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| currency_code | STRING | No | PK — ISO 4217 3-letter code |
| latest_rate_to_usd | FLOAT64 | No | Most recent exchange rate |
| rate_as_of | DATE | No | Date of the rate |

## dim_store

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| store_key | STRING | No | PK — e.g. "S-001" |
| store_name | STRING | No | Display name |
| city | STRING | No | City |
| region | STRING | No | Geographic region |
| country | STRING | No | ISO country code |
