"""
data_loader.py -- Data Input & Workload Data Module
===================================================

Part of: "Smart Storage Optimization for Modern Workloads"

This module is the single entry point for getting workload data into the
system. It loads a workload CSV, validates and cleans it, and hands a tidy
Pandas DataFrame to the other modules (optimizer, cost calculator,
dashboard). It contains NO optimization, cost, or UI logic.

Quick start
-----------
    from src.data_loader import load_and_validate_workload_data

    df, issues = load_and_validate_workload_data("data/sample_workload.csv")
    for line in issues:
        print(line)
    # `df` is now safe to pass to any other module.

Public API
----------
    load_workload_data(file)                  -> raw DataFrame (nothing validated)
    validate_workload_data(df)                -> (clean DataFrame, list[str] issues)
    load_and_validate_workload_data(file)     -> (clean DataFrame, list[str] issues)
    create_sample_workload(path, n_rows, seed)-> writes a synthetic CSV, returns DataFrame

Expected columns (the "data contract")
--------------------------------------
The DataFrame returned by `validate_workload_data` always has exactly these
columns, in this order, with these dtypes:

    column                   dtype            rules / normalisation
    -----------------------  ---------------  ------------------------------------------
    file_name                object (str)     required, non-empty, unique (first kept)
    size_gb                  float64          required, numeric, finite, > 0
    last_accessed            datetime64[ns]   required, valid date (time part removed)
    access_count             int64            required, whole number, >= 0
    workload_type            object (str)     required, non-empty, lower-cased
                                              (e.g. "database", "backup", "analytics")
    performance_requirement  object (str)     required, one of LOW / MEDIUM / HIGH /
                                              CRITICAL (case-insensitive on input,
                                              UPPER-CASE on output)
    current_tier             object (str)     optional; one of HOT / WARM / COLD /
                                              ARCHIVE (UPPER-CASE). Missing or invalid
                                              values become "UNKNOWN" (row is kept).

Guarantees for consumers of the clean DataFrame:
    * no missing values in any column
    * a fresh 0..n-1 index
    * every row passed validation (bad rows are dropped, never silently "fixed"
      -- except current_tier, which falls back to "UNKNOWN")
    * may be empty (zero rows) but ALWAYS has the columns above

Issue messages
--------------
`validate_workload_data` returns a list of human-readable strings, each
starting with a level tag:

    [ERROR]   a row was dropped, or the whole input was unusable
    [WARNING] the row was kept but something looks off / was adjusted
    [INFO]    summary line (always the last entry)

Row numbers in messages are 1-based positions of the data rows, i.e. the
first record under the CSV header is "Row 1". (Malformed lines skipped by the
loader are not counted, so numbers after one can be off by that many.)

Configuration
-------------
Change `VALID_PERFORMANCE_REQUIREMENTS` or `VALID_TIERS` below if the team
agrees on different vocabularies -- the rest of the module adapts.
"""

from __future__ import annotations 

import os 
from typing import IO ,List ,Tuple ,Union 

import numpy as np 
import pandas as pd 





REQUIRED_COLUMNS :List [str ]=[
"file_name",
"size_gb",
"last_accessed",
"access_count",
"workload_type",
"performance_requirement",
"current_tier",
]


OPTIONAL_COLUMNS :List [str ]=["current_tier"]




EXTENDED_NUMERIC_COLUMNS :List [str ]=[
"read_frequency",
"write_frequency",
"read_iops",
"write_iops",
"throughput_mbps",
"observed_latency_ms",
"max_latency_ms",
"growth_rate_pct",
"retention_days",
"recovery_time_hours",
"migration_cost",
]
EXTENDED_TEXT_COLUMNS :List [str ]=[
"required_region",
"current_region",
"security_class",
"approved_tiers",
"data_source",
]
EXTENDED_BOOL_COLUMNS :List [str ]=["legal_hold"]
EXTENDED_COLUMNS :List [str ]=EXTENDED_NUMERIC_COLUMNS +EXTENDED_TEXT_COLUMNS +EXTENDED_BOOL_COLUMNS 
VALID_SECURITY_CLASSES :Tuple [str ,...]=("PUBLIC","INTERNAL","CONFIDENTIAL","RESTRICTED")
_TRUE_WORDS ={"true","yes","y","1","t"}
_FALSE_WORDS ={"false","no","n","0","f"}

