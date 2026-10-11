import re 
import unicodedata 
from typing import Any ,Dict ,List ,Tuple 
import pandas as pd 
from engine .types import ChangeType ,Problem ,ProblemCategory 

def levenshtein_distance (s1 :str ,s2 :str )->int :
    if s1 ==s2 :
        return 0 
    m ,n =len (s1 ),len (s2 )
    if m ==0 :
        return n 
    if n ==0 :
        return m 

    dp =list (range (n +1 ))
    for i in range (1 ,m +1 ):
        new_dp =[i ]+[0 ]*n 
        for j in range (1 ,n +1 ):
            cost =0 if s1 [i -1 ]==s2 [j -1 ]else 1 
            new_dp [j ]=min (
            dp [j ]+1 ,
            new_dp [j -1 ]+1 ,
            dp [j -1 ]+cost 
            )
        dp =new_dp 
    return dp [n ]

def string_similarity (s1 :str ,s2 :str )->float :
    max_len =max (len (s1 ),len (s2 ))
    if max_len ==0 :
        return 1.0 
    dist =levenshtein_distance (s1 ,s2 )
    return 1.0 -(dist /max_len )

def normalize_text_key (s :str )->str :
    s =unicodedata .normalize ('NFKD',s )
    s =s .lower ()
    s =re .sub (r'\s+',' ',s ).strip ()
    s =re .sub (r'^[^\w]+|[^\w]+$','',s )
    return s 

def token_similarity (s1 :str ,s2 :str )->float :
    t1 =set (s1 .split ())
    t2 =set (s2 .split ())
    if not t1 or not t2 :
        return 0.0 
    intersection =t1 .intersection (t2 )
    union =t1 .union (t2 )
    return len (intersection )/len (union )

KNOWN_CITY_ALIASES ={
"bengaluru":"bangalore",
"bangalore":"bangalore",
"bombay":"mumbai",
"mumbai":"mumbai",
"madras":"chennai",
"chennai":"chennai",
"calcutta":"kolkata",
"kolkata":"kolkata",
}

def analyze_category_consistency (df :pd .DataFrame ,col_types :Dict [str ,str ])->List [Problem ]:
    problems :List [Problem ]=[]

    for col in df .columns :
        if col_types .get (col )!="categorical"and df [col ].dtype !=object :
            continue 

        series =df [col ].dropna ()
        if len (series )==0 :
            continue 

        raw_counts =series .astype (str ).value_counts ().to_dict ()
        unique_vals =list (raw_counts .keys ())
        if len (unique_vals )<=1 or len (unique_vals )>300 :
            continue 


        norm_to_raw :Dict [str ,List [Tuple [str ,int ]]]={}
        for val ,count in raw_counts .items ():
            norm_key =normalize_text_key (val )
            if not norm_key :
                continue 
            norm_to_raw .setdefault (norm_key ,[]).append ((val ,count ))

        safe_mappings :Dict [str ,str ]={}
        for norm_key ,variants in norm_to_raw .items ():
            if len (variants )>1 :
                variants .sort (key =lambda x :x [1 ],reverse =True )
                canonical =variants [0 ][0 ]
                for v ,_ in variants [1 :]:
                    safe_mappings [v ]=canonical 

        if safe_mappings :
            affected_rows =df [df [col ].isin (safe_mappings .keys ())].index .tolist ()
            if affected_rows :
                problems .append (Problem (
                id =f"inconsistent_case_ws_{col }",
                category =ProblemCategory .INCONSISTENT_VALUES ,
                column =str (col ),
                description =f"{len (affected_rows )} values in '{col }' have inconsistent casing or spacing.",
                affected_count =len (affected_rows ),
                action_type =ChangeType .SAFE ,
                proposed_change =f"Standardize {len (affected_rows )} casing and spacing variations to common form.",
                fix_type ="normalize_categories_safe",
                row_indices =affected_rows [:100 ],
                details ={
                "replacements":safe_mappings ,
                "variant_count":len (safe_mappings ),
                }
                ))


        unique_norm_keys =list (norm_to_raw .keys ())
        review_mappings :Dict [str ,str ]={}

        for i in range (len (unique_norm_keys )):
            k1 =unique_norm_keys [i ]
            for j in range (i +1 ,len (unique_norm_keys )):
                k2 =unique_norm_keys [j ]

                alias_match =False 
                if k1 in KNOWN_CITY_ALIASES and KNOWN_CITY_ALIASES [k1 ]==KNOWN_CITY_ALIASES .get (k2 ):
                    alias_match =True 

                sim =string_similarity (k1 ,k2 )
                tok_sim =token_similarity (k1 ,k2 )

                if alias_match or sim >=0.80 or tok_sim >=0.75 :
                    freq1 =sum (c for _ ,c in norm_to_raw [k1 ])
                    freq2 =sum (c for _ ,c in norm_to_raw [k2 ])

                    if freq1 >=freq2 :
                        target_canonical =norm_to_raw [k1 ][0 ][0 ]
                        source_variants =[v for v ,_ in norm_to_raw [k2 ]]
                    else :
                        target_canonical =norm_to_raw [k2 ][0 ][0 ]
                        source_variants =[v for v ,_ in norm_to_raw [k1 ]]

                    for src in source_variants :
                        if src not in safe_mappings :
                            review_mappings [src ]=target_canonical 

        if review_mappings :
            affected_rows =df [df [col ].isin (review_mappings .keys ())].index .tolist ()
            if affected_rows :
                problems .append (Problem (
                id =f"fuzzy_variants_{col }",
                category =ProblemCategory .INCONSISTENT_VALUES ,
                column =str (col ),
                description =f"{len (affected_rows )} values in '{col }' match near-duplicate categories (e.g. typos or regional names).",
                affected_count =len (affected_rows ),
                action_type =ChangeType .REVIEW ,
                proposed_change =f"Merge {len (review_mappings )} near-duplicate categories into main spelling.",
                fix_type ="normalize_categories_review",
                row_indices =affected_rows [:100 ],
                details ={"replacements":review_mappings }
                ))

    return problems 
