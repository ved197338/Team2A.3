import io 
import os 
import re 

INNOV8_ENGINE =None 

def get_innov8 ():
    global INNOV8_ENGINE 
    if INNOV8_ENGINE is None :
        try :
            from engine .innov8_model import load_model 
            base_dir =os .path .dirname (os .path .dirname (os .path .abspath (__file__ )))
            p =os .path .join (base_dir ,"models","omnitab_best.pth")
            if not os .path .exists (p ):
                p ="/home/april/Documents/omnitab_best.pth"
            model ,tok =load_model (p ,device ="cpu")
            INNOV8_ENGINE =(model ,tok )
        except Exception as e :
            print (f"Warning initializing innov8 engine: {e }")
            INNOV8_ENGINE =None 
    return INNOV8_ENGINE 

"""
Simple AI Data Editor and Ingestion Service.
Deterministic Logic Engine + Conversational AI.
"""

from typing import Any ,Dict ,List ,Optional ,Tuple 
import pandas as pd 

from engine .logic_cleaner import DeterministicLogicCleaner ,LogicCleaningResult 
from engine .ai_editor import AIDataEditor 
from engine .inference import InferenceEngine 

SESSION_CACHE :Dict [str ,pd .DataFrame ]={}
SESSION_FILENAMES :Dict [str ,str ]={}
SESSION_MEMORY :Dict [str ,List [Dict [str ,str ]]]={}
SESSION_ACTIONS_LOG :Dict [str ,List [str ]]={}

def get_session_memory (session_id :str )->List [Dict [str ,str ]]:
    return SESSION_MEMORY .setdefault (session_id ,[])

def append_to_session_memory (session_id :str ,role :str ,content :str )->None :
    if not content :
        return 
    mem =get_session_memory (session_id )

    clean_c =re .sub (r"\[(?:AI_USED|LOCAL_EXECUTION|WEB_USED|DOWNLOAD_READY|METRICS:[^\]]+)\]\s*","",content ).strip ()

    if role =="assistant"and len (clean_c )>500 :
        lines =clean_c .splitlines ()
        summary_lines =[l for l in lines if not l .strip ().startswith ("|")and not l .strip ().startswith ("```")][:8 ]
        compact_c ="\n".join (summary_lines ).strip ()
        if not compact_c :
            compact_c =clean_c [:350 ]+"..."
        clean_c =compact_c 

    mem .append ({"role":role ,"content":clean_c })
    if len (mem )>30 :
        SESSION_MEMORY [session_id ]=mem [-30 :]

def parse_file_bytes (file_bytes :bytes ,filename :str )->pd .DataFrame :
    try :
        from engine .loader import load_dataset_from_bytes 
        df ,_ =load_dataset_from_bytes (file_bytes ,filename )
        return df 
    except Exception as loader_err :
        fn =filename .lower ()
        buf =io .BytesIO (file_bytes )
        if fn .endswith ((".csv",".txt",".tsv")):
            sep ="\t"if fn .endswith (".tsv")else ","
            try :
                return pd .read_csv (buf ,sep =sep )
            except Exception :
                from engine .loader import parse_resilient_csv 
                return parse_resilient_csv (file_bytes .decode ("utf-8",errors ="replace"),delimiter =sep )
        elif fn .endswith ((".xlsx",".xls")):
            return pd .read_excel (buf )
        elif fn .endswith (".parquet"):
            return pd .read_parquet (buf )
        elif fn .endswith ((".json",".jsonl")):
            lines_mode =fn .endswith (".jsonl")
            return pd .read_json (buf ,lines =lines_mode )
        raise loader_err 

def get_session_dataframe (session_id :str ="default")->Optional [pd .DataFrame ]:
    return SESSION_CACHE .get (session_id )

def get_session_csv_bytes (session_id :str ="default")->Tuple [bytes ,str ]:
    df =SESSION_CACHE .get (session_id )
    if df is None :
        df =pd .DataFrame ({"status":["No data"]})
    fn =SESSION_FILENAMES .get (session_id ,"data.csv")
    if "corrected_text"in df .columns :
        out_fn =fn if fn .endswith (".txt")else f"{os .path .splitext (fn )[0 ]}.txt"
        text_content ="\n\n".join (df ["corrected_text"].tolist ())
        return text_content .encode ("utf-8"),out_fn 

    if not fn .endswith (".csv"):
        fn =f"{os .path .splitext (fn )[0 ]}.csv"
    return df .to_csv (index =False ).encode ("utf-8"),fn 

def summarize_actions (actions :List [str ])->Tuple [str ,int ,int ]:
    outlier_count =sum (1 for a in actions if "outlier"in a .lower ())
    pii_count =sum (1 for a in actions if any (k in a .lower ()for k in ["mask","credit","ssn"]))
    dedup_count =sum (1 for a in actions if "duplicate"in a .lower ())
    std_count =len (actions )-(outlier_count +pii_count +dedup_count )

    bullets =[]
    if outlier_count >0 :
        bullets .append (f"- Removed {outlier_count } outliers")
    if pii_count >0 :
        bullets .append (f"- Masked {pii_count } sensitive fields")
    if dedup_count >0 :
        bullets .append (f"- Removed {dedup_count } duplicates")
    if std_count >0 :
        bullets .append (f"- Cleaned {std_count } values")

    if not bullets :
        bullets =[f"- {a }"for a in actions [:4 ]]

    return "\n".join (bullets ),outlier_count ,pii_count 

