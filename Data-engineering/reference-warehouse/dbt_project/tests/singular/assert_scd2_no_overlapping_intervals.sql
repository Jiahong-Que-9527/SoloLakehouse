-- SCD2 acceptance guard (E04): zero overlapping validity intervals per natural
-- key. The current version's dbt_valid_to is null — treated as open-ended.

with pairs as (
    select
        'station' as entity,
        a.station_id as natural_key,
        a.dbt_scd_id as version_a,
        b.dbt_scd_id as version_b
    from {{ ref('dim_stations_scd2') }} as a
    inner join {{ ref('dim_stations_scd2') }} as b
        on
            b.station_id = a.station_id
            and b.dbt_scd_id != a.dbt_scd_id
    where
        a.dbt_valid_from < coalesce(b.dbt_valid_to, cast('9999-12-31' as date))
        and b.dbt_valid_from < coalesce(a.dbt_valid_to, cast('9999-12-31' as date))

    union all

    select
        'tariff' as entity,
        a.tariff_id as natural_key,
        a.dbt_scd_id as version_a,
        b.dbt_scd_id as version_b
    from {{ ref('dim_tariffs_scd2') }} as a
    inner join {{ ref('dim_tariffs_scd2') }} as b
        on
            b.tariff_id = a.tariff_id
            and b.dbt_scd_id != a.dbt_scd_id
    where
        a.dbt_valid_from < coalesce(b.dbt_valid_to, cast('9999-12-31' as date))
        and b.dbt_valid_from < coalesce(a.dbt_valid_to, cast('9999-12-31' as date))
)

select * from pairs
