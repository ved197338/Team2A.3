"""
ML-Based Data Profiling and Composite Quality Scoring Engine.

Computes comprehensive univariate and multivariate distributions alongside the
canonical 5-dimension Composite Data-Quality Score (Completeness, Validity,
Uniqueness, Consistency, Timeliness) required for AI-ready workloads.
"""

from dataclasses import asdict ,dataclass ,field 
from datetime import datetime ,timezone 
from typing import Any ,Dict ,List ,Optional 
import numpy as np 
import pandas as pd 
from engine .stats import compute_numerical_stats 


@dataclass 
class ColumnProfile :
    name :str 
    inferred_type :str 
    total_count :int 
    null_count :int 
    null_percentage :float 
    unique_count :int 
    cardinality_ratio :float 
    is_constant :bool 
    is_unique :bool 
    statistics :Optional [Dict [str ,Any ]]=None 
    top_values :List [Dict [str ,Any ]]=field (default_factory =list )


@dataclass 
class CompositeQualityScore :
    completeness :float 
    validity :float 
    uniqueness :float 
    consistency :float 
    timeliness :float 
    composite_total :float 
    grade :str 
    is_ai_ready :bool 
    weights :Dict [str ,float ]=field (default_factory =lambda :{
    "completeness":0.25 ,
    "validity":0.25 ,
    "uniqueness":0.20 ,
    "consistency":0.20 ,
    "timeliness":0.10 
    })


@dataclass 
class DatasetProfileReport :
    dataset_name :str 
    row_count :int 
    column_count :int 
    memory_usage_bytes :int 
    generated_at :str 
    column_profiles :List [ColumnProfile ]
    quality_score :CompositeQualityScore 
    correlation_matrix :Optional [Dict [str ,Dict [str ,float ]]]=None 
    summary_findings :List [str ]=field (default_factory =list )


