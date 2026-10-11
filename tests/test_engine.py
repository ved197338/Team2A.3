import os 
import pandas as pd 
import numpy as np 

from engine .loader import load_dataset_from_bytes ,detect_text_delimiter 
from engine .pipeline import run_step_by_step_analysis ,execute_cleaning_and_validate 
from engine .security import validate_file_content_and_size ,sanitize_cell_for_export 

SAMPLE_DIR ="/home/april/Documents/project1/samples"

def test_file_formats_loading ():
    formats =[
    ("messy_customers.csv","csv"),
    ("messy_products.tsv","tsv"),
    ("messy_orders.json","json"),
    ("messy_logs.jsonl","jsonl"),
    ("messy_metrics.parquet","parquet"),
    ("messy_inventory.feather","feather"),
    ("messy_accounts.xlsx","xlsx"),
    ]

    for filename ,fmt in formats :
        filepath =os .path .join (SAMPLE_DIR ,filename )
        assert os .path .exists (filepath ),f"Sample {filename } not found."
        with open (filepath ,"rb")as f :
            data =f .read ()

        is_valid ,err ,ext =validate_file_content_and_size (data ,filename )
        assert is_valid ,f"Validation failed for {filename }: {err }"

        df ,meta =load_dataset_from_bytes (data ,filename )
        assert len (df )>0 ,f"Loaded empty dataframe for {filename }"
        assert len (df .columns )>0 
        print (f"Format test passed: {filename } ({len (df )} rows, {len (df .columns )} cols)")

def test_security_protections ():
    fake_exe =b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00'
    valid ,err ,_ =validate_file_content_and_size (fake_exe ,"data.csv")
    assert not valid 
    assert "executable"in err .lower ()

    fake_elf =b'\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    valid ,err ,_ =validate_file_content_and_size (fake_elf ,"data.csv")
    assert not valid 
    assert "executable"in err .lower ()

    assert sanitize_cell_for_export ("=cmd|'/C calc'!A0")=="'=cmd|'/C calc'!A0"
    assert sanitize_cell_for_export ("+1+2")=="'+1+2"
    assert sanitize_cell_for_export ("-2+3")=="'-2+3"
    assert sanitize_cell_for_export ("@SUM(1,2)")=="'@SUM(1,2)"
    assert sanitize_cell_for_export ("Normal Text")=="Normal Text"

    valid ,err ,_ =validate_file_content_and_size (b"","empty.csv")
    assert not valid 
    assert "empty"in err .lower ()

def test_step_by_step_pipeline ():
    with open (os .path .join (SAMPLE_DIR ,"messy_customers.csv"),"rb")as f :
        data =f .read ()

    events =list (run_step_by_step_analysis (data ,"messy_customers.csv"))
    assert len (events )>=9 

    step_names =[e ["name"]for e in events ]
    assert "Reading file"in step_names 
    assert "Checking structure"in step_names 
    assert "Checking values"in step_names 
    assert "Finding duplicates"in step_names 
    assert "Checking missing values"in step_names 
    assert "Checking invalid values"in step_names 
    assert "Preparing fixes"in step_names 
    assert "Complete"in step_names 

    final_event =events [-1 ]
    assert final_event ["name"]=="Complete"
    analysis_data =final_event ["data"]
    assert analysis_data ["row_count"]==10 
    assert analysis_data ["counts"]["duplicates"]>=1 
    assert analysis_data ["quality_score"]["total"]>0 

    raw_df =final_event ["raw_df"]
    problems =final_event ["problems_list"]
    clean_res =execute_cleaning_and_validate (raw_df ,problems ,approved_changes ={})

    assert len (clean_res ["cleaned_df"])<len (raw_df )
    assert len (clean_res ["audit_log"])>0 
    assert clean_res ["metrics"]["quality_score"]["total"]>=analysis_data ["quality_score"]["total"]

    print ("Step-by-step pipeline end-to-end test passed successfully!")

if __name__ =="__main__":
    test_file_formats_loading ()
    test_security_protections ()
    test_step_by_step_pipeline ()
    print ("ALL TESTS PASSED.")
