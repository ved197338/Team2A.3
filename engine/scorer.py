from typing import Dict ,List ,Optional 
import pandas as pd 
from engine .types import QualityScore ,Problem ,QualityDimension 
from engine .missing import find_missing_mask 

def compute_quality_score (
df :pd .DataFrame ,
problems :List [Problem ],
weights :Optional [Dict [str ,float ]]=None 
)->QualityScore :
    total_rows =len (df )
    total_cols =len (df .columns )
    total_cells =max (1 ,total_rows *total_cols )

    default_weights ={
    "completeness":0.25 ,
    "validity":0.25 ,
    "uniqueness":0.20 ,
    "consistency":0.20 ,
    "timeliness":0.10 
    }
    w =weights or default_weights 

    if total_rows ==0 or total_cols ==0 :
        return QualityScore (
        completeness =100.0 ,validity =100.0 ,uniqueness =100.0 ,
        consistency =100.0 ,timeliness =100.0 ,total =100.0 ,weights =w 
        )


    missing_cells =0 
    for col in df .columns :
        missing_cells +=int (find_missing_mask (df [col ]).sum ())
    completeness =max (0.0 ,1.0 -(missing_cells /total_cells ))*100.0 


    invalid_cells =sum (p .affected_count for p in problems if p .dimension ==QualityDimension .VALIDITY )
    validity =max (0.0 ,1.0 -(invalid_cells /total_cells ))*100.0 


    dup_rows =sum (p .affected_count for p in problems if p .dimension ==QualityDimension .UNIQUENESS )
    uniqueness =max (0.0 ,1.0 -(dup_rows /total_rows ))*100.0 


    inconsistent_cells =sum (p .affected_count for p in problems if p .dimension ==QualityDimension .CONSISTENCY )
    consistency =max (0.0 ,1.0 -(inconsistent_cells /total_cells ))*100.0 


    timeliness_issues =sum (p .affected_count for p in problems if p .dimension ==QualityDimension .TIMELINESS )
    timeliness =max (0.0 ,1.0 -(timeliness_issues /max (1 ,total_rows )))*100.0 

    total =(
    w ["completeness"]*completeness +
    w ["validity"]*validity +
    w ["uniqueness"]*uniqueness +
    w ["consistency"]*consistency +
    w ["timeliness"]*timeliness 
    )

    return QualityScore (
    completeness =round (completeness ,1 ),
    validity =round (validity ,1 ),
    uniqueness =round (uniqueness ,1 ),
    consistency =round (consistency ,1 ),
    timeliness =round (timeliness ,1 ),
    total =round (total ,1 ),
    weights =w 
    )
