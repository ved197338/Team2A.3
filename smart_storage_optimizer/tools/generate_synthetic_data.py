"""
generate_synthetic_data.py -- builds the SYNTHETIC test data for SmartStore AI
==============================================================================

ALL DATA PRODUCED HERE IS SYNTHETIC (invented for testing). Every row has
data_source = SYNTHETIC. Nothing describes a real company or real systems.

Run from the project folder:
    python tools/generate_synthetic_data.py

Writes:
    sample_workload.csv        40 datasets with the extended schema
    sample_demand_history.csv  24 months of history (access counts + sizes)

The data is hand-designed (not random) so each demo scenario really happens:
frequently accessed, inactive, performance-critical, restricted, savings, blocked,
promotions, review cases. A fixed seed adds small, repeatable noise.
"""

from __future__ import annotations 

import os 
import sys 

import numpy as np 
import pandas as pd 

SEED =2026 
REFERENCE_DATE =pd .Timestamp ("2026-10-09")
HISTORY_MONTHS =24 

COLUMNS =[
"file_name","size_gb","last_accessed","access_count","workload_type","performance_requirement",
"current_tier","read_frequency","write_frequency","read_iops","write_iops","throughput_mbps",
"observed_latency_ms","max_latency_ms","growth_rate_pct","retention_days","recovery_time_hours",
"legal_hold","required_region","current_region","security_class","approved_tiers",
"migration_cost","data_source",
]


def ds (name ,size ,days ,r ,w ,wtype ,perf ,tier ,*,riops =0 ,wiops =0 ,tput =0 ,obs =None ,maxlat =None ,
growth =1.0 ,retention =0 ,rto =None ,hold ="no",req =None ,region ="us-east",sec ="INTERNAL",
approved =None ,pattern ="steady",short_history =False ,note =""):
    """One dataset definition (keyword-only extras keep the table below readable)."""
    return dict (name =name ,size =size ,days =days ,r =r ,w =w ,wtype =wtype ,perf =perf ,tier =tier ,riops =riops ,
    wiops =wiops ,tput =tput ,obs =obs ,maxlat =maxlat ,growth =growth ,retention =retention ,rto =rto ,
    hold =hold ,req =req ,region =region ,sec =sec ,approved =approved ,pattern =pattern ,
    short_history =short_history ,note =note )