VALID_PERFORMANCE_REQUIREMENTS :Tuple [str ,...]=("LOW","MEDIUM","HIGH","CRITICAL")
VALID_TIERS :Tuple [str ,...]=("HOT","WARM","COLD","ARCHIVE")
UNKNOWN_TIER :str ="UNKNOWN"

_TEXT_COLUMNS =["file_name","workload_type","performance_requirement","current_tier"]

FileInput =Union [str ,"os.PathLike[str]",IO ]






def _empty_workload_frame ()->pd .DataFrame :
    """Zero-row DataFrame with the final columns and dtypes."""
    return pd .DataFrame (
    {
    "file_name":pd .Series (dtype ="object"),
    "size_gb":pd .Series (dtype ="float64"),
    "last_accessed":pd .Series (dtype ="datetime64[ns]"),
    "access_count":pd .Series (dtype ="int64"),
    "workload_type":pd .Series (dtype ="object"),
    "performance_requirement":pd .Series (dtype ="object"),
    "current_tier":pd .Series (dtype ="object"),
    }
    )[REQUIRED_COLUMNS ]


def _normalise_column_name (name :object )->str :
    """' Size GB ' -> 'size_gb' so slightly messy headers still load."""
    return str (name ).strip ().lower ().replace (" ","_").replace ("-","_")


def _clean_text (series :pd .Series )->pd .Series :
    """Strip whitespace; blank strings become missing. Returns object dtype."""
    s =series .astype ("string").str .strip ()
    s =s .mask (s =="")
    return s .astype (object ).where (s .notna (),None )


def _to_number (raw :pd .Series )->pd .Series :
    """Convert to float; anything that is not a number becomes NaN."""
    return pd .to_numeric (raw ,errors ="coerce").astype ("float64")


def _to_datetime (raw :pd .Series )->pd .Series :
    """Parse dates leniently; anything unparseable becomes NaT."""
    try :
        parsed =pd .to_datetime (raw ,errors ="coerce",format ="mixed")
    except (TypeError ,ValueError ):
        parsed =pd .to_datetime (raw ,errors ="coerce")
    if getattr (parsed .dt ,"tz",None )is not None :
        parsed =parsed .dt .tz_convert (None )
    return parsed .dt .normalize ().astype ("datetime64[ns]")


def _shown (value :object )->str :
    """Format a raw cell for use inside a message."""
    return "<missing>"if value is None or (isinstance (value ,float )and np .isnan (value ))else repr (value )


