import numpy as np 
import pandas as pd 

from src .performance_sla import MAY_VIOLATE ,MEETS ,NEEDS_DATA ,evaluate_sla_for_tier 
from src .policy_engine import check_policies_for_tier ,deletion_allowed ,evaluate_policies 
from tests .helpers import make_row 


def S (**kw ):
    return pd .Series (make_row (**kw ))



def test_legal_hold_move_needs_manual_approval_and_blocks_deletion ():
    row =S (legal_hold =True ,current_tier ="COLD")
    fails ,warns =check_policies_for_tier (row ,"ARCHIVE")
    assert not fails and any ("Legal hold"in w for w in warns )
    assert deletion_allowed (row )is False 


def test_region_restricted_dataset_cannot_sit_in_other_region ():
    row =S (required_region ="eu-west",current_region ="us-east")
    fails ,_ =check_policies_for_tier (row ,"WARM")
    assert any ("Region"in f for f in fails )


def test_tier_not_offered_in_region_is_a_failure ():
    row =S (current_region ="ap-south",required_region ="ap-south",current_tier ="COLD")
    fails ,_ =check_policies_for_tier (row ,"ARCHIVE")
    assert any ("not offered"in f for f in fails )


def test_approved_tiers_are_enforced ():
    row =S (approved_tiers ="HOT|WARM")
    assert check_policies_for_tier (row ,"COLD")[0 ]
    assert not check_policies_for_tier (row ,"WARM")[0 ]


def test_restricted_data_not_allowed_in_archive ():
    fails ,_ =check_policies_for_tier (S (security_class ="RESTRICTED"),"ARCHIVE")
    assert any ("Security"in f for f in fails )


def test_strict_recovery_requirement_rejects_archive ():
    fails ,_ =check_policies_for_tier (S (recovery_time_hours =2 ),"ARCHIVE")
    assert any ("Recovery"in f for f in fails )
    assert not check_policies_for_tier (S (recovery_time_hours =2 ),"COLD")[0 ]


def test_missing_optional_columns_do_not_cause_failures ():
    fails ,warns =check_policies_for_tier (S (),"COLD")
    assert fails ==[]and warns ==[]


def test_evaluate_policies_status_and_manual_flag ():
    df =pd .DataFrame ([make_row ("a",approved_tiers ="HOT"),make_row ("b")])
    out =evaluate_policies (df ,pd .Series (["COLD","COLD"]))
    assert out .loc [0 ,"policy_status"]=="FAIL"and out .loc [0 ,"manual_approval_required"]
    assert out .loc [1 ,"policy_status"]=="PASS"



def test_latency_violation_detected ():
    res =evaluate_sla_for_tier (S (max_latency_ms =5 ,performance_requirement ="CRITICAL"),"WARM")
    assert res ["status"]==MAY_VIOLATE 


def test_latency_met ():
    assert evaluate_sla_for_tier (S (max_latency_ms =50 ),"WARM")["status"]==MEETS 


def test_high_performance_without_latency_limit_needs_data ():
    assert evaluate_sla_for_tier (S (performance_requirement ="HIGH"),"WARM")["status"]==NEEDS_DATA 


def test_unconfigured_tier_profile_is_uncertain_not_assumed_ok ():
    profiles ={"WARM":{"latency_ms":np .nan ,"max_iops":np .nan ,"max_throughput_mbps":np .nan ,"recovery_hours":np .nan }}
    res =evaluate_sla_for_tier (S (max_latency_ms =50 ),"WARM",profiles )
    assert res ["status"]==NEEDS_DATA 


def test_iops_and_throughput_limits ():
    assert evaluate_sla_for_tier (S (read_iops =20000 ,write_iops =5000 ,max_latency_ms =500 ),"WARM")["status"]==MAY_VIOLATE 
    assert evaluate_sla_for_tier (S (throughput_mbps =900 ,max_latency_ms =500 ),"WARM")["status"]==MAY_VIOLATE 
