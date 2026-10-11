import re 
from typing import Any ,Dict ,List 
import pandas as pd 
from engine .types import ChangeType ,Problem ,ProblemCategory 

PHONE_REGEX =re .compile (r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}$')
SSN_REGEX =re .compile (r'^\d{3}-\d{2}-\d{4}$')
CREDIT_CARD_REGEX =re .compile (r'^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})$')

def luhn_checksum_valid (card_num_str :str )->bool :
    digits =[int (c )for c in card_num_str if c .isdigit ()]
    if len (digits )<13 or len (digits )>19 :
        return False 
    checksum =0 
    reverse_digits =digits [::-1 ]
    for i ,d in enumerate (reverse_digits ):
        if i %2 ==1 :
            doubled =d *2 
            checksum +=doubled if doubled <10 else (doubled -9 )
        else :
            checksum +=d 
    return checksum %10 ==0 

def mask_card (val :str )->str :
    clean =re .sub (r'\D','',str (val ))
    if len (clean )>=4 :
        return f"****-****-****-{clean [-4 :]}"
    return "****"

def mask_ssn (val :str )->str :
    clean =re .sub (r'\D','',str (val ))
    if len (clean )>=4 :
        return f"***-**-{clean [-4 :]}"
    return "***-**-****"

def mask_phone (val :str )->str :
    clean =re .sub (r'\D','',str (val ))
    if len (clean )>=4 :
        return f"***-***-{clean [-4 :]}"
    return "***-***-****"

def detect_sensitive_data (df :pd .DataFrame )->List [Problem ]:
    problems :List [Problem ]=[]

    for col in df .columns :
        series =df [col ].dropna ().astype (str ).str .strip ()
        if len (series )==0 :
            continue 

        sample =series .iloc [:200 ]


        cc_candidates =[s for s in sample if CREDIT_CARD_REGEX .match (re .sub (r'[-\s]','',s ))]
        valid_cc =[s for s in cc_candidates if luhn_checksum_valid (s )]
        if len (valid_cc )>=2 or (len (valid_cc )>0 and len (sample )<10 ):
            all_cc_mask =series .apply (lambda s :luhn_checksum_valid (re .sub (r'[-\s]','',s )))
            cc_indices =series [all_cc_mask ].index .tolist ()
            count =len (cc_indices )
            if count >0 :
                problems .append (Problem (
                id =f"sensitive_credit_card_{col }",
                category =ProblemCategory .SENSITIVE_DATA ,
                column =str (col ),
                description =f"{count } credit card numbers detected in '{col }' with valid Luhn checksum.",
                affected_count =count ,
                action_type =ChangeType .SAFE ,
                proposed_change =f"Mask {count } credit cards (preserving last 4 digits).",
                fix_type ="mask_credit_cards",
                row_indices =cc_indices [:100 ],
                details ={"sensitive_type":"credit_card"}
                ))
                continue 


        ssn_matches =sample .apply (lambda s :bool (SSN_REGEX .match (s )))
        if ssn_matches .sum ()>=2 or (ssn_matches .sum ()>0 and len (sample )<10 ):
            all_ssn_mask =series .apply (lambda s :bool (SSN_REGEX .match (s )))
            ssn_indices =series [all_ssn_mask ].index .tolist ()
            count =len (ssn_indices )
            if count >0 :
                problems .append (Problem (
                id =f"sensitive_ssn_{col }",
                category =ProblemCategory .SENSITIVE_DATA ,
                column =str (col ),
                description =f"{count } Social Security Numbers detected in '{col }'.",
                affected_count =count ,
                action_type =ChangeType .SAFE ,
                proposed_change =f"Mask {count } Social Security Numbers (preserving last 4 digits).",
                fix_type ="mask_ssn",
                row_indices =ssn_indices [:100 ],
                details ={"sensitive_type":"ssn"}
                ))
                continue 


        phone_matches =sample .apply (lambda s :bool (PHONE_REGEX .match (s )))
        if phone_matches .sum ()/len (sample )>=0.5 :
            all_phone_mask =series .apply (lambda s :bool (PHONE_REGEX .match (s )))
            phone_indices =series [all_phone_mask ].index .tolist ()
            count =len (phone_indices )
            if count >0 :
                problems .append (Problem (
                id =f"sensitive_phone_{col }",
                category =ProblemCategory .SENSITIVE_DATA ,
                column =str (col ),
                description =f"{count } phone numbers detected in '{col }'.",
                affected_count =count ,
                action_type =ChangeType .SAFE ,
                proposed_change =f"Mask {count } phone numbers.",
                fix_type ="mask_phone",
                row_indices =phone_indices [:100 ],
                details ={"sensitive_type":"phone"}
                ))

    return problems 
