"""
recommendation_engine.py -- SmartStore AI decision layer (Features 2, 4, 5, 6, 10 inputs)
=========================================================================================

This module WRAPS the existing rule-based optimizer (src/optimizer.py) instead of
replacing it. The optimizer proposes a tier from access frequency, recency, performance
need and workload importance. This engine then makes the final, explainable decision:

    1. demand      predicted demand nudges the optimizer score (never decides alone)
    2. candidate   the score is turned into a PROPOSED tier (optimizer rules + guardrail)
    3. safety      the proposed tier is checked against policy rules and performance SLA
    4. search      if the proposal is unsafe, the nearest SAFE tier between the current
                   tier and the proposal is used instead
    5. economics   a demotion must actually save money and pay back within the limit
    6. action      KEEP / PROMOTE / DEMOTE / REVIEW / BLOCKED, with reasons

Actions
-------
    KEEP      stay in the current tier
    PROMOTE   move to a faster (hotter) tier
    DEMOTE    move to a cheaper (colder) tier
    REVIEW    not enough reliable information (or conflicting signals); a person decides
    BLOCKED   a policy or SLA rule forbids the proposed move; the dataset stays where it is

A policy FAIL always beats cost savings. Nothing here moves data.
"""

from __future__ import annotations 

from dataclasses import dataclass ,field 
from typing import Dict ,List ,Optional 

import numpy as np 
import pandas as pd 

from src import optimizer 
from src .cost_calculator import PricingInput ,resolve_pricing 
from src .performance_sla import (
DEFAULT_TIER_PROFILES ,MAY_VIOLATE ,MEETS ,NEEDS_DATA ,TIERS ,
evaluate_sla ,evaluate_sla_for_tier ,observed_latency_status ,
)
from src .policy_engine import (
DEFAULT_POLICY ,FAIL ,PASS ,WARN ,PolicyConfig ,check_policies_for_tier ,deletion_allowed ,
)
from src .tco_calculator import (
CostAssumptions ,break_even_months ,monthly_costs ,monthly_retrieved_gb ,
one_time_move_costs ,
)

TIER_RANK ={t :i for i ,t in enumerate (TIERS )}


DEMAND_SCORE_ADJUSTMENT ={
"LIKELY_ACTIVE":+10.0 ,
"POSSIBLE_REACTIVATION":+5.0 ,
"LIKELY_INACTIVE":-5.0 ,
"STABLE":0.0 ,
"INSUFFICIENT_HISTORY":0.0 ,
}

ACTIONS =("KEEP","PROMOTE","DEMOTE","REVIEW","BLOCKED")


@dataclass 
class EngineSettings :
    """Everything the engine needs besides the data (all configurable)."""
    pricing :PricingInput =None 
    cost :CostAssumptions =field (default_factory =CostAssumptions )
    policy :PolicyConfig =field (default_factory =PolicyConfig )
    tier_profiles :Dict =field (default_factory =lambda :{k :dict (v )for k ,v in DEFAULT_TIER_PROFILES .items ()})
    reference_date :object =None 






def _fmt_money (value :float ,currency :str ="USD")->str :
    sign ="-"if value <0 else ""
    return f"{sign }${abs (value ):,.2f}"


def _tier_path (candidate :str ,current :str )->List [str ]:
    """Tiers from `candidate` toward `current`, candidate first, current last."""
    a ,b =TIER_RANK [candidate ],TIER_RANK [current ]
    step =1 if b >a else -1 
    return [TIERS [i ]for i in range (a ,b +step ,step )]if a !=b else [current ]


def _evaluate (row :pd .Series ,tier :str ,is_move :bool ,settings :EngineSettings )->dict :
    """Policy + SLA verdict for one dataset on one tier -> OK / BLOCK / UNCERTAIN."""
    fails ,warns =check_policies_for_tier (row ,tier ,settings .policy )
    sla =evaluate_sla_for_tier (row ,tier ,settings .tier_profiles )
    if fails or sla ["status"]==MAY_VIOLATE :
        verdict ="BLOCK"
    elif sla ["status"]==NEEDS_DATA and is_move :
        verdict ="UNCERTAIN"
    else :
        verdict ="OK"
    return {"verdict":verdict ,"policy_fails":fails ,"policy_warns":warns ,"sla":sla }


def _join (messages :List [str ])->str :
    """'a. ' + 'b.' -> 'a; b' (no doubled full stops)."""
    return "; ".join (m .rstrip (".")for m in messages )


