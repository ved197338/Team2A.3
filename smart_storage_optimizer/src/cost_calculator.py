"""
cost_calculator.py -- Storage Cost Calculation
==============================================

Part of: "Smart Storage Optimization for Modern Workloads"

Calculates what a set of datasets costs on their CURRENT tier, what they would
cost on their RECOMMENDED tier, and the difference. It contains no
recommendation logic and no UI.

IMPORTANT -- PRICING
--------------------
The default prices below are **DEMO prices** chosen to make the tiers easy to
tell apart in a demo. They are NOT real cloud-provider prices and must not be
presented as such. To use other numbers, pass your own `pricing` (see below).
All prices are "currency units per GB per month", so every cost in this module
is an estimated MONTHLY cost.

Quick start
-----------
    from src.cost_calculator import calculate_potential_savings, calculate_cost_summary

    df_with_costs = calculate_potential_savings(df)   # adds 3 cost columns
    summary       = calculate_cost_summary(df)        # dict of totals

    # or both at once:
    df_with_costs, summary = analyze_costs(df)

Input DataFrame (from Developer 3)
----------------------------------
Required columns:  size_gb, current_tier, recommended_tier
Other columns (file_name, optimization_score, recommendation_reason, ...) are
passed through untouched. The input DataFrame is never modified.

Formulas
--------
    current_cost      = size_gb x price_per_gb(current_tier)
    optimized_cost    = size_gb x price_per_gb(recommended_tier)
    potential_savings = current_cost - optimized_cost

`potential_savings` can be NEGATIVE: moving data to a more expensive tier
(e.g. COLD -> HOT because of a performance requirement) adds cost. The
dashboard should show it as extra cost, not hide it.

Columns added to the returned DataFrame
---------------------------------------
    current_cost       float   monthly cost on the current tier
    optimized_cost     float   monthly cost on the recommended tier
    potential_savings  float   current_cost - optimized_cost

Rows whose tier is not one of HOT / WARM / COLD / ARCHIVE (for example the
"UNKNOWN" tier produced by data_loader.py), or whose size_gb is not a number,
cannot be priced. They get NaN in the cost columns and are EXCLUDED from all
totals so that total_potential_savings always equals
total_current_cost - total_optimized_cost. They are counted in
`files_unpriced` in the summary.

Summary dictionary (see `calculate_cost_summary`)
-------------------------------------------------
    total_current_cost, total_optimized_cost, total_potential_savings,
    savings_percent, file_count, total_size_gb, files_priced, files_unpriced,
    files_with_savings, files_with_added_cost, currency, billing_period,
    prices_per_gb_month, pricing_note
Money values are rounded to 2 decimals in the summary; the DataFrame keeps
full precision (round when displaying).
"""

from __future__ import annotations 

from dataclasses import dataclass ,field 
from typing import Dict ,List ,Mapping ,Optional ,Tuple ,Union 

import numpy as np 
import pandas as pd 





TIERS :Tuple [str ,...]=("HOT","WARM","COLD","ARCHIVE")


DEMO_PRICE_PER_GB_MONTH :Dict [str ,float ]={
"HOT":0.20 ,
"WARM":0.10 ,
"COLD":0.04 ,
"ARCHIVE":0.01 ,
}

DEMO_PRICING_NOTE =(
"DEMO pricing: illustrative values only. These are not real cloud-provider prices."
)
CUSTOM_PRICING_NOTE =(
"Custom prices supplied by the caller. This module has not verified them against any "
"cloud provider."
)


@dataclass (frozen =True )
class PricingConfig :
    """
    Storage prices plus a note describing where they came from.

    prices_per_gb_month : price per GB per month for each of HOT/WARM/COLD/ARCHIVE
    currency            : label only (no conversion is ever done)
    source_note         : shown in summaries/reports. If you configure REAL prices,
                          say where they came from here (provider, region, date).
    """

    prices_per_gb_month :Mapping [str ,float ]=field (
    default_factory =lambda :dict (DEMO_PRICE_PER_GB_MONTH )
    )
    currency :str ="USD"
    source_note :str =DEMO_PRICING_NOTE 