def _clean_extended_columns (work :pd .DataFrame ,issues :List [str ])->pd .DataFrame :
    """
    Clean whichever optional extended columns are present. Never drops rows:
    a bad optional value becomes missing (NaN / None) and is reported once per column.
    """
    out =pd .DataFrame (index =work .index )

    for col in EXTENDED_NUMERIC_COLUMNS :
        if col not in work .columns :
            continue 
        raw =_clean_text (work [col ])
        num =_to_number (raw )
        bad =raw .notna ()&(num .isna ()|~np .isfinite (num )|(num <0 ))
        if bad .any ():
            issues .append (
            f"[WARNING] Column '{col }': {int (bad .sum ())} value(s) were not valid non-negative "
            f"numbers (e.g. {_shown (raw [bad ].iloc [0 ])}); treated as missing."
            )
        out [col ]=num .where (~bad ,np .nan )

    for col in EXTENDED_TEXT_COLUMNS :
        if col not in work .columns :
            continue 
        raw =_clean_text (work [col ])
        if col in ("required_region","current_region"):
            raw =raw .str .lower ()
        elif col in ("security_class","data_source"):
            raw =raw .str .upper ()
        elif col =="approved_tiers":
            cleaned =[]
            for value in raw :
                if value is None or pd .isna (value ):
                    cleaned .append (None )
                    continue 
                tokens =[t .strip ().upper ()for t in str (value ).replace (",","|").replace (";","|").split ("|")]
                good =[t for t in tokens if t in VALID_TIERS ]
                if len (good )!=len ([t for t in tokens if t ]):
                    issues .append (f"[WARNING] approved_tiers value {_shown (value )} contains unknown tier names; they were ignored.")
                cleaned .append ("|".join (good )if good else None )
            raw =pd .Series (cleaned ,index =raw .index ,dtype =object )
        if col =="security_class":
            bad =raw .notna ()&~raw .isin (VALID_SECURITY_CLASSES )
            if bad .any ():
                issues .append (
                f"[WARNING] Column 'security_class': {int (bad .sum ())} value(s) not in "
                f"{', '.join (VALID_SECURITY_CLASSES )}; treated as missing."
                )
                raw =raw .where (~bad ,None )
        out [col ]=raw 

    for col in EXTENDED_BOOL_COLUMNS :
        if col not in work .columns :
            continue 
        raw =_clean_text (work [col ]).str .lower ()
        parsed =raw .map (lambda v :True if v in _TRUE_WORDS else (False if v in _FALSE_WORDS else None ))
        bad =raw .notna ()&parsed .isna ()
        if bad .any ():
            issues .append (f"[WARNING] Column '{col }': {int (bad .sum ())} value(s) were not yes/no; treated as unknown.")
        out [col ]=parsed .astype (object )

    return out 






def load_workload_data (file :FileInput )->pd .DataFrame :
    """
    Read a workload CSV into a DataFrame WITHOUT validating it.

    Parameters
    ----------
    file : str | os.PathLike | file-like
        A path to a CSV, or an open file-like object (e.g. a Streamlit
        ``UploadedFile`` or ``io.StringIO``).

    Returns
    -------
    pandas.DataFrame
        Every value is kept as text (dtype=str) so that bad values survive
        until `validate_workload_data` can report them properly. Column
        headers are normalised (trimmed, lower-cased, spaces -> underscores).
        Malformed CSV lines (wrong number of fields) are skipped and noted in
        ``df.attrs["load_warnings"]``, which `validate_workload_data` reports.

    Raises
    ------
    FileNotFoundError
        If ``file`` is a path that does not exist (nothing sensible to load).

    Notes
    -----
    Most callers want `load_and_validate_workload_data` instead; the raw
    DataFrame is NOT safe to feed to the optimizer.
    """
    if isinstance (file ,(str ,os .PathLike ))and not os .path .exists (file ):
        raise FileNotFoundError (f"Workload file not found: {file }")

    load_warnings :List [str ]=[]

    def _on_bad_line (fields :List [str ]):
        preview =",".join (fields )[:60 ]
        load_warnings .append (
        f"[ERROR] Malformed CSV line skipped (wrong number of fields): '{preview }'"
        )
        return None 

    try :
        df =pd .read_csv (
        file ,
        dtype =str ,
        skipinitialspace =True ,
        encoding ="utf-8-sig",
        engine ="python",
        on_bad_lines =_on_bad_line ,
        )
    except pd .errors .EmptyDataError :
        df =pd .DataFrame (columns =REQUIRED_COLUMNS ,dtype =str )
        load_warnings .append ("[ERROR] The file is empty (no header row found).")
    except UnicodeDecodeError :

        if hasattr (file ,"seek"):
            file .seek (0 )
        df =pd .read_csv (
        file ,
        dtype =str ,
        skipinitialspace =True ,
        encoding ="latin-1",
        engine ="python",
        on_bad_lines =_on_bad_line ,
        )
        load_warnings .append ("[WARNING] File is not UTF-8; it was read as latin-1.")

    df .columns =[_normalise_column_name (c )for c in df .columns ]
    df .attrs ["load_warnings"]=load_warnings 
    return df 






