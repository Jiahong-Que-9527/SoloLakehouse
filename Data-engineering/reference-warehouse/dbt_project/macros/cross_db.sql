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

{#- ---------------------------------------------------------------------
    E06: snapshot target schema. dbt snapshot `target_schema` is used
    directly (not routed through generate_schema_name), so on BigQuery it
    must name the Terraform-managed de_mart dataset; DuckDB keeps the
    E02-frozen name. -#}
{% macro snapshot_target_schema() -%}
    {%- if target.type == 'bigquery' -%}de_mart{%- else -%}mart{%- endif -%}
{%- endmacro %}

{#- ---------------------------------------------------------------------
    E06: BigQuery contract support.
    The E03-frozen contract data_types are DuckDB-canonical (`varchar`,
    `bigint`, `decimal(p,s)`). BigQuery rejects `varchar` outright
    ("Type not found: varchar"), so the two contract-check macros that
    execute SQL carrying those type names are dispatched per-adapter:

    - bigquery__get_empty_schema_sql: the contract validation probe runs
      `cast(null as <data_type>)` per column; translate varchar -> string.
    - bigquery__get_table_columns_and_constraints: CREATE TABLE uses the
      typed column list verbatim; same single translation.
    - bigquery__format_column: normalizes both sides of the name/type
      comparison (case, numeric parameterization) so the query-inferred
      schema and the yaml schema compare equal on BigQuery. DuckDB keeps
      the strict E03 path untouched.
   --------------------------------------------------------------------- #}

{% macro bq_contract_type(data_type) -%}
    {%- set dt = data_type | string | lower | trim -%}
    {%- if dt.startswith('varchar') -%}
        string
    {%- elif dt.startswith('bigint') or dt.startswith('integer') or dt == 'int' or dt.startswith('int64') -%}
        int64
    {%- elif dt.startswith('boolean') or dt == 'bool' -%}
        bool
    {%- elif dt.startswith('decimal') or dt.startswith('numeric') -%}
        {#- BQ: parameterized NUMERIC is legal in typed column lists but NOT
            inside CAST subqueries; the query-inferred side carries no params
            either, so compare scale-free on BigQuery (DuckDB stays strict). -#}
        numeric
    {%- else -%}
        {{ dt }}
    {%- endif -%}
{%- endmacro %}

{% macro bigquery__get_empty_schema_sql(columns) %}
    {%- set col_err = [] -%}
    {%- set col_naked_numeric = [] -%}
    select
    {% for i in columns %}
      {%- set col = columns[i] -%}
      {%- if col['data_type'] is not defined -%}
        {%- do col_err.append(col['name']) -%}
      {%- elif col['data_type'].strip().lower() in ('numeric', 'decimal', 'number') -%}
        {%- do col_naked_numeric.append(col['name']) -%}
      {%- endif -%}
      {% set col_name = adapter.quote(col['name']) if col.get('quote') else col['name'] %}
      {{ cast('null', bq_contract_type(col['data_type'])) }} as {{ col_name }}{{ ", " if not loop.last }}
    {%- endfor -%}
    {%- if (col_err | length) > 0 -%}
      {{ exceptions.column_type_missing(column_names=col_err) }}
    {%- elif (col_naked_numeric | length) > 0 -%}
      {{ exceptions.warn("Detected columns with numeric type and unspecified precision/scale, this can lead to unintended rounding: " ~ col_naked_numeric ~ "`") }}
    {%- endif -%}
{% endmacro %}

{% macro bigquery__get_table_columns_and_constraints() %}
  {#- Same shape as the default: rendered column constraints + model-level
      constraints, with BigQuery type names (only `varchar` is invalid on BQ). -#}
    {%- set raw_column_constraints = adapter.render_raw_columns_constraints(raw_columns=model['columns']) -%}
    {%- set raw_model_constraints = adapter.render_raw_model_constraints(raw_constraints=model['constraints']) -%}
    (
    {% for c in raw_column_constraints -%}
      {{ c | replace(' varchar', ' string') | replace(' bigint', ' int64') | replace(' integer', ' int64') | replace(' boolean', ' bool') | replace(' decimal(', ' numeric(') }}{{ "," if not loop.last or raw_model_constraints }}
    {% endfor -%}
    {% for c in raw_model_constraints -%}
      {{ c }}{{ "," if not loop.last }}
    {% endfor -%}
    )
{% endmacro %}

{% macro bigquery__format_column(column) -%}
  {#- bq_contract_type already strips numeric parameterization; normalize case. -#}
  {%- set dt = (bq_contract_type(column.dtype) | trim | lower) -%}
  {%- set formatted = column.column.lower() ~ " " ~ dt -%}
  {{ return({'name': column.name, 'data_type': dt, 'formatted': formatted}) }}
{%- endmacro -%}


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