DATASETS =[

ds ("txn_orders_oltp.db",420.5 ,0 ,80000 ,30000 ,"database","CRITICAL","HOT",riops =9000 ,wiops =4000 ,tput =450 ,obs =3 ,maxlat =5 ,growth =2.0 ,rto =1 ,sec ="CONFIDENTIAL"),
ds ("txn_payments_ledger.db",260.75 ,1 ,52000 ,21000 ,"database","CRITICAL","HOT",riops =7000 ,wiops =3500 ,tput =380 ,obs =4 ,maxlat =8 ,growth =1.5 ,retention =2555 ,rto =1 ,hold ="yes",sec ="RESTRICTED",req ="us-east"),
ds ("txn_inventory.db",150.0 ,2 ,12000 ,4000 ,"database","HIGH","HOT",riops =2500 ,wiops =800 ,tput =120 ,obs =4 ,maxlat =20 ,growth =1.0 ,rto =4 ,sec ="INTERNAL"),
ds ("txn_session_cache.rdb",32.4 ,0 ,120000 ,90000 ,"cache","CRITICAL","HOT",riops =20000 ,wiops =15000 ,tput =300 ,obs =1 ,maxlat =2 ,growth =0.5 ,sec ="INTERNAL"),

ds ("cust_profiles.db",185.0 ,1 ,40000 ,6000 ,"database","CRITICAL","HOT",riops =6000 ,wiops =1200 ,tput =200 ,obs =6 ,maxlat =15 ,growth =1.2 ,rto =2 ,sec ="CONFIDENTIAL",req ="eu-west",region ="eu-west"),
ds ("cust_crm_eu.db",310.0 ,5 ,6000 ,1500 ,"database","HIGH","WARM",riops =1800 ,wiops =500 ,tput =90 ,obs =8 ,maxlat =25 ,growth =0.8 ,sec ="CONFIDENTIAL",req ="eu-west",region ="eu-west"),
ds ("cust_support_tickets.db",90.0 ,120 ,8 ,2 ,"database","MEDIUM","HOT",riops =50 ,wiops =10 ,tput =5 ,obs =3 ,maxlat =200 ,growth =0.4 ,region ="ap-south",pattern ="falling"),
ds ("cust_pii_vault.db",55.0 ,130 ,5 ,1 ,"database","MEDIUM","HOT",riops =40 ,wiops =5 ,tput =3 ,obs =3 ,maxlat =500 ,growth =0.2 ,sec ="RESTRICTED",pattern ="dead",note ="RESTRICTED data must not go to COLD/ARCHIVE"),
ds ("cust_eu_gdpr_export.db",120.0 ,20 ,300 ,20 ,"database","MEDIUM","WARM",riops =200 ,wiops =20 ,tput =15 ,obs =9 ,maxlat =100 ,growth =0.3 ,req ="eu-west",region ="us-east",sec ="CONFIDENTIAL",note ="restricted to eu-west but stored in us-east"),

ds ("analytics_sales_dw_2026q3.parquet",1250.0 ,19 ,1500 ,100 ,"analytics","MEDIUM","WARM",riops =900 ,wiops =50 ,tput =180 ,obs =9 ,maxlat =100 ,growth =3.0 ),
ds ("analytics_clickstream_sep.parquet",1780.6 ,9 ,800 ,700 ,"analytics","MEDIUM","WARM",riops =700 ,wiops =400 ,tput =250 ,obs =9 ,maxlat =100 ,growth =4.0 ),
ds ("analytics_marketing_mart.parquet",1400.0 ,75 ,40 ,5 ,"analytics","MEDIUM","HOT",riops =100 ,wiops =10 ,tput =10 ,obs =2 ,maxlat =300 ,growth =1.0 ),
ds ("analytics_finance_reports_2024.xlsx",18.6 ,210 ,3 ,0 ,"reporting","LOW","COLD",riops =5 ,wiops =0 ,tput =1 ,obs =90 ,growth =0.0 ,retention =2555 ,sec ="CONFIDENTIAL",pattern ="dead"),
ds ("analytics_quarterly_snapshots.parquet",2200.0 ,150 ,12 ,0 ,"analytics","LOW","WARM",riops =30 ,wiops =0 ,tput =20 ,obs =9 ,growth =1.0 ,approved ="HOT|WARM|COLD",note ="ARCHIVE is not an approved tier"),
ds ("analytics_realtime_features.parquet",410.0 ,60 ,90 ,10 ,"analytics","HIGH","HOT",riops =1500 ,wiops =200 ,tput =100 ,obs =3 ,maxlat =None ,growth =1.5 ,note ="HIGH performance but no latency limit given"),

ds ("ai_train_vision_set.tar",1500.0 ,3 ,4000 ,50 ,"ai_training","HIGH","COLD",riops =800 ,wiops =10 ,tput =700 ,obs =140 ,maxlat =50 ,growth =2.0 ,note ="needs fast storage but sits in COLD"),
ds ("ai_train_llm_corpus_v2.tar",2600.0 ,1 ,9000 ,300 ,"ai_training","CRITICAL","WARM",riops =3000 ,wiops =100 ,tput =900 ,obs =14 ,maxlat =30 ,growth =5.0 ,short_history =True ,note ="needs 900 MB/s; WARM is assumed to give 800"),
ds ("ai_feature_store.parquet",940.0 ,12 ,2500 ,400 ,"ai_training","HIGH","WARM",riops =1800 ,wiops =300 ,tput =250 ,obs =8 ,maxlat =30 ,growth =2.5 ),
ds ("ai_model_checkpoints_v3.bin",800.0 ,200 ,0.2 ,0.1 ,"ai_training","MEDIUM","COLD",riops =10 ,wiops =5 ,tput =5 ,obs =95 ,growth =0.5 ,rto =6 ,pattern ="dead",note ="needs 6 h recovery; ARCHIVE assumed 12 h"),
ds ("ai_labeled_images_2023.tar",3100.0 ,140 ,6 ,0 ,"ai_training","LOW","WARM",riops =15 ,wiops =0 ,tput =10 ,obs =9 ,growth =0.0 ,pattern ="bursts",note ="used in quarterly bursts"),

ds ("search_product_index_v7.idx",610.2 ,0 ,25000 ,3000 ,"search","HIGH","HOT",riops =6000 ,wiops =800 ,tput =220 ,obs =5 ,maxlat =10 ,growth =1.8 ),
ds ("search_logs_index_2025.idx",240.0 ,35 ,70 ,5 ,"search","LOW","WARM",riops =150 ,wiops =10 ,tput =15 ,obs =9 ,maxlat =500 ,growth =1.0 ,pattern ="rising",note ="demand rising: demotion should be held"),
ds ("search_autocomplete_index.idx",28.0 ,0 ,90000 ,2000 ,"search","CRITICAL","HOT",riops =15000 ,wiops =500 ,tput =120 ,obs =2 ,maxlat =3 ,growth =0.3 ),

ds ("logs_app_2026_09.log.gz",95.4 ,10 ,30 ,400 ,"logs","LOW","COLD",riops =60 ,wiops =40 ,tput =15 ,obs =95 ,growth =3.0 ),
ds ("logs_app_2026_03.log.gz",88.1 ,200 ,1 ,0 ,"logs","LOW","COLD",riops =2 ,wiops =0 ,tput =1 ,obs =95 ,growth =0.0 ,pattern ="dead"),
ds ("logs_audit_trail_2025.log",210.0 ,150 ,1 ,0 ,"logs","LOW","COLD",riops =2 ,wiops =0 ,tput =1 ,obs =95 ,growth =0.0 ,retention =2555 ,hold ="yes",sec ="CONFIDENTIAL",pattern ="dead",note ="legal hold"),
ds ("logs_security_siem_2026.log",500.0 ,140 ,2 ,0 ,"logs","LOW","HOT",riops =10 ,wiops =0 ,tput =2 ,obs =2 ,growth =0.5 ,sec ="RESTRICTED",pattern ="dead",note ="RESTRICTED data"),
ds ("logs_web_access_2026_05.log",64.25 ,160 ,1 ,0 ,"logs","LOW","COLD",riops =2 ,wiops =0 ,tput =1 ,obs =95 ,growth =0.0 ,region ="ap-south",pattern ="dead",note ="ARCHIVE is not offered in ap-south"),

ds ("backup_db_2026_09_01.bak",830.0 ,38 ,1 ,0 ,"backup","LOW","WARM",riops =5 ,wiops =0 ,tput =3 ,obs =9 ,growth =1.0 ,rto =72 ,pattern ="dead"),
ds ("backup_db_2026_06_01.bak",795.5 ,130 ,1 ,0 ,"backup","LOW","COLD",riops =2 ,wiops =0 ,tput =1 ,obs =95 ,growth =0.0 ,rto =48 ,pattern ="dead"),
ds ("backup_vm_snapshots_q1.tar",2400.0 ,180 ,1 ,0 ,"backup","LOW","COLD",riops =2 ,wiops =0 ,tput =1 ,obs =95 ,growth =0.0 ,rto =72 ,pattern ="dead"),
ds ("backup_erp_nightly.tar",1900.0 ,45 ,1 ,0 ,"backup","LOW","HOT",riops =5 ,wiops =0 ,tput =3 ,obs =2 ,growth =0.8 ,rto =24 ,pattern ="dead"),
ds ("backup_dr_critical.tar",1200.0 ,100 ,1 ,0 ,"backup","LOW","COLD",riops =2 ,wiops =0 ,tput =1 ,obs =95 ,growth =0.5 ,rto =2 ,retention =1825 ,pattern ="dead",note ="disaster-recovery copy; 2 h recovery"),

ds ("archive_compliance_2021.tar",1850.0 ,600 ,0 ,0 ,"compliance","LOW","ARCHIVE",growth =0.0 ,retention =3650 ,hold ="yes",sec ="CONFIDENTIAL",pattern ="dead"),
ds ("archive_hr_records_2019.zip",45.2 ,800 ,0 ,0 ,"compliance","LOW","ARCHIVE",growth =0.0 ,retention =3650 ,sec ="CONFIDENTIAL",pattern ="dead"),
ds ("archive_medical_scans_2018.dcm",900.0 ,700 ,0 ,0 ,"media","LOW","ARCHIVE",growth =0.0 ,retention =3650 ,sec ="RESTRICTED",pattern ="dead",note ="RESTRICTED data currently in ARCHIVE"),
ds ("archive_email_2016.pst",730.4 ,900 ,0 ,0 ,"archive","LOW","ARCHIVE",growth =0.0 ,retention =1825 ,pattern ="dead"),
ds ("archive_surveillance_2020.mp4",6800.0 ,750 ,0 ,0 ,"media","LOW","ARCHIVE",growth =0.0 ,retention =1095 ,pattern ="dead"),
ds ("archive_customer_invoices_2020.pdf",22.75 ,400 ,0 ,0 ,"compliance","LOW","COLD",growth =0.0 ,retention =2555 ,sec ="CONFIDENTIAL",pattern ="dead"),
ds ("archive_old_contracts_2015.zip",150.0 ,4 ,90 ,0 ,"archive","MEDIUM","ARCHIVE",riops =40 ,wiops =0 ,tput =10 ,obs =3600000 ,maxlat =None ,growth =0.0 ,retention =3650 ,pattern ="revived",note ="old archive that became active again"),

ds ("misc_unclassified_export.dat",75.0 ,30 ,10 ,2 ,"analytics","LOW","",growth =0.0 ,short_history =True ,note ="current tier missing"),
]


