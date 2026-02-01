-- dim_date.sql
-- Materialized: table (full refresh)
--
-- Calendar date dimension covering 2023-01-01 through 2027-12-31.
-- Generated via a date spine — no external source required.

{{ config(materialized='table') }}

WITH date_spine AS (

    {{ dbt_date.get_date_dimension("2023-01-01", "2027-12-31") }}

)

SELECT
    CAST(FORMAT_DATE('%Y%m%d', date_day) AS INT64)   AS date_key,
    date_day                                          AS full_date,
    EXTRACT(YEAR FROM date_day)                       AS year,
    EXTRACT(QUARTER FROM date_day)                    AS quarter,
    EXTRACT(MONTH FROM date_day)                      AS month,
    FORMAT_DATE('%B', date_day)                        AS month_name,
    EXTRACT(WEEK FROM date_day)                       AS week_of_year,
    EXTRACT(DAY FROM date_day)                        AS day_of_month,
    EXTRACT(DAYOFWEEK FROM date_day)                  AS day_of_week,
    FORMAT_DATE('%A', date_day)                        AS day_name,
    CASE
        WHEN EXTRACT(DAYOFWEEK FROM date_day) IN (1, 7) THEN TRUE
        ELSE FALSE
    END                                                AS is_weekend

FROM date_spine