def validate_workload_data (df :pd .DataFrame )->Tuple [pd .DataFrame ,List [str ]]:
    """
    Validate and clean a workload DataFrame. Never raises on bad data.

    Parameters
    ----------
    df : pandas.DataFrame
        Raw workload data (typically from `load_workload_data`, but any
        DataFrame with the expected column names works).

    Returns
    -------
    (clean_df, issues) : tuple
        clean_df : DataFrame with exactly `REQUIRED_COLUMNS`, the dtypes in the
                   module docstring, and only valid rows.
        issues   : list of "[ERROR] ...", "[WARNING] ...", "[INFO] ..." strings.

    Validation rules
    ----------------
    Row is DROPPED ([ERROR]) when:
        * file_name is empty
        * size_gb is not a finite number, or is <= 0
        * access_count is not a number, is negative, or is not a whole number
        * last_accessed is missing or not a valid date
        * workload_type is empty
        * performance_requirement is empty or not in VALID_PERFORMANCE_REQUIREMENTS
        * file_name duplicates an earlier row (first occurrence is kept) [WARNING]

    Row is KEPT with a [WARNING] when:
        * current_tier is missing/invalid  -> set to "UNKNOWN"
        * last_accessed is in the future   -> kept as-is
        * the input had extra columns      -> ignored
    """
    issues :List [str ]=[]

    if not isinstance (df ,pd .DataFrame ):
        return _empty_workload_frame (),[
        f"[ERROR] Expected a pandas DataFrame but got {type (df ).__name__ }.",
        "[INFO] 0 of 0 rows valid.",
        ]

    issues .extend (df .attrs .get ("load_warnings",[]))

    work =df .copy ()
    work .columns =[_normalise_column_name (c )for c in work .columns ]
    work =work .reset_index (drop =True )


    missing_cols =[c for c in REQUIRED_COLUMNS if c not in work .columns ]

    for col in OPTIONAL_COLUMNS :
        if col in missing_cols :
            work [col ]=None 
            missing_cols .remove (col )
            issues .append (f"[WARNING] Column '{col }' not found; all rows set to '{UNKNOWN_TIER }'.")
    if missing_cols :
        issues .append (f"[ERROR] Required column(s) missing: {', '.join (missing_cols )}.")
        issues .append ("[INFO] 0 of 0 rows valid.")
        return _empty_workload_frame (),issues 

    extra_cols =[c for c in work .columns if c not in REQUIRED_COLUMNS and c not in EXTENDED_COLUMNS ]
    if extra_cols :
        issues .append (f"[WARNING] Ignoring unexpected column(s): {', '.join (extra_cols )}.")
    ext_present =[c for c in EXTENDED_COLUMNS if c in work .columns ]
    ext_missing =[c for c in EXTENDED_COLUMNS if c not in work .columns ]
    if ext_missing and len (ext_missing )<len (EXTENDED_COLUMNS ):
        issues .append (f"[INFO] Optional column(s) not provided (checks that need them are skipped or marked uncertain): {', '.join (ext_missing )}.")
    elif ext_missing :
        issues .append ("[INFO] No optional SmartStore columns found (latency, IOPS, region, legal hold ...). "
        "The basic pipeline still runs, but policy and SLA checks will be marked 'not evaluated' or 'needs data'.")
    extended =_clean_extended_columns (work ,issues )
    work =work [REQUIRED_COLUMNS ]

    total_rows =len (work )
    if total_rows ==0 :
        issues .append ("[WARNING] The input contains no data rows.")
        issues .append ("[INFO] 0 of 0 rows valid.")
        return _empty_workload_frame (),issues 


    raw ={col :_clean_text (work [col ])for col in REQUIRED_COLUMNS }

    size =_to_number (raw ["size_gb"])
    access =_to_number (raw ["access_count"])
    dates =_to_datetime (raw ["last_accessed"])
    workload =raw ["workload_type"].str .lower ()
    perf =raw ["performance_requirement"].str .upper ()
    tier =raw ["current_tier"].str .upper ()


    row_errors :List [List [str ]]=[[]for _ in range (total_rows )]

    def flag (mask :pd .Series ,message_for )->None :
        for i in np .flatnonzero (mask .to_numpy ()):
            row_errors [i ].append (message_for (i ))

    flag (raw ["file_name"].isna (),lambda i :"file_name is empty")

    flag (
    size .isna ()|~np .isfinite (size ),
    lambda i :f"size_gb is missing or not numeric ({_shown (raw ['size_gb'][i ])})",
    )
    flag (
    size .notna ()&np .isfinite (size )&(size <=0 ),
    lambda i :f"size_gb must be positive ({_shown (raw ['size_gb'][i ])})",
    )

    flag (
    access .isna ()|~np .isfinite (access ),
    lambda i :f"access_count is missing or not numeric ({_shown (raw ['access_count'][i ])})",
    )
    flag (
    access .notna ()&np .isfinite (access )&(access <0 ),
    lambda i :f"access_count must not be negative ({_shown (raw ['access_count'][i ])})",
    )
    flag (
    access .notna ()&np .isfinite (access )&(access >=0 )&(access %1 !=0 ),
    lambda i :f"access_count must be a whole number ({_shown (raw ['access_count'][i ])})",
    )

    flag (
    dates .isna (),
    lambda i :f"last_accessed is missing or not a valid date ({_shown (raw ['last_accessed'][i ])})",
    )

    flag (workload .isna (),lambda i :"workload_type is empty")

    flag (
    perf .isna (),
    lambda i :"performance_requirement is empty",
    )
    flag (
    perf .notna ()&~perf .isin (VALID_PERFORMANCE_REQUIREMENTS ),
    lambda i :(
    f"performance_requirement {_shown (raw ['performance_requirement'][i ])} is not one of "
    f"{', '.join (VALID_PERFORMANCE_REQUIREMENTS )}"
    ),
    )


    today =pd .Timestamp .now ().normalize ()
    future =dates .notna ()&(dates >today )
    for i in np .flatnonzero (future .to_numpy ()):
        if not row_errors [i ]:
            issues .append (
            f"[WARNING] Row {i +1 } ({raw ['file_name'][i ]}): last_accessed is in the future "
            f"({dates [i ].date ()}); kept as-is."
            )

    bad_tier =tier .isna ()|~tier .isin (VALID_TIERS )
    for i in np .flatnonzero (bad_tier .to_numpy ()):
        if row_errors [i ]:
            continue 
        if tier [i ]is None or pd .isna (tier [i ]):
            issues .append (
            f"[WARNING] Row {i +1 } ({raw ['file_name'][i ]}): current_tier is empty; "
            f"set to '{UNKNOWN_TIER }'."
            )
        else :
            issues .append (
            f"[WARNING] Row {i +1 } ({raw ['file_name'][i ]}): current_tier "
            f"{_shown (raw ['current_tier'][i ])} is not one of {', '.join (VALID_TIERS )}; "
            f"set to '{UNKNOWN_TIER }'."
            )
    tier =tier .where (~bad_tier ,UNKNOWN_TIER )


    valid_mask =pd .Series ([not errs for errs in row_errors ])
    for i ,errs in enumerate (row_errors ):
        if errs :
            name =raw ["file_name"][i ]if raw ["file_name"][i ]is not None else "<no file_name>"
            issues .append (f"[ERROR] Row {i +1 } ({name }) dropped: "+"; ".join (errs )+".")

    clean =pd .DataFrame (
    {
    "file_name":raw ["file_name"],
    "size_gb":size ,
    "last_accessed":dates ,
    "access_count":access ,
    "workload_type":workload ,
    "performance_requirement":perf ,
    "current_tier":tier ,
    }
    )
    for col in extended .columns :
        clean [col ]=extended [col ]
    clean =clean [valid_mask .to_numpy ()]


    dup =clean ["file_name"].duplicated (keep ="first")
    if dup .any ():
        for idx in clean .index [dup ]:
            issues .append (
            f"[WARNING] Row {idx +1 } ({clean .at [idx ,'file_name']}) dropped: duplicate "
            f"file_name (first occurrence kept)."
            )
        clean =clean [~dup ]


    if clean .empty :
        clean =_empty_workload_frame ()
    else :
        clean =clean .astype (
        {
        "file_name":"object",
        "size_gb":"float64",
        "last_accessed":"datetime64[ns]",
        "access_count":"int64",
        "workload_type":"object",
        "performance_requirement":"object",
        "current_tier":"object",
        }
        ).reset_index (drop =True )

    issues .append (f"[INFO] {len (clean )} of {total_rows } rows valid.")
    return clean ,issues 






