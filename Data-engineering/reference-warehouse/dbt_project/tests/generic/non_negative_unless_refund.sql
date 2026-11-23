{# Fails when the column is negative unless the row is a refund/reversal.
   Signed money columns (gross_amount_eur, roaming_fee_eur, net_amount_eur,
   wholesale_cost_eur — contract §1.4/§2): refunds are the only negative events. #}

{% test non_negative_unless_refund(model, column_name) %}

select *
from {{ model }}
where {{ column_name }} < 0
  and event_type not in ('refund')

{% endtest %}
