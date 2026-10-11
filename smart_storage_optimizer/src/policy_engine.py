"""
policy_engine.py -- Compliance and Policy Engine (Feature 4)
============================================================

A CONFIGURABLE POLICY-CHECKING PROTOTYPE. It checks recommendations against rules
that you configure. It does NOT guarantee legal or regulatory compliance and is
not legal advice.

Checks (each can FAIL, WARN, or pass)
-------------------------------------
    approved_tiers   dataset may only live in the tiers listed in its approved_tiers
    region           data restricted to a region must be in it, and the target tier
                     must be offered in that region
    security         the tier must be approved for the dataset's security class
    recovery         the tier's assumed restore time must meet the recovery requirement
    legal_hold       a hold means: never delete, and any tier change needs approval
    retention        informational: deletion is not allowed during the retention period

Rule of the engine: a FAIL always overrides cost savings (the move is BLOCKED).

Output columns of evaluate_policies()
-------------------------------------
    policy_status              PASS / WARN / FAIL
    policy_failed_checks       text list of failed checks
    policy_warnings            text list of warnings
    policy_blocked_reason      why the action is blocked (empty if not blocked)
    manual_approval_required   True when a person must review before acting
    deletion_allowed           False when a legal hold exists (the app never deletes anything)
"""

from __future__ import annotations 

from dataclasses import dataclass ,field 
from typing import Dict ,List ,Mapping ,Optional ,Tuple 

import numpy as np 
import pandas as pd 

from src .performance_sla import (
DEFAULT_TIER_PROFILES ,
MAY_VIOLATE ,
NEEDS_DATA ,
TIERS ,
recovery_check ,
)

SECURITY_ORDER :Tuple [str ,...]=("PUBLIC","INTERNAL","CONFIDENTIAL","RESTRICTED")

PASS ,WARN ,FAIL ="PASS","WARN","FAIL"

POLICY_DISCLAIMER =(
"Configurable policy-checking prototype. It applies the rules configured in this app to "
"your CSV metadata; it does not guarantee legal or regulatory compliance."
)


@dataclass 
class PolicyConfig :
    """
    Rules that are the same for every dataset (edit to match your organisation).

    tier_regions       tier -> regions where that tier is offered/approved.
                       A tier missing from this dict means "not configured" (a WARNING).
    tier_max_security  tier -> highest security class allowed in that tier.
    tier_profiles      performance/recovery assumptions (see performance_sla.py).
    """

    tier_regions :Dict [str ,List [str ]]=field (default_factory =lambda :{
    "HOT":["us-east","eu-west","ap-south"],
    "WARM":["us-east","eu-west","ap-south"],
    "COLD":["us-east","eu-west","ap-south"],
    "ARCHIVE":["us-east","eu-west"],
    })
    tier_max_security :Dict [str ,str ]=field (default_factory =lambda :{
    "HOT":"RESTRICTED",
    "WARM":"RESTRICTED",
    "COLD":"CONFIDENTIAL",
    "ARCHIVE":"CONFIDENTIAL",
    })
    tier_profiles :Mapping =field (default_factory =lambda :DEFAULT_TIER_PROFILES )


DEFAULT_POLICY =PolicyConfig ()


def _clean_str (value )->Optional [str ]:
    if value is None :
        return None 
    try :
        if pd .isna (value ):
            return None 
    except (TypeError ,ValueError ):
        pass 
    text =str (value ).strip ()
    return text or None 


def parse_approved_tiers (value )->Optional [List [str ]]:
    """'HOT|WARM' -> ['HOT','WARM'];  blank/missing -> None (= every tier approved)."""
    text =_clean_str (value )
    if text is None :
        return None 
    parts =[p .strip ().upper ()for p in text .replace (",","|").replace (";","|").split ("|")]
    tiers =[p for p in parts if p in TIERS ]
    return tiers or None 


def legal_hold_value (row )->Optional [bool ]:
    """True / False / None (None = column missing or blank, i.e. unknown)."""
    try :
        value =row .get ("legal_hold",None )
    except AttributeError :
        return None 
    if value is None :
        return None 
    try :
        if pd .isna (value ):
            return None 
    except (TypeError ,ValueError ):
        pass 
    return bool (value )