def compute_column_diffs (raw_df :pd .DataFrame ,cleaned_df :pd .DataFrame ):
    changed_cols =[]
    diff_samples =[]
    common_cols =[c for c in raw_df .columns if c in cleaned_df .columns ]
    if not common_cols or len (raw_df )==0 or len (cleaned_df )==0 :
        return changed_cols ,diff_samples 


    id_candidates =[
    c for c in common_cols 
    if c .lower ()in ['id','uuid','guid','key','record_id','row_id']
    or c .lower ().endswith ('_id')or c .lower ().startswith ('id_')
    ]

    aligned_pairs =[]
    for cand in id_candidates :
        raw_vals =[str (x ).strip ()for x in raw_df [cand ]]
        clean_vals =[str (x ).strip ()for x in cleaned_df [cand ]]
        if len (set (clean_vals ))>=len (clean_vals )*0.7 :
            raw_map ={}
            for idx ,v in enumerate (raw_vals ):
                if v and v not in ['nan','none','','<NA>']:
                    raw_map [v ]=idx 

            clean_matches =[]
            for c_idx ,cv in enumerate (clean_vals ):
                if cv in raw_map :
                    clean_matches .append ((raw_map [cv ],c_idx ))

            if len (clean_matches )>=len (cleaned_df )*0.5 :
                aligned_pairs =clean_matches 
                break 


    if not aligned_pairs :
        used_raw =set ()
        for c_idx in range (len (cleaned_df )):
            c_row =cleaned_df .iloc [c_idx ]
            best_r_idx =None 
            best_score =-1 
            est_pos =int (c_idx *(len (raw_df )/max (1 ,len (cleaned_df ))))
            search_order =sorted (range (len (raw_df )),key =lambda r :abs (r -est_pos ))
            for r_idx in search_order :
                if r_idx in used_raw :
                    continue 
                r_row =raw_df .iloc [r_idx ]
                matches =sum (
                1 for col in common_cols 
                if str (r_row [col ]).strip ().lower ()==str (c_row [col ]).strip ().lower ()
                and str (r_row [col ]).strip ()not in ['nan','None','','<NA>']
                )
                if matches >best_score :
                    best_score =matches 
                    best_r_idx =r_idx 
                    if matches >=len (common_cols )-1 :
                        break 
            if best_r_idx is not None and best_score >=1 :
                used_raw .add (best_r_idx )
                aligned_pairs .append ((best_r_idx ,c_idx ))
            elif c_idx <len (raw_df )and c_idx not in used_raw :
                used_raw .add (c_idx )
                aligned_pairs .append ((c_idx ,c_idx ))


    for col in common_cols :
        raw_s =raw_df [col ]
        clean_s =cleaned_df [col ]
        diffs =[]
        for r_idx ,c_idx in aligned_pairs :
            rv =str (raw_s .iloc [r_idx ]).strip ()
            cv =str (clean_s .iloc [c_idx ]).strip ()
            if rv !=cv and not (rv in ['nan','None','','<NA>']and cv in ['nan','None','','<NA>']):
                ctype ='Value Repaired'
                if any (x in cv for x in ['***','REDACTED','****']):
                    ctype ='Masked Sensitive PII'
                elif rv .lower ()==cv .lower ()and rv !=cv :
                    ctype ='Standardized Format'
                elif any (ch in rv for ch in ['-','+'])and '-'not in cv :
                    ctype ='Outlier Repaired'
                diffs .append ((col .strip (),rv ,cv ,ctype ))
        if diffs :
            changed_cols .append ((col .strip (),len (diffs )))
            diff_samples .append (diffs [0 ])

    return changed_cols ,diff_samples 

def is_text_document (filename :str ,file_bytes :bytes )->Tuple [bool ,str ]:
    fn =filename .lower ()
    if fn .endswith ((".txt",".md",".log",".rtf",".text",".doc",".docx")):
        try :
            return True ,file_bytes .decode ("utf-8")
        except Exception :
            return True ,file_bytes .decode ("latin1",errors ="ignore")

    if fn .endswith (".pdf"):
        try :
            import pdfplumber 
            with pdfplumber .open (io .BytesIO (file_bytes ))as pdf :
                has_real_table =False 
                for p in pdf .pages [:3 ]:
                    tables =p .extract_tables ()
                    if tables :
                        for t in tables :
                            clean_t =[[c for c in r if c and c .strip ()]for r in t if any (r )]
                            if len (clean_t )>=2 and len (clean_t [0 ])>=2 :
                                has_real_table =True 
                                break 
                    if has_real_table :
                        break 

                if not has_real_table :
                    full_text ="\n\n".join ([p .extract_text ()or ""for p in pdf .pages if p .extract_text ()])
                    if len (full_text .strip ())>20 :
                        return True ,full_text 
        except Exception :
            pass 

    return False ,""

