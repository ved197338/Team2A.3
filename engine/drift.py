"""
Schema and Data Drift Detection Module.

Implements Population Stability Index (PSI), Two-Sample Kolmogorov-Smirnov (KS)
hypothesis testing, Wasserstein Earth Mover's Distance, and Schema Structural Diff.
"""

from dataclasses import asdict ,dataclass ,field 
from typing import Any ,Dict ,List ,Optional ,Tuple 
import numpy as np 
import pandas as pd 
from scipy import stats 


@dataclass 
class FeatureDriftResult :
    feature_name :str 
    feature_type :str 
    drift_detected :bool 
    drift_score :float 
    metric_name :str 
    threshold :float 
    p_value :Optional [float ]=None 
    baseline_summary :Dict [str ,Any ]=field (default_factory =dict )
    target_summary :Dict [str ,Any ]=field (default_factory =dict )


@dataclass 
class SchemaDriftResult :
    drift_detected :bool 
    added_columns :List [str ]
    removed_columns :List [str ]
    type_mutations :Dict [str ,Tuple [str ,str ]]
    nullability_changes :Dict [str ,Tuple [bool ,bool ]]


@dataclass 
class DatasetDriftReport :
    baseline_rows :int 
    target_rows :int 
    schema_drift :SchemaDriftResult 
    feature_drifts :List [FeatureDriftResult ]
    drifted_feature_count :int 
    total_feature_count :int 
    dataset_drift_ratio :float 
    is_dataset_drifted :bool 