def check_policies_for_tier (row ,tier :str ,config :Optional [PolicyConfig ]=None )->Tuple [List [str ],List [str ]]:
    """
    Check one dataset (row/dict) against one target tier.
    Returns (failed_checks, warnings) - two lists of readable messages.
    """
    config =config or DEFAULT_POLICY 
    fails :List [str ]=[]
    warns :List [str ]=[]

    current_tier =_clean_str (row .get ("current_tier"))
    current_tier =current_tier .upper ()if current_tier else None 
    is_move =current_tier is not None and tier !=current_tier 


    approved =parse_approved_tiers (row .get ("approved_tiers"))
    if approved is not None and tier not in approved :
        fails .append (f"Approved tiers: {tier } is not approved for this dataset (approved: {', '.join (approved )}).")


    required =_clean_str (row .get ("required_region"))
    current_region =_clean_str (row .get ("current_region"))
    required =required .lower ()if required else None 
    current_region =current_region .lower ()if current_region else None 
    region_for_tier =current_region or required 
    if required and current_region and required !=current_region :
        fails .append (f"Region: dataset is restricted to '{required }' but is placed in '{current_region }' "
        f"(existing violation; changing tier does not fix it).")
    elif required and not current_region :
        warns .append (f"Region: dataset is restricted to '{required }' but its current region is not provided, so it cannot be verified.")
    if region_for_tier :
        offered =config .tier_regions .get (tier )if config .tier_regions else None 
        if offered :
            if region_for_tier not in [r .lower ()for r in offered ]:
                fails .append (f"Region: tier {tier } is not offered in region '{region_for_tier }'.")
        elif is_move :
            warns .append (f"Region: availability of {tier } in '{region_for_tier }' is not configured, so it cannot be verified.")


    sec =_clean_str (row .get ("security_class"))
    sec =sec .upper ()if sec else None 
    if sec in SECURITY_ORDER :
        max_sec =(config .tier_max_security or {}).get (tier )
        if max_sec in SECURITY_ORDER and SECURITY_ORDER .index (sec )>SECURITY_ORDER .index (max_sec ):
            fails .append (f"Security: {sec } data is not approved for {tier } (highest allowed class: {max_sec }).")


    status ,message =recovery_check (row ,tier ,config .tier_profiles )
    if status ==MAY_VIOLATE :
        fails .append (message )
    elif status ==NEEDS_DATA :
        warns .append (message )


    hold =legal_hold_value (row )
    if hold is True :
        if is_move :
            warns .append ("Legal hold: dataset is under legal hold; the tier change needs manual approval and the data must not be deleted or altered.")
        else :
            warns .append ("Legal hold: dataset is under legal hold (do not delete or alter).")
    elif hold is None and hasattr (row ,"index")and "legal_hold"in row .index :
        warns .append ("Legal hold: status is unknown (blank in the CSV).")

    return fails ,warns 


def deletion_allowed (row )->bool :
    """
    The app never deletes data. This says whether deletion would even be PERMITTED
    by the metadata. Conservative: a legal hold or any retention period blocks it.
    """
    if legal_hold_value (row )is True :
        return False 
    try :
        retention =float (row .get ("retention_days",np .nan ))
    except (TypeError ,ValueError ):
        retention =np .nan 
    return bool (np .isfinite (retention )and retention ==0 )


def evaluate_policies (df :pd .DataFrame ,tiers :pd .Series ,config :Optional [PolicyConfig ]=None )->pd .DataFrame :
    """
    Run all checks for every row, assuming each row is placed in `tiers[row]`.
    Returns a DataFrame with the columns listed in the module docstring (same index as df).
    """
    config =config or DEFAULT_POLICY 
    tiers =pd .Series (tiers ,index =df .index )
    out_rows =[]
    for idx ,row in df .iterrows ():
        tier =str (tiers [idx ]).strip ().upper ()
        if tier not in TIERS :
            fails ,warns =[],[f"Tier '{tier }' is not recognised, so policies could not be checked."]
        else :
            fails ,warns =check_policies_for_tier (row ,tier ,config )
        status =FAIL if fails else (WARN if warns else PASS )
        out_rows .append ({
        "policy_status":status ,
        "policy_failed_checks":" | ".join (fails ),
        "policy_warnings":" | ".join (warns ),
        "policy_blocked_reason":" | ".join (fails ),
        "manual_approval_required":bool (fails or warns ),
        "deletion_allowed":deletion_allowed (row ),
        })
    cols =["policy_status","policy_failed_checks","policy_warnings","policy_blocked_reason",
    "manual_approval_required","deletion_allowed"]
    return pd .DataFrame (out_rows ,index =df .index ,columns =cols )
