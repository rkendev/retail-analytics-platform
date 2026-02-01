# Data Contracts

Each data source has a Pydantic model that acts as the **contract** between the source system and the pipeline. Records that violate the contract are quarantined — they never enter the bronze layer.

## Orders (CDC)

**Source:** Faker CDC simulator (mimics PostgreSQL replication log)
**Contract:** `src/validators/OrderContract`

| Field | Type | Rules |
|-------|------|-------|
| `order_id` | int | > 0, required |
| `customer_id` | int | > 0, required |
| `product_id` | int | > 0, required |
| `quantity` | int | > 0, required |
| `unit_price_local` | float | > 0, required |
| `currency_code` | str | Exactly 3 uppercase letters (ISO 4217) |
| `order_date` | datetime | Required, cannot be in the future |
| `store_key` | str | Required |

**Schema evolution policy:** `extra='ignore'` — unknown fields from the source are silently dropped. If a *required* field is removed from the source, validation fails and the record is quarantined.

## Exchange Rates

**Source:** Open Exchange Rates REST API
**Contract:** `src/validators/ExchangeRateContract`

| Field | Type | Rules |
|-------|------|-------|
| `currency_code` | str | 3 uppercase letters |
| `rate_to_usd` | float | > 0 |
| `base_currency` | str | Default: "USD" |
| `rate_date` | str | ISO date string |

## Supplier Catalog

**Source:** CSV file drops in GCS bucket
**Contract:** `src/validators/SupplierCatalogContract`

| Field | Type | Rules |
|-------|------|-------|
| `product_id` | int | > 0 |
| `product_name` | str | Non-empty |
| `category` | str | Non-empty |
| `subcategory` | str | Non-empty |
| `brand` | str | Non-empty |
| `supplier_id` | int | > 0 |
| `unit_cost` | float | >= 0 |

## Customers

**Source:** Derived from CDC order data
**Contract:** `src/validators/CustomerContract`

| Field | Type | Rules |
|-------|------|-------|
| `customer_id` | int | > 0 |
| `name` | str | Non-empty |
| `email` | str | Any string (not validated as email) |
| `city` | str | Any |
| `country` | str | 2 uppercase letters (ISO 3166-1 alpha-2) |
| `signup_date` | str | ISO date string |
| `customer_segment` | str | Any |
