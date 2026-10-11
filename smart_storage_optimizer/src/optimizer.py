"""
Storage Optimization Engine (Developer 3)
=========================================

A transparent, rule-based engine that RECOMMENDS storage tiers. It never moves data.

Pipeline
--------
    analyzed DataFrame (Developer 2)
        -> calculate_storage_score()   adds component scores + optimization_score (0-100)
        -> classify_storage_tier()     maps score to HOT / WARM / COLD / ARCHIVE
        -> generate_recommendation()   adds action, reason, review flag; returns the
                                       DataFrame that Developer 4 consumes

How the score works (explain this to the judges)
------------------------------------------------
    optimization_score = 0.40 * access_frequency
                       + 0.25 * recency
                       + 0.20 * performance_requirement
                       + 0.15 * workload_importance

Each factor is first converted to a 0-100 "how much does this data deserve fast
storage" score. The weights live in SCORE_WEIGHTS below and can be changed in one
place (or passed in as an argument). A higher score means hotter, faster storage.

Safety rules (the engine only recommends)
-----------------------------------------
    * Data with a HIGH/CRITICAL performance requirement is never recommended
      colder than PERFORMANCE_FLOOR_TIER.
    * Moves of 2+ tiers, and anything going to ARCHIVE, are flagged requires_review.
    * Rows with an unrecognised current tier get action "REVIEW", not a move.
"""

from __future__ import annotations 

import numpy as np 
import pandas as pd 






SCORE_WEIGHTS :dict [str ,float ]={
"access_frequency":0.40 ,
"recency":0.25 ,
"performance":0.20 ,
"workload_importance":0.15 ,
}


TIER_THRESHOLDS :list [tuple [str ,float ]]=[
("HOT",80 ),
("WARM",60 ),
("COLD",30 ),
("ARCHIVE",0 ),
]


TIER_ORDER :list [str ]=[name for name ,_ in TIER_THRESHOLDS ]


RECENCY_ZERO_AFTER_DAYS :int =180 


WORKLOAD_IMPORTANCE :dict [str ,int ]={
"database":95 ,
"oltp":95 ,
"ai_training":90 ,
"ml_training":90 ,
"ai_ml":90 ,
"machine_learning":90 ,
"ai":90 ,
"virtual_machine":80 ,
"vm":80 ,
"analytics":75 ,
"search":80 ,
"cache":85 ,
"ml_model":85 ,
"media":60 ,
"reporting":40 ,
"web":70 ,
"web_server":70 ,
"streaming":70 ,
"video":65 ,
"backup":30 ,
"logs":25 ,
"log":25 ,
"compliance":20 ,
"archive":10 ,
"cold_storage":10 ,
}
DEFAULT_WORKLOAD_IMPORTANCE :int =50 


NEUTRAL_SCORE :float =50.0 


HIGH_PERFORMANCE_VALUES :set [str ]={"high","critical"}
PERFORMANCE_FLOOR_TIER :str ="WARM"


LOW_FACTOR :float =30.0 
HIGH_FACTOR :float =70.0 


REVIEW_STEP_THRESHOLD :int =2 

REQUIRED_COLUMNS :list [str ]=[
"file_name",
"size_gb",
"workload_type",
"performance_requirement",
"current_tier",
]

COMPONENT_COLUMNS :list [str ]=[
"frequency_score",
"recency_score",
"performance_component",
"importance_score",
]

RECOMMENDATION_COLUMNS :list [str ]=[
"file_name",
"size_gb",
"workload_type",
"current_tier",
"recommended_tier",
"action",
"optimization_score",
"recommendation_reason",
"requires_review",
]






def _check_columns (df :pd .DataFrame ,columns :list [str ])->None :
    missing =[c for c in columns if c not in df .columns ]
    if missing :
        raise ValueError (f"Input DataFrame is missing required columns: {missing }")


def _check_weights (weights :dict [str ,float ])->None :
    expected =set (SCORE_WEIGHTS )
    if set (weights )!=expected :
        raise ValueError (f"weights must have exactly these keys: {sorted (expected )}")
    if not np .isclose (sum (weights .values ()),1.0 ):
        raise ValueError (f"weights must sum to 1.0, got {sum (weights .values ()):.3f}")


def _to_0_100 (series :pd .Series )->pd .Series :
    """Coerce to numeric on a 0-100 scale. Auto-detects 0-1 inputs. Missing -> neutral."""
    s =pd .to_numeric (series ,errors ="coerce")
    if s .notna ().any ()and s .max ()<=1.0 :
        s =s *100.0 
    return s .clip (0 ,100 ).fillna (NEUTRAL_SCORE )


