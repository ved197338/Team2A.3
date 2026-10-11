"""
performance_sla.py -- Performance SLA Protection (Feature 5)
============================================================

Checks whether a dataset would still meet its performance needs if it lived in a
given storage tier.

IMPORTANT - what this is and is not
-----------------------------------
* It compares the numbers in your uploaded CSV (required IOPS, throughput,
  maximum latency, recovery time) against TIER PROFILES that YOU configure below.
* The tier profiles are ASSUMPTIONS for a simulation. This module never measures
  real hardware.
* If a tier profile value is missing, the result is "NEEDS_DATA" -- it never
  assumes the tier is good enough.

Statuses
--------
    MEETS         every check we could run passed
    MAY_VIOLATE   at least one check failed (the tier may break the SLA)
    NEEDS_DATA    we could not decide (missing requirement or missing tier profile)
"""

from __future__ import annotations 

from typing import Dict ,List ,Mapping ,Optional ,Tuple 

import numpy as np 
import pandas as pd 

TIERS :Tuple [str ,...]=("HOT","WARM","COLD","ARCHIVE")

MEETS ="MEETS"
MAY_VIOLATE ="MAY_VIOLATE"
NEEDS_DATA ="NEEDS_DATA"






DEFAULT_TIER_PROFILES :Dict [str ,Dict [str ,float ]]={
"HOT":{"latency_ms":2.0 ,"max_iops":50000 ,"max_throughput_mbps":1500 ,"recovery_hours":0.0 },
"WARM":{"latency_ms":10.0 ,"max_iops":10000 ,"max_throughput_mbps":800 ,"recovery_hours":0.0 },
"COLD":{"latency_ms":100.0 ,"max_iops":1500 ,"max_throughput_mbps":200 ,"recovery_hours":1.0 },
"ARCHIVE":{"latency_ms":3_600_000.0 ,"max_iops":100 ,"max_throughput_mbps":60 ,"recovery_hours":12.0 },
}

TIER_PROFILE_NOTE =(
"Tier performance values are configured ASSUMPTIONS used for simulation. "
"They are not measurements of real hardware."
)

HIGH_PERFORMANCE_LABELS ={"HIGH","CRITICAL"}


def _num (row ,key )->float :
    """Read a number from a row; missing -> NaN."""
    try :
        value =row .get (key ,np .nan )
    except AttributeError :
        return np .nan 
    try :
        value =float (value )
    except (TypeError ,ValueError ):
        return np .nan 
    return value if np .isfinite (value )else np .nan 


def _profile_value (profiles :Optional [Mapping ],tier :str ,key :str )->float :
    try :
        value =float (profiles [tier ][key ])
    except (TypeError ,ValueError ,KeyError ):
        return np .nan 
    return value if np .isfinite (value )else np .nan 


def recovery_check (row ,tier :str ,profiles :Optional [Mapping ])->Tuple [str ,str ]:
    """
    Recovery-time check, shared with policy_engine.
    Returns (status, message) where status is MEETS / MAY_VIOLATE / NEEDS_DATA / "NOT_CHECKED".
    """
    rto =_num (row ,"recovery_time_hours")
    if np .isnan (rto ):
        return "NOT_CHECKED","Recovery: no recovery-time requirement provided."
    tier_hours =_profile_value (profiles ,tier ,"recovery_hours")
    if np .isnan (tier_hours ):
        return NEEDS_DATA ,f"Recovery: time of {tier } is not configured, so the {rto :g} h requirement cannot be checked."
    if tier_hours >rto :
        return MAY_VIOLATE ,(f"Recovery: requirement is {rto :g} h but {tier } is assumed to need "
        f"{tier_hours :g} h to restore data.")
    return MEETS ,f"Recovery: {tier } ({tier_hours :g} h) is within the {rto :g} h requirement."


