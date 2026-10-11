import time 
import tracemalloc 
from datetime import datetime 
from typing import Any ,Dict ,Generator ,List ,Optional ,Tuple 
import pandas as pd 
import numpy as np 

from engine .types import (
ChangeClassification ,
Problem ,
QualityDimension ,
QualityScore ,
ColumnProfile ,
AuditRecord ,
LineageRecord ,
GovernanceStatus ,
GovernanceReport 
)
from engine .loader import load_dataset_from_bytes 
from engine .detect import detect_unified 
from engine .cleaner import clean_dataset 
from engine .scorer import compute_quality_score 
from engine .govern import evaluate_governance 
from engine .stats import compute_numerical_stats 
from engine .type_detector import profile_column_type 
from engine .missing import find_missing_mask 

def sanitize_for_json (obj :Any )->Any :
    if isinstance (obj ,(float ,np .floating )):
        val =float (obj )
        if np .isnan (val )or np .isinf (val ):
            return None 
        return round (val ,2 )
    elif isinstance (obj ,(int ,np .integer )):
        return int (obj )
    elif isinstance (obj ,(bool ,np .bool_ )):
        return bool (obj )
    elif isinstance (obj ,dict ):
        return {str (k ):sanitize_for_json (v )for k ,v in obj .items ()}
    elif isinstance (obj ,(list ,tuple ,set )):
        return [sanitize_for_json (v )for v in obj ]
    elif pd .isna (obj ):
        return None 
    return obj 

def profile_dataset_columns (df :pd .DataFrame )->Tuple [Dict [str ,ColumnProfile ],Dict [str ,str ]]:
    col_profiles :Dict [str ,ColumnProfile ]={}
    col_types :Dict [str ,str ]={}

    for col in df .columns :
        col_str =str (col )
        s =df [col ]
        total_cnt =len (s )
        null_cnt =int (find_missing_mask (s ).sum ())
        non_null_s =s .dropna ()
        uniq_cnt =int (non_null_s .nunique ())

        p_info =profile_column_type (s ,col_str )
        detected_type =p_info ["type"]
        col_types [col_str ]=detected_type 

        stats_dict :Dict [str ,Any ]={}
        if detected_type in ("integer","decimal"):
            clean_num =pd .to_numeric (s ,errors ="coerce").to_numpy (dtype =float )
            stats_dict =compute_numerical_stats (clean_num )
        elif detected_type =="categorical":
            stats_dict ={
            "top_categories":non_null_s .astype (str ).value_counts ().head (5 ).to_dict ()
            }

        col_profiles [col_str ]=ColumnProfile (
        name =col_str ,
        detected_type =detected_type ,
        total_count =total_cnt ,
        null_count =null_cnt ,
        unique_count =uniq_cnt ,
        stats =stats_dict 
        )

    return col_profiles ,col_types 

