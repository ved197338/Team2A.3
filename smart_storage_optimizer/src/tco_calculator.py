"""
tco_calculator.py -- Total Cost of Ownership (Feature 3, extension of cost_calculator)
=======================================================================================

cost_calculator.py answers: "what does storage cost on tier A vs tier B per month?"
This module adds the other costs that decide whether a move is worth it:

    * retrieval charges (reading data back out of a tier)
    * one-time migration cost = transfer cost + retrieval-out charge + fixed overhead
    * transfer time (size and bandwidth, with consistent units)
    * break-even time and a multi-month total cost of ownership (TCO)

Everything here is an ESTIMATE based on the prices and assumptions you configure.
No real cloud-provider prices are built in; the defaults are DEMO numbers.

Units (kept consistent on purpose)
----------------------------------
    sizes            GB (decimal: 1 GB = 1,000 MB = 8,000 megabits)
    bandwidth        megabits per second (Mbps)
    transfer time    hours = size_gb * 8000 / (bandwidth_mbps * efficiency) / 3600
    money            currency units (label only)
"""

from __future__ import annotations 

from dataclasses import dataclass ,field 
from typing import Dict ,Mapping ,Optional ,Tuple 

import numpy as np 
import pandas as pd 

from src .cost_calculator import (
TIERS ,
PricingInput ,
_normalise_tiers ,
_numeric_sizes ,
_price_per_gb ,
analyze_costs ,
resolve_pricing ,
)

MEGABITS_PER_GB =8000.0 

ESTIMATE_LABEL =(
"All figures are ESTIMATES based on the configured pricing and assumptions "
"(demo values unless you change them). They are not real cloud-provider prices."
)


@dataclass 
class CostAssumptions :
    """Configurable assumptions beyond the per-GB storage prices."""

    transfer_price_per_gb :float =0.02 
    retrieval_price_per_gb :Mapping [str ,float ]=field (
    default_factory =lambda :{"HOT":0.0 ,"WARM":0.0 ,"COLD":0.01 ,"ARCHIVE":0.03 }
    )
    bandwidth_mbps :float =1000.0 
    bandwidth_efficiency :float =0.7 
    reads_per_full_retrieval :float =30000.0 
    horizon_months :int =12 
    max_break_even_months :float =12.0 
    premium_tier :str ="HOT"

    def validate (self )->"CostAssumptions":
        for name in ("transfer_price_per_gb","bandwidth_mbps","bandwidth_efficiency",
        "reads_per_full_retrieval","horizon_months","max_break_even_months"):
            value =getattr (self ,name )
            if not np .isfinite (float (value ))or float (value )<0 :
                raise ValueError (f"{name } must be a non-negative number (got {value !r }).")
        if self .bandwidth_mbps <=0 or not (0 <self .bandwidth_efficiency <=1 ):
            raise ValueError ("bandwidth_mbps must be > 0 and bandwidth_efficiency must be in (0, 1].")
        if self .premium_tier not in TIERS :
            raise ValueError (f"premium_tier must be one of {TIERS }.")
        missing =[t for t in TIERS if t not in self .retrieval_price_per_gb ]
        if missing :
            raise ValueError (f"retrieval_price_per_gb is missing tiers: {missing }")
        return self 


DEFAULT_ASSUMPTIONS =CostAssumptions ()






def transfer_hours (size_gb ,assumptions :CostAssumptions ):
    """Hours to move `size_gb` at the configured bandwidth (works on numbers or Series)."""
    usable_mbps =assumptions .bandwidth_mbps *assumptions .bandwidth_efficiency 
    return size_gb *MEGABITS_PER_GB /usable_mbps /3600.0 


def monthly_retrieved_gb (df :pd .DataFrame ,assumptions :CostAssumptions )->pd .Series :
    """
    ASSUMPTION-BASED estimate of GB read per month:

        reads per month   = read_frequency * 30   (or access_count if read_frequency is absent)
        fraction of data  = min(1, reads per month / reads_per_full_retrieval)
        retrieved GB      = size_gb * fraction
    """
    size =_numeric_sizes (df )
    if "read_frequency"in df .columns :
        reads =pd .to_numeric (df ["read_frequency"],errors ="coerce")*30.0 
        if "access_count"in df .columns :
            reads =reads .fillna (pd .to_numeric (df ["access_count"],errors ="coerce"))
    elif "access_count"in df .columns :
        reads =pd .to_numeric (df ["access_count"],errors ="coerce")
    else :
        reads =pd .Series (0.0 ,index =df .index )
    fraction =(reads .fillna (0.0 )/max (assumptions .reads_per_full_retrieval ,1.0 )).clip (0 ,1 )
    return size *fraction 


