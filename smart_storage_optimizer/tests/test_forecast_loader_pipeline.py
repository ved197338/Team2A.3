import io 

import numpy as np 
import pandas as pd 

from src import data_loader ,demand_forecaster as df_ 
from src .demand_forecaster import _model_next ,forecast_capacity ,load_history ,run_demand_analysis 
from src .pipeline import run_pipeline ,resolve_reference_date 
from src .recommendation_engine import EngineSettings 


def hist (months =24 ,slope =100.0 ,noise =0.0 ):
    rng =np .random .default_rng (0 )
    dates =pd .date_range ("2024-01-01",periods =months ,freq ="MS")
    return pd .DataFrame ({"date":dates ,"file_name":"a","access_count":10.0 ,
    "size_gb":1000 +slope *np .arange (months )+rng .normal (0 ,noise ,months )})



def test_no_history_means_no_predictions ():
    out =run_demand_analysis (None ,pd .DataFrame ({"file_name":["a"]}))
    assert not out ["has_history"]and not out ["capacity"]["available"]
    assert (out ["activity"]["demand_outlook"]=="INSUFFICIENT_HISTORY").all ()


def test_short_history_is_refused_not_fabricated ():
    res =forecast_capacity (hist (months =8 ))
    assert not res ["available"]and res ["forecast"]is None and "12"in res ["message"]


def test_gaps_in_history_are_not_filled_in ():
    h =hist ().drop (index =5 )
    assert not forecast_capacity (h )["available"]


def test_forecast_reports_baseline_comparison_and_horizon ():
    res =forecast_capacity (hist (),horizon =4 )
    assert res ["available"]and len (res ["forecast"])==4 
    m =res ["metrics"]
    assert {"baseline_mae_gb","model_mae_gb","model_beats_baseline"}<=set (m )

    assert m ["model_beats_baseline"]is True 


def test_model_prediction_ignores_future_values ():
    values =np .arange (1 ,21 ,dtype =float )
    a =_model_next (values [:12 ])
    values2 =values .copy ();values2 [12 :]=99999.0 
    assert _model_next (values2 [:12 ])==a 


def test_history_loader_gives_friendly_errors ():
    out ,msgs =load_history (io .StringIO ("a,b\n1,2\n"))
    assert out .empty and "missing required column"in msgs [0 ]



BASE ="file_name,size_gb,last_accessed,access_count,workload_type,performance_requirement,current_tier"


def test_missing_required_column_message ():
    df ,issues =data_loader .load_and_validate_workload_data (io .StringIO ("file_name,size_gb\na,5\n"))
    assert df .empty and any ("Required column"in m for m in issues )


def test_optional_columns_are_cleaned_and_bad_values_become_missing ():
    csv =BASE +",max_latency_ms,legal_hold,approved_tiers\na,5,2026-10-01,10,database,HIGH,HOT,abc,yes,hot|warm\n"
    df ,issues =data_loader .load_and_validate_workload_data (io .StringIO (csv ))
    assert len (df )==1 and np .isnan (df .loc [0 ,"max_latency_ms"])
    assert df .loc [0 ,"legal_hold"]is True and df .loc [0 ,"approved_tiers"]=="HOT|WARM"
    assert any ("max_latency_ms"in m for m in issues )


def test_legacy_seven_column_csv_still_works ():
    csv =BASE +"\na,5,2026-10-01,10,database,HIGH,HOT\n"
    df ,_ =data_loader .load_and_validate_workload_data (io .StringIO (csv ))
    assert list (df .columns )==data_loader .REQUIRED_COLUMNS 
    r =run_pipeline (df ,None ,EngineSettings (reference_date =pd .Timestamp ("2026-10-09")))
    assert len (r ["recommendations"])==1 



def test_end_to_end_with_synthetic_sample ():
    df ,issues =data_loader .load_and_validate_workload_data ("sample_workload.csv")
    assert len (df )>=30 and (df ["data_source"]=="SYNTHETIC").all ()
    h ,_ =load_history ("sample_demand_history.csv")
    r =run_pipeline (df ,h ,EngineSettings (reference_date =resolve_reference_date (df )))
    recs ,cs =r ["recommendations"],r ["cost_summary"]
    assert len (recs )==len (df )
    assert set (recs ["action"])=={"KEEP","PROMOTE","DEMOTE","REVIEW","BLOCKED"}
    assert recs ["current_tier"].isin (["HOT","WARM","COLD","ARCHIVE","UNKNOWN"]).all ()
    assert abs (cs ["monthly_savings"]-(cs ["total_current_cost"]-cs ["total_optimized_cost"]))<0.02 
    blocked =recs [recs ["action"]=="BLOCKED"]
    assert len (blocked )>=1 and (blocked ["net_monthly_savings"]==0 ).all ()
    assert (blocked ["recommended_tier"]==blocked ["current_tier"]).all ()

    cmp_ =r ["comparison"].set_index ("strategy")
    assert cmp_ .loc ["A. All-fast baseline","datasets_moved"]>=cmp_ .loc ["C. SmartStore AI","datasets_moved"]-100 
    assert cmp_ .loc ["C. SmartStore AI","policy_violations"]<=cmp_ .loc ["B. Rule-based baseline","policy_violations"]
    assert r ["verdict"][-1 ].startswith ("Overall")
    assert r ["migration"]["summary"]["simulation_only"]is True 