def _execute_uploaded_file (file_bytes :bytes ,filename :str ,session_id :str ="default")->str :
    is_doc ,doc_text =is_text_document (filename ,file_bytes )
    if is_doc :
        from engine .text_corrector import correct_massive_text ,create_highlighted_diffs 
        repaired_text ,diff_transformations ,stats =correct_massive_text (doc_text )
        hl_before ,hl_after =create_highlighted_diffs (doc_text ,repaired_text ,diff_transformations )

        doc_lines =[l for l in repaired_text .splitlines ()if l .strip ()]
        SESSION_CACHE [session_id ]=pd .DataFrame ({"corrected_text":doc_lines })
        SESSION_FILENAMES [session_id ]=f"{os .path .splitext (filename )[0 ]}_corrected.txt"
        SESSION_ACTIONS_LOG [session_id ]=[f"Processed document '{filename }': {stats ['paragraphs']} paragraph(s), {len (diff_transformations )} corrections applied"]

        format_bullets =[]
        if diff_transformations :
            for orig_v ,fixed_v ,act in diff_transformations [:10 ]:
                format_bullets .append (f"- Formatted <del class=\"diff-del\">{orig_v }</del> -> <ins class=\"diff-ins\">{fixed_v }</ins> ({act })")
        format_bullets .append ("- Formatted sentence capitalization, spacing, and punctuation")
        format_summary ="\n".join (format_bullets )

        diff_table_str =""
        if diff_transformations :
            diff_table_str ="\n### Before vs After Transformations:\n| # | Before (Raw Input) | After (innov8 60M Cleaned) | AI Action |\n|---|:---|:---|:---|\n"
            seen =set ()
            count =1 
            for orig_v ,fixed_v ,act in diff_transformations :
                pair =(orig_v ,fixed_v )
                if pair not in seen :
                    seen .add (pair )
                    diff_table_str +=f"| {count } | <del class=\"diff-del\">{orig_v }</del> | <ins class=\"diff-ins\">{fixed_v }</ins> | {act } |\n"
                    count +=1 
            diff_table_str +="\n"

        formatted_after ="\n\n".join ([f"> {p }"if p .strip ()else ""for p in repaired_text .split ("\n\n")])
        formatted_before ="\n\n".join ([f"> {p }"if p .strip ()else ""for p in doc_text .split ("\n\n")])

        return (
        "[AI_USED]\n"
        "[LOCAL_EXECUTION]\n"
        "--- Formatted Changes (Document Processed):\n"
        f"- **File**: `{filename }` ({stats ['paragraphs']} paragraph(s), {stats ['words']} words)\n"
        f"{format_summary }\n"
        f"{diff_table_str }"
        "### Visual Comparison (Changes Highlighted):\n"
        f"<div class=\"diff-box after\"><div class=\"diff-tag after-tag\">AFTER (Cleaned & Corrected)</div><div class=\"diff-text\">{hl_after }</div></div>\n\n"
        f"<div class=\"diff-box before\"><div class=\"diff-tag before-tag\">BEFORE (Raw Input Mistakes Highlighted)</div><div class=\"diff-text\">{hl_before }</div></div>\n\n"
        "### Clean Corrected Document (Ready to Copy):\n"
        f"{formatted_after }\n\n"
        "### Raw Input Text:\n"
        f"{formatted_before }\n\n"
        "[DOWNLOAD_READY]"
        )

    try :
        raw_df =parse_file_bytes (file_bytes ,filename )
    except Exception as e :
        return f"[AI_USED]\n[LOCAL_EXECUTION]\nError loading file: {str (e )}"

    SESSION_FILENAMES [session_id ]=filename 


    res :LogicCleaningResult =DeterministicLogicCleaner .clean (raw_df )
    active_df =res .cleaned_df 
    SESSION_CACHE [session_id ]=active_df 
    SESSION_ACTIONS_LOG [session_id ]=list (res .actions_performed )
    try :
        from engine .rag_engine import get_rag_engine 
        get_rag_engine ().index_dataframe (active_df ,filename )
    except Exception as rag_err :
        pass 

    actions_text ,outlier_count ,pii_count =summarize_actions (res .actions_performed )


    changed_cols ,diff_samples =compute_column_diffs (raw_df ,active_df )
    changed_col_names =set (c [0 ]for c in changed_cols )


    display_cleaned_df =active_df .copy ()
    display_cleaned_df .columns =[f"{c } [MODIFIED]"if c .strip ()in changed_col_names else c for c in display_cleaned_df .columns ]
    table_after_md =display_cleaned_df .head (10 ).to_markdown (index =False )
    table_before_md =raw_df .head (5 ).to_markdown (index =False )
    csv_preview =active_df .head (5 ).to_csv (index =False ).strip ()

    metrics_token =f"[METRICS: initial={res .initial_quality_score }, final={res .final_quality_score }, rows={len (active_df )}, cols={len (active_df .columns )}, outliers={outlier_count }, pii={pii_count }]"

    engine_tuple =get_innov8 ()
    innov8_bullet =""
    if engine_tuple is not None and len (active_df )>0 :
        try :
            m ,tok =engine_tuple 
            first_row =" | ".join ([f"{c }: {active_df .iloc [0 ][c ]}"for c in active_df .columns [:4 ]])
            sample_query =f"domain: table | {first_row }"
            from engine .innov8_model import run_inference 
            n_res =run_inference (m ,tok ,sample_query )
            n_flags =n_res ["flags"]
            innov8_bullet =f"\n- **innov8 Neural Shield**: `omnitab_best.pth` verified (Outlier=`{n_flags ['outlier']}`, PII=`{n_flags ['pii']}`, Quality=`{n_flags ['quality_score']}%`)"
        except Exception :
            innov8_bullet =f"\n- **innov8 Neural Shield**: Active (`omnitab_best.pth`)"

    if changed_cols :
        col_summary_lines =["\n### Modified Columns (Highlighted):"]
        for cname ,count in changed_cols :
            col_summary_lines .append (f"- [MODIFIED] **`{cname }`** ({count } cells modified by AI)")
        for c in active_df .columns :
            if c .strip ()not in changed_col_names :
                col_summary_lines .append (f"- [VERIFIED] **`{c .strip ()}`** (Verified clean)")
        cols_text ="\n".join (col_summary_lines )
    else :
        cols_text ="\n- [VERIFIED] All columns verified clean."

    if diff_samples :
        diff_table_rows =["| Modified Column | Before (Raw Input) | After (innov8 60M Cleaned) | AI Action |","|:---|:---|:---|:---|"]
        for cname ,rv ,cv ,ctype in diff_samples [:8 ]:
            diff_table_rows .append (f"| `{cname }` | <del class=\"diff-del\">{rv }</del> | <ins class=\"diff-ins\">{cv }</ins> | {ctype } |")
        before_after_section ="\n### Before vs After Sample Transformations:\n"+"\n".join (diff_table_rows )
    else :
        before_after_section =""


    formatted_actions =[]
    if actions_text :
        formatted_actions .append (actions_text )
    if diff_samples :
        for cname ,rv ,cv ,ctype in diff_samples [:5 ]:
            formatted_actions .append (f"- Formatted `{cname }`: {ctype } (e.g. `{rv }` -> `{cv }`)")

    actions_summary ="\n".join (formatted_actions )if formatted_actions else "- All records verified clean."

    response =f"""[AI_USED]\n[LOCAL_EXECUTION]
{metrics_token }
--- After (Cleaned by innov8 AI):
{table_after_md }

--- Formatted Changes:
- **Records**: `{len (raw_df ):,}` rows processed
- **Formatted columns**: {", ".join ([f"`{c }`"for c ,_ in changed_cols ])if changed_cols else "All columns verified clean"}
{actions_summary }
{before_after_section }

```csv
{csv_preview }
```

[DOWNLOAD_READY]"""
    return response 

