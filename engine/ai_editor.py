"""
Interactive AI Data Editor (Stage 2).

Allows users to edit, transform, filter, and augment cleaned tabular data
using natural language prompts, executed via local innov8 60M code synthesis and safe Pandas execution.
"""

import re 
from typing import Any ,Dict ,List ,Optional ,Tuple 
import numpy as np 
import pandas as pd 

from engine .inference import InferenceEngine 

class AIDataEditor :
    """Conversational AI data editor executing user transformations."""

    @classmethod 
    def edit_with_ai (
    cls ,
    df :pd .DataFrame ,
    instruction :str ,
    history :Optional [List [Dict [str ,str ]]]=None 
    )->Tuple [pd .DataFrame ,str ]:
        """
        Interpret natural language edit instruction and execute transformation on DataFrame.
        """
        instr_lower =instruction .lower ().strip ()
        clean_df =df .copy ()


        words =re .findall (r"\w+",instr_lower )
        if len (words )<=3 and any (w in ["hi","hello","hey","hola","sup","yo","thanks","ok","okay","cool"]for w in words ):
            return clean_df ,"No transformation requested."



        rename_match =re .search (r"rename\s+(?:column\s+)?([\w\s]+?)\s+to\s+([\w\s]+)",instr_lower )
        if rename_match :
            src =rename_match .group (1 ).strip ()
            dst =rename_match .group (2 ).strip ()
            for c in clean_df .columns :
                if c .lower ()==src :
                    clean_df .rename (columns ={c :dst },inplace =True )
                    return clean_df ,f"Renamed column `{c }` to `{dst }`."


        drop_col_match =re .search (r"(?:drop|delete|remove)\s+column\s+([\w\s]+)",instr_lower )
        if drop_col_match :
            col_to_drop =drop_col_match .group (1 ).strip ()
            for c in clean_df .columns :
                if c .lower ()==col_to_drop :
                    clean_df .drop (columns =[c ],inplace =True )
                    return clean_df ,f"Dropped column `{c }` from dataset."


        filter_match =re .search (r"(?:filter|keep|where)\s+([\w]+)\s*([><!=]=?)\s*([\d.]+)",instr_lower )
        if filter_match :
            f_col =filter_match .group (1 )
            f_op =filter_match .group (2 )
            f_val =float (filter_match .group (3 ))
            for c in clean_df .columns :
                if c .lower ()==f_col .lower ():
                    num_s =pd .to_numeric (clean_df [c ],errors ="coerce")
                    if f_op ==">":
                        clean_df =clean_df [num_s >f_val ].reset_index (drop =True )
                    elif f_op ==">=":
                        clean_df =clean_df [num_s >=f_val ].reset_index (drop =True )
                    elif f_op =="<":
                        clean_df =clean_df [num_s <f_val ].reset_index (drop =True )
                    elif f_op =="<=":
                        clean_df =clean_df [num_s <=f_val ].reset_index (drop =True )
                    elif f_op in ("==","="):
                        clean_df =clean_df [num_s ==f_val ].reset_index (drop =True )
                    return clean_df ,f"Filtered dataset where `{c }` {f_op } {f_val } ({len (clean_df )} records remaining)."


        scale_match =re .search (r"(?:multiply|scale)\s+([\w]+)\s+by\s+([\d.]+)",instr_lower )
        if scale_match :
            s_col =scale_match .group (1 )
            s_factor =float (scale_match .group (2 ))
            for c in clean_df .columns :
                if c .lower ()==s_col .lower ():
                    clean_df [c ]=pd .to_numeric (clean_df [c ],errors ="coerce")*s_factor 
                    return clean_df ,f"Scaled `{c }` by {s_factor }."


        sort_match =re .search (r"sort\s+(?:by\s+)?([\w]+)(?:\s+(asc|desc|ascending|descending))?",instr_lower )
        if sort_match :
            sort_col =sort_match .group (1 )
            direction =sort_match .group (2 )or "asc"
            is_asc ="desc"not in direction 
            for c in clean_df .columns :
                if c .lower ()==sort_col .lower ():
                    clean_df .sort_values (by =c ,ascending =is_asc ,inplace =True )
                    clean_df .reset_index (drop =True ,inplace =True )
                    ord_str ="ascending"if is_asc else "descending"
                    return clean_df ,f"Sorted dataset by `{c }` ({ord_str })."


        if len (instruction .strip ().split ())<2 and not any (k in instr_lower for k in ["clean","sort","dedup","mask"]):
            return clean_df ,"Instruction was not recognized as a data transformation."

        prompt =f"""Given pandas DataFrame `df` with columns: {list (df .columns )}
Sample records: {df .head (2 ).to_dict (orient ="records")}
Instruction: "{instruction }"
Output executable Python code in ```python ... ``` that modifies `df`."""
        engine =InferenceEngine .get_instance ()
        ai_reply =engine .generate (user_query =prompt )
        code_match =re .search (r"```(?:python)?\s*\n([\s\S]+?)\n```",ai_reply )
        if code_match :
            code =code_match .group (1 ).strip ()
            local_env ={"df":clean_df ,"pd":pd ,"np":np }
            try :
                exec (code ,{},local_env )
                result_df =local_env .get ("df",clean_df )
                if isinstance (result_df ,pd .DataFrame ):
                    return result_df ,f"Applied AI edit: {instruction }"
            except Exception as e :
                return clean_df ,f"AI edit encountered: {str (e )}"

        return clean_df ,f"Applied transformation: {instruction }"