def _performance_to_0_100 (series :pd .Series )->pd .Series :
    """
    Convert performance_score to 0-100.

    workload_analyzer produces a 1..5 scale (LOW=2 ... CRITICAL=5). Treating that as
    0-100 made every workload look like it needed almost no performance, so a
    1..5 input is now rescaled: 1 -> 0, 3 -> 50, 5 -> 100.
    Values already on 0-1 or 0-100 scales are handled by _to_0_100 as before.
    """
    s =pd .to_numeric (series ,errors ="coerce")
    if s .notna ().any ()and 1.0 <s .max ()<=5.0 :
        return ((s -1.0 )/4.0 *100.0 ).clip (0 ,100 ).fillna (NEUTRAL_SCORE )
    return _to_0_100 (s )


def _days_since_access (df :pd .DataFrame ,reference_date =None )->pd .Series :
    """Use days_since_last_access if present; fill gaps from last_accessed."""
    days =pd .to_numeric (df .get ("days_since_last_access"),errors ="coerce")
    if days is None or isinstance (days ,float ):
        days =pd .Series (np .nan ,index =df .index )
    if days .isna ().any ()and "last_accessed"in df .columns :
        ref =pd .Timestamp (reference_date )if reference_date is not None else pd .Timestamp .now ().normalize ()
        last =pd .to_datetime (df ["last_accessed"],errors ="coerce")
        days =days .fillna ((ref -last ).dt .days )
    return days 


def _normalize_key (value )->str :
    return str (value ).strip ().lower ().replace (" ","_").replace ("-","_").replace ("/","_")


def _normalize_tier (value )->str :
    return str (value ).strip ().upper ()


def _tier_for_score (score :float )->str :
    for name ,minimum in TIER_THRESHOLDS :
        if score >=minimum :
            return name 
    return TIER_THRESHOLDS [-1 ][0 ]






def calculate_storage_score (
df :pd .DataFrame ,
weights :dict [str ,float ]|None =None ,
reference_date =None ,
)->pd .DataFrame :
    """
    Add the four factor scores (each 0-100) and the weighted optimization_score.

    New columns: frequency_score, recency_score, performance_component,
    importance_score, optimization_score, days_since_last_access (filled if missing).
    The input DataFrame is not modified.
    """
    weights =weights or SCORE_WEIGHTS 
    _check_weights (weights )
    _check_columns (df ,["workload_type"])

    out =df .copy ()


    if "access_frequency_score"not in out .columns :
        raise ValueError ("Input DataFrame is missing required column: 'access_frequency_score'")
    out ["frequency_score"]=_to_0_100 (out ["access_frequency_score"])


    days =_days_since_access (out ,reference_date )
    out ["days_since_last_access"]=days 
    recency =(1 -days /RECENCY_ZERO_AFTER_DAYS )*100 
    out ["recency_score"]=recency .clip (0 ,100 ).fillna (NEUTRAL_SCORE )


    if "performance_score"not in out .columns :
        raise ValueError ("Input DataFrame is missing required column: 'performance_score'")
    out ["performance_component"]=_performance_to_0_100 (out ["performance_score"])


    out ["importance_score"]=(
    out ["workload_type"].map (lambda v :WORKLOAD_IMPORTANCE .get (_normalize_key (v ),DEFAULT_WORKLOAD_IMPORTANCE ))
    .astype (float )
    )

    out ["optimization_score"]=(
    weights ["access_frequency"]*out ["frequency_score"]
    +weights ["recency"]*out ["recency_score"]
    +weights ["performance"]*out ["performance_component"]
    +weights ["workload_importance"]*out ["importance_score"]
    ).round (2 )

    return out 






def classify_storage_tier (df :pd .DataFrame )->pd .DataFrame :
    """
    Map optimization_score to a tier. Adds recommended_tier and guardrail_applied.

    If optimization_score is not present yet, calculate_storage_score() is run first.
    """
    out =df .copy ()if "optimization_score"in df .columns else calculate_storage_score (df )

    out ["recommended_tier"]=out ["optimization_score"].map (_tier_for_score )


    floor_rank =TIER_ORDER .index (PERFORMANCE_FLOOR_TIER )
    if "performance_requirement"in out .columns :
        is_high =out ["performance_requirement"].map (_normalize_key ).isin (HIGH_PERFORMANCE_VALUES )
    else :
        is_high =pd .Series (False ,index =out .index )
    too_cold =out ["recommended_tier"].map (TIER_ORDER .index )>floor_rank 
    guardrail =is_high &too_cold 
    out .loc [guardrail ,"recommended_tier"]=PERFORMANCE_FLOOR_TIER 
    out ["guardrail_applied"]=guardrail 

    return out 






