"""
approval_workflow.py -- Recommendation review (Feature 10)
==========================================================

Keeps the operator's decisions (approve / reject / mark for review) in a plain dict,
which the dashboard stores in st.session_state. Approving a recommendation does NOT
move any data -- it only records the decision for the simulation.

Rules
-----
* BLOCKED recommendations cannot be approved (a policy/SLA rule forbids the move).
* Recommendations with action KEEP have nothing to approve.
* Every decision stores who/what/when so the report can be exported.
"""

from __future__ import annotations 

from datetime import datetime 
from typing import Dict ,Optional ,Tuple 

import pandas as pd 

APPROVED ,REJECTED ,MARKED_REVIEW ="APPROVED","REJECTED","MARKED_FOR_REVIEW"
DECISIONS =(APPROVED ,REJECTED ,MARKED_REVIEW )

SIMULATION_NOTICE =("All actions are SIMULATED. Approving a recommendation only records your decision; "
"no real data is moved, deleted or modified.")


def can_decide (rec_row )->Tuple [bool ,str ]:
    """Whether an operator may approve this recommendation, with a reason if not."""
    action =str (rec_row ["action"])
    if action =="BLOCKED":
        return False ,f"Blocked: {rec_row .get ('blocked_reason')or 'a policy or SLA rule forbids this move'}"
    if action =="KEEP":
        return False ,"Nothing to approve: the dataset stays where it is."
    return True ,""


def record_decision (store :Dict [str ,dict ],rec_row ,decision :str ,note :str ="")->Tuple [Dict [str ,dict ],str ]:
    """
    Record a decision. Returns (store, message). The store is modified in place and returned.
    Rejecting or marking for review is always allowed; approving follows `can_decide`.
    """
    if decision not in DECISIONS :
        return store ,f"Unknown decision '{decision }'."
    allowed ,why =can_decide (rec_row )
    if decision ==APPROVED and not allowed :
        return store ,f"Cannot approve. {why }"
    name =str (rec_row ["file_name"])
    store [name ]={
    "file_name":name ,
    "decision":decision ,
    "action":str (rec_row ["action"]),
    "from_tier":str (rec_row ["current_tier"]),
    "to_tier":str (rec_row ["recommended_tier"]),
    "note":note .strip (),
    "decided_at":datetime .now ().isoformat (timespec ="seconds"),
    "simulated":True ,
    }
    return store ,f"Recorded {decision .replace ('_',' ').lower ()} for {name } (simulation only)."


def clear_decision (store :Dict [str ,dict ],file_name :str )->Dict [str ,dict ]:
    store .pop (str (file_name ),None )
    return store 


def decisions_frame (store :Dict [str ,dict ])->pd .DataFrame :
    cols =["file_name","decision","action","from_tier","to_tier","note","decided_at","simulated"]
    return pd .DataFrame (list (store .values ()),columns =cols )


def decision_summary (store :Dict [str ,dict ],recs :pd .DataFrame )->dict :
    """Counts and simulated monthly savings of the approved moves."""
    frame =decisions_frame (store )
    approved =frame [frame ["decision"]==APPROVED ]["file_name"]if not frame .empty else []
    savings =0.0 
    if len (approved )and "net_monthly_savings"in recs .columns :
        savings =float (pd .to_numeric (recs [recs ["file_name"].isin (approved )]["net_monthly_savings"],errors ="coerce").sum ())
    return {
    "approved":int ((frame ["decision"]==APPROVED ).sum ())if not frame .empty else 0 ,
    "rejected":int ((frame ["decision"]==REJECTED ).sum ())if not frame .empty else 0 ,
    "marked_for_review":int ((frame ["decision"]==MARKED_REVIEW ).sum ())if not frame .empty else 0 ,
    "simulated_monthly_savings_of_approved":round (savings ,2 ),
    }
