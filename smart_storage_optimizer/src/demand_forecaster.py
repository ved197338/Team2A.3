"""
demand_forecaster.py -- Future Demand Prediction (Feature 6, optional)
======================================================================

Uses an OPTIONAL monthly history CSV. If there is not enough history, this module
says so and does NOT invent predictions; the rest of the app falls back to rule-based
recommendations (and, for capacity, a growth-rate projection that is labelled as a
projection, not a prediction).

History CSV columns
-------------------
    date          first day of the month (any parseable date)
    file_name     must match file_name in the workload CSV
    access_count  accesses during that month
    size_gb       OPTIONAL stored size that month (needed for the capacity forecast)

What is forecast
----------------
1. TOTAL CAPACITY (needs size_gb, >= MIN_MONTHS_CAPACITY months)
     baseline : moving average of the last 3 months
     model    : scikit-learn LinearRegression on the last 3 months (lags), applied recursively
   Both are scored with WALK-FORWARD validation: for each month the models are fitted
   ONLY on earlier months and asked about the next one, so no future information leaks in.
   The model is used only if its error is lower than the baseline's; otherwise the baseline is used.

2. DATASET ACTIVITY (>= MIN_MONTHS_ACTIVITY months per dataset)
     baseline : mean of the last 3 months
     method   : the same mean scaled by a damped trend (recent 3 months vs the 3 before)
   Outlook labels: LIKELY_ACTIVE, POSSIBLE_REACTIVATION, STABLE, LIKELY_INACTIVE,
   INSUFFICIENT_HISTORY. The activity method is a transparent heuristic; its walk-forward
   error versus the baseline is reported so you can see whether it actually helps.

Limitations (also shown in the dashboard)
-----------------------------------------
Short synthetic or real histories cannot capture yearly seasonality or one-off events;
forecasts are estimates and should be reviewed by a person.
"""

from __future__ import annotations 

from typing import Dict ,IO ,List ,Mapping ,Optional ,Tuple ,Union 

import numpy as np 
import pandas as pd 

MIN_MONTHS_CAPACITY =12 
MIN_MONTHS_ACTIVITY =6 
MIN_TRAIN_ROWS =5 
LAGS =3 
DEFAULT_HORIZON =6 

ACTIVE_MIN_ACCESSES =50 
RISING_MOMENTUM =1.25 
FALLING_MOMENTUM =0.8 
INACTIVE_MAX_ACCESSES =10 
BURST_RATIO =10 
MIN_BURST_ACCESSES =100 

LIMITATIONS =[
"Forecasts come from a short monthly history and cannot see seasonality longer than the history or one-off events.",
"The scikit-learn model is only used when it beats the moving-average baseline in walk-forward validation.",
"Per-dataset activity labels are a transparent heuristic, not a trained model; review them before acting.",
"If a dataset has too little history it is labelled INSUFFICIENT_HISTORY and only rule-based logic is used.",
]






def load_history (file )->Tuple [pd .DataFrame ,List [str ]]:
    """Read and validate a history CSV. Never raises on bad content; returns (df, messages)."""
    messages :List [str ]=[]
    try :
        raw =pd .read_csv (file ,dtype =str ,skipinitialspace =True ,encoding ="utf-8-sig")
    except Exception as exc :
        return _empty_history (),[f"[ERROR] Could not read the history file: {exc }"]
    raw .columns =[str (c ).strip ().lower ().replace (" ","_")for c in raw .columns ]
    missing =[c for c in ("date","file_name","access_count")if c not in raw .columns ]
    if missing :
        return _empty_history (),[f"[ERROR] History file is missing required column(s): {', '.join (missing )}."]

    out =pd .DataFrame ({
    "date":pd .to_datetime (raw ["date"],errors ="coerce"),
    "file_name":raw ["file_name"].astype ("string").str .strip (),
    "access_count":pd .to_numeric (raw ["access_count"],errors ="coerce"),
    })
    out ["size_gb"]=pd .to_numeric (raw ["size_gb"],errors ="coerce")if "size_gb"in raw .columns else np .nan 
    size_known =pd .to_numeric (raw ["size_gb"],errors ="coerce").notna ()if "size_gb"in raw .columns else pd .Series (False ,index =raw .index )
    bad =(out ["date"].isna ()|out ["file_name"].isna ()
    |(out ["access_count"].isna ()&~size_known )|(out ["access_count"]<0 ))
    if bad .any ():
        messages .append (f"[WARNING] {int (bad .sum ())} history row(s) had an invalid date/name or no usable numbers and were dropped.")
    out =out [~bad ].copy ()
    out ["month"]=out ["date"].dt .to_period ("M").dt .to_timestamp ()
    out =out .groupby (["month","file_name"],as_index =False ).agg (
    access_count =("access_count",lambda x :x .sum (min_count =1 )),size_gb =("size_gb",lambda x :x .sum (min_count =1 )))
    if "size_gb"not in raw .columns :
        out ["size_gb"]=np .nan 
    out =out .rename (columns ={"month":"date"})
    messages .append (f"[INFO] {len (out )} history rows loaded for {out ['file_name'].nunique ()} datasets.")
    return out ,messages 


