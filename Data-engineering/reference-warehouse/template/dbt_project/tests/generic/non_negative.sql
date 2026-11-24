{# Fails when the column holds a negative value. For columns that must never
   be negative at all (measurements, counts, sums of positive quantities).
   Copied from the primary warehouse's tests/generic/non_negative.sql. #}

{% test non_negative(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} < 0

{% endtest %}