def run_unified_pipeline (
data :bytes ,
filename :str ,
sheet_name :Optional [str ]=None ,
approved_changes :Optional [Dict [str ,bool ]]=None ,
reference_profile :Optional [Dict [str ,Any ]]=None 
)->Generator [Dict [str ,Any ],None ,None ]:
    start_total_time =time .perf_counter ()
    tracemalloc .start ()
    lineage_records :List [LineageRecord ]=[]

    def log_lineage (stage :str ,src_ver :str ,out_ver :str ,desc :str ,cnt :int =0 ,details :Dict =None ):
        lineage_records .append (LineageRecord (
        stage =stage ,
        timestamp =datetime .now ().isoformat (),
        source_version =src_ver ,
        output_version =out_ver ,
        description =desc ,
        changes_count =cnt ,
        details =details or {}
        ))




    yield {"stage":"INGEST","status":"running","name":"Ingesting file"}
    t0 =time .perf_counter ()
    df ,meta =load_dataset_from_bytes (data ,filename ,sheet_name )
    ingest_ms =round ((time .perf_counter ()-t0 )*1000 ,1 )

    log_lineage (
    stage ="INGEST",
    src_ver ="Raw File Upload",
    out_ver ="v1.0-raw",
    desc =f"Safely ingested {filename } ({len (df ):,} rows, {len (df .columns )} columns)",
    details =meta 
    )

    raw_preview_rows =[sanitize_for_json (r )for r in df .head (20 ).to_dict (orient ="records")]
    yield {
    "stage":"INGEST",
    "status":"done",
    "name":"Ingest complete",
    "detail":f"{len (df ):,} rows, {len (df .columns )} columns in {ingest_ms } ms",
    "rows":len (df ),
    "columns":len (df .columns ),
    "file_meta":meta ,
    "preview":{
    "stage_name":"Stage 1 — Original Data",
    "status_text":"Original data",
    "rows":raw_preview_rows ,
    "columns":[str (c )for c in df .columns ],
    "highlight_cells":{},
    "modified_cells":{}
    }
    }




    yield {"stage":"PROFILE","status":"running","name":"Profiling dataset structure"}
    t0 =time .perf_counter ()
    col_profiles ,col_types =profile_dataset_columns (df )
    profile_ms =round ((time .perf_counter ()-t0 )*1000 ,1 )

    log_lineage (
    stage ="PROFILE",
    src_ver ="v1.0-raw",
    out_ver ="v1.1-profiled",
    desc =f"Calculated statistics and inferred data types for {len (col_profiles )} columns",
    details ={"types":col_types }
    )

    yield {
    "stage":"PROFILE",
    "status":"done",
    "name":"Profile complete",
    "detail":f"Inferred types and distributions for {len (col_profiles )} columns in {profile_ms } ms",
    "column_profiles":{k :v .to_dict ()for k ,v in col_profiles .items ()}
    }




    yield {"stage":"DETECT","status":"running","name":"Detecting anomalies, PII, and quality issues"}
    t0 =time .perf_counter ()
    problems ,pii_items ,anomalies ,drift_items ,cell_highlights =detect_unified (df ,col_types ,reference_profile )
    detect_ms =round ((time .perf_counter ()-t0 )*1000 ,1 )

    log_lineage (
    stage ="DETECT",
    src_ver ="v1.1-profiled",
    out_ver ="v1.2-detected",
    desc =f"Detected {len (problems )} quality issues, {len (pii_items )} sensitive PII attributes, and {len (anomalies )} statistical anomalies",
    cnt =len (problems ),
    details ={"problems_count":len (problems ),"pii_count":len (pii_items ),"anomalies_count":len (anomalies )}
    )


    initial_score =compute_quality_score (df ,problems )

    yield {
    "stage":"DETECT",
    "status":"done",
    "name":"Detection complete",
    "detail":f"{len (problems )} issues found ({len (pii_items )} PII, {len (anomalies )} anomalies) in {detect_ms } ms",
    "problems_count":len (problems ),
    "pii_count":len (pii_items ),
    "anomalies_count":len (anomalies ),
    "problems":[p .to_dict ()for p in problems ],
    "pii_items":[p .to_dict ()for p in pii_items ],
    "anomalies":[a .to_dict ()for a in anomalies ],
    "drift_items":[d .to_dict ()for d in drift_items ],
    "initial_score":initial_score .to_dict (),
    "preview":{
    "stage_name":"Stage 2 — Profiled & Detected Issues",
    "status_text":f"{len (problems )} issues highlighted on preview",
    "rows":raw_preview_rows ,
    "columns":[str (c )for c in df .columns ],
    "highlight_cells":cell_highlights ,
    "modified_cells":{}
    }
    }




    yield {"stage":"RESOLVE","status":"running","name":"Applying safe corrections"}
    t0 =time .perf_counter ()
    resolved_df ,audit_log ,modified_cells =clean_dataset (df ,problems ,approved_changes )
    resolve_ms =round ((time .perf_counter ()-t0 )*1000 ,1 )

    safe_count =sum (1 for p in problems if p .action_type ==ChangeClassification .SAFE )
    review_count =sum (1 for p in problems if p .action_type ==ChangeClassification .REVIEW )
    unresolved_count =sum (1 for p in problems if p .action_type ==ChangeClassification .UNRESOLVED )

    log_lineage (
    stage ="RESOLVE",
    src_ver ="v1.2-detected",
    out_ver ="v2.0-resolved",
    desc =f"Applied {len (audit_log )} verified modifications across {len (modified_cells )} cells",
    cnt =len (audit_log ),
    details ={"safe_count":safe_count ,"review_count":review_count ,"unresolved_count":unresolved_count }
    )

    resolved_preview_rows =[sanitize_for_json (r )for r in resolved_df .head (20 ).to_dict (orient ="records")]
    yield {
    "stage":"RESOLVE",
    "status":"done",
    "name":"Resolution complete",
    "detail":f"{len (audit_log )} changes applied, {review_count } require review in {resolve_ms } ms",
    "audit_count":len (audit_log ),
    "safe_count":safe_count ,
    "review_count":review_count ,
    "unresolved_count":unresolved_count ,
    "audit_log":[a .to_dict ()for a in audit_log ],
    "preview":{
    "stage_name":"Stage 3 — Resolved & Transformed",
    "status_text":f"{len (audit_log )} changes applied ({len (modified_cells )} cells modified)",
    "rows":resolved_preview_rows ,
    "columns":[str (c )for c in resolved_df .columns ],
    "highlight_cells":{},
    "modified_cells":modified_cells 
    }
    }




    yield {"stage":"VALIDATE","status":"running","name":"Validating resolved dataset"}
    t0 =time .perf_counter ()
    val_profiles ,val_types =profile_dataset_columns (resolved_df )
    val_problems ,val_pii ,val_anom ,val_drift ,val_highlights =detect_unified (resolved_df ,val_types ,reference_profile )
    validate_ms =round ((time .perf_counter ()-t0 )*1000 ,1 )

    total_cells =max (1 ,len (resolved_df )*len (resolved_df .columns ))
    invalid_cells =sum (p .affected_count for p in val_problems if p .dimension ==QualityDimension .VALIDITY )
    validity_pct =round (max (0.0 ,1.0 -(invalid_cells /total_cells ))*100.0 ,1 )

    critical_errors =sum (1 for p in val_problems if p .action_type ==ChangeClassification .UNRESOLVED and p .dimension in (QualityDimension .VALIDITY ,QualityDimension .COMPLETENESS ))

    log_lineage (
    stage ="VALIDATE",
    src_ver ="v2.0-resolved",
    out_ver ="v2.1-validated",
    desc =f"Re-validated dataset with {validity_pct }% validity rate and {critical_errors } critical flags",
    cnt =len (val_problems )
    )

    yield {
    "stage":"VALIDATE",
    "status":"done",
    "name":"Validation complete",
    "detail":f"{validity_pct }% valid ({len (val_problems )} remaining issues) in {validate_ms } ms",
    "validity_percentage":validity_pct ,
    "remaining_problems_count":len (val_problems ),
    "critical_errors_count":critical_errors 
    }




    yield {"stage":"SCORE","status":"running","name":"Calculating multi-dimensional quality score"}
    t0 =time .perf_counter ()
    final_score =compute_quality_score (resolved_df ,val_problems )
    score_ms =round ((time .perf_counter ()-t0 )*1000 ,1 )

    log_lineage (
    stage ="SCORE",
    src_ver ="v2.1-validated",
    out_ver ="v2.2-scored",
    desc =f"Final score: {final_score .total :.1f}/100 (up from {initial_score .total :.1f})",
    details =final_score .to_dict ()
    )

    yield {
    "stage":"SCORE",
    "status":"done",
    "name":"Score complete",
    "detail":f"{final_score .total :.1f} / 100 in {score_ms } ms",
    "score":final_score .to_dict (),
    "initial_score":initial_score .to_dict (),
    "delta":round (final_score .total -initial_score .total ,1 )
    }




    yield {"stage":"GOVERN","status":"running","name":"Evaluating governance policies and lineage"}
    t0 =time .perf_counter ()
    govern_report =evaluate_governance (
    dataset_name =filename ,
    source =f"Direct Upload ({filename })",
    version ="v2.2-certified",
    score =final_score ,
    pii_items =val_pii ,
    critical_errors =critical_errors ,
    lineage_records =lineage_records 
    )
    govern_ms =round ((time .perf_counter ()-t0 )*1000 ,1 )

    log_lineage (
    stage ="GOVERN",
    src_ver ="v2.2-scored",
    out_ver ="v2.3-governed",
    desc =f"Dataset certified as {govern_report .status .value }",
    details ={"status":govern_report .status .value }
    )

    yield {
    "stage":"GOVERN",
    "status":"done",
    "name":"Governance complete",
    "detail":f"Status: {govern_report .status .value } in {govern_ms } ms",
    "status_badge":govern_report .status .value ,
    "governance_report":govern_report .to_dict ()
    }




    current_mem ,peak_mem =tracemalloc .get_traced_memory ()
    tracemalloc .stop ()
    total_elapsed_ms =round ((time .perf_counter ()-start_total_time )*1000 ,1 )

    yield {
    "stage":"EXPORT",
    "status":"ready",
    "name":"Ready for export",
    "detail":f"Entire pipeline finished in {total_elapsed_ms } ms (Memory peak: {round (peak_mem /1024 ,1 )} KB)",
    "preview":{
    "stage_name":"Stage 4 — Final Validated & Governed Dataset",
    "status_text":f"Validated dataset: {len (resolved_df ):,} rows, {len (resolved_df .columns )} columns • Score {final_score .total :.1f}/100 ({govern_report .status .value })",
    "rows":[sanitize_for_json (r )for r in resolved_df .head (20 ).to_dict (orient ="records")],
    "columns":[str (c )for c in resolved_df .columns ],
    "highlight_cells":{},
    "modified_cells":modified_cells 
    },
    "resolved_df":resolved_df ,
    "audit_log":audit_log ,
    "governance_report":govern_report ,
    "final_score":final_score ,
    "initial_score":initial_score ,
    "problems":problems ,
    "validation_problems":val_problems ,
    "pii_items":val_pii ,
    "anomalies":val_anom ,
    "drift_items":val_drift ,
    "lineage":lineage_records ,
    "total_elapsed_ms":total_elapsed_ms ,
    "peak_mem_kb":round (peak_mem /1024 ,1 )
    }