def monthly_costs (df :pd .DataFrame ,tiers :pd .Series ,pricing :PricingInput =None ,
assumptions :Optional [CostAssumptions ]=None )->pd .DataFrame :
    """
    Monthly storage + retrieval cost for each row if it sits in `tiers[row]`.
    Rows with an unrecognised tier or size get NaN (and are excluded from totals later).
    """
    assumptions =assumptions or DEFAULT_ASSUMPTIONS 
    config =resolve_pricing (pricing )
    tiers =_normalise_tiers (pd .Series (tiers ,index =df .index ))
    size =_numeric_sizes (df )
    storage =size *_price_per_gb (tiers ,config )
    retrieval_price =tiers .map ({k .upper ():float (v )for k ,v in assumptions .retrieval_price_per_gb .items ()}).astype ("float64")
    retrieval =monthly_retrieved_gb (df ,assumptions )*retrieval_price 
    return pd .DataFrame ({
    "storage_cost":storage ,
    "retrieval_cost":retrieval ,
    "monthly_total":storage +retrieval ,
    },index =df .index )


def one_time_move_costs (df :pd .DataFrame ,from_tiers :pd .Series ,to_tiers :pd .Series ,
assumptions :Optional [CostAssumptions ]=None )->pd .DataFrame :
    """
    One-time cost of moving each dataset from one tier to another (0 if it does not move).

        transfer_cost   = size_gb x transfer_price_per_gb
        retrieval_out   = size_gb x retrieval price of the SOURCE tier
        fixed_overhead  = migration_cost column (0 if absent)
        one_time_cost   = sum of the three
    """
    assumptions =assumptions or DEFAULT_ASSUMPTIONS 
    src =_normalise_tiers (pd .Series (from_tiers ,index =df .index ))
    dst =_normalise_tiers (pd .Series (to_tiers ,index =df .index ))
    size =_numeric_sizes (df )
    valid =src .isin (TIERS )&dst .isin (TIERS )
    moved =valid &(src !=dst )

    retr_map ={k .upper ():float (v )for k ,v in assumptions .retrieval_price_per_gb .items ()}
    transfer =(size *assumptions .transfer_price_per_gb ).where (moved ,0.0 )
    retrieval_out =(size *src .map (retr_map ).astype ("float64")).where (moved ,0.0 )
    if "migration_cost"in df .columns :
        fixed =pd .to_numeric (df ["migration_cost"],errors ="coerce").fillna (0.0 ).where (moved ,0.0 )
    else :
        fixed =pd .Series (0.0 ,index =df .index )
    hours =transfer_hours (size ,assumptions ).where (moved ,0.0 )
    return pd .DataFrame ({
    "moved":moved .astype (bool ),
    "transfer_cost":transfer ,
    "retrieval_out_cost":retrieval_out ,
    "fixed_overhead":fixed ,
    "one_time_cost":transfer +retrieval_out +fixed ,
    "transfer_hours":hours ,
    },index =df .index )


def break_even_months (one_time_cost ,monthly_benefit ):
    """
    Months until the one-time cost is paid back by the monthly benefit.
    No move (cost 0) -> 0.0.  Cost but no monthly benefit -> inf (never).
    Works on scalars or Series.
    """
    cost =pd .Series (one_time_cost ,dtype ="float64")if not np .isscalar (one_time_cost )else one_time_cost 
    benefit =pd .Series (monthly_benefit ,dtype ="float64")if not np .isscalar (monthly_benefit )else monthly_benefit 
    if np .isscalar (cost )and np .isscalar (benefit ):
        if cost <=0 :
            return 0.0 
        return float (cost /benefit )if benefit >0 else float ("inf")
    result =pd .Series (np .where (benefit >0 ,cost /benefit .where (benefit >0 ,1.0 ),np .inf ),index =cost .index )
    return result .where (cost >0 ,0.0 )






