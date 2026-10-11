from typing import Any ,Dict ,List ,Optional ,Tuple 
import pandas as pd 
from engine .types import ChangeClassification ,Problem ,AuditRecord 
from engine .sensitive import mask_card ,mask_ssn ,mask_phone 
from engine .missing import find_missing_mask 

def clean_dataset (
df_raw :pd .DataFrame ,
problems :List [Problem ],
approved_changes :Optional [Dict [str ,bool ]]=None 
)->Tuple [pd .DataFrame ,List [AuditRecord ],Dict [str ,Dict [str ,Any ]]]:
    df =df_raw .copy ()
    audit_log :List [AuditRecord ]=[]
    modified_cells :Dict [str ,Dict [str ,Any ]]={}
    approvals =approved_changes or {}

    def is_enabled (p :Problem )->bool :
        if p .action_type in (ChangeClassification .SAFE ,ChangeClassification .REVIEW ):
            return approvals .get (p .id ,True )
        return False 

    def record_cell_mod (r :int ,c :str ,old_val :Any ,new_val :Any ,change_desc :str ):
        if r >=0 :
            modified_cells [f"{r }:{c }"]={
            "old":str (old_val ),
            "new":str (new_val ),
            "change":change_desc 
            }


    for p in problems :
        if p .fix_type =="rename_columns"and is_enabled (p ):
            mapping =p .details .get ("mapping",{})
            for old_col ,new_col in mapping .items ():
                if old_col in df .columns :
                    df .rename (columns ={old_col :new_col },inplace =True )
                    audit_log .append (AuditRecord (
                    row =-1 ,
                    column =old_col ,
                    old_value =old_col ,
                    new_value =new_col ,
                    change ="Cleaned column header",
                    reason ="Removed leading/trailing spaces",
                    classification =p .action_type 
                    ))


    for p in problems :
        if p .fix_type =="drop_duplicates"and is_enabled (p ):
            dup_rows =p .details .get ("duplicate_rows",[])
            valid_drops =[r for r in dup_rows if r in df .index ]
            if valid_drops :
                for r in valid_drops :
                    audit_log .append (AuditRecord (
                    row =int (r ),
                    column ="<RECORD>",
                    old_value ="Duplicate record",
                    new_value ="[REMOVED]",
                    change ="Removed duplicate row",
                    reason ="Exact match with previous record",
                    classification =p .action_type 
                    ))
                df .drop (index =valid_drops ,inplace =True )


    for p in problems :
        if p .fix_type =="cast_integer"and is_enabled (p ):
            col =p .column 
            if col and col in df .columns :
                for idx in p .row_indices :
                    if idx in df .index :
                        orig =df .loc [idx ,col ]
                        try :
                            val_int =int (float (str (orig ).strip ()))
                            df .loc [idx ,col ]=val_int 
                            record_cell_mod (int (idx ),col ,orig ,val_int ,"Converted text to number")
                            audit_log .append (AuditRecord (
                            row =int (idx ),
                            column =col ,
                            old_value =orig ,
                            new_value =val_int ,
                            change ="Converted text to number",
                            reason ="Standardized string representation of integer",
                            classification =p .action_type 
                            ))
                        except (ValueError ,TypeError ):
                            pass 


    for p in problems :
        if p .fix_type in ("normalize_categories_safe","normalize_categories_review")and is_enabled (p ):
            col =p .column 
            if col and col in df .columns :
                replacements =p .details .get ("replacements",{})
                for old_val ,new_val in replacements .items ():
                    match_mask =df [col ]==old_val 
                    indices =df [match_mask ].index .tolist ()
                    for idx in indices :
                        record_cell_mod (int (idx ),col ,old_val ,new_val ,"Standardized category")
                        audit_log .append (AuditRecord (
                        row =int (idx ),
                        column =col ,
                        old_value =old_val ,
                        new_value =new_val ,
                        change ="Standardized category",
                        reason =f"Normalized '{old_val }' to '{new_val }'",
                        classification =p .action_type 
                        ))
                    df .loc [match_mask ,col ]=new_val 


    for p in problems :
        if is_enabled (p ):
            col =p .column 
            if col and col in df .columns :
                df [col ]=df [col ].astype (object )
                if p .fix_type =="mask_credit_cards":
                    for idx in df .index :
                        val =str (df .loc [idx ,col ])
                        masked =mask_card (val )
                        if masked !=val and "****"in masked :
                            record_cell_mod (int (idx ),col ,val ,masked ,"Masked credit card number")
                            audit_log .append (AuditRecord (
                            row =int (idx ),
                            column =col ,
                            old_value =val ,
                            new_value =masked ,
                            change ="Masked credit card number",
                            reason ="Replaced digits with asterisks, keeping last 4 digits",
                            classification =p .action_type 
                            ))
                            df .loc [idx ,col ]=masked 
                elif p .fix_type =="mask_ssn":
                    for idx in df .index :
                        val =str (df .loc [idx ,col ])
                        masked =mask_ssn (val )
                        if masked !=val and "***-**-"in masked :
                            record_cell_mod (int (idx ),col ,val ,masked ,"Masked Social Security Number")
                            audit_log .append (AuditRecord (
                            row =int (idx ),
                            column =col ,
                            old_value =val ,
                            new_value =masked ,
                            change ="Masked Social Security Number",
                            reason ="Preserved last 4 digits",
                            classification =p .action_type 
                            ))
                            df .loc [idx ,col ]=masked 
                elif p .fix_type =="mask_phone":
                    for idx in df .index :
                        val =str (df .loc [idx ,col ])
                        masked =mask_phone (val )
                        if masked !=val and "***-***-"in masked :
                            record_cell_mod (int (idx ),col ,val ,masked ,"Masked phone number")
                            audit_log .append (AuditRecord (
                            row =int (idx ),
                            column =col ,
                            old_value =val ,
                            new_value =masked ,
                            change ="Masked phone number",
                            reason ="Standardized privacy format",
                            classification =p .action_type 
                            ))
                            df .loc [idx ,col ]=masked 


    for p in problems :
        if p .fix_type =="impute_missing"and is_enabled (p ):
            col =p .column 
            if col and col in df .columns :
                impute_val =p .details .get ("impute_val")
                if impute_val is not None :
                    mask =find_missing_mask (df [col ])
                    indices =df [mask ].index .tolist ()
                    for idx in indices :
                        orig =df .loc [idx ,col ]
                        record_cell_mod (int (idx ),col ,str (orig )if pd .notna (orig )else "NULL",impute_val ,"Filled missing value")
                        audit_log .append (AuditRecord (
                        row =int (idx ),
                        column =col ,
                        old_value =str (orig )if pd .notna (orig )else "NULL",
                        new_value =impute_val ,
                        change ="Filled missing value",
                        reason =f"Imputed with column median/mode ({impute_val })",
                        classification =p .action_type 
                        ))
                    df .loc [mask ,col ]=impute_val 


    for p in problems :
        if p .fix_type =="cap_percentage"and is_enabled (p ):
            col =p .column 
            if col and col in df .columns :
                num_s =pd .to_numeric (df [col ],errors ="coerce")
                out_mask =(num_s <0 )|(num_s >100 )
                for idx in num_s [out_mask ].index .tolist ():
                    orig =df .loc [idx ,col ]
                    clamped =0.0 if float (orig )<0 else 100.0 
                    df .loc [idx ,col ]=clamped 
                    record_cell_mod (int (idx ),col ,orig ,clamped ,"Clamped out-of-range percentage")
                    audit_log .append (AuditRecord (
                    row =int (idx ),
                    column =col ,
                    old_value =orig ,
                    new_value =clamped ,
                    change ="Clamped percentage",
                    reason ="Adjusted value outside [0, 100]",
                    classification =p .action_type 
                    ))

    return df ,audit_log ,modified_cells 
