{# Copied from template/dbt_project/macros/cross_db.sql during onboarding;
   generates clean verbatim schema names (stg/mart/raw) on DuckDB. #}

{% macro decimal_type(precision, scale) -%}
    {%- if target.type == 'bigquery' -%}
        numeric({{ precision }}, {{ scale }})
    {%- else -%}
        decimal({{ precision }}, {{ scale }})
    {%- endif -%}
{%- endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
