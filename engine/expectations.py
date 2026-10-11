"""
Great Expectations and Soda style Contract Validation Engine.

Implements declarative expectation suites, validation execution,
and compliance reporting for AI-ready data engineering pipelines.
"""

from dataclasses import asdict ,dataclass ,field 
from datetime import datetime ,timezone 
import re 
from typing import Any ,Callable ,Dict ,List ,Optional ,Union 
import numpy as np 
import pandas as pd 


@dataclass 
class ExpectationResult :
    expectation_type :str 
    kwargs :Dict [str ,Any ]
    success :bool 
    observed_value :Any 
    unexpected_count :int =0 
    unexpected_percent :float =0.0 
    unexpected_sample :List [Any ]=field (default_factory =list )
    details :Dict [str ,Any ]=field (default_factory =dict )


@dataclass 
class SuiteValidationReport :
    suite_name :str 
    dataset_name :str 
    evaluated_at :str 
    total_expectations :int 
    successful_expectations :int 
    failed_expectations :int 
    success_rate :float 
    results :List [ExpectationResult ]
    ai_ready :bool 


class ExpectationSuite :
    """
    Declarative quality test suite modeled after Great Expectations and Soda Core.
    """

    def __init__ (self ,suite_name :str ="ai_readiness_suite"):
        self .suite_name =suite_name 
        self .rules :List [Dict [str ,Any ]]=[]

    def expect_table_row_count_to_be_between (self ,min_value :int =1 ,max_value :Optional [int ]=None )->"ExpectationSuite":
        self .rules .append ({
        "type":"expect_table_row_count_to_be_between",
        "kwargs":{"min_value":min_value ,"max_value":max_value }
        })
        return self 

    def expect_column_values_to_not_be_null (self ,column :str ,mostly :float =1.0 )->"ExpectationSuite":
        self .rules .append ({
        "type":"expect_column_values_to_not_be_null",
        "kwargs":{"column":column ,"mostly":mostly }
        })
        return self 

    def expect_column_values_to_be_unique (self ,column :str ,mostly :float =1.0 )->"ExpectationSuite":
        self .rules .append ({
        "type":"expect_column_values_to_be_unique",
        "kwargs":{"column":column ,"mostly":mostly }
        })
        return self 

    def expect_column_values_to_match_regex (self ,column :str ,regex :str ,mostly :float =1.0 )->"ExpectationSuite":
        self .rules .append ({
        "type":"expect_column_values_to_match_regex",
        "kwargs":{"column":column ,"regex":regex ,"mostly":mostly }
        })
        return self 

    def expect_column_values_to_be_in_set (self ,column :str ,value_set :List [Any ])->"ExpectationSuite":
        self .rules .append ({
        "type":"expect_column_values_to_be_in_set",
        "kwargs":{"column":column ,"value_set":list (value_set )}
        })
        return self 

    def expect_column_min_to_be_between (self ,column :str ,min_value :float ,max_value :Optional [float ]=None )->"ExpectationSuite":
        self .rules .append ({
        "type":"expect_column_min_to_be_between",
        "kwargs":{"column":column ,"min_value":min_value ,"max_value":max_value }
        })
        return self 

    def expect_column_max_to_be_between (self ,column :str ,min_value :Optional [float ]=None ,max_value :Optional [float ]=None )->"ExpectationSuite":
        self .rules .append ({
        "type":"expect_column_max_to_be_between",
        "kwargs":{"column":column ,"min_value":min_value ,"max_value":max_value }
        })
        return self 

    def expect_column_mean_to_be_between (self ,column :str ,min_value :float ,max_value :float )->"ExpectationSuite":
        self .rules .append ({
        "type":"expect_column_mean_to_be_between",
        "kwargs":{"column":column ,"min_value":min_value ,"max_value":max_value }
        })
        return self 

    def validate (self ,df :pd .DataFrame ,dataset_name :str ="dataset")->SuiteValidationReport :
        results :List [ExpectationResult ]=[]
        n_rows =len (df )

        for rule in self .rules :
            exp_type =rule ["type"]
            kwargs =rule ["kwargs"]

            if exp_type =="expect_table_row_count_to_be_between":
                min_v =kwargs .get ("min_value",0 )
                max_v =kwargs .get ("max_value")
                success =n_rows >=min_v and (max_v is None or n_rows <=max_v )
                results .append (ExpectationResult (
                expectation_type =exp_type ,
                kwargs =kwargs ,
                success =success ,
                observed_value =n_rows 
                ))

            elif exp_type =="expect_column_values_to_not_be_null":
                col =kwargs ["column"]
                if col not in df .columns :
                    results .append (ExpectationResult (exp_type ,kwargs ,False ,"Column Missing"))
                    continue 
                null_mask =df [col ].isna ()
                unexp_count =int (null_mask .sum ())
                unexp_pct =(unexp_count /max (1 ,n_rows ))
                mostly =kwargs .get ("mostly",1.0 )
                success =(1.0 -unexp_pct )>=mostly 
                results .append (ExpectationResult (
                expectation_type =exp_type ,
                kwargs =kwargs ,
                success =success ,
                observed_value =float (1.0 -unexp_pct ),
                unexpected_count =unexp_count ,
                unexpected_percent =float (unexp_pct *100 ),
                unexpected_sample =df [col ][null_mask ].head (5 ).tolist ()
                ))

            elif exp_type =="expect_column_values_to_be_unique":
                col =kwargs ["column"]
                if col not in df .columns :
                    results .append (ExpectationResult (exp_type ,kwargs ,False ,"Column Missing"))
                    continue 
                dup_mask =df [col ].duplicated (keep =False )&df [col ].notna ()
                unexp_count =int (dup_mask .sum ())
                unexp_pct =(unexp_count /max (1 ,n_rows ))
                mostly =kwargs .get ("mostly",1.0 )
                success =(1.0 -unexp_pct )>=mostly 
                results .append (ExpectationResult (
                expectation_type =exp_type ,
                kwargs =kwargs ,
                success =success ,
                observed_value =float (1.0 -unexp_pct ),
                unexpected_count =unexp_count ,
                unexpected_percent =float (unexp_pct *100 ),
                unexpected_sample =df [col ][dup_mask ].head (5 ).tolist ()
                ))

            elif exp_type =="expect_column_values_to_match_regex":
                col =kwargs ["column"]
                pattern =re .compile (kwargs ["regex"])
                if col not in df .columns :
                    results .append (ExpectationResult (exp_type ,kwargs ,False ,"Column Missing"))
                    continue 
                non_nulls =df [col ].dropna ().astype (str )
                matches =non_nulls .apply (lambda val :bool (pattern .search (val )))
                unexp_count =int ((~matches ).sum ())
                unexp_pct =(unexp_count /max (1 ,len (non_nulls )))
                mostly =kwargs .get ("mostly",1.0 )
                success =(1.0 -unexp_pct )>=mostly 
                results .append (ExpectationResult (
                expectation_type =exp_type ,
                kwargs =kwargs ,
                success =success ,
                observed_value =float (1.0 -unexp_pct ),
                unexpected_count =unexp_count ,
                unexpected_percent =float (unexp_pct *100 ),
                unexpected_sample =non_nulls [~matches ].head (5 ).tolist ()
                ))

            elif exp_type =="expect_column_values_to_be_in_set":
                col =kwargs ["column"]
                allowed =set (kwargs ["value_set"])
                if col not in df .columns :
                    results .append (ExpectationResult (exp_type ,kwargs ,False ,"Column Missing"))
                    continue 
                non_nulls =df [col ].dropna ()
                valid_mask =non_nulls .isin (allowed )
                unexp_count =int ((~valid_mask ).sum ())
                unexp_pct =(unexp_count /max (1 ,len (non_nulls )))
                success =unexp_count ==0 
                results .append (ExpectationResult (
                expectation_type =exp_type ,
                kwargs =kwargs ,
                success =success ,
                observed_value =list (set (non_nulls [~valid_mask ].head (5 ))),
                unexpected_count =unexp_count ,
                unexpected_percent =float (unexp_pct *100 ),
                unexpected_sample =non_nulls [~valid_mask ].head (5 ).tolist ()
                ))

            elif exp_type =="expect_column_min_to_be_between":
                col =kwargs ["column"]
                if col not in df .columns :
                    results .append (ExpectationResult (exp_type ,kwargs ,False ,"Column Missing"))
                    continue 
                obs_min =float (pd .to_numeric (df [col ],errors ="coerce").min ())
                min_v =kwargs .get ("min_value")
                max_v =kwargs .get ("max_value")
                success =(min_v is None or obs_min >=min_v )and (max_v is None or obs_min <=max_v )
                results .append (ExpectationResult (
                expectation_type =exp_type ,
                kwargs =kwargs ,
                success =success ,
                observed_value =obs_min 
                ))

            elif exp_type =="expect_column_max_to_be_between":
                col =kwargs ["column"]
                if col not in df .columns :
                    results .append (ExpectationResult (exp_type ,kwargs ,False ,"Column Missing"))
                    continue 
                obs_max =float (pd .to_numeric (df [col ],errors ="coerce").max ())
                min_v =kwargs .get ("min_value")
                max_v =kwargs .get ("max_value")
                success =(min_v is None or obs_max >=min_v )and (max_v is None or obs_max <=max_v )
                results .append (ExpectationResult (
                expectation_type =exp_type ,
                kwargs =kwargs ,
                success =success ,
                observed_value =obs_max 
                ))

            elif exp_type =="expect_column_mean_to_be_between":
                col =kwargs ["column"]
                if col not in df .columns :
                    results .append (ExpectationResult (exp_type ,kwargs ,False ,"Column Missing"))
                    continue 
                obs_mean =float (pd .to_numeric (df [col ],errors ="coerce").mean ())
                success =kwargs ["min_value"]<=obs_mean <=kwargs ["max_value"]
                results .append (ExpectationResult (
                expectation_type =exp_type ,
                kwargs =kwargs ,
                success =success ,
                observed_value =obs_mean 
                ))

        total =len (results )
        passed =sum (1 for r in results if r .success )
        failed =total -passed 
        success_rate =(passed /max (1 ,total ))*100.0 
        ai_ready =(success_rate >=95.0 and failed ==0 )

        return SuiteValidationReport (
        suite_name =self .suite_name ,
        dataset_name =dataset_name ,
        evaluated_at =datetime .now (timezone .utc ).isoformat (),
        total_expectations =total ,
        successful_expectations =passed ,
        failed_expectations =failed ,
        success_rate =round (success_rate ,2 ),
        results =results ,
        ai_ready =ai_ready 
        )
