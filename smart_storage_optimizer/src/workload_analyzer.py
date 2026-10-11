"""
workload_analyzer.py -- Workload Analysis Module
================================================

Part of: "Smart Storage Optimization for Modern Workloads"

Takes the validated DataFrame produced by ``data_loader`` and enriches it with
numeric signals that the classification / cost modules can use directly.
It contains NO storage classification, cost, UI, cloud or ML logic.

Quick start
-----------
    from src.data_loader import load_and_validate_workload_data
    from src.workload_analyzer import analyze_workload

    df, issues = load_and_validate_workload_data("data/sample_workload.csv")
    enriched = analyze_workload(df)

Public API
----------
    calculate_recency(df, reference_date=None)          -> df + days_since_last_access
    calculate_access_frequency(df)                      -> df + access_frequency_score
    calculate_data_age(df, reference_date=None)         -> df (+ data_age_days, ONLY if a creation date exists)
    calculate_performance_score(df)                     -> df + performance_score
    analyze_workload(df, reference_date=None)           -> df with all of the above

Input contract (from data_loader)
---------------------------------
    file_name, size_gb, last_accessed (datetime64), access_count (int),
    workload_type, performance_requirement, current_tier

Output contract
---------------
Every original column is returned unchanged (same values, same order), and
these columns are appended:

    column                   dtype      meaning
    -----------------------  ---------  -------------------------------------------
    days_since_last_access   int64      whole days between last_accessed and today
                                        (0 = accessed today; never negative)
    access_frequency_score   float64    0.0 (never accessed) .. 1.0 (busiest file)
    performance_score        int64      1 (very low) .. 5 (very high)
    data_age_days            int64      OPTIONAL -- only present when the input has
                                        a creation-date column (see calculate_data_age)

Each function returns a NEW DataFrame; the DataFrame you pass in is never modified.
"""

from __future__ import annotations 

import warnings 
from typing import Iterable ,List ,Optional ,Union 

import numpy as np 
import pandas as pd 











PERFORMANCE_SCORE_MAP ={
"VERY_LOW":1 ,
"LOW":2 ,
"MEDIUM":3 ,
"HIGH":4 ,
"CRITICAL":5 ,
"VERY_HIGH":5 ,
}



CREATION_DATE_COLUMNS =(
"created_at",
"creation_date",
"created_date",
"date_created",
"created_on",
"created",
"creation_time",
)

DateLike =Union [str ,pd .Timestamp ,"np.datetime64",None ]






def _require_columns (df :pd .DataFrame ,columns :Iterable [str ])->None :
    """Raise a clear error if the input is not a DataFrame or lacks columns."""
    if not isinstance (df ,pd .DataFrame ):
        raise TypeError (f"Expected a pandas DataFrame but got {type (df ).__name__ }.")
    missing =[c for c in columns if c not in df .columns ]
    if missing :
        raise ValueError (
        f"Missing required column(s) for workload analysis: {', '.join (missing )}."
        )


def _resolve_reference_date (reference_date :DateLike )->pd .Timestamp :
    """
    The date "now" is measured against. Defaults to today (midnight).

    Passing an explicit date makes results reproducible (useful for tests and
    for a demo where the sample data should not drift day by day).
    """
    ref =pd .Timestamp .now ()if reference_date is None else pd .Timestamp (reference_date )
    if ref .tzinfo is not None :
        ref =ref .tz_convert (None )
    return ref .normalize ()


def _to_naive_dates (series :pd .Series )->pd .Series :
    """Parse to datetime (bad values -> NaT), drop timezone, strip time-of-day."""
    try :
        parsed =pd .to_datetime (series ,errors ="coerce",format ="mixed")
    except (TypeError ,ValueError ):
        parsed =pd .to_datetime (series ,errors ="coerce")
    if getattr (parsed .dt ,"tz",None )is not None :
        parsed =parsed .dt .tz_convert (None )
    return parsed .dt .normalize ()