def _blocking_messages (ev :dict )->List [str ]:
    return list (dict .fromkeys (ev ["policy_fails"]+ev ["sla"]["issues"]))


def _uncertain_messages (ev :dict )->List [str ]:
    return list (dict .fromkeys (ev ["sla"]["gaps"]))


def _factor_reason (row :pd .Series ,cur :str ,action :str ,tier :str )->str :
    """Reuse the optimizer's own wording for the factors behind a KEEP / DEMOTE / PROMOTE."""
    text_row =row .copy ()
    text_row ["action"],text_row ["recommended_tier"],text_row ["current_tier"]=action ,tier ,cur 
    return optimizer ._build_reason (text_row )


def _worse (a :str ,b :str ,order )->str :
    return a if order .index (a )>=order .index (b )else b 






def recommend (analyzed :pd .DataFrame ,demand_activity :Optional [pd .DataFrame ]=None ,
settings :Optional [EngineSettings ]=None )->pd .DataFrame :
    """
    Produce one recommendation per dataset.

    Parameters
    ----------
    analyzed         output of workload_analyzer.analyze_workload (plus optional extended columns)
    demand_activity  optional table from demand_forecaster.forecast_activity (joined on file_name)
    settings         EngineSettings (pricing, assumptions, policy rules, tier profiles)

    Returns a DataFrame with (among others):
        file_name, workload_type, size_gb, performance_requirement, current_tier,
        proposed_tier (what the optimizer wanted), recommended_tier (what is actually recommended),
        action, optimization_score, demand_outlook, recommendation_reason,
        sla_status, policy_status, policy_failed_checks, policy_warnings, blocked_reason,
        manual_approval_required, why_text, financial_text, performance_text, policy_text,
        uncertainty_text, current_monthly_cost, recommended_monthly_cost, net_monthly_savings,
        one_time_cost, break_even_months, potential_savings_if_unblocked
    """
    settings =settings or EngineSettings ()
    config =resolve_pricing (settings .pricing )
    if analyzed .empty :
        return analyzed .assign (recommended_tier =pd .Series (dtype =object ),action =pd .Series (dtype =object ))


    base =optimizer .generate_recommendation (analyzed ,reference_date =settings .reference_date )
    base =base .rename (columns ={"recommended_tier":"base_tier","action":"base_action",
    "optimization_score":"base_score",
    "recommendation_reason":"base_reason"})
    base ["current_tier"]=base ["current_tier"].astype (str ).str .upper ()

    outlook =pd .Series ("INSUFFICIENT_HISTORY",index =base .index ,dtype =object )
    if demand_activity is not None and not demand_activity .empty :
        mapping =demand_activity .set_index ("file_name")["demand_outlook"].to_dict ()
        outlook =base ["file_name"].map (mapping ).fillna ("INSUFFICIENT_HISTORY")
    base ["demand_outlook"]=outlook 
    adjust =outlook .map (DEMAND_SCORE_ADJUSTMENT ).astype (float )
    base ["optimization_score"]=(base ["base_score"]+adjust ).clip (0 ,100 ).round (2 )


    classified =optimizer .classify_storage_tier (base .drop (columns =["guardrail_applied"],errors ="ignore"))
    base ["proposed_tier"]=classified ["recommended_tier"]
    base ["guardrail_applied"]=classified ["guardrail_applied"]


    retrieved =monthly_retrieved_gb (base ,settings .cost )

    results =[]
    for idx ,row in base .iterrows ():
        results .append (_decide_row (idx ,row ,base ,retrieved ,config ,settings ))
    decisions =pd .DataFrame (results ,index =base .index )
    out =pd .concat ([base ,decisions ],axis =1 )


    out ["recommendation_reason"]=out ["reason_text"]
    out ["reason"]=out ["reason_text"]
    out ["observed_latency_status"]=observed_latency_status (out )
    out ["deletion_allowed"]=[deletion_allowed (r )for _ ,r in out .iterrows ()]

    leading =["file_name","workload_type","size_gb","performance_requirement","current_tier",
    "proposed_tier","recommended_tier","action","optimization_score",
    "demand_outlook","recommendation_reason","blocked_reason","manual_approval_required",
    "policy_status","sla_status"]
    rest =[c for c in out .columns if c not in leading ]
    return out [leading +rest ].reset_index (drop =True )


