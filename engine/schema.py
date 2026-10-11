import re 
from typing import Any ,Dict ,List 
import pandas as pd 
from engine .types import ChangeType ,Problem ,ProblemCategory 

def analyze_schema (df :pd .DataFrame )->List [Problem ]:
    problems :List [Problem ]=[]
    total_rows =len (df )


    dirty_columns ={}
    for col in df .columns :
        clean_col =re .sub (r'\s+',' ',str (col )).strip ()
        if clean_col !=str (col ):
            dirty_columns [str (col )]=clean_col 

    if dirty_columns :
        problems .append (Problem (
        id ="dirty_column_names",
        category =ProblemCategory .SCHEMA_PROBLEMS ,
        column =None ,
        description =f"{len (dirty_columns )} column names have leading, trailing, or uneven spaces.",
        affected_count =len (dirty_columns ),
        action_type =ChangeType .SAFE ,
        proposed_change ="Clean and trim column names.",
        fix_type ="rename_columns",
        details ={"mapping":dirty_columns }
        ))


    dup_cols =[str (c )for c in df .columns if re .search (r'\.\d+$',str (c ))]
    if dup_cols :
        problems .append (Problem (
        id ="duplicate_column_headers",
        category =ProblemCategory .SCHEMA_PROBLEMS ,
        column =None ,
        description =f"Found {len (dup_cols )} duplicate column names: {', '.join (dup_cols )}.",
        affected_count =len (dup_cols ),
        action_type =ChangeType .REVIEW ,
        proposed_change ="Review and rename duplicate column headers.",
        fix_type ="review_duplicate_columns",
        details ={"duplicate_columns":dup_cols }
        ))


    empty_cols =[str (c )for c in df .columns if df [c ].isna ().all ()]
    if empty_cols :
        problems .append (Problem (
        id ="empty_columns",
        category =ProblemCategory .SCHEMA_PROBLEMS ,
        column =None ,
        description =f"Found {len (empty_cols )} completely empty columns (all values missing): {', '.join (empty_cols )}.",
        affected_count =len (empty_cols ),
        action_type =ChangeType .REVIEW ,
        proposed_change =f"Drop {len (empty_cols )} empty columns that contain no data.",
        fix_type ="drop_empty_columns",
        details ={"empty_columns":empty_cols }
        ))


    if total_rows >1 :
        constant_cols =[]
        for col in df .columns :
            if str (col )not in empty_cols :
                non_null =df [col ].dropna ()
                if len (non_null )>0 and non_null .nunique ()==1 :
                    constant_cols .append (str (col ))

        if constant_cols :
            problems .append (Problem (
            id ="constant_columns",
            category =ProblemCategory .SCHEMA_PROBLEMS ,
            column =None ,
            description =f"Found {len (constant_cols )} constant columns where all rows have the exact same value: {', '.join (constant_cols )}.",
            affected_count =len (constant_cols ),
            action_type =ChangeType .UNCHANGED ,
            proposed_change ="Flag constant columns for review.",
            fix_type ="flag_constant_columns",
            details ={"constant_columns":constant_cols }
            ))

    return problems 
