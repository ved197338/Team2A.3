"""
Deterministic Logic Data Cleaning Pipeline (Stage 1).

Executes reproducible, rule-based mathematical cleaning without LLM hallucinations:
- Header normalization
- Duplicate record removal
- Missing value imputation (median / mode)
- Sensitive PII detection & Luhn Modulo 10 masking
- Outlier detection via Median Absolute Deviation (MAD, factor 1.4826)
- 5-dimension Composite Quality Scoring
"""

from dataclasses import dataclass ,field 
from typing import Any ,Dict ,List ,Optional ,Tuple 
import pandas as pd 
import numpy as np 

from engine .pipeline import profile_dataset_columns 
from engine .detect import detect_unified 
from engine .cleaner import clean_dataset 
from engine .scorer import compute_quality_score 
from engine .stats import find_outlier_indices 
from engine .types import Problem ,QualityScore 

@dataclass 
class LogicCleaningResult :
    cleaned_df :pd .DataFrame 
    problems_detected :int 
    actions_performed :List [str ]
    initial_quality_score :float 
    final_quality_score :float 
    score_details :Dict [str ,float ]
    audit_log :List [Dict [str ,Any ]]

class DeterministicLogicCleaner :
    """Rule-based data cleaner implementing the verified mathematical cleaning process."""

    @classmethod 
    def clean (cls ,df_raw :pd .DataFrame )->LogicCleaningResult :
        df =df_raw .copy ()
        actions =[]
        audit_records =[]


        col_profiles ,col_types =profile_dataset_columns (df )
        problems ,pii_items ,anomalies ,drift_items ,cell_highlights =detect_unified (df ,col_types ,None )


        initial_score =compute_quality_score (df ,problems )


        cleaned_df ,audit_log ,modified_cells =clean_dataset (df ,problems )


        outlier_rows =set ()
        for col in cleaned_df .columns :
            num_s =pd .to_numeric (cleaned_df [col ],errors ="coerce")
            if num_s .notna ().sum ()>=4 :
                arr =num_s .to_numpy (dtype =float )
                idx =find_outlier_indices (arr )
                if len (idx )>0 :
                    outlier_rows .update (idx .tolist ())
                    actions .append (f"innov8 AI Shield: Pruned {len (idx )} extreme outlier rows in `{col }`.")
        if outlier_rows :
            cleaned_df =cleaned_df .drop (index =[r for r in outlier_rows if r in cleaned_df .index ],errors ='ignore').reset_index (drop =True )


        for col in cleaned_df .columns :
            col_lower =str (col ).lower ().strip ()


            if 'age'in col_lower :
                num =pd .to_numeric (cleaned_df [col ],errors ='coerce')
                valid_median =num [(num >=0 )&(num <=120 )].median ()
                if pd .isna (valid_median ):
                    valid_median =30.0 
                fixed_age =num .apply (lambda v :abs (v )if pd .notna (v )and -120 <=v <0 else (v if pd .notna (v )and 0 <=v <=120 else valid_median ))
                if (cleaned_df [col ]!=fixed_age ).any ():
                    actions .append (f"AI repaired negative and missing values in `{col }` to valid age range.")
                cleaned_df [col ]=fixed_age .round ().astype (int )


            elif any (k in col_lower for k in ['pct','percentage','completion','discount','rate','ratio']):
                num =pd .to_numeric (cleaned_df [col ],errors ='coerce')
                valid_median =num [(num >=0 )&(num <=100 )].median ()
                if pd .isna (valid_median ):
                    valid_median =50.0 
                fixed_pct =num .apply (lambda v :abs (v )if pd .notna (v )and -100 <=v <0 else (v if pd .notna (v )and 0 <=v <=100 else valid_median ))
                fixed_pct =fixed_pct .clip (lower =0.0 ,upper =100.0 )
                if (cleaned_df [col ]!=fixed_pct ).any ():
                    actions .append (f"AI clamped and imputed out-of-range percentage values in `{col }`.")
                cleaned_df [col ]=fixed_pct .round (1 )


            elif any (k in col_lower for k in ['quantity','items','count','units']):
                num =pd .to_numeric (cleaned_df [col ],errors ='coerce')
                valid_median =num [num >=0 ].median ()
                if pd .isna (valid_median ):
                    valid_median =1.0 
                fixed_qty =num .apply (lambda v :abs (v )if pd .notna (v )and v <0 else (v if pd .notna (v )and v >=0 else valid_median ))
                if (cleaned_df [col ]!=fixed_qty ).any ():
                    actions .append (f"AI normalized negative counts in `{col }` to non-negative.")
                cleaned_df [col ]=fixed_qty .round ().astype (int )


            elif 'email'in col_lower :
                def fix_email (val ):
                    if pd .isna (val )or str (val ).strip ().lower ()in ['nan','none','','null','na','<na>']:
                        return ''
                    s =str (val ).strip ()
                    import re 
                    s =re .sub (r'@+','@',s )
                    return s 
                cleaned_df [col ]=cleaned_df [col ].apply (fix_email )


            else :
                is_id_col =any (k in col_lower for k in ['id','email','phone','name','first_name','last_name','ssn','account','user'])
                if cleaned_df [col ].isna ().any ():
                    num =pd .to_numeric (cleaned_df [col ],errors ='coerce')
                    if num .notna ().sum ()>len (cleaned_df )*0.5 and not is_id_col :
                        med =num .median ()
                        cleaned_df [col ]=num .fillna (med )
                        actions .append (f"AI imputed missing numbers in `{col }` with median.")
                    elif not is_id_col :
                        mode_s =cleaned_df [col ].dropna ().mode ()
                        fill_val =mode_s .iloc [0 ]if len (mode_s )>0 else 'Unknown'

                        if len (cleaned_df [col ].dropna ().unique ())>len (cleaned_df )*0.6 :
                            fill_val ='Unknown'
                        cleaned_df [col ]=cleaned_df [col ].fillna (fill_val )
                        actions .append (f"AI imputed missing text in `{col }`.")


        for col in cleaned_df .columns :
            cleaned_df [col ]=cleaned_df [col ].replace ({'nan':'Unknown','NaN':'Unknown','None':'Unknown','<NA>':'Unknown',None :'Unknown'})
            cleaned_df [col ]=cleaned_df [col ].fillna ('Unknown')


        for a in audit_log :
            audit_records .append ({
            "row":a .row ,
            "column":a .column ,
            "change":a .change ,
            "reason":a .reason 
            })
            if a .change not in actions :
                actions .append (f"{a .change } ({a .column }): {a .reason }")


        val_profiles ,val_types =profile_dataset_columns (cleaned_df )
        val_problems ,_ ,_ ,_ ,_ =detect_unified (cleaned_df ,val_types ,None )
        final_score =compute_quality_score (cleaned_df ,val_problems )

        return LogicCleaningResult (
        cleaned_df =cleaned_df ,
        problems_detected =len (problems )+len (outlier_rows ),
        actions_performed =actions if actions else ["Dataset conforms to mathematical quality rules; no structural defects."],
        initial_quality_score =round (float (initial_score .total ),2 ),
        final_quality_score =round (float (final_score .total ),2 ),
        score_details ={
        "completeness":round (float (final_score .completeness ),2 ),
        "validity":round (float (final_score .validity ),2 ),
        "uniqueness":round (float (final_score .uniqueness ),2 ),
        "consistency":round (float (final_score .consistency ),2 ),
        "timeliness":round (float (final_score .timeliness ),2 )
        },
        audit_log =audit_records 
        )
