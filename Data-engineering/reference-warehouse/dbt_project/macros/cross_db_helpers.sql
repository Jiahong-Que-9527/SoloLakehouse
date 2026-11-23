{# Reusable project macros (E05). Dialect branches live here (contract §3.9):
   models stay engine-agnostic. #}

{% macro eur_currency_convert(amount_local, fx_rate) -%}
    {#- Local currency -> EUR, single division, half-up 2dp, exact money
        (contract §3.3). DuckDB and BigQuery both return DOUBLE for DECIMAL
        division, hence the final cast. -#}
    cast(round({{ amount_local }} / {{ fx_rate }}, 2) as decimal(18, 2))
{%- endmacro %}


{% macro incremental_lookback_filter(column_name, days) -%}
    {#- 48-hour late-arrival watermark (contract §3.5) with a bounded-backfill
        override. Emits a WHERE fragment; only valid inside is_incremental().
        The watermark aggregate uses the bare column name — a table-qualified
        aggregate breaks under dbt unit-test rendering. -#}
    {%- set bare = column_name.split('.')[-1] -%}
    {%- if var('backfill_start', none) and var('backfill_end', none) -%}
    where {{ column_name }} >= cast('{{ var("backfill_start") }}' as timestamp)
      and {{ column_name }} < cast('{{ var("backfill_end") }}' as timestamp)
    {%- else -%}
    where {{ column_name }} >= (select {{ dbt.dateadd('day', days * -1, 'max(' ~ bare ~ ')') }} from {{ this }})
    {%- endif -%}
{%- endmacro %}


{% macro target_partition_config(field, data_type, cluster_fields) -%}
    {#- BigQuery partition/cluster config (E06); no-op on other adapters so the
        SQL stays 100% unified (contract §3.9). -#}
    {%- if target.type == 'bigquery' -%}
        {{ return({
            'partition_by': {
                'field': field,
                'data_type': data_type,
                'granularity': 'day',
            },
            'cluster_by': cluster_fields,
            'require_partition_filter': True,
        }) }}
    {%- else -%}
        {{ return({}) }}
    {%- endif -%}
{%- endmacro %}