DEFAULT_PRICING =PricingConfig ()

PricingInput =Union [PricingConfig ,Mapping [str ,float ],None ]


def get_demo_prices ()->Dict [str ,float ]:
    """Return a copy of the demo price table (safe to edit)."""
    return dict (DEMO_PRICE_PER_GB_MONTH )


def resolve_pricing (pricing :PricingInput =None )->PricingConfig :
    """
    Turn whatever the caller passed into a validated PricingConfig.

    * None            -> the DEMO prices
    * PricingConfig   -> validated and used as-is
    * dict of prices  -> {"HOT": .., "WARM": .., "COLD": .., "ARCHIVE": ..}
                         (all four tiers required)

    Raises ValueError for missing/unknown tiers or negative / non-numeric prices.
    """
    if pricing is None :
        return DEFAULT_PRICING 

    if isinstance (pricing ,PricingConfig ):
        config =pricing 
    elif isinstance (pricing ,Mapping ):
        config =PricingConfig (
        prices_per_gb_month =dict (pricing ),source_note =CUSTOM_PRICING_NOTE 
        )
    else :
        raise ValueError ("pricing must be None, a PricingConfig, or a dict of tier prices.")

    prices ={str (k ).strip ().upper ():v for k ,v in config .prices_per_gb_month .items ()}
    missing =[t for t in TIERS if t not in prices ]
    unknown =[t for t in prices if t not in TIERS ]
    if missing or unknown :
        raise ValueError (
        f"Pricing must define exactly {', '.join (TIERS )}. "
        f"Missing: {missing or 'none'}; unexpected: {unknown or 'none'}."
        )
    for tier ,price in prices .items ():
        try :
            ok =np .isfinite (float (price ))and float (price )>=0 
        except (TypeError ,ValueError ):
            ok =False 
        if not ok :
            raise ValueError (f"Price for {tier } must be a non-negative number (got {price !r }).")

    return PricingConfig (
    prices_per_gb_month ={t :float (prices [t ])for t in TIERS },
    currency =config .currency ,
    source_note =config .source_note ,
    )






def _require_columns (df :pd .DataFrame ,columns :List [str ])->None :
    if not isinstance (df ,pd .DataFrame ):
        raise ValueError (f"Expected a pandas DataFrame but got {type (df ).__name__ }.")
    missing =[c for c in columns if c not in df .columns ]
    if missing :
        raise ValueError (
        f"Input DataFrame is missing required column(s): {', '.join (missing )}. "
        f"Columns found: {', '.join (map (str ,df .columns ))}."
        )


def _normalise_tiers (series :pd .Series )->pd .Series :
    """Trim + upper-case tier names. Missing values stay missing (None)."""
    s =series .astype ("string").str .strip ().str .upper ()
    return s .astype (object ).where (s .notna (),None )


def _numeric_sizes (df :pd .DataFrame )->pd .Series :
    return pd .to_numeric (df ["size_gb"],errors ="coerce").astype ("float64")


def _price_per_gb (tiers :pd .Series ,config :PricingConfig )->pd .Series :
    """Price for each row's tier; NaN where the tier is not HOT/WARM/COLD/ARCHIVE."""
    return tiers .map (dict (config .prices_per_gb_month )).astype ("float64")






def calculate_current_cost (df :pd .DataFrame ,pricing :PricingInput =None )->pd .DataFrame :
    """
    current_cost = size_gb x price(current_tier)

    Returns a COPY of `df` with a `current_cost` column added.
    Requires columns: size_gb, current_tier.
    """
    _require_columns (df ,["size_gb","current_tier"])
    config =resolve_pricing (pricing )
    out =df .copy ()
    out ["current_cost"]=_numeric_sizes (out )*_price_per_gb (
    _normalise_tiers (out ["current_tier"]),config 
    )
    return out 


