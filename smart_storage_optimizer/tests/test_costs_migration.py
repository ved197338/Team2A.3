import numpy as np 
import pandas as pd 
import pytest 

from src .migration_simulator import simulate_detailed_migration 
from src .tco_calculator import CostAssumptions ,break_even_months ,calculate_tco ,transfer_hours 


def frame (**over ):
    d ={"file_name":["a","b"],"size_gb":[100.0 ,1000.0 ],"current_tier":["HOT","COLD"],
    "recommended_tier":["COLD","COLD"],"access_count":[0 ,0 ]}
    d .update (over )
    return pd .DataFrame (d )


def test_formulas_match_the_brief ():
    _ ,s =calculate_tco (frame (),pricing ={"HOT":0.2 ,"WARM":0.1 ,"COLD":0.04 ,"ARCHIVE":0.01 })
    assert s ["total_current_cost"]==pytest .approx (100 *0.2 +1000 *0.04 )
    assert s ["total_optimized_cost"]==pytest .approx (1100 *0.04 )
    assert s ["monthly_savings"]==pytest .approx (16.0 )
    assert s ["savings_percent"]==pytest .approx (16 /60 *100 ,abs =0.01 )
    assert s ["annual_savings"]==pytest .approx (192.0 )


def test_zero_cost_is_safe ():
    _ ,s =calculate_tco (frame (size_gb =[0.0 ,0.0 ]))
    assert s ["savings_percent"]==0.0 


def test_empty_frame_is_safe ():
    _ ,s =calculate_tco (frame ().iloc [0 :0 ])
    assert s ["total_current_cost"]==0 and s ["savings_percent"]==0.0 


def test_moving_to_a_more_expensive_tier_gives_negative_savings ():
    _ ,s =calculate_tco (frame (current_tier =["COLD","COLD"],recommended_tier =["HOT","COLD"]))
    assert s ["monthly_savings"]<0 


def test_transfer_time_units ():
    a =CostAssumptions (bandwidth_mbps =1000 ,bandwidth_efficiency =1.0 )

    assert transfer_hours (1000.0 ,a )==pytest .approx (8000 /3600 )


def test_break_even ():
    assert break_even_months (10 ,5 )==2 
    assert break_even_months (0 ,0 )==0 
    assert break_even_months (10 ,0 )==float ("inf")
    assert break_even_months (10 ,-3 )==float ("inf")


def test_one_time_costs_include_all_overheads ():
    a =CostAssumptions (transfer_price_per_gb =0.02 ,retrieval_price_per_gb ={"HOT":0 ,"WARM":0 ,"COLD":0.01 ,"ARCHIVE":0.03 })
    rows ,s =calculate_tco (frame (current_tier =["COLD","COLD"],recommended_tier =["WARM","COLD"],migration_cost =[5 ,5 ]),
    assumptions =a )
    assert rows .loc [0 ,"one_time_cost"]==pytest .approx (100 *0.02 +100 *0.01 +5 )
    assert rows .loc [1 ,"one_time_cost"]==0 


def test_detailed_migration_plan_only_lists_moves_and_never_touches_files (tmp_path ):
    marker =tmp_path /"data.bin"
    marker .write_text ("x")
    recs =frame ().assign (action =["DEMOTE","KEEP"])
    plan =simulate_detailed_migration (recs )
    assert list (plan ["file_name"])==["a"]
    assert {"transfer_hours","one_time_cost","break_even_months","migration_risk","performance_impact"}<=set (plan .columns )
    assert marker .read_text ()=="x"


def test_invalid_assumptions_are_rejected ():
    with pytest .raises (ValueError ):
        CostAssumptions (bandwidth_mbps =0 ).validate ()
