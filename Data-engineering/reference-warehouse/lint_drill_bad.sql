select session_id, wholesale_eur_mwh / rate
from raw.raw_smard_prices
join raw.raw_ecb_fx_rates on 1 = 1