def _decide_row (idx ,row :pd .Series ,frame :pd .DataFrame ,retrieved :pd .Series ,
config ,settings :EngineSettings )->dict :
    cur =str (row ["current_tier"]).upper ()
    cand =str (row ["proposed_tier"]).upper ()
    size =float (row ["size_gb"])
    notes :List [str ]=[]
    uncertainties :List [str ]=[]
    outlook =row ["demand_outlook"]
    perf_label =str (row .get ("performance_requirement","")).upper ()


    if cur not in TIERS :
        return _row_result (row ,cur ,cand ,cur ,"REVIEW",
        f"{row ['base_reason']} A person must set a valid current tier before any move can be judged.",
        None ,None ,[],[f"Current tier '{cur }' is not recognised."],
        config ,settings ,retrieved [idx ],blocked_reason ="",force_manual =True )


    evals ={t :_evaluate (row ,t ,t !=cur ,settings )for t in TIERS }
    ev_cand =evals [cand ]
    path =_tier_path (cand ,cur )
    chosen =next ((t for t in path if evals [t ]["verdict"]=="OK"),None )
    action_hint =None 

    if chosen is None :

        by_distance =sorted (TIERS ,key =lambda t :(abs (TIER_RANK [t ]-TIER_RANK [cur ]),TIER_RANK [t ]))
        fix =next ((t for t in by_distance if t !=cur and evals [t ]["verdict"]=="OK"),None )
        existing =_blocking_messages (evals [cur ])
        if fix is not None :
            chosen =fix 
            notes .append ("Current placement already breaks a rule ("+_join (existing )+f"), so moving to {fix } is proposed to fix it.")
            action_hint ="REMEDIATE"
        else :
            msg =("Current placement already breaks a rule and no configured tier satisfies every rule: "
            +_join (existing )+". Manual remediation is needed.")
            return _row_result (row ,cur ,cand ,cur ,"REVIEW",msg ,evals [cur ],evals [cand ],
            notes ,["No tier satisfies all configured rules."],config ,settings ,
            retrieved [idx ],blocked_reason =" | ".join (existing ),force_manual =True )

    action ="KEEP"if chosen ==cur else ("DEMOTE"if TIER_RANK [chosen ]>TIER_RANK [cur ]else "PROMOTE")
    blocked_reason =""


    if chosen !=cand and action_hint !="REMEDIATE":
        if ev_cand ["verdict"]=="BLOCK":
            blocked_reason =" | ".join (_blocking_messages (ev_cand ))
            if chosen ==cur :
                action ="BLOCKED"
                notes .append (f"Proposed {cand } is blocked: {_join (_blocking_messages (ev_cand ))}. A rule violation overrides the cost saving, so it stays in {cur }.")
            else :
                notes .append (f"Proposed {cand } is blocked ({_join (_blocking_messages (ev_cand ))}); the nearest safe tier {chosen } is recommended instead.")
        elif ev_cand ["verdict"]=="UNCERTAIN":
            gaps =_uncertain_messages (ev_cand )
            uncertainties .extend (gaps )
            if chosen ==cur :
                action ="REVIEW"
                notes .append (f"Moving to {cand } could not be verified safely ({_join (gaps )}), so a person should review it.")
            else :
                notes .append (f"Moving to {cand } could not be verified ({_join (gaps )}); {chosen } is recommended instead.")


    if action =="DEMOTE":
        if outlook =="LIKELY_ACTIVE":
            action ,chosen ="KEEP",cur 
            notes .append ("Demotion held: forecast shows this dataset is likely to stay or become active.")
        elif outlook =="POSSIBLE_REACTIVATION":
            action ,chosen ="REVIEW",cur 
            notes .append ("Demotion held for review: history shows past bursts of activity, so it may become active again.")
            uncertainties .append ("History shows earlier activity bursts; reactivation is possible.")


    cur_cost =monthly_costs (frame .loc [[idx ]],pd .Series ([cur ],index =[idx ]),config ,settings .cost ).iloc [0 ]
    if action =="DEMOTE":
        new_cost =monthly_costs (frame .loc [[idx ]],pd .Series ([chosen ],index =[idx ]),config ,settings .cost ).iloc [0 ]
        once =one_time_move_costs (frame .loc [[idx ]],pd .Series ([cur ],index =[idx ]),pd .Series ([chosen ],index =[idx ]),settings .cost ).iloc [0 ]
        net =float (cur_cost ["monthly_total"]-new_cost ["monthly_total"])
        be =break_even_months (float (once ["one_time_cost"]),net )
        if net <=0 :
            action ,chosen ="KEEP",cur 
            notes .append (f"Demotion skipped: it would not reduce monthly cost after retrieval charges ({_fmt_money (net )}/month).")
        elif be >settings .cost .max_break_even_months :
            action ,chosen ="KEEP",cur 
            notes .append (f"Demotion skipped: break-even would take {be :,.1f} months, longer than the {settings .cost .max_break_even_months :g}-month limit.")


    ev_final =evals [chosen ]
    uncertainties .extend (ev_final ["sla"]["gaps"])
    if outlook =="INSUFFICIENT_HISTORY":
        uncertainties .append ("No demand history for this dataset; future demand is not predicted.")


    adj =float (row ["optimization_score"]-row ["base_score"])
    if adj !=0 :
        notes .insert (0 ,f"Forecast outlook {outlook } adjusted the score by {adj :+g} points.")
    if action_hint =="REMEDIATE":
        reason =""
    else :
        if action in ("DEMOTE","PROMOTE"):
            text_action ,text_tier =action ,chosen 
        elif cand !=cur :
            text_action ,text_tier =("DEMOTE"if TIER_RANK [cand ]>TIER_RANK [cur ]else "PROMOTE"),cand 
        else :
            text_action ,text_tier ="KEEP",cur 
        reason =_factor_reason (row ,cur ,text_action ,text_tier )
    return _row_result (row ,cur ,cand ,chosen ,action ,(reason +" "+" ".join (notes )).strip (),
    ev_final ,ev_cand ,notes ,list (dict .fromkeys (uncertainties )),config ,settings ,
    retrieved [idx ],blocked_reason =blocked_reason ,
    force_manual =(action_hint =="REMEDIATE"))