def _empty_history ()->pd .DataFrame :
    return pd .DataFrame ({"date":pd .Series (dtype ="datetime64[ns]"),"file_name":pd .Series (dtype ="object"),
    "access_count":pd .Series (dtype ="float64"),"size_gb":pd .Series (dtype ="float64")})






def _lag_matrix (values :np .ndarray ,lags :int =LAGS )->Tuple [np .ndarray ,np .ndarray ]:
    X =np .array ([values [i -lags :i ]for i in range (lags ,len (values ))])
    y =values [lags :]
    return X ,y 


def _baseline_next (values :np .ndarray ,window :int =3 )->float :
    return float (np .mean (values [-window :]))


def _model_next (train :np .ndarray )->Optional [float ]:
    """Fit LinearRegression on `train` only and predict one step ahead (None if too little data)."""
    from sklearn .linear_model import LinearRegression 
    X ,y =_lag_matrix (train )
    if len (y )<MIN_TRAIN_ROWS :
        return None 
    model =LinearRegression ().fit (X ,y )
    return float (model .predict (train [-LAGS :].reshape (1 ,-1 ))[0 ])


def forecast_capacity (history :pd .DataFrame ,horizon :int =DEFAULT_HORIZON )->dict :
    """
    Forecast TOTAL stored GB per month. Returns a dict with keys:
        available (bool), message, history (df: date, size_gb), forecast (df), metrics (dict), limitations
    """
    result ={"available":False ,"message":"","history":None ,"forecast":None ,
    "metrics":{},"limitations":LIMITATIONS }
    if history is None or history .empty :
        result ["message"]="No history file provided - capacity forecast not available."
        return result 
    if history ["size_gb"].isna ().all ():
        result ["message"]="The history file has no size_gb column, so total capacity cannot be forecast."
        return result 

    series =history .groupby ("date")["size_gb"].sum (min_count =1 ).sort_index ().dropna ()
    months =pd .date_range (series .index .min (),series .index .max (),freq ="MS")
    if len (months )!=len (series ):
        result ["message"]=("The history has missing months, so no forecast was made "
        "(filling gaps would mean inventing data).")
        return result 
    if len (series )<MIN_MONTHS_CAPACITY :
        result ["message"]=(f"Only {len (series )} months of history; at least {MIN_MONTHS_CAPACITY } are needed "
        f"for a reliable forecast. Using rule-based growth projection instead.")
        result ["history"]=series .reset_index ().rename (columns ={"index":"date"})
        return result 

    values =series .to_numpy (dtype =float )


    start =LAGS +MIN_TRAIN_ROWS 
    actual ,base_pred ,model_pred =[],[],[]
    for t in range (start ,len (values )):
        past =values [:t ]
        m =_model_next (past )
        if m is None :
            continue 
        actual .append (values [t ]);base_pred .append (_baseline_next (past ));model_pred .append (m )
    actual ,base_pred ,model_pred =map (np .array ,(actual ,base_pred ,model_pred ))
    if len (actual )==0 :
        result ["message"]="Not enough history for validation."
        return result 
    mae_base =float (np .mean (np .abs (actual -base_pred )))
    mae_model =float (np .mean (np .abs (actual -model_pred )))
    rmse_base =float (np .sqrt (np .mean ((actual -base_pred )**2 )))
    rmse_model =float (np .sqrt (np .mean ((actual -model_pred )**2 )))
    use_model =mae_model <mae_base 


    def roll (step_fn )->List [float ]:
        buf =list (values )
        out =[]
        for _ in range (horizon ):
            nxt =step_fn (np .array (buf ))
            nxt =max (float (nxt ),0.0 )
            out .append (nxt );buf .append (nxt )
        return out 

    base_f =roll (_baseline_next )
    def model_step (b ):
        pred =_model_next (b )
        return pred if pred is not None else _baseline_next (b )

    model_f =roll (model_step )
    future_idx =pd .date_range (series .index .max ()+pd .offsets .MonthBegin (1 ),periods =horizon ,freq ="MS")
    forecast =pd .DataFrame ({"date":future_idx ,"baseline_gb":base_f ,"model_gb":model_f })
    forecast ["selected_gb"]=forecast ["model_gb"]if use_model else forecast ["baseline_gb"]

    result .update ({
    "available":True ,
    "message":"Capacity forecast available.",
    "history":series .reset_index ().rename (columns ={"index":"date"}),
    "forecast":forecast ,
    "metrics":{
    "validation_points":int (len (actual )),
    "baseline_mae_gb":round (mae_base ,2 ),"model_mae_gb":round (mae_model ,2 ),
    "baseline_rmse_gb":round (rmse_base ,2 ),"model_rmse_gb":round (rmse_model ,2 ),
    "selected_method":"scikit-learn LinearRegression (lag features)"if use_model else "3-month moving average (baseline)",
    "model_beats_baseline":bool (use_model ),
    "improvement_vs_baseline_pct":round ((mae_base -mae_model )/mae_base *100 ,1 )if mae_base >0 else 0.0 ,
    "horizon_months":int (horizon ),
    },
    })
    return result 