def _build_reason (row :pd .Series )->str :
    action =row ["action"]
    score =row ["optimization_score"]
    days =row ["days_since_last_access"]
    days_txt =f"{int (days )} days ago"if pd .notna (days )else "unknown date"

    if action =="REVIEW":
        return (f"Current tier '{row ['current_tier']}' is not recognised, "
        f"so no move is suggested. Score {score :.1f} fits {row ['recommended_tier']}.")

    if action =="KEEP":
        text =f"Current {row ['current_tier']} tier matches the usage profile (score {score :.1f})."
        if row ["guardrail_applied"]:
            text +=f" High performance requirement keeps it at {row ['recommended_tier']} or hotter."
        return text 

    parts :list [str ]=[]
    if action =="DEMOTE":
        if row ["frequency_score"]<LOW_FACTOR :
            parts .append ("low access frequency")
        if row ["recency_score"]<LOW_FACTOR :
            parts .append (f"no recent access detected (last used {days_txt })")
        if row ["performance_component"]<LOW_FACTOR :
            parts .append ("low performance requirement")
        if row ["importance_score"]<LOW_FACTOR :
            parts .append ("low-priority workload type")
        if not parts :
            parts .append (f"overall usage no longer justifies {row ['current_tier']} storage")
    else :
        if row ["frequency_score"]>=HIGH_FACTOR :
            parts .append ("high access frequency")
        if row ["recency_score"]>=HIGH_FACTOR :
            parts .append (f"recently accessed (last used {days_txt })")
        if row ["performance_component"]>=HIGH_FACTOR :
            parts .append ("strong performance requirement")
        if row ["importance_score"]>=HIGH_FACTOR :
            parts .append ("business-critical workload type")
        if not parts :
            parts .append (f"overall usage justifies faster storage than {row ['current_tier']}")

    text =", ".join (parts )
    text =text [0 ].upper ()+text [1 :]+f" (score {score :.1f})."
    if row ["guardrail_applied"]:
        text +=f" Held at {row ['recommended_tier']} because of a high performance requirement."
    return text 


def generate_recommendation (
df :pd .DataFrame ,
weights :dict [str ,float ]|None =None ,
reference_date =None ,
)->pd .DataFrame :
    """
    Run the full pipeline and return one recommendation row per file.

    Leading columns (for Developer 4): file_name, size_gb, workload_type, current_tier,
    recommended_tier, action, optimization_score, recommendation_reason, requires_review.
    Then the four factor scores (for charts / explainability), then every other input column.

    action: KEEP, DEMOTE (move colder), PROMOTE (move hotter) or REVIEW (unknown current tier).
    Nothing is migrated - these are suggestions only.
    """
    _check_columns (df ,REQUIRED_COLUMNS )

    out =calculate_storage_score (df ,weights =weights ,reference_date =reference_date )
    out =classify_storage_tier (out )

    out ["current_tier"]=out ["current_tier"].map (_normalize_tier )

    cur_rank =out ["current_tier"].map (lambda t :TIER_ORDER .index (t )if t in TIER_ORDER else np .nan )
    rec_rank =out ["recommended_tier"].map (TIER_ORDER .index )
    step =rec_rank -cur_rank 

    out ["action"]=np .select (
    [cur_rank .isna (),step >0 ,step <0 ],
    ["REVIEW","DEMOTE","PROMOTE"],
    default ="KEEP",
    )

    out ["requires_review"]=(
    cur_rank .isna ()
    |(step .abs ()>=REVIEW_STEP_THRESHOLD )
    |((out ["recommended_tier"]=="ARCHIVE")&(out ["current_tier"]!="ARCHIVE"))
    )

    out ["recommendation_reason"]=out .apply (_build_reason ,axis =1 )

    leading =[c for c in RECOMMENDATION_COLUMNS if c in out .columns ]
    rest =[c for c in out .columns if c not in leading and c not in COMPONENT_COLUMNS ]
    return out [leading +COMPONENT_COLUMNS +rest ].reset_index (drop =True )






if __name__ =="__main__":
    today =pd .Timestamp ("2026-10-09")
    sample =pd .DataFrame ({
    "file_name":["orders.db","model_v3.ckpt","q1_backup.tar","app.log","dashboard.parquet","old_scans.zip"],
    "size_gb":[120 ,800 ,450 ,12 ,60 ,300 ],
    "last_accessed":today -pd .to_timedelta ([1 ,10 ,220 ,150 ,40 ,400 ],unit ="D"),
    "access_count":[5400 ,320 ,2 ,6 ,90 ,0 ],
    "workload_type":["Database","AI/ML","Backup","Logs","Analytics","Archive"],
    "performance_requirement":["High","High","Low","Low","Medium","Low"],
    "current_tier":["HOT","COLD","HOT","HOT","WARM","WARM"],
    "days_since_last_access":[1 ,10 ,220 ,150 ,40 ,400 ],
    "access_frequency_score":[98 ,60 ,2 ,8 ,35 ,0 ],
    "performance_score":[95 ,90 ,10 ,10 ,50 ,5 ],
    })
    pd .set_option ("display.width",220 ,"display.max_colwidth",90 )
    result =generate_recommendation (sample ,reference_date =today )
    print (result [["file_name","current_tier","recommended_tier","action",
    "optimization_score","requires_review","recommendation_reason"]].to_string (index =False ))
