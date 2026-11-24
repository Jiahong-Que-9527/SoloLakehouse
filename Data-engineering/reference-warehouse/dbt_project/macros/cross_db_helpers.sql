{# Reusable project macros (E05). Dialect branches live here (contract §3.9):
   models stay engine-agnostic. #}

{% macro eur_currency_convert(amount_local, fx_rate) -%}
    {#- Local currency -> EUR, single division, half-up 2dp, exact money
        (contract §3.3). DuckDB and BigQuery both return DOUBLE for DECIMAL
        division, hence the final cast. -#}
    cast(round({{ amount_local }} / {{ fx_rate }}, 2) as {{ decimal_type(18, 2) }})
{%- endmacro %}


{% macro decimal_type(precision, scale) -%}
    {#- Cast-target for exact-money decimals (E06). BigQuery rejects
        parameterized CAST targets outright ("Parameterized types are not
        allowed in CAST expressions"); there the E06 typed-column-list
        contract re-applies the exact (p,s) at storage time. DuckDB keeps
        the E03-frozen decimal(p,s) verbatim. -#}
    {{- 'numeric' if target.type == 'bigquery' else 'decimal(' ~ precision ~ ', ' ~ scale ~ ')' -}}
{%- endmacro %}


{% macro as_timestamp(expr) -%}
    {#- Explicit bound cast for the SCD2 as-of joins (E06): BigQuery has no
        implicit TIMESTAMP/DATE comparison; DuckDB accepts the identical
        cast with unchanged midnight semantics. -#}
    cast({{ expr }} as timestamp)
{%- endmacro %}


{% macro incremental_lookback_filter(column_name, days) -%}
    {#- 48-hour late-arrival watermark (contract §3.5) with a bounded-backfill
        override. Emits a WHERE fragment; only valid inside is_incremental().
        The watermark aggregate uses the bare column name — a table-qualified
        aggregate breaks under dbt unit-test rendering.
        E06: on BigQuery the watermark subquery must itself satisfy the
        require_partition_filter guard on the target table; the constant
        `>= 1970-01-01` predicate prunes nothing away (every partition is
        newer) but is a valid partition-elimination filter. -#}
    {%- set bare = column_name.split('.')[-1] -%}
    {%- set partition = config.get('partition_by') if target.type == 'bigquery' else none -%}
    {%- if var('backfill_start', none) and var('backfill_end', none) -%}
    where {{ column_name }} >= cast('{{ var("backfill_start") }}' as timestamp)
      and {{ column_name }} < cast('{{ var("backfill_end") }}' as timestamp)
    {%- else -%}
    where {{ column_name }} >= (
        select {{ as_timestamp(dbt.dateadd('day', days * -1, 'max(' ~ bare ~ ')')) }}
        from {{ this }}
        {%- if partition %}
        where {{ partition['field'] }} >= date '1970-01-01'
        {%- endif %}
    )
    {%- endif -%}
{%- endmacro %}


{% macro target_partition_config(field, data_type, cluster_fields) -%}
    {#- BigQuery partition/cluster config (E06); no-op on other adapters so the
        SQL stays 100% unified (contract §3.9).
        E06 note: require_partition_filter was evaluated and deliberately NOT
        set — it is incompatible with dbt's data tests, which legitimately
        scan the whole table and cannot carry a partition predicate. The
        enforced cost guard is instead the profile-level
        maximum_bytes_billed cap (100 MiB per query, profiles.yml) plus
        partition pruning when queries do filter (verified via
        INFORMATION_SCHEMA.JOBS bytes_billed). -#}
    {%- if target.type == 'bigquery' -%}
        {{ return({
            'partition_by': {
                'field': field,
                'data_type': data_type,
                'granularity': 'day',
            },
            'cluster_by': cluster_fields,
        }) }}
    {%- else -%}
        {{ return({}) }}
    {%- endif -%}
{%- endmacro %}