def _days_before (reference :pd .Timestamp ,dates :pd .Series )->pd .Series :
    """
    Whole days from ``dates`` up to ``reference``, floored at 0.

    A date later than the reference (a "future" date, which data_loader keeps
    with a warning) would give a negative number. We clip it to 0, i.e.
    "happened today", so downstream maths never sees negative ages.
    """
    days =(reference -_to_naive_dates (dates )).dt .days 
    days =days .clip (lower =0 )



    return days .astype ("int64")if days .notna ().all ()else days .astype ("float64")






def calculate_recency (df :pd .DataFrame ,reference_date :DateLike =None )->pd .DataFrame :
    """
    Add ``days_since_last_access``: how many days ago each file was last used.

    Calculation
    -----------
        days_since_last_access = reference_date - last_accessed   (in whole days)

    * ``reference_date`` defaults to today.
    * Time-of-day is ignored (both dates are normalised to midnight).
    * Dates in the future are clipped to 0.
    * Small number  -> recently used ("hot" signal).
      Large number  -> idle for a long time ("cold" signal).

    Parameters
    ----------
    df : DataFrame with a ``last_accessed`` column.
    reference_date : optional date-like; fixes "today" for reproducible results.

    Returns
    -------
    A copy of ``df`` with the extra ``days_since_last_access`` column (int64).
    """
    _require_columns (df ,["last_accessed"])
    out =df .copy ()
    reference =_resolve_reference_date (reference_date )
    out ["days_since_last_access"]=_days_before (reference ,out ["last_accessed"])
    return out 






def calculate_access_frequency (df :pd .DataFrame )->pd .DataFrame :
    """
    Add ``access_frequency_score``: access_count normalised to 0.0 .. 1.0.

    Calculation (log-scaled, relative to the busiest file)
    ------------------------------------------------------
        score = log(1 + access_count) / log(1 + max_access_count)

    Why log? Access counts are very skewed (a database may have 90,000 reads
    while a log file has 40). A plain min-max scale would squash every
    non-database file to ~0.00; the log keeps the differences visible.

    Behaviour
    ---------
    * 0 accesses            -> 0.0 (log(1) = 0), always.
    * the busiest file      -> 1.0.
    * every file has 0 hits -> all 0.0 (no divide-by-zero).
    * The score is RELATIVE to the rows passed in, so the same file can score
      differently in a different dataset. Analyse the whole workload at once.

    Parameters
    ----------
    df : DataFrame with an ``access_count`` column (non-negative numbers).

    Returns
    -------
    A copy of ``df`` with the extra ``access_frequency_score`` column
    (float64, rounded to 4 decimals).
    """
    _require_columns (df ,["access_count"])
    out =df .copy ()


    counts =pd .to_numeric (out ["access_count"],errors ="coerce").clip (lower =0 )
    logged =np .log1p (counts )
    max_logged =logged .max ()

    if pd .isna (max_logged )or max_logged ==0 :

        score =logged *0.0 
    else :
        score =logged /max_logged 

    out ["access_frequency_score"]=score .round (4 ).astype ("float64")
    return out 






def _find_creation_column (df :pd .DataFrame )->Optional [str ]:
    """Return the name of a creation-date column if the frame has one."""
    for col in df .columns :
        if str (col ).strip ().lower ().replace (" ","_")in CREATION_DATE_COLUMNS :
            return col 
    return None 


def calculate_data_age (df :pd .DataFrame ,reference_date :DateLike =None )->pd .DataFrame :
    """
    Add ``data_age_days``: how old each file is, IF a creation date exists.

    Calculation
    -----------
        data_age_days = reference_date - creation date   (in whole days)

    The creation date is read from the first column whose name matches one of
    ``CREATION_DATE_COLUMNS`` (e.g. ``created_at``, ``creation_date``).

    IMPORTANT: the standard data_loader schema has NO creation date. In that
    case this function returns the DataFrame unchanged and adds NO column.
    Nothing is guessed -- ``last_accessed`` is not a creation date and is
    never used as a substitute. Check ``"data_age_days" in df.columns``
    before using it downstream.

    Parameters
    ----------
    df : DataFrame, optionally containing a creation-date column.
    reference_date : optional date-like; defaults to today.

    Returns
    -------
    A copy of ``df``; with ``data_age_days`` appended only when a creation-date
    column was found. Unparseable or future creation dates are handled like
    in ``calculate_recency`` (future -> 0, unparseable -> NaN).
    """
    if not isinstance (df ,pd .DataFrame ):
        raise TypeError (f"Expected a pandas DataFrame but got {type (df ).__name__ }.")
    out =df .copy ()

    creation_col =_find_creation_column (out )
    if creation_col is None :
        return out 

    reference =_resolve_reference_date (reference_date )
    out ["data_age_days"]=_days_before (reference ,out [creation_col ])
    return out 






