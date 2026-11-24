{# Cross-warehouse helpers (contract §3.9): every dialect branch lives here, models stay engine-agnostic. #}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {#- E06: on BigQuery, custom schemas land in the Terraform-managed de_* datasets
        (de_raw/de_stg/de_int/de_mart, design §4); models without a custom schema
        (the E04 snapshots) stay in the profile's target dataset (de_mart).
        DuckDB keeps the E02-frozen schema names verbatim. Naming config only —
        zero business-SQL change (contract §3.9). -#}
    {%- if target.type == 'bigquery' -%}
        {%- if custom_schema_name is none -%}
            {{ target.schema }}
        {%- else -%}
            de_{{ custom_schema_name | trim }}
        {%- endif -%}
    {%- else -%}
        {%- if custom_schema_name is none -%}
            {{ target.schema }}
        {%- else -%}
            {{ custom_schema_name | trim }}
        {%- endif -%}
    {%- endif -%}
{%- endmacro %}


{% macro to_berlin_date(column) -%}
    {#- Civil date of a naive-UTC timestamp in Europe/Berlin (contract §3.4). -#}
    {%- if target.type == 'duckdb' -%}
        cast(({{ column }} at time zone 'UTC') at time zone 'Europe/Berlin' as date)
    {%- elif target.type == 'bigquery' -%}
        date({{ column }}, 'Europe/Berlin')
    {%- else -%}
        {{ exceptions.raise_compiler_error("to_berlin_date: unsupported adapter " ~ target.type) }}
    {%- endif -%}
{%- endmacro %}


{% macro iso_day_of_week(column) -%}
    {#- ISO weekday, 1 = Monday .. 7 = Sunday. -#}
    {%- if target.type == 'duckdb' -%}
        extract(isodow from {{ column }})
    {%- elif target.type == 'bigquery' -%}
        mod(extract(dayofweek from {{ column }}) + 5, 7) + 1
    {%- else -%}
        {{ exceptions.raise_compiler_error("iso_day_of_week: unsupported adapter " ~ target.type) }}
    {%- endif -%}
{%- endmacro %}


{% macro date_spine(start_date, end_date) -%}
    {#- Inclusive daily date spine between two ISO dates. -#}
    {%- if target.type == 'duckdb' -%}
        select cast(d as date) as date_day
        from generate_series(cast('{{ start_date }}' as date), cast('{{ end_date }}' as date), interval 1 day) as t(d)
    {%- elif target.type == 'bigquery' -%}
        select date_day
        from unnest(generate_date_array(cast('{{ start_date }}' as date), cast('{{ end_date }}' as date))) as date_day
    {%- else -%}
        {{ exceptions.raise_compiler_error("date_spine: unsupported adapter " ~ target.type) }}
    {%- endif -%}
{%- endmacro %}


{% macro safe_divide(numerator, denominator) -%}
    {#- Null-safe division (contract §3.9); denominators of 0 yield null instead of an error. -#}
    case when {{ denominator }} is null or {{ denominator }} = 0 then null else {{ numerator }} / {{ denominator }} end
{%- endmacro %}