def _activity_prediction (values :np .ndarray ,use_trend :bool =True )->Tuple [float ,float ,str ]:
    """From a month-by-month access series return (recent_mean, predicted, trend_label)."""
    recent =float (np .mean (values [-3 :]))
    prior =float (np .mean (values [-6 :-3 ]))if len (values )>=6 else recent 
    momentum =(recent +1.0 )/(prior +1.0 )
    predicted =recent *float (np .clip (momentum ,0.5 ,2.0 ))if use_trend else recent 
    trend ="RISING"if momentum >=RISING_MOMENTUM else ("FALLING"if momentum <=FALLING_MOMENTUM else "STABLE")
    return recent ,predicted ,trend 


def _outlook (values :np .ndarray ,predicted :float ,trend :str )->str :
    recent =float (np .mean (values [-3 :]))
    peak =float (np .max (values ))
    earlier =values [:-3 ]
    bursts =int (np .sum (earlier >=0.5 *peak ))if peak >0 else 0 
    if trend =="RISING"and predicted >=ACTIVE_MIN_ACCESSES :
        return "LIKELY_ACTIVE"
    if recent <INACTIVE_MAX_ACCESSES and peak >=MIN_BURST_ACCESSES and peak >=BURST_RATIO *(recent +1 )and bursts >=2 :
        return "POSSIBLE_REACTIVATION"
    if predicted <INACTIVE_MAX_ACCESSES and trend !="RISING":
        return "LIKELY_INACTIVE"
    return "STABLE"


def _walk_forward_activity (pivot :Optional [pd .DataFrame ])->dict :
    """
    Compare the trend-adjusted predictor with the plain 3-month mean, one month ahead,
    always fitting on earlier months only. Error = WAPE (sum |error| / sum actual), which
    is not dominated by the busiest datasets.
    """
    err_base =err_trend =actual_sum =0.0 
    points =0 
    if pivot is not None :
        for name in pivot .index :
            values =pivot .loc [name ].dropna ().to_numpy (dtype =float )
            for t in range (MIN_MONTHS_ACTIVITY ,len (values )):
                past =values [:t ]
                err_base +=abs (values [t ]-_activity_prediction (past ,use_trend =False )[1 ])
                err_trend +=abs (values [t ]-_activity_prediction (past ,use_trend =True )[1 ])
                actual_sum +=abs (values [t ])
                points +=1 
    metrics ={"evaluated_points":points }
    if points and actual_sum >0 :
        metrics .update ({
        "baseline_wape_pct":round (err_base /actual_sum *100 ,2 ),
        "trend_method_wape_pct":round (err_trend /actual_sum *100 ,2 ),
        "trend_method_beats_baseline":bool (err_trend <err_base ),
        })
    return metrics 