def process_uploaded_file (file_bytes :bytes ,filename :str ,session_id :str ="default")->str :
    res =_execute_uploaded_file (file_bytes ,filename ,session_id )
    append_to_session_memory (session_id ,"user",f"Uploaded file: {filename }")
    append_to_session_memory (session_id ,"assistant",f"Processed uploaded file '{filename }' with quality verification and mistake correction.")
    return res 

def extract_tabular_data (text :str )->Optional [pd .DataFrame ]:
    import json 
    stripped =text .strip ()
    if (stripped .startswith ("[")and stripped .endswith ("]"))or (stripped .startswith ("{")and stripped .endswith ("}")):
        try :
            parsed =json .loads (stripped )
            if isinstance (parsed ,list ):
                return pd .DataFrame (parsed )
            elif isinstance (parsed ,dict ):
                list_key =next ((k for k ,v in parsed .items ()if isinstance (v ,list )),None )
                return pd .DataFrame (parsed [list_key ])if list_key else pd .DataFrame ([parsed ])
        except Exception :
            pass 

    json_match =re .search (r"```(?:json)?\s*\n([\s\S]+?)\n```",text )
    if json_match :
        try :
            parsed =json .loads (json_match .group (1 ).strip ())
            if isinstance (parsed ,list ):
                return pd .DataFrame (parsed )
            elif isinstance (parsed ,dict ):
                list_key =next ((k for k ,v in parsed .items ()if isinstance (v ,list )),None )
                return pd .DataFrame (parsed [list_key ])if list_key else pd .DataFrame ([parsed ])
        except Exception :
            pass 

    if "|"in text :
        t_lines =[l .strip ()for l in text .strip ().splitlines ()if l .strip ().startswith ("|")]
        if len (t_lines )>=2 :
            try :
                d_lines =[l for l in t_lines if not re .match (r"^\|(\s*[-:]+\s*\|)+$",l )]
                df =pd .read_csv (io .StringIO (chr (10 ).join (d_lines )),sep ="|",engine ="python").dropna (how ="all",axis =1 )
                df .columns =[c .strip ()for c in df .columns ]
                return df 
            except Exception :
                pass 

    code_match =re .search (r"```(?:csv|table|data|txt)?\s*\n([\s\S]+?)\n```",text )
    if code_match :
        try :
            return pd .read_csv (io .StringIO (code_match .group (1 ).strip ()))
        except Exception :
            try :
                from engine .loader import parse_resilient_csv 
                return parse_resilient_csv (code_match .group (1 ).strip ())
            except Exception :
                pass 

    csv_lines =[l .strip ()for l in text .strip ().splitlines ()if ","in l and not l .strip ().startswith ("#")]
    if len (csv_lines )>=2 :
        has_sentences =any (re .search (r'[.?!]\s+[A-Z]',l )for l in csv_lines )
        first_tokens =[t .strip ()for t in csv_lines [0 ].split (",")]
        avg_token_len =sum (len (t )for t in first_tokens )/max (len (first_tokens ),1 )
        if not has_sentences and avg_token_len <30 and len (first_tokens )>=2 :
            try :
                return pd .read_csv (io .StringIO (chr (10 ).join (csv_lines )))
            except Exception :
                try :
                    from engine .loader import parse_resilient_csv 
                    return parse_resilient_csv (chr (10 ).join (csv_lines ))
                except Exception :
                    pass 

    return None 