def calculate_performance_score (df :pd .DataFrame )->pd .DataFrame :
    """
    Add ``performance_score``: performance_requirement as a number, 1..5.

        VERY_LOW  = 1
        LOW       = 2
        MEDIUM    = 3
        HIGH      = 4
        CRITICAL  = 5   (also accepted: VERY_HIGH = 5)

    Matching ignores case, surrounding spaces, and treats spaces/hyphens as
    underscores ("very low", "Very-Low" -> VERY_LOW).

    A higher score means the workload needs faster storage. Any value outside
    the table above gets NaN (never a guessed number) and triggers a warning,
    so one bad label does not crash the whole pipeline.

    Parameters
    ----------
    df : DataFrame with a ``performance_requirement`` column.

    Returns
    -------
    A copy of ``df`` with the extra ``performance_score`` column (int64, or
    float64 with NaN if some labels were unrecognised).
    """
    _require_columns (df ,["performance_requirement"])
    out =df .copy ()

    labels =(
    out ["performance_requirement"]
    .astype ("string")
    .str .strip ()
    .str .upper ()
    .str .replace (r"[\s\-]+","_",regex =True )
    )
    scores =labels .map (PERFORMANCE_SCORE_MAP )

    unknown =sorted (set (labels [scores .isna ()&labels .notna ()].dropna ()))
    if unknown :
        warnings .warn (
        "Unrecognised performance_requirement value(s) "
        f"{unknown }; performance_score set to NaN for those rows. "
        f"Known values: {', '.join (PERFORMANCE_SCORE_MAP )}.",
        stacklevel =2 ,
        )

    scores =scores .astype ("float64")
    out ["performance_score"]=scores .astype ("int64")if scores .notna ().all ()else scores 
    return out 






def analyze_workload (df :pd .DataFrame ,reference_date :DateLike =None )->pd .DataFrame :
    """
    Run the whole workload analysis and return the enriched DataFrame.

    Steps (in order)
    ----------------
        1. calculate_recency            -> days_since_last_access
        2. calculate_access_frequency   -> access_frequency_score
        3. calculate_data_age           -> data_age_days (only if a creation date exists)
        4. calculate_performance_score  -> performance_score

    Original columns are left untouched and stay first; the new columns are
    appended in the order above. The input DataFrame is not modified.

    Parameters
    ----------
    df : validated DataFrame from data_loader.
    reference_date : optional; fixes "today" so results are reproducible.

    Returns
    -------
    Enriched DataFrame, ready for the next module. An empty input gives an
    empty output that still has all the columns.
    """
    _require_columns (df ,["last_accessed","access_count","performance_requirement"])

    result =calculate_recency (df ,reference_date )
    result =calculate_access_frequency (result )
    result =calculate_data_age (result ,reference_date )
    result =calculate_performance_score (result )
    return result 






if __name__ =="__main__":
    import sys 

    from src .data_loader import load_and_validate_workload_data 

    csv_path =sys .argv [1 ]if len (sys .argv )>1 else "data/sample_workload.csv"
    frame ,messages =load_and_validate_workload_data (csv_path )
    print ("\n".join (messages ))
    print ()
    enriched =analyze_workload (frame )
    print (enriched .dtypes )
    print ()
    show =[
    "file_name",
    "days_since_last_access",
    "access_count",
    "access_frequency_score",
    "performance_requirement",
    "performance_score",
    ]
    print (enriched [show ].head (15 ).to_string ())
