"""
Mathematical statistics and robust outlier detection algorithms.

Implements Median Absolute Deviation (MAD), Tukey's interquartile ranges,
Gaussian consistency factor (1.4826), and Boris Iglewicz modified Z-scores.
"""

from typing import Any ,Dict 
import numpy as np 

def compute_numerical_stats (series :np .ndarray )->Dict [str ,Any ]:
    """
    Compute comprehensive univariate dispersion and distribution statistics.

    Calculates sample mean, sample standard deviation (ddof=1), quantiles
    (P1, Q25, Median, Q75, P99), Interquartile Range (IQR), Median Absolute
    Deviation (MAD scaled to Gaussian consistency), and Pearson skewness.

    Args:
        series: 1D numpy array of numerical values (may contain NaNs).

    Returns:
        Dictionary containing computed statistical parameters.
    """
    valid_mask =~np .isnan (series )
    valid_data =series [valid_mask ]
    n =len (valid_data )

    if n ==0 :
        return {
        "count":0 ,"mean":None ,"std":None ,"median":None ,
        "q25":None ,"q75":None ,"iqr":None ,"mad":None ,
        "p1":None ,"p99":None ,"iqr_lower":None ,"iqr_upper":None ,
        "skewness":None ,"outlier_count":0 ,"outlier_ratio":0.0 ,
        }

    mean_val =float (np .mean (valid_data ))
    std_val =float (np .std (valid_data ,ddof =1 ))if n >1 else 0.0 


    p1 ,q25 ,median_val ,q75 ,p99 =[
    float (x )for x in np .percentile (valid_data ,[1 ,25 ,50 ,75 ,99 ])
    ]

    iqr_val =float (q75 -q25 )
    iqr_lower =float (q25 -1.5 *iqr_val )
    iqr_upper =float (q75 +1.5 *iqr_val )


    abs_deviations =np .abs (valid_data -median_val )
    mad_raw =float (np .median (abs_deviations ))
    mad_scaled =float (mad_raw *1.4826022185 )


    skew_val =float ((mean_val -median_val )/std_val )if std_val >1e-9 else 0.0 

    outlier_mask =(valid_data <iqr_lower )|(valid_data >iqr_upper )
    outlier_count =int (np .sum (outlier_mask ))
    outlier_ratio =float (outlier_count /n )

    return {
    "count":n ,
    "mean":round (mean_val ,4 ),
    "std":round (std_val ,4 ),
    "median":round (median_val ,4 ),
    "q25":round (q25 ,4 ),
    "q75":round (q75 ,4 ),
    "iqr":round (iqr_val ,4 ),
    "mad":round (mad_scaled ,4 ),
    "p1":round (p1 ,4 ),
    "p99":round (p99 ,4 ),
    "iqr_lower":round (iqr_lower ,4 ),
    "iqr_upper":round (iqr_upper ,4 ),
    "skewness":round (skew_val ,4 ),
    "outlier_count":outlier_count ,
    "outlier_ratio":round (outlier_ratio ,4 ),
    }

def find_outlier_indices (series :np .ndarray )->np .ndarray :
    """
    Detect statistical outlier indices using modified Z-score and Tukey fences.

    Piecewise Decision Logic:
    1. If IQR > 0: uses Tukey's fences [Q1 - 1.5*IQR, Q3 + 1.5*IQR].
    2. If IQR == 0 (discrete / sparse data with >50% identical values):
       uses Boris Iglewicz modified Z-score with threshold 3.5:
       [Median - 3.5*MAD_scaled, Median + 3.5*MAD_scaled].

    Args:
        series: 1D numpy array of values.

    Returns:
        1D integer array of indices corresponding to identified outliers.
    """
    valid_mask =~np .isnan (series )
    if np .sum (valid_mask )<4 :
        return np .array ([],dtype =int )

    valid_data =series [valid_mask ]
    q25 ,q75 =np .percentile (valid_data ,[25 ,75 ])
    iqr =q75 -q25 

    if iqr ==0 :
        med =float (np .median (valid_data ))
        mad =float (np .median (np .abs (valid_data -med ))*1.4826022185 )
        if mad >1e-9 :
            lower =med -3.5 *mad 
            upper =med +3.5 *mad 
        else :
            return np .array ([],dtype =int )
    else :
        lower =float (q25 -1.5 *iqr )
        upper =float (q75 +1.5 *iqr )

    is_outlier =(series <lower )|(series >upper )
    is_outlier =is_outlier &valid_mask 
    return np .flatnonzero (is_outlier )
