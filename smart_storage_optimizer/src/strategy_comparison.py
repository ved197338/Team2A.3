"""
strategy_comparison.py -- Storage Optimization Comparison (Feature 8)
=====================================================================

Evaluates three strategies on the SAME workload, with the SAME prices and assumptions:

    A. ALL-FAST BASELINE   every dataset in the configured premium tier
    B. RULE-BASED BASELINE simple, visible rules on days since last access / access count
    C. SMARTSTORE AI       the recommended_tier from recommendation_engine
                           (workload analysis + demand forecast if available + cost +
                           SLA + policy checks)

Plus a reference row, "Current placement", so you can see the starting point.

Every strategy is judged by the same code:
    * monthly cost             tco_calculator.monthly_costs        (calculated from the CSV + prices)
    * data movement/overhead   tco_calculator.one_time_move_costs   (calculated from the CSV + assumptions)
    * SLA risk                 performance_sla.evaluate_sla         (simulated: uses configured tier profiles)
    * policy violations        policy_engine.evaluate_policies      (configured rules)

"Measured vs simulated": nothing here is measured on real hardware. Cost and movement
numbers are CALCULATED from your metadata and prices; SLA risk and violations are
SIMULATED against the configured tier profiles and policy rules. The verdict text only
says SmartStore is better where the numbers show it.
"""

from __future__ import annotations 

from typing import Dict ,List ,Optional ,Tuple 

import numpy as np 
import pandas as pd 

from src .cost_calculator import PricingInput ,_normalise_tiers ,_numeric_sizes ,resolve_pricing 
from src .performance_sla import MAY_VIOLATE ,NEEDS_DATA ,TIERS ,evaluate_sla 
from src .policy_engine import FAIL ,evaluate_policies 
from src .recommendation_engine import EngineSettings 
from src .tco_calculator import break_even_months ,monthly_costs ,one_time_move_costs 


RULE_HOT_MAX_DAYS =14 
RULE_HOT_MIN_ACCESSES =1000 
RULE_WARM_MAX_DAYS =45 
RULE_COLD_MAX_DAYS =180 

STRATEGY_A ="A. All-fast baseline"
STRATEGY_B ="B. Rule-based baseline"
STRATEGY_C ="C. SmartStore AI"
CURRENT ="Current placement (reference)"

RULES_TEXT =(
f"Rule-based baseline: HOT if last access <= {RULE_HOT_MAX_DAYS } days or >= {RULE_HOT_MIN_ACCESSES } accesses; "
f"WARM if <= {RULE_WARM_MAX_DAYS } days; COLD if <= {RULE_COLD_MAX_DAYS } days; otherwise ARCHIVE. "
"It ignores performance requirements and policies."
)

BASIS =pd .DataFrame ([
("Estimated monthly cost","Calculated","from your CSV sizes x the configured prices"),
("Estimated savings","Calculated","current monthly cost - strategy monthly cost"),
("Data movement / migration overhead","Calculated","from sizes, bandwidth, transfer price and the migration_cost column"),
("SLA risk","Simulated","datasets compared with CONFIGURED tier profiles (assumptions, not hardware measurements)"),
("Policy violations","Simulated","datasets checked against the CONFIGURED policy rules"),
],columns =["Metric","Kind","How it is obtained"])


def rule_based_tiers (recs :pd .DataFrame )->pd .Series :
    """Tier for each dataset using only recency and access count."""
    days =pd .to_numeric (recs .get ("days_since_last_access"),errors ="coerce")
    hits =pd .to_numeric (recs .get ("access_count"),errors ="coerce").fillna (0 )
    tier =pd .Series ("ARCHIVE",index =recs .index ,dtype =object )
    tier [days <=RULE_COLD_MAX_DAYS ]="COLD"
    tier [days <=RULE_WARM_MAX_DAYS ]="WARM"
    tier [(days <=RULE_HOT_MAX_DAYS )|(hits >=RULE_HOT_MIN_ACCESSES )]="HOT"
    tier [days .isna ()]=recs .loc [days .isna (),"current_tier"]
    return tier 


def strategy_assignments (recs :pd .DataFrame ,settings :EngineSettings )->Dict [str ,pd .Series ]:
    return {
    CURRENT :_normalise_tiers (recs ["current_tier"]),
    STRATEGY_A :pd .Series (settings .cost .premium_tier ,index =recs .index ,dtype =object ),
    STRATEGY_B :rule_based_tiers (recs ),
    STRATEGY_C :_normalise_tiers (recs ["recommended_tier"]),
    }