def build_workload (rng :np .random .Generator )->pd .DataFrame :
    rows =[]
    for d in DATASETS :
        jitter =rng .uniform (0.9 ,1.1 )
        access =int (round ((d ["r"]+d ["w"])*30 *jitter ))if (d ["r"]+d ["w"])>=1 else int (rng .integers (0 ,2 ))
        critical =d ["perf"]in ("HIGH","CRITICAL")
        rows .append ({
        "file_name":d ["name"],
        "size_gb":d ["size"],
        "last_accessed":(REFERENCE_DATE -pd .Timedelta (days =d ["days"])).date ().isoformat (),
        "access_count":access ,
        "workload_type":d ["wtype"],
        "performance_requirement":d ["perf"],
        "current_tier":d ["tier"],
        "read_frequency":d ["r"],
        "write_frequency":d ["w"],
        "read_iops":d ["riops"],
        "write_iops":d ["wiops"],
        "throughput_mbps":d ["tput"],
        "observed_latency_ms":d ["obs"]if d ["obs"]is not None else "",
        "max_latency_ms":d ["maxlat"]if d ["maxlat"]is not None else "",
        "growth_rate_pct":d ["growth"],
        "retention_days":d ["retention"],
        "recovery_time_hours":d ["rto"]if d ["rto"]is not None else "",
        "legal_hold":d ["hold"],
        "required_region":d ["req"]or "",
        "current_region":d ["region"],
        "security_class":d ["sec"],
        "approved_tiers":d ["approved"]or "",
        "migration_cost":round (10 +d ["size"]*0.01 +(100 if critical else 0 ),2 ),
        "data_source":"SYNTHETIC",
        })
    return pd .DataFrame (rows ,columns =COLUMNS )


