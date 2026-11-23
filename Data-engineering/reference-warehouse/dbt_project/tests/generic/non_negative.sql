{# Fails when the column holds a negative value. For columns that must never be
   negative at all (e.g. energy_kwh — contract §1.4: energy is a physical
   measurement, refunds reverse amounts, never energy). #}

{% test non_negative(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} < 0

{% endtest %}
