import numpy as np 
import pandas as pd 

from src import approval_workflow 
from tests .helpers import make_row ,rec_of ,run 


def test_old_last_access_alone_does_not_demote_a_busy_critical_dataset ():
    r =run (make_row ("busy",last_accessed ="2026-03-01",access_count =900000 ,performance_requirement ="CRITICAL",
    current_tier ="HOT",max_latency_ms =5 ,read_iops =8000 ))
    assert rec_of (r ,"busy")["recommended_tier"]=="HOT"


def test_inactive_low_priority_dataset_is_demoted_and_saves_money ():
    r =run (make_row ("old",workload_type ="backup",performance_requirement ="LOW",last_accessed ="2026-02-01",
    access_count =0 ,current_tier ="HOT",size_gb =1000 ),
    make_row ("busy",access_count =800000 ,current_tier ="HOT",performance_requirement ="CRITICAL",
    max_latency_ms =5 ))
    row =rec_of (r ,"old")
    assert row ["action"]=="DEMOTE"and row ["net_monthly_savings"]>0 


def test_performance_critical_dataset_is_protected_from_unsafe_demotion ():
    r =run (make_row ("db",performance_requirement ="CRITICAL",current_tier ="HOT",access_count =2 ,
    last_accessed ="2026-01-01",max_latency_ms =2 ),
    make_row ("other",access_count =100000 ))
    assert rec_of (r ,"db")["recommended_tier"]=="HOT"


def test_policy_violation_overrides_cost_saving ():
    r =run (make_row ("dr",workload_type ="backup",performance_requirement ="LOW",last_accessed ="2025-06-01",
    access_count =0 ,current_tier ="COLD",recovery_time_hours =2 ,size_gb =2000 ),
    make_row ("busy",access_count =800000 ,current_tier ="HOT",performance_requirement ="CRITICAL",
    max_latency_ms =5 ))
    row =rec_of (r ,"dr")
    assert row ["action"]=="BLOCKED"and row ["recommended_tier"]=="COLD"
    assert row ["net_monthly_savings"]==0 and row ["blocked_reason"]
    assert row ["potential_savings_if_unblocked"]>0 


def test_blocked_recommendation_cannot_be_approved ():
    r =run (make_row ("dr",workload_type ="backup",performance_requirement ="LOW",last_accessed ="2025-06-01",
    access_count =0 ,current_tier ="COLD",recovery_time_hours =2 ),
    make_row ("busy",access_count =800000 ,current_tier ="HOT",performance_requirement ="CRITICAL",max_latency_ms =5 ))
    row =rec_of (r ,"dr")
    store ={}
    _ ,msg =approval_workflow .record_decision (store ,row ,approval_workflow .APPROVED )
    assert store =={}and "Cannot approve"in msg 
    approval_workflow .record_decision (store ,row ,approval_workflow .REJECTED ,"ok")
    assert store ["dr"]["simulated"]is True 


def test_unknown_current_tier_goes_to_review ():
    r =run (make_row ("x",current_tier =""))
    assert rec_of (r ,"x")["action"]=="REVIEW"


def test_insufficient_sla_data_for_high_performance_demotion_goes_to_review ():
    r =run (make_row ("hp",performance_requirement ="HIGH",current_tier ="HOT",access_count =3 ,
    last_accessed ="2026-03-01"),
    make_row ("busy",access_count =800000 ,current_tier ="HOT",performance_requirement ="CRITICAL",max_latency_ms =5 ))
    assert rec_of (r ,"hp")["action"]=="REVIEW"
    assert rec_of (r ,"hp")["recommended_tier"]=="HOT"


def test_region_violation_cannot_be_fixed_by_tier_change_and_needs_review ():
    r =run (make_row ("g",required_region ="eu-west",current_region ="us-east"))
    assert rec_of (r ,"g")["action"]=="REVIEW"


def test_demand_forecast_holds_back_demotion ():
    rows =[make_row ("old",workload_type ="backup",performance_requirement ="LOW",last_accessed ="2026-02-01",
    access_count =0 ,current_tier ="HOT",size_gb =1000 ),
    make_row ("busy",access_count =800000 ,current_tier ="HOT",performance_requirement ="CRITICAL",max_latency_ms =5 )]
    from src .pipeline import run_pipeline 
    from src .recommendation_engine import recommend 
    from src .workload_analyzer import analyze_workload 
    from tests .helpers import make_df ,settings 
    analyzed =analyze_workload (make_df (*rows ),reference_date ="2026-10-09")
    activity =pd .DataFrame ({"file_name":["old","busy"],"demand_outlook":["LIKELY_ACTIVE","STABLE"]})
    out =recommend (analyzed ,activity ,settings ())
    assert out .set_index ("file_name").loc ["old","action"]in ("KEEP","REVIEW")


def test_actions_are_always_valid_and_costs_consistent ():
    r =run (make_row ("a"),make_row ("b",current_tier ="COLD",access_count =1 ,last_accessed ="2025-01-01",
    performance_requirement ="LOW",workload_type ="logs"))
    recs =r ["recommendations"]
    assert set (recs ["action"])<={"KEEP","PROMOTE","DEMOTE","REVIEW","BLOCKED"}
    cs =r ["cost_summary"]
    assert abs (cs ["monthly_savings"]-(cs ["total_current_cost"]-cs ["total_optimized_cost"]))<0.02 


def test_empty_workload_gives_a_clear_error ():
    import pytest 
    from src .pipeline import run_pipeline 
    with pytest .raises (ValueError ):
        run_pipeline (pd .DataFrame ())
