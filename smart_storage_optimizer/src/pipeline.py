"""
pipeline.py -- one function that runs the whole SmartStore AI pipeline
======================================================================

    validated CSV -> workload analysis -> demand forecast -> recommendations
    (optimizer + demand + SLA + policy) -> costs / TCO -> migration simulation
    -> strategy comparison

The Streamlit app and the tests both call run_pipeline(), so what you test is what
the dashboard shows.
"""

from __future__ import annotations 

from typing import Optional 

import pandas as pd 

from src import demand_forecaster ,migration_simulator ,recommendation_engine ,strategy_comparison ,tco_calculator 
from src .recommendation_engine import EngineSettings 
from src .workload_analyzer import analyze_workload 


def resolve_reference_date (df :pd .DataFrame ,use_today :bool =False ):
    """
    "Today" for recency calculations.
    use_today=False -> the day after the newest last_accessed in the file (stable demos).
    use_today=True  -> the real current date.
    """
    if use_today or df .empty :
        return pd .Timestamp .now ().normalize ()
    return pd .to_datetime (df ["last_accessed"]).max ().normalize ()+pd .Timedelta (days =1 )


def run_pipeline (df :pd .DataFrame ,history :Optional [pd .DataFrame ]=None ,
settings :Optional [EngineSettings ]=None ,horizon :int =demand_forecaster .DEFAULT_HORIZON ,
capacities_gb :Optional [dict ]=None )->dict :
    """
    Run everything and return a dict:
        analyzed, demand, recommendations, cost_rows, cost_summary,
        migration (existing simulator output), migration_plan (detailed),
        comparison, verdict, strategy_details, projection, shortages
    Raises ValueError with a readable message if the input is unusable.
    """
    if df is None or df .empty :
        raise ValueError ("The workload table is empty - nothing to analyse.")
    settings =settings or EngineSettings ()

    analyzed =analyze_workload (df ,reference_date =settings .reference_date )
    demand =demand_forecaster .run_demand_analysis (history ,analyzed ,horizon )
    recs =recommendation_engine .recommend (analyzed ,demand ["activity"],settings )

    cost_rows ,cost_summary =tco_calculator .calculate_tco (
    recs ,"current_tier","recommended_tier",settings .pricing ,settings .cost )
    recs =recs .join (cost_rows [["current_storage_cost","optimized_storage_cost","storage_savings"]])

    migration =migration_simulator .run_migration_simulation (recs ,settings .pricing )
    plan =migration_simulator .simulate_detailed_migration (
    recs ,settings .pricing ,settings .cost ,settings .tier_profiles )
    comparison ,verdict ,details =strategy_comparison .compare_strategies (recs ,settings )

    projection =demand_forecaster .project_capacity_by_growth (recs ,"recommended_tier",months =12 )
    shortages =demand_forecaster .find_capacity_shortages (projection ,capacities_gb or {})

    return {
    "analyzed":analyzed ,"demand":demand ,"recommendations":recs ,
    "cost_rows":cost_rows ,"cost_summary":cost_summary ,
    "migration":migration ,"migration_plan":plan ,
    "comparison":comparison ,"verdict":verdict ,"strategy_details":details ,
    "projection":projection ,"shortages":shortages ,
    }
