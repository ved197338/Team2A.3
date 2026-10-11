from typing import Any ,Dict ,List ,Optional 
import pandas as pd 
from engine .types import ChangeType ,Problem ,ProblemCategory 

def detect_duplicates (df :pd .DataFrame ,key_columns :Optional [List [str ]]=None )->List [Problem ]:
    problems :List [Problem ]=[]
    total_rows =len (df )
    if total_rows <=1 :
        return problems 


    row_hashes =pd .util .hash_pandas_object (df ,index =False )
    hash_groups =row_hashes .groupby (row_hashes ).groups 

    exact_duplicate_rows :List [int ]=[]
    samples :List [Dict [str ,Any ]]=[]

    for h ,indices in hash_groups .items ():
        if len (indices )>1 :
            idx_list =indices .tolist ()
            first_row =df .iloc [idx_list [0 ]]
            for i in idx_list [1 :]:
                if df .iloc [i ].equals (first_row ):
                    exact_duplicate_rows .append (i )
            if len (samples )<5 :
                samples .append ({
                "original_row":idx_list [0 ],
                "duplicate_rows":idx_list [1 :],
                })

    if exact_duplicate_rows :
        count =len (exact_duplicate_rows )
        problems .append (Problem (
        id ="exact_duplicates",
        category =ProblemCategory .DUPLICATE_RECORDS ,
        column =None ,
        description =f"Found {count } exact duplicate rows ({count /total_rows :.1%}).",
        affected_count =count ,
        action_type =ChangeType .SAFE ,
        proposed_change =f"Remove {count } duplicate rows, keeping the first occurrence.",
        fix_type ="drop_duplicates",
        row_indices =sorted (exact_duplicate_rows ),
        details ={
        "duplicate_rows":sorted (exact_duplicate_rows ),
        "samples":samples ,
        }
        ))

    if key_columns :
        for key_col in key_columns :
            if key_col in df .columns :
                dups =df [df .duplicated (subset =[key_col ],keep =False )]
                if len (dups )>0 :
                    dup_indices =[i for i in dups .index .tolist ()if i not in exact_duplicate_rows ]
                    if dup_indices :
                        problems .append (Problem (
                        id =f"key_duplicates_{key_col }",
                        category =ProblemCategory .DUPLICATE_RECORDS ,
                        column =key_col ,
                        description =f"Found {len (dup_indices )} rows with duplicate identifier '{key_col }'.",
                        affected_count =len (dup_indices ),
                        action_type =ChangeType .REVIEW ,
                        proposed_change =f"Review rows with duplicate key '{key_col }'.",
                        fix_type ="review_key_duplicates",
                        row_indices =dup_indices [:100 ],
                        details ={"key_column":key_col }
                        ))

    return problems 
