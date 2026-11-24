{# Cross-database helper pattern (E05 convention): never cast decimals or
   compute dates with vendor syntax inline — route them through macros so the
   same model runs on duckdb and bigquery. Extend this file with the helpers
   your domain needs; see the primary warehouse's macros/cross_db.sql for the
   full catalogue (eur_currency_convert, incremental_lookback_filter,
   target_partition_config, to_berlin_date, ...). #}

{% macro decimal_type(precision, scale) -%}
    {%- if target.type == 'bigquery' -%}
        numeric({{ precision }}, {{ scale }})
    {%- else -%}
        decimal({{ precision }}, {{ scale }})
    {%- endif -%}
{%- endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- E02 convention: custom schemas (stg/mart/raw/...) are used verbatim on
        DuckDB, so relations live in `stg`, `mart`, `raw` — not dbt's default
        `<profile>_<custom>` concatenation. Add a BigQuery branch (E06
        pattern: Terraform-managed dataset prefix) only when the domain
        earns a cloud target. -#}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