def forecast_activity (history :pd .DataFrame ,file_names :Optional [List [str ]]=None )->Tuple [pd .DataFrame ,dict ]:
    """
    Activity outlook per dataset.
    Returns (table, metrics). The table has one row per dataset in `file_names`
    (or in the history) with: file_name, history_months, recent_avg_accesses,
    predicted_monthly_accesses, demand_trend, demand_outlook.

    The trend-adjusted predictor is used only if it beats the plain 3-month mean in
    walk-forward validation; otherwise the 3-month mean (baseline) is the prediction.
    """
    cols =["file_name","history_months","recent_avg_accesses","predicted_monthly_accesses",
    "demand_trend","demand_outlook"]
    names =list (file_names )if file_names is not None else (list (history ["file_name"].unique ())if history is not None and not history .empty else [])
    pivot =None 
    if history is not None and not history .empty :
        usable =history .dropna (subset =["access_count"])
        if not usable .empty :
            pivot =usable .pivot_table (index ="file_name",columns ="date",values ="access_count",aggfunc ="sum").sort_index (axis =1 )
    metrics =_walk_forward_activity (pivot )
    use_trend =metrics .get ("trend_method_beats_baseline",False )
    metrics ["selected_method"]="trend-adjusted 3-month mean"if use_trend else "3-month mean (baseline)"

    rows =[]
    for name in names :
        values =np .array ([])
        if pivot is not None and name in pivot .index :
            values =pivot .loc [name ].dropna ().to_numpy (dtype =float )
        if len (values )<MIN_MONTHS_ACTIVITY :
            rows .append ((name ,len (values ),np .nan ,np .nan ,"UNKNOWN","INSUFFICIENT_HISTORY"))
            continue 
        recent ,predicted ,trend =_activity_prediction (values ,use_trend =use_trend )
        rows .append ((name ,len (values ),round (recent ,1 ),round (predicted ,1 ),trend ,_outlook (values ,predicted ,trend )))
    return pd .DataFrame (rows ,columns =cols ),metrics 






def project_capacity_by_growth (df :pd .DataFrame ,tier_col :str ,months :int =12 )->pd .DataFrame :
    """
    RULE-BASED PROJECTION (not a prediction): size x (1 + growth_rate_pct/100) ** m for each tier.
    Returns tidy rows: month, tier, projected_gb. Empty if growth_rate_pct is not in the data.
    """
    if "growth_rate_pct"not in df .columns or tier_col not in df .columns :
        return pd .DataFrame (columns =["month","tier","projected_gb"])
    growth =pd .to_numeric (df ["growth_rate_pct"],errors ="coerce").fillna (0.0 )/100.0 
    size =pd .to_numeric (df ["size_gb"],errors ="coerce").fillna (0.0 )
    tiers =df [tier_col ].astype (str ).str .upper ()
    rows =[]
    for m in range (0 ,months +1 ):
        projected =size *(1.0 +growth )**m 
        for tier in ("HOT","WARM","COLD","ARCHIVE"):
            rows .append ({"month":m ,"tier":tier ,"projected_gb":float (projected [tiers ==tier ].sum ())})
    return pd .DataFrame (rows )


def find_capacity_shortages (projection :pd .DataFrame ,capacities_gb :Mapping [str ,float ])->pd .DataFrame :
    """
    First month in which projected usage of a tier exceeds its configured capacity.
    `capacities_gb` values <= 0 mean "not configured" (ignored).
    """
    rows =[]
    if projection is None or projection .empty :
        return pd .DataFrame (columns =["tier","capacity_gb","first_month_over","projected_gb_at_that_month"])
    for tier ,cap in (capacities_gb or {}).items ():
        if cap is None or not np .isfinite (cap )or cap <=0 :
            continue 
        sub =projection [(projection ["tier"]==tier )&(projection ["projected_gb"]>cap )].sort_values ("month")
        if not sub .empty :
            rows .append ({"tier":tier ,"capacity_gb":cap ,"first_month_over":int (sub .iloc [0 ]["month"]),
            "projected_gb_at_that_month":round (float (sub .iloc [0 ]["projected_gb"]),1 )})
    return pd .DataFrame (rows ,columns =["tier","capacity_gb","first_month_over","projected_gb_at_that_month"])






def run_demand_analysis (history :Optional [pd .DataFrame ],df :pd .DataFrame ,horizon :int =DEFAULT_HORIZON )->dict :
    """
    Returns {"has_history", "messages", "capacity", "activity", "activity_metrics", "limitations"}.
    `activity` always has one row per dataset in df (INSUFFICIENT_HISTORY when unknown),
    so the optimizer can join it safely.
    """
    names =list (df ["file_name"])if "file_name"in df .columns else []
    has_history =history is not None and not history .empty 
    messages :List [str ]=[]
    if not has_history :
        messages .append ("No demand history was provided: no predictions are shown and recommendations "
        "use access counts, recency and policy rules only.")
        capacity =forecast_capacity (None ,horizon )
    else :
        capacity =forecast_capacity (history ,horizon )
        if capacity ["message"]and not capacity ["available"]:
            messages .append (capacity ["message"])
        unknown =sorted (set (history ["file_name"])-set (names ))
        if unknown :
            messages .append (f"{len (unknown )} dataset(s) in the history file are not in the workload file and were ignored.")
    activity ,metrics =forecast_activity (history if has_history else None ,names )
    return {"has_history":has_history ,"messages":messages ,"capacity":capacity ,
    "activity":activity ,"activity_metrics":metrics ,"limitations":LIMITATIONS }