def _row_result (row ,cur ,cand ,chosen ,action ,reason ,ev_final ,ev_cand ,notes ,uncertainties ,
config ,settings ,retrieved_gb ,blocked_reason ="",force_manual =False )->dict :
    """Assemble every output column for one dataset."""
    idx_frame =pd .DataFrame ([row ])
    idx_frame .index =[0 ]
    priced =cur in TIERS and chosen in TIERS 
    if priced :
        cur_c =monthly_costs (idx_frame ,pd .Series ([cur ],index =[0 ]),config ,settings .cost ).iloc [0 ]
        new_c =monthly_costs (idx_frame ,pd .Series ([chosen ],index =[0 ]),config ,settings .cost ).iloc [0 ]
        once =one_time_move_costs (idx_frame ,pd .Series ([cur ],index =[0 ]),pd .Series ([chosen ],index =[0 ]),settings .cost ).iloc [0 ]
        net =float (cur_c ["monthly_total"]-new_c ["monthly_total"])
        one_time =float (once ["one_time_cost"])
        be =break_even_months (one_time ,net )
        cur_m ,new_m =float (cur_c ["monthly_total"]),float (new_c ["monthly_total"])

        if cand in TIERS and cand !=chosen :
            cand_c =monthly_costs (idx_frame ,pd .Series ([cand ],index =[0 ]),config ,settings .cost ).iloc [0 ]
            unblocked =float (cur_c ["monthly_total"]-cand_c ["monthly_total"])if action in ("BLOCKED","REVIEW")else 0.0 
        else :
            unblocked =0.0 
    else :
        net =one_time =cur_m =new_m =np .nan 
        be =np .nan 
        unblocked =0.0 


    def policy_status (ev ):
        if ev is None :
            return PASS 
        return FAIL if ev ["policy_fails"]else (WARN if ev ["policy_warns"]else PASS )

    def sla_status (ev ):
        return MEETS if ev is None else ev ["sla"]["status"]

    p_final ,p_cand =policy_status (ev_final ),policy_status (ev_cand )
    p_status =_worse (p_final ,p_cand ,[PASS ,WARN ,FAIL ])if cand !=chosen else p_final 
    s_status =_worse (sla_status (ev_final ),sla_status (ev_cand ),[MEETS ,NEEDS_DATA ,MAY_VIOLATE ])if cand !=chosen else sla_status (ev_final )

    fails ,warns =[],[]
    for ev in (ev_final ,ev_cand if cand !=chosen else None ):
        if ev is not None :
            fails +=ev ["policy_fails"]
            warns +=ev ["policy_warns"]
    fails ,warns =list (dict .fromkeys (fails )),list (dict .fromkeys (warns ))

    sla_issues =[]
    for ev in (ev_final ,ev_cand if cand !=chosen else None ):
        if ev is not None :
            sla_issues +=ev ["sla"]["issues"]
    sla_issues =list (dict .fromkeys (sla_issues ))


    manual =bool (force_manual or action =="REVIEW"or action =="BLOCKED"or warns 
    or (bool (row .get ("requires_review",False ))and action in ("DEMOTE","PROMOTE"))
    or (chosen =="ARCHIVE"and cur !="ARCHIVE"))


    if action =="KEEP":
        what =f"Keep in {cur }."
    elif action in ("DEMOTE","PROMOTE"):
        what =f"{action .title ()} from {cur } to {chosen }."
    elif action =="BLOCKED":
        what =f"Do NOT move: the proposed move to {cand } is blocked; stay in {cur }."
    else :
        what =f"Human review needed; stay in {cur } for now."

    if not priced :
        financial ="Cost impact cannot be estimated because a tier is not recognised."
    elif action in ("DEMOTE","PROMOTE"):
        financial =(f"Estimated net monthly change: {_fmt_money (net )} (negative = extra cost). One-time move cost "
        f"~{_fmt_money (one_time )}; break-even "
        +("never"if not np .isfinite (be )else f"~{be :,.1f} months")+".")
    elif action in ("BLOCKED","REVIEW")and unblocked >0 :
        financial =(f"No change in cost. The held-back proposal would have saved ~{_fmt_money (unblocked )}/month, "
        f"which is NOT counted because a rule or missing information stops it.")
    else :
        financial =f"No change in cost (~{_fmt_money (cur_m )}/month in {cur })."

    perf_parts =[]
    if ev_final is not None :
        sla =ev_final ["sla"]
        if sla ["status"]==MEETS :
            perf_parts .append (f"Configured {chosen } profile meets the performance requirements we could check.")
        if sla ["issues"]:
            perf_parts .append ("Possible SLA problems: "+"; ".join (sla ["issues"]))
        if sla ["gaps"]:
            perf_parts .append ("Cannot be checked: "+"; ".join (sla ["gaps"]))
        perf_parts .extend (sla ["notes"][:1 ])
    if ev_cand is not None and cand !=chosen and ev_cand ["sla"]["issues"]:
        perf_parts .append (f"Proposed {cand } may violate: "+"; ".join (ev_cand ["sla"]["issues"]))
    performance =" ".join (perf_parts )or "No performance data to evaluate."

    final_fails =ev_final ["policy_fails"]if ev_final is not None else []
    final_warns =ev_final ["policy_warns"]if ev_final is not None else []
    cand_fails =ev_cand ["policy_fails"]if (ev_cand is not None and cand !=chosen )else []
    parts =[]
    if final_fails :
        parts .append (f"Recommended placement ({chosen }) FAILS: {_join (final_fails )}.")
    if cand_fails :
        parts .append (f"Proposed {cand } would FAIL: {_join (cand_fails )}."
        +(f" The recommended {chosen } passes the policy checks."if not final_fails else ""))
    if not parts :
        parts .append (("Passed with warnings: "+_join (final_warns )+".")if final_warns else 
        "All configured policy checks passed (checks that need optional CSV columns are skipped when the columns are missing).")
    elif final_warns :
        parts .append ("Warnings: "+_join (final_warns )+".")
    policy_text =" ".join (parts )

    return {
    "recommended_tier":chosen ,
    "action":action ,
    "reason_text":reason ,
    "blocked_reason":blocked_reason ,
    "manual_approval_required":manual ,
    "policy_status":p_status ,
    "policy_failed_checks":" | ".join (fails ),
    "policy_warnings":" | ".join (warns ),
    "sla_status":s_status ,
    "sla_issues":" | ".join (sla_issues ),
    "sla_gaps":" | ".join (ev_final ["sla"]["gaps"])if ev_final is not None else "",
    "what_text":what ,
    "why_text":reason ,
    "financial_text":financial ,
    "performance_text":performance ,
    "policy_text":policy_text ,
    "uncertainty_text":"; ".join (uncertainties )if uncertainties else "None identified from the available data.",
    "current_monthly_cost":cur_m ,
    "recommended_monthly_cost":new_m ,
    "net_monthly_savings":net ,
    "one_time_cost":one_time ,
    "break_even_months":be ,
    "potential_savings_if_unblocked":unblocked ,
    }
