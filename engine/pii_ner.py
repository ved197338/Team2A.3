"""
Automated PII Classification (NER) and Anonymization Engine.

Identifies, scores, and redacts sensitive Personally Identifiable Information
including SSNs, Credit Cards (with Luhn verification), Emails, Phones, and IPs.
"""

from dataclasses import dataclass ,field 
import hashlib 
import re 
from typing import Any ,Dict ,List ,Optional ,Tuple 
import pandas as pd 


@dataclass 
class PIIScanMatch :
    entity_type :str 
    column :str 
    row_index :int 
    raw_snippet :str 
    confidence :float 
    is_checksum_verified :bool =False 
    sensitivity_tier :str ="CONFIDENTIAL"


@dataclass 
class PIIColumnClassification :
    column_name :str 
    detected_entities :List [str ]
    match_count :int 
    match_ratio :float 
    highest_sensitivity :str 
    recommended_action :str 


class PIINERClassifier :
    """
    Rule and pattern based Named Entity Recognizer for PII governance.
    """

    PATTERNS ={
    "SSN":re .compile (r"\d{3}-\d{2}-\d{4}"),
    "CREDIT_CARD":re .compile (r"(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})"),
    "EMAIL":re .compile (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}"),
    "PHONE":re .compile (r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    "IPV4":re .compile (r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"),
    }

    TIERS ={
    "SSN":"RESTRICTED",
    "CREDIT_CARD":"RESTRICTED",
    "EMAIL":"CONFIDENTIAL",
    "PHONE":"CONFIDENTIAL",
    "IPV4":"INTERNAL"
    }

    @staticmethod 
    def verify_luhn (card_number_str :str )->bool :
        """Luhn Modulo 10 Checksum Algorithm."""
        digits =[int (c )for c in card_number_str if c .isdigit ()]
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

    @classmethod 
    def scan_dataframe (cls ,df :pd .DataFrame ,sample_size :int =1000 )->List [PIIColumnClassification ]:
        sample_df =df .head (sample_size )
        n_rows =len (sample_df )
        classifications :List [PIIColumnClassification ]=[]

        for col in df .columns :
            series =sample_df [col ].dropna ().astype (str )
            if len (series )==0 :
                continue 

            col_lower =str (col ).lower ()
            detected_types =set ()
            total_matches =0 
            highest_tier ="PUBLIC"


            if "email"in col_lower :
                detected_types .add ("EMAIL")
            elif "ssn"in col_lower or "social"in col_lower :
                detected_types .add ("SSN")
            elif "card"in col_lower or "cc_"in col_lower :
                detected_types .add ("CREDIT_CARD")
            elif "phone"in col_lower or "mobile"in col_lower :
                detected_types .add ("PHONE")


            for p_type ,regex in cls .PATTERNS .items ():
                matches =series .apply (lambda val :bool (regex .search (val )))
                m_count =int (matches .sum ())
                if m_count >0 :
                    if p_type =="CREDIT_CARD":

                        valid_luhn =series [matches ].apply (cls .verify_luhn ).sum ()
                        if valid_luhn >0 :
                            detected_types .add (p_type )
                            total_matches +=int (valid_luhn )
                    else :
                        detected_types .add (p_type )
                        total_matches +=m_count 

            if detected_types :

                for dt in detected_types :
                    tier =cls .TIERS .get (dt ,"CONFIDENTIAL")
                    if tier =="RESTRICTED":
                        highest_tier ="RESTRICTED"
                    elif tier =="CONFIDENTIAL"and highest_tier !="RESTRICTED":
                        highest_tier ="CONFIDENTIAL"

                ratio =total_matches /max (1 ,n_rows )
                action ="MASK"if highest_tier in ("RESTRICTED","CONFIDENTIAL")else "INTERNAL"

                classifications .append (PIIColumnClassification (
                column_name =str (col ),
                detected_entities =sorted (list (detected_types )),
                match_count =total_matches ,
                match_ratio =round (float (ratio ),4 ),
                highest_sensitivity =highest_tier ,
                recommended_action =action 
                ))

        return classifications 

    @classmethod 
    def anonymize_dataframe (
    cls ,
    df :pd .DataFrame ,
    classifications :List [PIIColumnClassification ],
    salt :str ="innovATE-salt"
    )->pd .DataFrame :
        """
        Apply governance anonymization transformations to data frame.
        """
        clean_df =df .copy ()

        for c_info in classifications :
            col =c_info .column_name 
            if col not in clean_df .columns :
                continue 

            action =c_info .recommended_action 
            if action =="MASK":
                if "CREDIT_CARD"in c_info .detected_entities :
                    clean_df [col ]=clean_df [col ].astype (str ).apply (
                    lambda x :f"****-****-****-{re .sub (r'\D','',x )[-4 :]}"if len (re .sub (r'\D','',x ))>=4 else "****"
                    )
                elif "SSN"in c_info .detected_entities :
                    clean_df [col ]=clean_df [col ].astype (str ).apply (
                    lambda x :f"***-**-{re .sub (r'\D','',x )[-4 :]}"if len (re .sub (r'\D','',x ))>=4 else "***-**-****"
                    )
                elif "EMAIL"in c_info .detected_entities :
                    clean_df [col ]=clean_df [col ].astype (str ).apply (
                    lambda x :f"{x .split ('@')[0 ][:2 ]}***@{x .split ('@')[1 ]}"if '@'in x else "***@anonymized.org"
                    )
                elif "PHONE"in c_info .detected_entities :
                    clean_df [col ]=clean_df [col ].astype (str ).apply (
                    lambda x :f"***-***-{re .sub (r'\D','',x )[-4 :]}"if len (re .sub (r'\D','',x ))>=4 else "***-***-****"
                    )
                else :
                    clean_df [col ]="[CONFIDENTIAL-MASKED]"

            elif action =="HASH":
                clean_df [col ]=clean_df [col ].astype (str ).apply (
                lambda x :hashlib .sha256 (f"{x }:{salt }".encode ("utf-8")).hexdigest ()[:16 ]
                )

            elif action =="REDACT":
                clean_df [col ]="[REDACTED]"

        return clean_df 