def compare_strategies (recs :pd .DataFrame ,settings :Optional [EngineSettings ]=None 
)->Tuple [pd .DataFrame ,List [str ],Dict [str ,pd .DataFrame ]]:
    """
    Returns (comparison table, verdict sentences, per-strategy detail frames).

    The comparison table has one row per strategy with columns:
        strategy, monthly_cost, monthly_savings_vs_current, savings_percent, datasets_moved,
        data_moved_gb, migration_overhead, tco_over_horizon, sla_may_violate, sla_needs_data,
        policy_violations
    Datasets whose current tier is unrecognised are excluded from every strategy (same basis).
    """
    settings =settings or EngineSettings ()
    config =resolve_pricing (settings .pricing )
    cost =settings .cost 
    if recs .empty :
        return pd .DataFrame (),["No datasets to compare."],{}

    assignments =strategy_assignments (recs ,settings )
    comparable =assignments [CURRENT ].isin (TIERS )
    if not comparable .any ():
        return pd .DataFrame (),["No dataset has a recognised current tier, so strategies cannot be compared."],{}
    frame =recs [comparable ].reset_index (drop =True )
    cur_tiers =assignments [CURRENT ][comparable ].reset_index (drop =True )
    cur_cost =float (monthly_costs (frame ,cur_tiers ,config ,cost )["monthly_total"].sum ())

    rows ,details =[],{}
    for name ,tiers in assignments .items ():
        t =tiers [comparable ].reset_index (drop =True )
        monthly =monthly_costs (frame ,t ,config ,cost )
        move =one_time_move_costs (frame ,cur_tiers ,t ,cost )
        sla =evaluate_sla (frame ,t ,settings .tier_profiles )
        pol =evaluate_policies (frame ,t ,settings .policy )
        total =float (monthly ["monthly_total"].sum ())
        overhead =float (move ["one_time_cost"].sum ())
        savings =cur_cost -total 
        rows .append ({
        "strategy":name ,
        "monthly_cost":round (total ,2 ),
        "monthly_savings_vs_current":round (savings ,2 ),
        "savings_percent":round (savings /cur_cost *100 ,2 )if cur_cost >0 else 0.0 ,
        "datasets_moved":int (move ["moved"].sum ()),
        "data_moved_gb":round (float (_numeric_sizes (frame )[move ["moved"]].sum ()),2 ),
        "migration_overhead":round (overhead ,2 ),
        "tco_over_horizon":round (total *cost .horizon_months +overhead ,2 ),
        "sla_may_violate":int ((sla ["sla_status"]==MAY_VIOLATE ).sum ()),
        "sla_needs_data":int ((sla ["sla_status"]==NEEDS_DATA ).sum ()),
        "policy_violations":int ((pol ["policy_status"]==FAIL ).sum ()),
        })
        details [name ]=pd .concat ([frame [["file_name","size_gb"]],t .rename ("tier"),monthly ,sla ,pol ],axis =1 )

    table =pd .DataFrame (rows )
    return table ,_verdict (table ,cost .horizon_months ),details 


def _verdict (table :pd .DataFrame ,horizon :int )->List [str ]:
    """Plain statements generated from the numbers; SmartStore is only praised where the data shows it."""
    def get (name ):
        return table [table ["strategy"]==name ].iloc [0 ]
    a ,b ,c =get (STRATEGY_A ),get (STRATEGY_B ),get (STRATEGY_C )
    lines :List [str ]=[]

    def compare (metric ,label ,lower_is_better =True ,fmt ="{:,.0f}"):
        for other ,other_name in ((a ,"all-fast"),(b ,"rule-based")):
            diff =c [metric ]-other [metric ]
            if abs (diff )<1e-9 :
                lines .append (f"{label }: SmartStore AI equals the {other_name } baseline ({fmt .format (c [metric ])}).")
            elif (diff <0 )==lower_is_better :
                lines .append (f"{label }: SmartStore AI is better than the {other_name } baseline "
                f"({fmt .format (c [metric ])} vs {fmt .format (other [metric ])}).")
            else :
                lines .append (f"{label }: SmartStore AI is WORSE than the {other_name } baseline "
                f"({fmt .format (c [metric ])} vs {fmt .format (other [metric ])}).")

    compare ("tco_over_horizon",f"{horizon }-month total cost incl. migration",fmt ="${:,.2f}")
    compare ("policy_violations","Policy violations")
    compare ("sla_may_violate","Datasets that may violate SLA")
    compare ("migration_overhead","One-time migration overhead",fmt ="${:,.2f}")

    better_tco =c ["tco_over_horizon"]<b ["tco_over_horizon"]-1e-9 
    safer =(c ["policy_violations"]+c ["sla_may_violate"])<(b ["policy_violations"]+b ["sla_may_violate"])
    if better_tco and safer :
        lines .append ("Overall: on this workload SmartStore AI has lower cost AND fewer policy/SLA problems than the rule-based baseline.")
    elif safer and not better_tco :
        lines .append ("Overall: SmartStore AI is safer than the rule-based baseline here, but it is NOT cheaper - the extra cost is the price of respecting policies and SLAs.")
    elif better_tco and not safer :
        lines .append ("Overall: SmartStore AI is cheaper here but is NOT demonstrably safer than the rule-based baseline.")
    else :
        lines .append ("Overall: on this workload the data does NOT show SmartStore AI beating the rule-based baseline.")
    return lines 