class DataProfiler :
    """
    Enterprise data profiler and composite quality scorer.
    """

    @classmethod 
    def profile_dataframe (
    cls ,
    df :pd .DataFrame ,
    dataset_name :str ="dataset",
    timestamp_col :Optional [str ]=None ,
    max_age_days :float =30.0 
    )->DatasetProfileReport :
        n_rows =len (df )
        n_cols =len (df .columns )
        total_cells =max (1 ,n_rows *n_cols )

        col_profiles :List [ColumnProfile ]=[]
        missing_cells =0 
        invalid_cells =0 
        inconsistent_cells =0 


        for col in df .columns :
            series =df [col ]
            nulls =int (series .isna ().sum ())
            missing_cells +=nulls 
            uniques =int (series .nunique (dropna =True ))

            is_numeric =pd .api .types .is_numeric_dtype (series )
            inferred ="numeric"if is_numeric else ("datetime"if pd .api .types .is_datetime64_any_dtype (series )else "categorical")

            stats_dict =None 
            if is_numeric :
                clean_arr =series .dropna ().values .astype (float )
                stats_dict =compute_numerical_stats (clean_arr )

                if stats_dict .get ("outlier_count"):
                    invalid_cells +=int (stats_dict ["outlier_count"])


            val_counts =series .value_counts (dropna =True ).head (5 )
            top_vals =[{"value":str (v ),"count":int (c )}for v ,c in val_counts .items ()]

            col_profiles .append (ColumnProfile (
            name =str (col ),
            inferred_type =inferred ,
            total_count =n_rows ,
            null_count =nulls ,
            null_percentage =round ((nulls /max (1 ,n_rows ))*100 ,2 ),
            unique_count =uniques ,
            cardinality_ratio =round (uniques /max (1 ,n_rows ),4 ),
            is_constant =(uniques <=1 ),
            is_unique =(uniques ==n_rows ),
            statistics =stats_dict ,
            top_values =top_vals 
            ))



        comp_score =max (0.0 ,1.0 -(missing_cells /total_cells ))*100.0 


        valid_score =max (0.0 ,1.0 -(invalid_cells /total_cells ))*100.0 


        dup_rows =int (df .duplicated ().sum ())
        uniq_score =max (0.0 ,1.0 -(dup_rows /max (1 ,n_rows )))*100.0 



        for col_p in col_profiles :
            if col_p .inferred_type =="numeric"and col_p .statistics :
                if "id"in col_p .name .lower ()or "age"in col_p .name .lower ()or "amount"in col_p .name .lower ():
                    if col_p .statistics .get ("p1")is not None and col_p .statistics ["p1"]<0 :
                        inconsistent_cells +=10 
        cons_score =max (0.0 ,1.0 -(inconsistent_cells /total_cells ))*100.0 


        time_score =100.0 
        if timestamp_col and timestamp_col in df .columns :
            try :
                ts_series =pd .to_datetime (df [timestamp_col ],errors ="coerce")
                latest =ts_series .max ()
                if pd .notna (latest ):
                    now =pd .Timestamp .now (tz =latest .tz )if latest .tz else pd .Timestamp .now ()
                    diff_days =(now -latest ).total_seconds ()/86400.0 
                    if diff_days >max_age_days :
                        time_score =max (20.0 ,100.0 -((diff_days -max_age_days )*2.0 ))
            except Exception :
                time_score =80.0 


        weights ={
        "completeness":0.25 ,
        "validity":0.25 ,
        "uniqueness":0.20 ,
        "consistency":0.20 ,
        "timeliness":0.10 
        }
        composite =(
        comp_score *weights ["completeness"]+
        valid_score *weights ["validity"]+
        uniq_score *weights ["uniqueness"]+
        cons_score *weights ["consistency"]+
        time_score *weights ["timeliness"]
        )

        grade ="F"
        if composite >=95.0 :
            grade ="A+"
        elif composite >=90.0 :
            grade ="A"
        elif composite >=80.0 :
            grade ="B"
        elif composite >=70.0 :
            grade ="C"

        is_ai_ready =(composite >=90.0 and comp_score >=85.0 and uniq_score >=90.0 )


        num_cols =[c .name for c in col_profiles if c .inferred_type =="numeric"]
        corr_dict =None 
        if len (num_cols )>=2 :
            corr_df =df [num_cols ].corr ()
            corr_dict ={
            c1 :{c2 :round (float (corr_df .loc [c1 ,c2 ]),3 )for c2 in num_cols if pd .notna (corr_df .loc [c1 ,c2 ])}
            for c1 in num_cols 
            }

        findings =[]
        if comp_score <90.0 :
            findings .append (f"Completeness degraded: {missing_cells } missing values ({round (100 -comp_score ,1 )}% null rate).")
        if uniq_score <95.0 :
            findings .append (f"Uniqueness defect: {dup_rows } exact duplicate rows identified.")
        if invalid_cells >0 :
            findings .append (f"Validity warning: {invalid_cells } values flagged as extreme statistical outliers.")
        if is_ai_ready :
            findings .append ("Dataset certified as AI-Ready for ML training and LLM fine-tuning.")
        else :
            findings .append ("Dataset requires remediation before deployment into AI workloads.")

        return DatasetProfileReport (
        dataset_name =dataset_name ,
        row_count =n_rows ,
        column_count =n_cols ,
        memory_usage_bytes =int (df .memory_usage (deep =True ).sum ()),
        generated_at =datetime .now (timezone .utc ).isoformat (),
        column_profiles =col_profiles ,
        quality_score =CompositeQualityScore (
        completeness =round (comp_score ,2 ),
        validity =round (valid_score ,2 ),
        uniqueness =round (uniq_score ,2 ),
        consistency =round (cons_score ,2 ),
        timeliness =round (time_score ,2 ),
        composite_total =round (composite ,2 ),
        grade =grade ,
        is_ai_ready =is_ai_ready ,
        weights =weights 
        ),
        correlation_matrix =corr_dict ,
        summary_findings =findings 
        )