def calculate_tco (df :pd .DataFrame ,current_col :str ="current_tier",target_col :str ="recommended_tier",
pricing :PricingInput =None ,
assumptions :Optional [CostAssumptions ]=None )->Tuple [pd .DataFrame ,dict ]:
    """
    Cost of the current placement versus the recommended placement.

    Returns (row_costs, summary):
      row_costs  per dataset: current_*/optimized_* storage + retrieval, one-time costs,
                 net monthly saving, break-even months
      summary    totals, using EXACTLY the formulas of the project brief:
                     monthly_savings = current_cost - optimized_cost    (storage only)
                     savings_percent = monthly_savings / current_cost * 100  (0 if current_cost is 0)
                 plus retrieval, one-time overhead and TCO over `horizon_months`.
    """
    assumptions =(assumptions or DEFAULT_ASSUMPTIONS ).validate ()
    config =resolve_pricing (pricing )

    work =df .copy ()
    work ["recommended_tier"]=work [target_col ]
    work ["current_tier"]=work [current_col ]
    storage_df ,storage_summary =analyze_costs (work ,config )

    cur =monthly_costs (work ,work ["current_tier"],config ,assumptions )
    new =monthly_costs (work ,work ["recommended_tier"],config ,assumptions )
    once =one_time_move_costs (work ,work ["current_tier"],work ["recommended_tier"],assumptions )

    priced =cur ["monthly_total"].notna ()&new ["monthly_total"].notna ()
    rows =pd .DataFrame ({
    "current_storage_cost":cur ["storage_cost"],
    "optimized_storage_cost":new ["storage_cost"],
    "current_retrieval_cost":cur ["retrieval_cost"],
    "optimized_retrieval_cost":new ["retrieval_cost"],
    "current_monthly_total":cur ["monthly_total"],
    "optimized_monthly_total":new ["monthly_total"],
    },index =df .index )
    rows ["storage_savings"]=rows ["current_storage_cost"]-rows ["optimized_storage_cost"]
    rows ["net_monthly_savings"]=rows ["current_monthly_total"]-rows ["optimized_monthly_total"]
    rows =rows .join (once )
    rows ["break_even_months"]=break_even_months (rows ["one_time_cost"].fillna (0.0 ),
    rows ["net_monthly_savings"].fillna (0.0 ))
    rows ["priced"]=priced 


    by_tier =pd .DataFrame ({"tier":list (TIERS )})
    by_tier ["current_cost"]=[float (rows .loc [priced &(_normalise_tiers (work ["current_tier"])==t ),"current_storage_cost"].sum ())for t in TIERS ]
    by_tier ["optimized_cost"]=[float (rows .loc [priced &(_normalise_tiers (work ["recommended_tier"])==t ),"optimized_storage_cost"].sum ())for t in TIERS ]

    h =int (assumptions .horizon_months )
    cur_monthly =float (rows .loc [priced ,"current_monthly_total"].sum ())
    new_monthly =float (rows .loc [priced ,"optimized_monthly_total"].sum ())
    one_time =float (rows .loc [priced ,"one_time_cost"].sum ())
    net_monthly =cur_monthly -new_monthly 

    summary =dict (storage_summary )
    summary .update ({
    "label":ESTIMATE_LABEL ,
    "monthly_savings":storage_summary ["total_potential_savings"],
    "annual_savings":round (storage_summary ["total_potential_savings"]*12 ,2 ),
    "current_retrieval_cost":round (float (rows .loc [priced ,"current_retrieval_cost"].sum ()),2 ),
    "optimized_retrieval_cost":round (float (rows .loc [priced ,"optimized_retrieval_cost"].sum ()),2 ),
    "current_monthly_total":round (cur_monthly ,2 ),
    "optimized_monthly_total":round (new_monthly ,2 ),
    "net_monthly_savings":round (net_monthly ,2 ),
    "one_time_migration_cost":round (one_time ,2 ),
    "horizon_months":h ,
    "tco_current":round (cur_monthly *h ,2 ),
    "tco_optimized":round (new_monthly *h +one_time ,2 ),
    "tco_savings":round (cur_monthly *h -(new_monthly *h +one_time ),2 ),
    "overall_break_even_months":break_even_months (one_time ,net_monthly ),
    "datasets_moved":int (rows .loc [priced ,"moved"].sum ()),
    "data_moved_gb":round (float (_numeric_sizes (work )[priced &rows ["moved"]].sum ()),2 ),
    "total_transfer_hours":round (float (rows .loc [priced ,"transfer_hours"].sum ()),2 ),
    "cost_by_tier":by_tier ,
    })
    return rows ,summary 