def calculate_optimized_cost (df :pd .DataFrame ,pricing :PricingInput =None )->pd .DataFrame :
    """
    optimized_cost = size_gb x price(recommended_tier)

    Returns a COPY of `df` with an `optimized_cost` column added.
    Requires columns: size_gb, recommended_tier.
    """
    _require_columns (df ,["size_gb","recommended_tier"])
    config =resolve_pricing (pricing )
    out =df .copy ()
    out ["optimized_cost"]=_numeric_sizes (out )*_price_per_gb (
    _normalise_tiers (out ["recommended_tier"]),config 
    )
    return out 


def calculate_potential_savings (df :pd .DataFrame ,pricing :PricingInput =None )->pd .DataFrame :
    """
    potential_savings = current_cost - optimized_cost

    Returns a COPY of `df` with `current_cost`, `optimized_cost` and
    `potential_savings` columns (computes the first two for you).
    Negative savings mean the recommended tier costs MORE than the current one.
    """
    out =calculate_current_cost (df ,pricing )
    out ["optimized_cost"]=calculate_optimized_cost (df ,pricing )["optimized_cost"]
    out ["potential_savings"]=out ["current_cost"]-out ["optimized_cost"]
    return out 






def calculate_cost_summary (df :pd .DataFrame ,pricing :PricingInput =None )->dict :
    """
    Totals for the whole dataset, as a plain dict (keys documented in the
    module docstring). Only rows that could be priced on BOTH tiers count
    toward the totals; the rest are reported in `files_unpriced`.
    """
    config =resolve_pricing (pricing )
    costed =calculate_potential_savings (df ,config )
    return _summarise (costed ,config )


def analyze_costs (df :pd .DataFrame ,pricing :PricingInput =None )->Tuple [pd .DataFrame ,dict ]:
    """Convenience: returns (DataFrame with cost columns, summary dict)."""
    config =resolve_pricing (pricing )
    costed =calculate_potential_savings (df ,config )
    return costed ,_summarise (costed ,config )


def _summarise (costed :pd .DataFrame ,config :PricingConfig )->dict :
    priced =costed ["potential_savings"].notna ()
    total_current =float (costed .loc [priced ,"current_cost"].sum ())
    total_optimized =float (costed .loc [priced ,"optimized_cost"].sum ())
    total_savings =total_current -total_optimized 
    savings =costed .loc [priced ,"potential_savings"]

    return {
    "total_current_cost":round (total_current ,2 ),
    "total_optimized_cost":round (total_optimized ,2 ),
    "total_potential_savings":round (total_savings ,2 ),
    "savings_percent":round (total_savings /total_current *100 ,2 )if total_current >0 else 0.0 ,
    "file_count":int (len (costed )),
    "total_size_gb":round (float (_numeric_sizes (costed ).sum (skipna =True )),2 ),
    "files_priced":int (priced .sum ()),
    "files_unpriced":int ((~priced ).sum ()),
    "files_with_savings":int ((savings >0 ).sum ()),
    "files_with_added_cost":int ((savings <0 ).sum ()),
    "currency":config .currency ,
    "billing_period":"month",
    "prices_per_gb_month":dict (config .prices_per_gb_month ),
    "pricing_note":config .source_note ,
    }






if __name__ =="__main__":
    demo =pd .DataFrame (
    {
    "file_name":["orders.db","logs_2024.csv","backup_2019.tar"],
    "size_gb":[100.0 ,250.0 ,1000.0 ],
    "current_tier":["HOT","HOT","WARM"],
    "recommended_tier":["HOT","COLD","ARCHIVE"],
    }
    )
    result ,totals =analyze_costs (demo )
    print (result .to_string (index =False ))
    print ()
    for key ,value in totals .items ():
        print (f"{key }: {value }")