def load_and_validate_workload_data (file :FileInput )->Tuple [pd .DataFrame ,List [str ]]:
    """
    Load a workload CSV and validate it in one step.

    This is what the other modules should normally call.

    Returns
    -------
    (clean_df, issues) -- see `validate_workload_data`.

    Raises
    ------
    FileNotFoundError if ``file`` is a non-existent path.
    """
    return validate_workload_data (load_workload_data (file ))






def create_sample_workload (
path :Union [str ,"os.PathLike[str]",None ]="data/sample_workload.csv",
n_rows :int =50 ,
seed :int =42 ,
)->pd .DataFrame :
    """
    Generate a realistic synthetic workload dataset (useful for demos/tests).

    Parameters
    ----------
    path   : where to write the CSV; pass None to skip writing.
    n_rows : number of rows to generate.
    seed   : random seed so teammates get identical data.

    Returns
    -------
    The generated DataFrame (already satisfies the data contract).
    """
    rng =np .random .default_rng (seed )
    today =pd .Timestamp .now ().normalize ()


    profiles =[
    ("database",(50 ,800 ),3 ,90000 ,["CRITICAL","HIGH"],"HOT"),
    ("analytics",(100 ,2000 ),30 ,2500 ,["HIGH","MEDIUM"],"WARM"),
    ("media",(20 ,1500 ),120 ,300 ,["MEDIUM","LOW"],"WARM"),
    ("logs",(5 ,300 ),200 ,60 ,["LOW"],"COLD"),
    ("backup",(200 ,5000 ),730 ,4 ,["LOW"],"COLD"),
    ("archive",(500 ,10000 ),1500 ,1 ,["LOW"],"ARCHIVE"),
    ]

    rows =[]
    for i in range (n_rows ):
        wtype ,(lo ,hi ),max_days ,max_hits ,perfs ,tier =profiles [i %len (profiles )]
        rows .append (
        {
        "file_name":f"{wtype }_{i +1 :03d}.dat",
        "size_gb":round (float (rng .uniform (lo ,hi )),2 ),
        "last_accessed":(today -pd .Timedelta (days =int (rng .integers (0 ,max_days +1 )))).date (),
        "access_count":int (rng .integers (0 ,max_hits +1 )),
        "workload_type":wtype ,
        "performance_requirement":str (rng .choice (perfs )),
        "current_tier":tier ,
        }
        )
    df =pd .DataFrame (rows ,columns =REQUIRED_COLUMNS )

    if path is not None :
        os .makedirs (os .path .dirname (os .fspath (path ))or ".",exist_ok =True )
        df .to_csv (path ,index =False )

    clean ,_ =validate_workload_data (df )
    return clean 






if __name__ =="__main__":
    import sys 

    csv_path =sys .argv [1 ]if len (sys .argv )>1 else "data/sample_workload.csv"
    frame ,messages =load_and_validate_workload_data (csv_path )
    print ("\n".join (messages ))
    print ()
    print (frame .dtypes )
    print ()
    print (frame .head (10 ).to_string ())
