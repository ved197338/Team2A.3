"""Small helpers that build tiny, hand-made workloads for the tests."""
import pandas as pd 

from src import data_loader 
from src .pipeline import run_pipeline 
from src .recommendation_engine import EngineSettings 
from src .workload_analyzer import analyze_workload 

REF =pd .Timestamp ("2026-10-09")


def make_row (name ="ds1",**over ):
    row =dict (file_name =name ,size_gb =500.0 ,last_accessed ="2026-10-08",access_count =5000 ,
    workload_type ="database",performance_requirement ="MEDIUM",current_tier ="WARM")
    row .update (over )
    return row 


def make_df (*rows ):
    clean ,_ =data_loader .validate_workload_data (pd .DataFrame (list (rows )))
    return clean 


def settings ():
    return EngineSettings (reference_date =REF )


def run (*rows ,history =None ):
    return run_pipeline (make_df (*rows ),history ,settings ())


def rec_of (result ,name ):
    r =result ["recommendations"]
    return r [r ["file_name"]==name ].iloc [0 ]