class DriftDetector :
    """
    Detects statistical covariate shift and structural schema drift between
    baseline reference datasets and newly arrived target batches.
    """

    def __init__ (self ,psi_threshold :float =0.25 ,ks_alpha :float =0.05 ):
        self .psi_threshold =psi_threshold 
        self .ks_alpha =ks_alpha 

    @staticmethod 
    def calculate_psi (
    baseline :np .ndarray ,
    target :np .ndarray ,
    num_buckets :int =10 ,
    epsilon :float =1e-4 
    )->float :
        """
        Calculate Population Stability Index (PSI).
        Formula: PSI = sum((Actual_i - Expected_i) * ln(Actual_i / Expected_i))
        Standard boundaries:
          PSI < 0.10: No significant shift (Stable).
          0.10 <= PSI < 0.25: Moderate shift (Warning).
          PSI >= 0.25: Significant shift (Drift detected).
        """
        b_clean =baseline [~np .isnan (baseline )]
        t_clean =target [~np .isnan (target )]

        if len (b_clean )==0 or len (t_clean )==0 :
            return 0.0 


        quantiles =np .linspace (0 ,100 ,num_buckets +1 )
        bins =np .percentile (b_clean ,quantiles )
        bins [0 ]=-np .inf 
        bins [-1 ]=np .inf 

        for i in range (1 ,len (bins )):
            if bins [i ]<=bins [i -1 ]:
                bins [i ]=bins [i -1 ]+1e-6 


        b_counts ,_ =np .histogram (b_clean ,bins =bins )
        t_counts ,_ =np .histogram (t_clean ,bins =bins )


        b_pct =(b_counts /len (b_clean ))+epsilon 
        t_pct =(t_counts /len (t_clean ))+epsilon 


        b_pct /=np .sum (b_pct )
        t_pct /=np .sum (t_pct )

        psi_val =np .sum ((t_pct -b_pct )*np .log (t_pct /b_pct ))
        return float (max (0.0 ,psi_val ))

    def detect_schema_drift (self ,df_base :pd .DataFrame ,df_target :pd .DataFrame )->SchemaDriftResult :
        base_cols =set (df_base .columns )
        target_cols =set (df_target .columns )

        added =sorted (list (target_cols -base_cols ))
        removed =sorted (list (base_cols -target_cols ))

        common =base_cols .intersection (target_cols )
        mutations :Dict [str ,Tuple [str ,str ]]={}
        nullability :Dict [str ,Tuple [bool ,bool ]]={}

        for c in common :
            b_type =str (df_base [c ].dtype )
            t_type =str (df_target [c ].dtype )
            if b_type !=t_type :
                mutations [c ]=(b_type ,t_type )

            b_null =bool (df_base [c ].isna ().any ())
            t_null =bool (df_target [c ].isna ().any ())
            if b_null !=t_null :
                nullability [c ]=(b_null ,t_null )

        drift_detected =bool (added or removed or mutations )

        return SchemaDriftResult (
        drift_detected =drift_detected ,
        added_columns =added ,
        removed_columns =removed ,
        type_mutations =mutations ,
        nullability_changes =nullability 
        )

    def evaluate (self ,df_base :pd .DataFrame ,df_target :pd .DataFrame )->DatasetDriftReport :
        schema_drift =self .detect_schema_drift (df_base ,df_target )
        common_cols =set (df_base .columns ).intersection (set (df_target .columns ))

        results :List [FeatureDriftResult ]=[]

        for col in sorted (list (common_cols )):
            b_s =df_base [col ]
            t_s =df_target [col ]

            if pd .api .types .is_numeric_dtype (b_s )and pd .api .types .is_numeric_dtype (t_s ):
                b_arr =b_s .dropna ().values .astype (float )
                t_arr =t_s .dropna ().values .astype (float )

                if len (b_arr )>5 and len (t_arr )>5 :
                    psi_score =self .calculate_psi (b_arr ,t_arr )
                    ks_stat ,ks_p =stats .ks_2samp (b_arr ,t_arr )
                    w_dist =stats .wasserstein_distance (b_arr ,t_arr )


                    drift_flag =(psi_score >=self .psi_threshold )or (ks_p <self .ks_alpha )

                    results .append (FeatureDriftResult (
                    feature_name =col ,
                    feature_type ="numerical",
                    drift_detected =drift_flag ,
                    drift_score =round (psi_score ,4 ),
                    metric_name ="PSI",
                    threshold =self .psi_threshold ,
                    p_value =round (float (ks_p ),5 ),
                    baseline_summary ={
                    "mean":round (float (np .mean (b_arr )),3 ),
                    "std":round (float (np .std (b_arr )),3 )
                    },
                    target_summary ={
                    "mean":round (float (np .mean (t_arr )),3 ),
                    "std":round (float (np .std (t_arr )),3 ),
                    "wasserstein_dist":round (float (w_dist ),4 )
                    }
                    ))
            else :

                b_counts =b_s .value_counts (normalize =True )
                t_counts =t_s .value_counts (normalize =True )
                all_cats =set (b_counts .index ).union (set (t_counts .index ))

                tvd =0.5 *sum (abs (b_counts .get (c ,0.0 )-t_counts .get (c ,0.0 ))for c in all_cats )
                drift_flag =tvd >0.15 

                results .append (FeatureDriftResult (
                feature_name =col ,
                feature_type ="categorical",
                drift_detected =drift_flag ,
                drift_score =round (float (tvd ),4 ),
                metric_name ="TVD",
                threshold =0.15 ,
                p_value =None ,
                baseline_summary ={"top_category":str (b_counts .index [0 ])if len (b_counts )>0 else "None"},
                target_summary ={"top_category":str (t_counts .index [0 ])if len (t_counts )>0 else "None"}
                ))

        drifted_count =sum (1 for r in results if r .drift_detected )
        total_count =max (1 ,len (results ))
        ratio =drifted_count /total_count 

        is_drifted =schema_drift .drift_detected or (ratio >0.25 )

        return DatasetDriftReport (
        baseline_rows =len (df_base ),
        target_rows =len (df_target ),
        schema_drift =schema_drift ,
        feature_drifts =results ,
        drifted_feature_count =drifted_count ,
        total_feature_count =total_count ,
        dataset_drift_ratio =round (ratio ,3 ),
        is_dataset_drifted =is_drifted 
        )
