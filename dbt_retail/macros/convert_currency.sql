-- macros/convert_currency.sql
-- Reusable Jinja macro for currency conversion.
-- Usage: {{ convert_to_usd('unit_price_local', 'currency_code', 'order_date') }}

{% macro convert_to_usd(amount_column, currency_column, date_column) %}
    {{ amount_column }} * COALESCE(
        (
            SELECT ex.rate_to_usd
            FROM {{ ref('stg_exchange_rates') }} ex
            WHERE ex.currency_code = {{ currency_column }}
              AND ex.rate_date = CAST({{ date_column }} AS DATE)
            LIMIT 1
        ),
        1.0  -- Default to 1.0 (assume USD) if no rate found
    )
{% endmacro %}