def build_history (workload :pd .DataFrame ,rng :np .random .Generator )->pd .DataFrame :
    months =pd .date_range (end =REFERENCE_DATE .to_period ("M").to_timestamp (),periods =HISTORY_MONTHS ,freq ="MS")
    out =[]
    for d ,(_ ,row )in zip (DATASETS ,workload .iterrows ()):
        use =months 
        n_recent =4 if d ["short_history"]else HISTORY_MONTHS 
        current =max (float (row ["access_count"]),0.0 )
        g =d ["growth"]/100.0 
        for k ,month in enumerate (use ):
            back =len (use )-1 -k 
            noise =rng .uniform (0.85 ,1.15 )
            pattern =d ["pattern"]
            if pattern =="steady":
                acc =current *noise 
            elif pattern =="rising":
                acc =current *(0.3 if back >=6 else 0.3 +0.7 *(6 -back )/6 )*noise 
            elif pattern =="falling":
                acc =current +400 *max (0.0 ,1 -(1 -back /max (len (use )-1 ,1 ))*1.3 )*noise if back >3 else current *noise 
            elif pattern =="bursts":
                acc =450 *noise if (len (use )-1 -back )%6 ==2 and back >2 else current *0.3 *noise 
            elif pattern =="revived":
                acc =current *noise if back <3 else rng .uniform (0 ,1.5 )
            else :
                acc =current *noise if back <3 else current *noise *(1 +0.5 *rng .random ())
            size =d ["size"]/((1 +g )**back )
            access_value =int (round (max (acc ,0 )))if back <n_recent else ""
            out .append ({"date":month .date ().isoformat (),"file_name":d ["name"],
            "access_count":access_value ,
            "size_gb":round (size *rng .uniform (0.995 ,1.005 ),2 )})
    return pd .DataFrame (out ,columns =["date","file_name","access_count","size_gb"])


def main (out_dir :str =".")->None :
    rng =np .random .default_rng (SEED )
    workload =build_workload (rng )
    history =build_history (workload ,rng )
    workload .to_csv (os .path .join (out_dir ,"sample_workload.csv"),index =False )
    history .to_csv (os .path .join (out_dir ,"sample_demand_history.csv"),index =False )
    print (f"Wrote sample_workload.csv ({len (workload )} datasets) and sample_demand_history.csv "
    f"({len (history )} rows). ALL DATA IS SYNTHETIC.")


if __name__ =="__main__":
    main (sys .argv [1 ]if len (sys .argv )>1 else ".")
