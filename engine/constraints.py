import re 
from typing import Any ,Dict ,List ,Optional 
import pandas as pd 
from engine .types import ChangeType ,Problem ,ProblemCategory 

EMAIL_REGEX =re .compile (r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

def validate_constraints (df :pd .DataFrame ,col_types :Dict [str ,str ])->List [Problem ]:
    problems :List [Problem ]=[]

    for col in df .columns :
        col_lower =str (col ).lower ()
        col_type =col_types .get (col ,"text")
        series =df [col ].dropna ()
        if len (series )==0 :
            continue 


        if "email"in col_lower or (col_type =="text"and series .astype (str ).str .contains ("@").mean ()>0.5 ):
            invalid_indices =[]
            for idx ,val in series .items ():
                s =str (val ).strip ()
                if s and s .lower ()not in {"na","null","none","?"}and not bool (EMAIL_REGEX .match (s )):
                    invalid_indices .append (idx )

            if invalid_indices :
                count =len (invalid_indices )
                problems .append (Problem (
                id =f"invalid_email_{col }",
                category =ProblemCategory .INVALID_VALUES ,
                column =str (col ),
                description =f"{count } email addresses do not follow standard format in '{col }'.",
                affected_count =count ,
                action_type =ChangeType .REVIEW ,
                proposed_change =f"Flag {count } invalid email values for review.",
                fix_type ="flag_invalid_email",
                row_indices =invalid_indices [:100 ],
                details ={"samples":[str (df .loc [i ,col ])for i in invalid_indices [:5 ]]}
                ))


        if "age"in col_lower and col_type in ("integer","decimal"):
            num_vals =pd .to_numeric (series ,errors ="coerce")
            invalid_mask =(num_vals <0 )|(num_vals >125 )
            invalid_indices =num_vals [invalid_mask ].index .tolist ()
            if invalid_indices :
                count =len (invalid_indices )
                problems .append (Problem (
                id =f"invalid_age_{col }",
                category =ProblemCategory .INVALID_VALUES ,
                column =str (col ),
                description =f"{count } values in '{col }' fall outside realistic human age range (0 to 125).",
                affected_count =count ,
                action_type =ChangeType .REVIEW ,
                proposed_change =f"Review {count } out-of-range age values.",
                fix_type ="flag_invalid_age",
                row_indices =invalid_indices [:100 ],
                details ={"samples":[str (df .loc [i ,col ])for i in invalid_indices [:5 ]]}
                ))


        if any (k in col_lower for k in ["percent","percentage","pct","rate_pct"])and col_type in ("integer","decimal"):
            num_vals =pd .to_numeric (series ,errors ="coerce")
            invalid_mask =(num_vals <0 )|(num_vals >100 )
            invalid_indices =num_vals [invalid_mask ].index .tolist ()
            if invalid_indices :
                count =len (invalid_indices )
                problems .append (Problem (
                id =f"invalid_percentage_{col }",
                category =ProblemCategory .INVALID_VALUES ,
                column =str (col ),
                description =f"{count } values in '{col }' fall outside percentage range (0% to 100%).",
                affected_count =count ,
                action_type =ChangeType .REVIEW ,
                proposed_change =f"Review or clamp {count } values to range [0, 100].",
                fix_type ="cap_percentage",
                row_indices =invalid_indices [:100 ],
                details ={"samples":[str (df .loc [i ,col ])for i in invalid_indices [:5 ]]}
                ))


        if any (k in col_lower for k in ["qty","quantity","count","stock","units"])and col_type in ("integer","decimal"):
            num_vals =pd .to_numeric (series ,errors ="coerce")
            invalid_mask =num_vals <0 
            invalid_indices =num_vals [invalid_mask ].index .tolist ()
            if invalid_indices :
                count =len (invalid_indices )
                problems .append (Problem (
                id =f"invalid_quantity_{col }",
                category =ProblemCategory .INVALID_VALUES ,
                column =str (col ),
                description =f"{count } negative counts or quantities in '{col }'.",
                affected_count =count ,
                action_type =ChangeType .REVIEW ,
                proposed_change =f"Review {count } negative quantity values.",
                fix_type ="flag_negative_quantity",
                row_indices =invalid_indices [:100 ],
                details ={"samples":[str (df .loc [i ,col ])for i in invalid_indices [:5 ]]}
                ))


        if any (k in col_lower for k in ["birth","dob"])and col_type in ("date","datetime"):
            today =pd .Timestamp .now ().normalize ()
            date_vals =pd .to_datetime (series ,errors ="coerce")
            future_mask =date_vals >today 
            future_indices =date_vals [future_mask ].index .tolist ()
            if future_indices :
                count =len (future_indices )
                problems .append (Problem (
                id =f"invalid_future_date_{col }",
                category =ProblemCategory .INVALID_VALUES ,
                column =str (col ),
                description =f"{count } birthdates in '{col }' are dated in the future.",
                affected_count =count ,
                action_type =ChangeType .REVIEW ,
                proposed_change =f"Review {count } future birthdates.",
                fix_type ="flag_future_date",
                row_indices =future_indices [:100 ],
                details ={"samples":[str (df .loc [i ,col ])for i in future_indices [:5 ]]}
                ))

    return problems 