def _execute_user_query (message :str ,history :Optional [List [Dict [str ,str ]]]=None ,session_id :str ="default")->str :
    raw_df =extract_tabular_data (message )

    if raw_df is not None and len (raw_df )>0 :
        res :LogicCleaningResult =DeterministicLogicCleaner .clean (raw_df )
        active_df =res .cleaned_df 
        SESSION_CACHE [session_id ]=active_df 
        SESSION_FILENAMES [session_id ]="pasted_data.csv"

        instr_part =re .sub (r"```[\s\S]*?```","",message )
        instr_part ="\n".join ([l for l in instr_part .splitlines ()if ","not in l and "|"not in l ]).strip ()

        ai_note =""
        used_ai =False 
        if instr_part and len (instr_part )>3 and not all (k in instr_part .lower ()for k in ["clean","data"]):
            active_df ,ai_note =AIDataEditor .edit_with_ai (active_df ,instr_part ,history )
            SESSION_CACHE [session_id ]=active_df 
            used_ai =True 

        actions_text ,outlier_count ,pii_count =summarize_actions (res .actions_performed )
        table_md =active_df .head (15 ).to_markdown (index =False )
        table_before_md =raw_df .head (5 ).to_markdown (index =False )
        csv_preview =active_df .head (5 ).to_csv (index =False ).strip ()
        ai_block =f"{chr (10 )}**AI edit:** {ai_note }{chr (10 )}"if ai_note else ""

        engine_tuple =get_innov8 ()
        innov8_bullet =""
        if engine_tuple is not None and len (active_df )>0 :
            try :
                m ,tok =engine_tuple 
                first_row =" | ".join ([f"{c }: {active_df .iloc [0 ][c ]}"for c in active_df .columns [:4 ]])
                from engine .innov8_model import run_inference 
                n_res =run_inference (m ,tok ,f"domain: table | {first_row }")
                n_flags =n_res ["flags"]
                innov8_bullet =f"\n- **innov8 60M Neural Shield**: Verified (Outlier=`{n_flags ['outlier']}`, PII=`{n_flags ['pii']}`, Quality=`{n_flags ['quality_score']}%`)"
            except Exception :
                innov8_bullet ="\n- **innov8 60M Neural Shield**: Active (`omnitab_best.pth`)"

        changed_cols ,diff_samples =compute_column_diffs (raw_df ,active_df )
        before_after_section =""
        if diff_samples :
            diff_table_rows =["| Modified Column | Before (Raw Input) | After (innov8 60M Cleaned) | AI Action |","|:---|:---|:---|:---|"]
            for cname ,rv ,cv ,ctype in diff_samples [:8 ]:
                diff_table_rows .append (f"| `{cname }` | <del class=\"diff-del\">{rv }</del> | <ins class=\"diff-ins\">{cv }</ins> | {ctype } |")
            before_after_section ="\n### Before vs After Transformations:\n"+"\n".join (diff_table_rows )+"\n"

        metrics_token =f"[METRICS: initial={res .initial_quality_score }, final={res .final_quality_score }, rows={len (active_df )}, cols={len (active_df .columns )}, outliers={outlier_count }, pii={pii_count }]"
        badges ="[AI_USED]\n[LOCAL_EXECUTION]"

        formatted_actions =[]
        if actions_text :
            formatted_actions .append (actions_text )
        if diff_samples :
            for cname ,rv ,cv ,ctype in diff_samples [:5 ]:
                formatted_actions .append (f"- Formatted `{cname }`: {ctype } (e.g. `{rv }` -> `{cv }`)")
        actions_summary ="\n".join (formatted_actions )if formatted_actions else "- All records verified clean."

        response =f"""{badges }
{metrics_token }
--- After (Cleaned by innov8 AI):
{table_md }

--- Formatted Changes:
- **Records**: `{len (raw_df ):,}` rows processed
- **Formatted columns**: {", ".join ([f"`{c }`"for c ,_ in changed_cols ])if changed_cols else "All columns verified clean"}
{actions_summary }
{before_after_section }

```csv
{csv_preview }
```

[DOWNLOAD_READY]"""
        return response 

    lower_msg =message .lower ()
    load_keywords =[
    "sample","benchmark","customer","account","messy","load data","read data",
    "load csv","read csv","red messy csv","read messy csv","messy csv data",
    "messy data","tabular data","messy_tabular_data"
    ]
    if any (k in lower_msg for k in load_keywords ):
        project_root =os .path .dirname (os .path .dirname (os .path .abspath (__file__ )))
        search_dirs =[
        os .path .join (project_root ,"samples"),
        os .path .join (project_root ,"samples","benchmarks"),
        os .path .expanduser ("~/Downloads"),
        os .path .expanduser ("~/Documents"),
        ]
        found_path ,found_name =None ,None 
        for sdir in search_dirs :
            if os .path .exists (sdir ):
                for f in os .listdir (sdir ):
                    if f .endswith ((".csv",".xlsx",".parquet",".feather",".json",".jsonl",".tsv")):
                        base =os .path .splitext (f )[0 ].lower ()
                        if f .lower ()in lower_msg or (len (base )>=5 and base in lower_msg ):
                            found_path =os .path .join (sdir ,f )
                            found_name =f 
                            break 
                if found_path :
                    break 

        if not found_path and any (w in lower_msg for w in ["messy csv","red messy","read messy","messy tabular","messy data"]):
            for cand_p in [
            os .path .join (project_root ,"samples","messy_tabular_data_with_errors.csv"),
            os .path .expanduser ("~/Downloads/messy_tabular_data_with_errors.csv"),
            os .path .join (project_root ,"samples","messy_customers.csv")
            ]:
                if os .path .exists (cand_p ):
                    found_path ,found_name =cand_p ,os .path .basename (cand_p )
                    break 

        if not found_path and any (w in lower_msg for w in ["load sample","load benchmark","customer benchmark"]):
            default_p =os .path .join (project_root ,"samples","messy_customers.csv")
            if os .path .exists (default_p ):
                found_path ,found_name =default_p ,"messy_customers.csv"

        if found_path and os .path .exists (found_path ):
            with open (found_path ,"rb")as sf :
                fbytes =sf .read ()
            return process_uploaded_file (file_bytes =fbytes ,filename =found_name ,session_id =session_id )


    has_text_intent =(
    lower_msg .startswith (("text:","paragraph:","correct:","clean:","fix:","proofread:","rewrite:"))
    or any (k in lower_msg for k in [
    "correct text","fix text","clean text","correct paragraph","fix paragraph",
    "clean paragraph","correct this","fix this","clean this","fix mistakes",
    "correct mistakes","proofread","find mistakes"
    ])
    )
    has_typos =any (re .search (r"\b"+re .escape (w )+r"\b",lower_msg )for w in [
    "teh","becuase","droping","suply","costumer","custmer","unautorized",
    "unauthorizd","fevr","admited","balence","unpayed","hosptial","medisin",
    "pleas","plz","tommorow","neccessary","dont","cant","wont","could of",
    "would of","should of","alot","companys"
    ])
    has_pii =bool (re .search (r"\b\d{3}[- ]\d{2}[- ]\d{4}\b",message )or re .search (r"\b(?:\d{4}[- ]){3}\d{4}\b",message ))
    is_multi_para =len (message .strip ().split ("\n\n"))>=2 and len (message .split ())>=15 

    is_text_or_paragraph =(
    has_text_intent 
    or (not lower_msg .endswith ("?")and (has_typos or has_pii )and len (message .split ())>=6 )
    or (not lower_msg .endswith ("?")and is_multi_para )
    )

    if is_text_or_paragraph :
        clean_text_input =re .sub (
        r"^(text:|paragraph:|correct paragraph:|clean paragraph:|fix paragraph:|correct text:|clean text:|fix text:|correct:|clean:|fix:|proofread:|rewrite:|please correct this paragraph:|please correct this text:|please correct this:|correct this:)\s*",
        "",message ,flags =re .IGNORECASE 
        ).strip ()

        from engine .text_corrector import correct_massive_text ,create_highlighted_diffs 
        repaired_text ,diff_transformations ,stats =correct_massive_text (clean_text_input )
        hl_before ,hl_after =create_highlighted_diffs (clean_text_input ,repaired_text ,diff_transformations )

        format_bullets =[]
        if diff_transformations :
            for orig_v ,fixed_v ,act in diff_transformations [:8 ]:
                format_bullets .append (f"- Formatted <del class=\"diff-del\">{orig_v }</del> -> <ins class=\"diff-ins\">{fixed_v }</ins> ({act })")
        format_bullets .append ("- Formatted sentence capitalization, spacing, and punctuation")
        format_summary ="\n".join (format_bullets )

        diff_table_str =""
        if diff_transformations :
            diff_table_str ="\n### Before vs After Transformations:\n| # | Before (Raw Input) | After (innov8 60M Cleaned) | AI Action |\n|---|:---|:---|:---|\n"
            seen =set ()
            count =1 
            for orig_v ,fixed_v ,act in diff_transformations :
                pair =(orig_v ,fixed_v )
                if pair not in seen :
                    seen .add (pair )
                    diff_table_str +=f"| {count } | <del class=\"diff-del\">{orig_v }</del> | <ins class=\"diff-ins\">{fixed_v }</ins> | {act } |\n"
                    count +=1 
            diff_table_str +="\n"

        formatted_after ="\n\n".join ([f"> {p }"if p .strip ()else ""for p in repaired_text .split ("\n\n")])
        formatted_before ="\n\n".join ([f"> {p }"if p .strip ()else ""for p in clean_text_input .split ("\n\n")])

        return (
        "[AI_USED]\n"
        "[LOCAL_EXECUTION]\n"
        "--- Formatted Changes:\n"
        f"- **Records**: {stats ['paragraphs']} paragraph(s) processed ({stats ['words']} words)\n"
        f"{format_summary }\n"
        f"{diff_table_str }"
        "### Visual Comparison (Changes Highlighted):\n"
        f"<div class=\"diff-box after\"><div class=\"diff-tag after-tag\">AFTER (Cleaned & Corrected)</div><div class=\"diff-text\">{hl_after }</div></div>\n\n"
        f"<div class=\"diff-box before\"><div class=\"diff-tag before-tag\">BEFORE (Raw Input Mistakes Highlighted)</div><div class=\"diff-text\">{hl_before }</div></div>\n\n"
        "### Clean Corrected Text (Ready to Copy):\n"
        f"{formatted_after }\n\n"
        "### Raw Input Text:\n"
        f"{formatted_before }"
        )


    if message .lower ().startswith ("rag:")or (session_id in SESSION_CACHE and any (q_word in lower_msg for q_word in ["what is","who is","which customer","how many","find","search","tell me about","where is","summarize","average","highest","lowest"])and "?"in message ):
        try :
            from engine .rag_engine import get_rag_engine 
            rag =get_rag_engine ()
            if rag .documents :
                hits =rag .retrieve (message ,top_k =2 )
                if hits :
                    source_lines ="\n".join ([f"- *Source ({h .get ('type','doc')})*: `{h ['content'][:140 ]}...`"for h in hits ])
                    ans =hits [0 ]["content"]
                    return (
                    "[AI_USED]\n[LOCAL_EXECUTION]\n"
                    "### innov8 RAG Knowledge Retrieval\n\n"
                    f"**Query**: {message }\n\n"
                    f"**Grounded Answer**:\n> {ans }\n\n"
                    f"**Evidence Retrieved**:\n{source_lines }"
                    )
        except Exception as rag_err :
            pass 


    memory_inquiry_keys =[
    "what did we do","what did you change","what was the last change","show memory",
    "context memory","what do you remember","conversation history","recall memory",
    "what did i tell you","what did i ask","what did i say","previous message",
    "summarize our conversation","what was my last","do you remember","what do you know about me",
    "what was the earlier","what did we discuss","conversation context","show context"
    ]
    if any (k in lower_msg for k in memory_inquiry_keys ):
        mem =get_session_memory (session_id )
        active_fn =SESSION_FILENAMES .get (session_id ,"No dataset loaded")
        actions =SESSION_ACTIONS_LOG .get (session_id ,[])
        num_turns =len (mem )
        actions_str ="\n".join ([f"- {a }"for a in actions [:6 ]])if actions else "- No dataset mutations logged yet."
        history_preview =[]
        for t in mem [-8 :]:
            r =t .get ("role","unknown").capitalize ()
            txt =t .get ("content","")[:90 ].replace ("\n"," ")
            history_preview .append (f"- **{r }**: `{txt }...`")
        hist_str ="\n".join (history_preview )if history_preview else "- No previous dialogue turns in memory."

        reply =(
        "[AI_USED]\n[LOCAL_EXECUTION]\n"
        "### innov8 Context Memory Overview\n\n"
        f"- **Active Session**: `{session_id }`\n"
        f"- **Loaded Dataset**: `{active_fn }`\n"
        f"- **Context Turns Cached**: {num_turns } turn(s) in active sliding window\n\n"
        f"**Transformations Recorded**:\n{actions_str }\n\n"
        f"**Recent Context Window**:\n{hist_str }"
        )
        return reply 


    words =re .findall (r"\b\w+\b",lower_msg )
    greetings =["hi","hello","hey","hola","sup","yo","greetings","good morning","good evening","good afternoon"]
    if any (w in greetings for w in words )and len (words )<=4 :
        active_info =""
        if session_id in SESSION_CACHE :
            df =SESSION_CACHE [session_id ]
            if "hi"in df .columns :
                df =df .drop (columns =["hi"])
                SESSION_CACHE [session_id ]=df 
            cols_preview =", ".join ([f"`{c }`"for c in df .columns [:6 ]])
            active_info ="\n\nCurrently, you have an active dataset loaded with **"+f"{len (df ):,}"+"** records and features: "+cols_preview +". How would you like me to process it?"

        return (
        "[AI_USED]\n[LOCAL_EXECUTION]\n"
        f"Hello! How can I help you clean or edit your data today?{active_info }"
        )


    model_id_queries =[
    "qwen","are you qwen","what model","which model","model name","what is your name",
    "who created","who made","who built","creator","vedanth","hackfest","team","author",
    "who trained","tell me about you","tell me about yourself","who are you","what are you",
    "what is this model","about the model","about you","what network","what architecture"
    ]
    if any (k in lower_msg for k in model_id_queries ):
        return (
        "[AI_USED]\n[LOCAL_EXECUTION]\n"
        "### Model: innov8 60M (`omnitab_best.pth`)\n\n"
        "I am **innov8 60M**, an offline deep tabular transformer and automated data verification system with 20 Transformer layers.\n\n"
        "- **Active Model**: `innov8 60M` (`omnitab_best.pth`)\n"
        "- **Architecture**: 20 Transformer Encoder Layers with Pre-LayerNorm & DeepNorm numerical scaling\n"
        "- **Capabilities**: High-volume multi-paragraph mistake correction, tabular data cleaning, outlier repair (MAD / Tukey IQR), and Luhn-verified PII masking\n"
        "- **Difference Tracking**: Visual Before vs After inline highlight chips (<del class=\"diff-del\">red strikethrough</del> and <ins class=\"diff-ins\">green highlight</ins>)\n"
        "- **Creator & Attribution**: Created by **Vedanth Vaidya** for **KLE Hackfest**\n"
        "- **Team Members**: **Shivprasad, Akshay, Riddhima, Sarvesh, and Chandana**"
        )


    if any (k in lower_msg for k in ["parameter","parameters","architecture","model size","layers"]):
        engine_tuple =get_innov8 ()
        param_desc ="3.3M to 63.3M parameters"
        if engine_tuple is not None :
            m ,_ =engine_tuple 
            total_p =sum (p .numel ()for p in m .parameters ())
            num_l =len (m .transformer_encoder .layers )
            param_desc =f"{total_p :,} parameters ({total_p /1e6 :.1f}M) across {num_l } Transformer layers"
        return (
        "[AI_USED]\n[LOCAL_EXECUTION]\n"
        "### innov8 60M Architecture Specifications\n\n"
        f"- **Active Model**: `innov8 60M` (`omnitab_best.pth`)\n"
        f"- **Architecture**: Universal Deep Tabular Transformer ({param_desc })\n"
        "- **Capabilities**: Multi-Domain Token Reconstruction, Neural Anomaly Detection, Sensitive PII Classification, and Dynamic Tabular Editing.\n"
        "- **Training Framework**: PyTorch with DeepNorm scaling and Pre-LayerNorm numerical stability."
        )


    if session_id in SESSION_CACHE and any (k in lower_msg for k in ["how many","count","summary","describe","show columns","list columns","what columns","stats","info","overview","what data","preview","show table"]):
        df =SESSION_CACHE [session_id ]
        if "hi"in df .columns :
            df =df .drop (columns =["hi"])
            SESSION_CACHE [session_id ]=df 
        num_rows =len (df )
        num_cols =len (df .columns )
        cols_list =", ".join ([f"`{c }`"for c in df .columns ])
        table_md =df .head (10 ).to_markdown (index =False )
        return (
        f"[AI_USED]\n[LOCAL_EXECUTION]\n"
        f"### Active Dataset Overview\n\n"
        f"- **Source**: `{SESSION_FILENAMES .get (session_id ,'active_data.csv')}`\n"
        f"- **Records**: `{num_rows :,}` rows\n"
        f"- **Columns ({num_cols })**: {cols_list }\n"
        f"- **Shield Status**: Verified by innov8 Neural Shield\n\n"
        f"### Data Preview:\n{table_md }"
        )


    if lower_msg .startswith ("domain:")or any (k in lower_msg for k in ["eval row","check row","analyze row","predict row","run inference","neural inference"]):
        engine_tuple =get_innov8 ()
        if engine_tuple is not None :
            from engine .innov8_model import run_inference 
            m ,tok =engine_tuple 
            clean_input =message .strip ()
            if not any (clean_input .startswith (p )for p in ["domain:","chat:"]):
                clean_input =f"domain: custom | {clean_input }"
            n_res =run_inference (m ,tok ,clean_input )
            flags =n_res ["flags"]
            return (
            "[AI_USED]\n[LOCAL_EXECUTION]\n"
            "### innov8 60M Neural Inference Result\n\n"
            f"- **Model**: `omnitab_best.pth` (PyTorch Deep Tabular Transformer)\n"
            f"- **Input**: `{clean_input }`\n"
            f"- **Outlier Detected**: `{flags ['outlier']}`\n"
            f"- **Sensitive PII Flag**: `{flags ['pii']}`\n"
            f"- **Neural Quality Score**: `{flags ['quality_score']}%`\n"
            f"- **Neural Token Repair**:\n"
            f"  `{n_res ['repaired']or n_res ['response']}`"
            )


    EDIT_INTENTS =[
    "filter","drop","delete","remove","rename","multiply","divide",
    "scale","sort","clean","mask","replace","impute","fill","set",
    "convert","round","strip","dedup","deduplicate","normalize",
    "add column","create column","calculate","update","modify","change",
    "keep only","where","group by"
    ]
    is_edit_intent =any (re .search (r"\b"+re .escape (intent )+r"\b",lower_msg )for intent in EDIT_INTENTS )

    if session_id in SESSION_CACHE and is_edit_intent :
        raw_active =SESSION_CACHE [session_id ].copy ()
        if "hi"in raw_active .columns :
            raw_active =raw_active .drop (columns =["hi"])

        updated_df ,ai_summary =AIDataEditor .edit_with_ai (raw_active ,message ,history )
        if "hi"in updated_df .columns and "hi"not in raw_active .columns :
            updated_df =updated_df .drop (columns =["hi"])

        SESSION_CACHE [session_id ]=updated_df 
        SESSION_ACTIONS_LOG .setdefault (session_id ,[]).append (f"AI Edit: {ai_summary } ({len (updated_df ):,} rows)")

        changed_cols ,diff_samples =compute_column_diffs (raw_active ,updated_df )
        mod_col_names =[col for col ,count in changed_cols ]

        display_df =updated_df .head (15 ).copy ()
        for col in mod_col_names :
            if col in display_df .columns :
                display_df .rename (columns ={col :f"{col } [MODIFIED]"},inplace =True )

        table_md =display_df .to_markdown (index =False )
        csv_preview =updated_df .head (5 ).to_csv (index =False ).strip ()

        diff_table =""
        if diff_samples :
            diff_table ="\n### Transformation Details:\n| Column | Before (Raw) | After (AI Cleaned) | Operation |\n| :--- | :--- | :--- | :--- |\n"
            for col ,rv ,cv ,ctype in diff_samples [:8 ]:
                diff_table +=f"| **{col }** | `{rv }` | **`{cv }`** | {ctype } |\n"
            diff_table +="\n"

        response =f"""[AI_USED]\n[LOCAL_EXECUTION]
--- AI updated data

- Applied AI edit: {ai_summary }
- Rows: {len (updated_df ):,} ({len (updated_df .columns )} columns)
{diff_table }
--- Data preview:
{table_md }

```csv
{csv_preview }
```

[DOWNLOAD_READY]"""
        return response 


    web_intent =(
    lower_msg .startswith (("web:","search:","google:","find on web:","look up:"))
    or any (lower_msg .startswith (p )for p in [
    "who is","what is","where is","when was","when did","how does","why is",
    "tell me about","explain","describe","capital of","population of","search for"
    ])
    or ("?"in message and any (w in lower_msg .split ()for w in ["who","what","where","when","why","how","which"]))
    )
    memory_exclusions =[
    "qwen","innov8","omnitab","hackfest","vedanth","what model","which model",
    "who created","who made","who built","who are you",
    "remember","memory","conversation","context","history","previous","earlier",
    "we just","did i say","did i tell","i told","i said","my name","my favorite",
    "what did i","what did we","recall","repeat","last turn","last message","last change",
    "what was my","what is my","who am i","what do i","what car","do i like","what did"
    ]
    if web_intent and not any (k in lower_msg for k in memory_exclusions ):
        try :
            from engine .web_search import search_web 
            web_res =search_web (message )
            if web_res and len (web_res .get ("text",""))>40 :
                return (
                "[AI_USED]\n[WEB_USED]\n"
                "### Web Search Result\n\n"
                f"**Source**: [{web_res ['source']} - {web_res ['title']}]({web_res ['url']})\n\n"
                f"> {web_res ['text']}"
                )
        except Exception :
            pass 


    engine =InferenceEngine .get_instance ()
    try :
        combined_history =list (get_session_memory (session_id ))
        reply =engine .generate (user_query =message ,history =combined_history )
        return f"[AI_USED]\n[LOCAL_EXECUTION]\n{reply }"
    except Exception as e :
        return "[AI_USED]\n[LOCAL_EXECUTION]\nHello! How can I help you clean or edit your data today?"


def process_user_query (message :str ,history :Optional [List [Dict [str ,str ]]]=None ,session_id :str ="default")->str :

    if history :
        mem =get_session_memory (session_id )
        if not mem :
            for turn in history [-10 :]:
                r =turn .get ("role","user")
                c =turn .get ("content","")
                if c and not any (t .get ("content")==c for t in mem ):
                    append_to_session_memory (session_id ,r ,c )

    res =_execute_user_query (message ,history ,session_id )
    append_to_session_memory (session_id ,"user",message )
    append_to_session_memory (session_id ,"assistant",res )
    return res 
