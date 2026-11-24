{# Copied unchanged from template/dbt_project/tests/generic/ during onboarding. #}

{% test non_negative(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} < 0

{% endtest %}
