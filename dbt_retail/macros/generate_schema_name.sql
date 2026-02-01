-- macros/generate_schema_name.sql
--
-- By default, dbt generates schema names like "staging_dev_marts_dev" (concatenating
-- the profile dataset + the model schema). We override this so that:
--   - Models with a custom schema go EXACTLY to that schema (e.g., "marts_dev")
--   - Models without a custom schema stay in the profile default dataset (e.g., "staging_dev")
--
-- This means staging views → staging_dev, mart tables → marts_dev.

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is not none -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ target.dataset }}
    {%- endif -%}
{%- endmacro %}
