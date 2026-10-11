import re 
from datetime import datetime 
from typing import Any ,Dict ,List 
import pandas as pd 

INT_REGEX =re .compile (r'^[+-]?\d+$')
DECIMAL_REGEX =re .compile (r'^[+-]?\d*\.\d+([eE][+-]?\d+)?$|^[+-]?\d+[eE][+-]?\d+$')
BOOLEAN_SET ={'true','false','yes','no','t','f','1','0'}
DATE_PATTERNS =[
(re .compile (r'^\d{4}-\d{2}-\d{2}$'),'%Y-%m-%d'),
(re .compile (r'^\d{4}/\d{2}/\d{2}$'),'%Y/%m/%d'),
(re .compile (r'^\d{2}/\d{2}/\d{4}$'),'%m/%d/%Y'),
(re .compile (r'^\d{2}-\d{2}-\d{4}$'),'%d-%m-%Y'),
]
DATETIME_PATTERNS =[
re .compile (r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$'),
]
UUID_REGEX =re .compile (r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
ID_NAME_REGEX =re .compile (r'(_id|id$|^id|_key|code|uuid|guid)',re .IGNORECASE )

def is_val_int (v :str )->bool :
    return bool (INT_REGEX .match (v ))

def is_val_decimal (v :str )->bool :
    return bool (DECIMAL_REGEX .match (v ))

def is_val_bool (v :str )->bool :
    return v .lower ()in BOOLEAN_SET 

def is_val_date (v :str )->bool :
    for pat ,fmt in DATE_PATTERNS :
        if pat .match (v ):
            try :
                datetime .strptime (v ,fmt )
                return True 
            except ValueError :
                pass 
    return False 

def is_val_datetime (v :str )->bool :
    for pat in DATETIME_PATTERNS :
        if pat .match (v ):
            return True 
    return False 

def is_val_uuid (v :str )->bool :
    return bool (UUID_REGEX .match (v ))

def profile_column_type (series :pd .Series ,col_name :str )->Dict [str ,Any ]:
    non_null =series .dropna ().astype (str ).str .strip ()
    non_null =non_null [~non_null .isin (["","NA","N/A","null","NULL","None","none","?","-","NaN"])]

    total_valid =len (non_null )
    if total_valid ==0 :
        return {
        "type":"empty",
        "is_mixed":False ,
        "counts":{},
        "mixed_rows":[]
        }

    int_mask =non_null .apply (is_val_int )
    dec_mask =non_null .apply (is_val_decimal )
    bool_mask =non_null .apply (is_val_bool )
    date_mask =non_null .apply (is_val_date )
    dt_mask =non_null .apply (is_val_datetime )
    uuid_mask =non_null .apply (is_val_uuid )

    int_count =int (int_mask .sum ())
    dec_count =int (dec_mask .sum ())
    bool_count =int (bool_mask .sum ())
    date_count =int (date_mask .sum ())
    dt_count =int (dt_mask .sum ())
    uuid_count =int (uuid_mask .sum ())

    unique_count =non_null .nunique ()
    unique_ratio =unique_count /total_valid 

    is_id =False 
    if uuid_count /total_valid >0.8 :
        is_id =True 
    elif ID_NAME_REGEX .search (col_name )and unique_ratio >0.85 :
        is_id =True 

    numeric_count =int_count +dec_count 
    detected_type ="text"
    is_mixed =False 
    mixed_rows =[]

    if is_id :
        detected_type ="identifier"
    elif bool_count /total_valid >=0.85 and unique_count <=2 :
        detected_type ="boolean"
        if bool_count <total_valid :
            is_mixed =True 
            mixed_rows =non_null [~bool_mask ].index .tolist ()
    elif dt_count /total_valid >=0.80 :
        detected_type ="datetime"
        if dt_count <total_valid :
            is_mixed =True 
            mixed_rows =non_null [~dt_mask ].index .tolist ()
    elif date_count /total_valid >=0.80 :
        detected_type ="date"
        if date_count <total_valid :
            is_mixed =True 
            mixed_rows =non_null [~date_mask ].index .tolist ()
    elif numeric_count /total_valid >=0.70 :
        if dec_count >0 :
            detected_type ="decimal"
            mixed_mask =~(int_mask |dec_mask )
            if mixed_mask .sum ()>0 :
                is_mixed =True 
                mixed_rows =non_null [mixed_mask ].index .tolist ()
        else :
            detected_type ="integer"
            mixed_mask =~int_mask 
            if mixed_mask .sum ()>0 :
                is_mixed =True 
                mixed_rows =non_null [mixed_mask ].index .tolist ()
    elif unique_ratio <0.20 or unique_count <=30 :
        detected_type ="categorical"
    else :
        detected_type ="text"

    if not is_mixed and series .dtype ==object :
        types_present =set (type (x )for x in series .dropna ())
        if len (types_present )>1 :
            is_mixed =True 
            mixed_rows =[i for i ,x in series .dropna ().items ()if type (x )is str and is_val_int (x )]

    return {
    "type":detected_type ,
    "is_mixed":is_mixed ,
    "mixed_rows":mixed_rows [:100 ],
    "total_mixed_count":len (mixed_rows ),
    }
