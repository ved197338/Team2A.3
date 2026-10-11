from typing import Any ,Dict ,List ,Optional ,Set 
import pandas as pd 
import numpy as np 
from engine .types import ChangeType ,Problem ,ProblemCategory 

MISSING_SENTINELS :Set [str ]={
""," ","  ","na","n/a","null","none","?","-","--","#n/a",
"nan","nil","undefined","n.a.","missing","unknown"
}

def find_missing_mask (series :pd .Series )->pd .Series :
    mask =series .isna ()
    if series .dtype ==object or pd .api .types .is_string_dtype (series ):
        str_series =series .astype (str ).str .strip ().str .lower ()
        mask =mask |str_series .isin (MISSING_SENTINELS )
    return mask 

def analyze_missing_values (df :pd .DataFrame ,col_types :Dict [str ,str ])->List [Problem ]:
    problems :List [Problem ]=[]
    total_rows =len (df )
    if total_rows ==0 :
        return problems 

    for col in df .columns :
        mask =find_missing_mask (df [col ])
        missing_count =int (mask .sum ())
        if missing_count ==0 :
            continue 

        missing_ratio =missing_count /total_rows 
        missing_indices =mask [mask ].index .tolist ()
        col_type =col_types .get (col ,"text")

        if col_type in ("identifier","sensitive","text"):
            action_type =ChangeType .UNCHANGED 
            impute_val =None 
            fix_desc ="Identifiers and free text are not imputed. Leave missing or review records."
        elif missing_ratio >0.30 :
            action_type =ChangeType .UNCHANGED 
            impute_val =None 
            fix_desc =f"High missing rate ({missing_ratio :.1%}). Imputing values would distort the distribution."
        elif col_type in ("integer","decimal"):
            valid_vals =pd .to_numeric (df .loc [~mask ,col ],errors ="coerce").dropna ()
            if len (valid_vals )>0 :
                median_val =float (np .median (valid_vals ))
                impute_val =int (round (median_val ))if col_type =="integer"else round (median_val ,2 )
                action_type =ChangeType .REVIEW 
                fix_desc =f"Fill {missing_count } missing values with column median ({impute_val })."
            else :
                action_type =ChangeType .UNCHANGED 
                impute_val =None 
                fix_desc ="No valid numbers found to compute a median."
        elif col_type =="categorical":
            valid_vals =df .loc [~mask ,col ].astype (str ).str .strip ()
            val_counts =valid_vals .value_counts ()
            if len (val_counts )>0 and (val_counts .iloc [0 ]/len (valid_vals ))>=0.65 :
                top_cat =val_counts .index [0 ]
                impute_val =top_cat 
                action_type =ChangeType .REVIEW 
                fix_desc =f"Fill missing values with common category '{top_cat }'."
            else :
                action_type =ChangeType .UNCHANGED 
                impute_val =None 
                fix_desc ="No single dominant category. Manual review recommended."
        else :
            action_type =ChangeType .UNCHANGED 
            impute_val =None 
            fix_desc ="Manual review recommended."

        problems .append (Problem (
        id =f"missing_{col }",
        category =ProblemCategory .MISSING_VALUES ,
        column =str (col ),
        description =f"{missing_count } missing or empty values ({missing_ratio :.1%}) in column '{col }'.",
        affected_count =missing_count ,
        action_type =action_type ,
        proposed_change =fix_desc ,
        fix_type ="impute_missing",
        row_indices =missing_indices [:100 ],
        details ={
        "missing_count":missing_count ,
        "missing_ratio":round (missing_ratio ,4 ),
        "impute_val":impute_val ,
        "col_type":col_type ,
        }
        ))

    return problems 