def evaluate_sla_for_tier (row ,tier :str ,profiles :Optional [Mapping ]=None )->dict :
    """
    Evaluate one dataset (a row/dict) against one tier.

    Returns {"status", "issues": [..], "gaps": [..], "notes": [..]}:
        issues  messages for checks that FAILED
        gaps    messages for things we could not check (missing data)
        notes   informational messages for checks that passed
    """
    profiles =DEFAULT_TIER_PROFILES if profiles is None else profiles 
    issues :List [str ]=[]
    gaps :List [str ]=[]
    notes :List [str ]=[]

    perf_label =str (row .get ("performance_requirement","")).strip ().upper ()if hasattr (row ,"get")else ""


    max_lat =_num (row ,"max_latency_ms")
    tier_lat =_profile_value (profiles ,tier ,"latency_ms")
    if np .isnan (max_lat ):
        if perf_label in HIGH_PERFORMANCE_LABELS :
            gaps .append (f"No maximum latency given for a {perf_label } performance workload.")
        else :
            notes .append ("No latency limit given; a LOW/MEDIUM requirement is assumed to tolerate this tier.")
    elif np .isnan (tier_lat ):
        gaps .append (f"Latency of {tier } is not configured, so the {max_lat :g} ms limit cannot be checked.")
    elif tier_lat >max_lat :
        issues .append (f"Latency limit is {max_lat :g} ms but {tier } is assumed to deliver ~{tier_lat :g} ms.")
    else :
        notes .append (f"{tier } latency (~{tier_lat :g} ms) is within the {max_lat :g} ms limit.")


    r_iops ,w_iops =_num (row ,"read_iops"),_num (row ,"write_iops")
    if not (np .isnan (r_iops )and np .isnan (w_iops )):
        need =np .nansum ([r_iops ,w_iops ])
        cap =_profile_value (profiles ,tier ,"max_iops")
        if np .isnan (cap ):
            gaps .append (f"IOPS capability of {tier } is not configured.")
        elif need >cap :
            issues .append (f"Workload needs ~{need :,.0f} IOPS but {tier } is assumed to give ~{cap :,.0f}.")


    tput =_num (row ,"throughput_mbps")
    if not np .isnan (tput ):
        cap =_profile_value (profiles ,tier ,"max_throughput_mbps")
        if np .isnan (cap ):
            gaps .append (f"Throughput capability of {tier } is not configured.")
        elif tput >cap :
            issues .append (f"Workload needs ~{tput :,.0f} MB/s but {tier } is assumed to give ~{cap :,.0f} MB/s.")


    status ,message =recovery_check (row ,tier ,profiles )
    if status ==MAY_VIOLATE :
        issues .append (message )
    elif status ==NEEDS_DATA :
        gaps .append (message )

    overall =MAY_VIOLATE if issues else (NEEDS_DATA if gaps else MEETS )
    return {"status":overall ,"issues":issues ,"gaps":gaps ,"notes":notes }


def evaluate_sla (df :pd .DataFrame ,tiers :pd .Series ,profiles :Optional [Mapping ]=None )->pd .DataFrame :
    """
    Evaluate every row of `df` against the tier given for that row in `tiers`.

    Returns a DataFrame (same index as df) with: sla_status, sla_issues, sla_gaps.
    Rows whose tier is not HOT/WARM/COLD/ARCHIVE get NEEDS_DATA.
    """
    rows =[]
    tiers =pd .Series (tiers ,index =df .index )
    for idx ,row in df .iterrows ():
        tier =str (tiers [idx ]).strip ().upper ()
        if tier not in TIERS :
            rows .append ((NEEDS_DATA ,"","Tier is not recognised."))
            continue 
        res =evaluate_sla_for_tier (row ,tier ,profiles )
        rows .append ((res ["status"]," | ".join (res ["issues"])," | ".join (res ["gaps"])))
    return pd .DataFrame (rows ,columns =["sla_status","sla_issues","sla_gaps"],index =df .index )


def observed_latency_status (df :pd .DataFrame )->pd .Series :
    """
    From the uploaded metadata only: is the OBSERVED latency within the maximum allowed?
    (We do not measure anything - both numbers come from the CSV.)
    Values: MEETS / MAY_VIOLATE / NEEDS_DATA
    """
    obs =pd .to_numeric (df .get ("observed_latency_ms"),errors ="coerce")if "observed_latency_ms"in df else pd .Series (np .nan ,index =df .index )
    lim =pd .to_numeric (df .get ("max_latency_ms"),errors ="coerce")if "max_latency_ms"in df else pd .Series (np .nan ,index =df .index )
    out =pd .Series (NEEDS_DATA ,index =df .index ,dtype =object )
    known =obs .notna ()&lim .notna ()
    out [known &(obs <=lim )]=MEETS 
    out [known &(obs >lim )]=MAY_VIOLATE 
    return out 
