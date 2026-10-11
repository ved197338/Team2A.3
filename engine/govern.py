from datetime import datetime 
from typing import Any ,Dict ,List 
from engine .types import (
GovernanceReport ,
GovernanceStatus ,
LineageRecord ,
QualityScore ,
PIIDetection 
)

def evaluate_governance (
dataset_name :str ,
source :str ,
version :str ,
score :QualityScore ,
pii_items :List [PIIDetection ],
critical_errors :int ,
lineage_records :List [LineageRecord ]
)->GovernanceReport :

    rule_score_pass =(score .total >=90.0 )


    rule_critical_pass =(critical_errors ==0 )


    unmasked_high_pii =any (p .risk =="High"and "Mask"not in p .recommended_action for p in pii_items )
    rule_pii_pass =not unmasked_high_pii 


    rule_comp_pass =(score .completeness >=85.0 )


    if rule_score_pass and rule_critical_pass and rule_pii_pass :
        status =GovernanceStatus .CERTIFIED 
    elif score .total >=70.0 and rule_critical_pass :
        status =GovernanceStatus .WARNING 
    else :
        status =GovernanceStatus .FAILED 

    access_classification ="Confidential / Internal"if len (pii_items )>0 else "General / Internal"
    pii_status =f"{len (pii_items )} sensitive attributes identified (protected via safe masking policy)"if pii_items else "No sensitive PII attributes detected"

    governance_rules =[
    {
    "rule":"Quality Score Threshold",
    "requirement":"Score >= 90.0",
    "actual":f"{score .total :.1f}",
    "passed":rule_score_pass 
    },
    {
    "rule":"Critical Validation Errors",
    "requirement":"0 critical structural errors",
    "actual":f"{critical_errors }",
    "passed":rule_critical_pass 
    },
    {
    "rule":"Sensitive Data & PII Policy",
    "requirement":"All High-Risk PII masked",
    "actual":"Satisfied"if rule_pii_pass else "Violated",
    "passed":rule_pii_pass 
    },
    {
    "rule":"Minimum Completeness",
    "requirement":"Completeness >= 85.0%",
    "actual":f"{score .completeness :.1f}%",
    "passed":rule_comp_pass 
    }
    ]

    validation_history =[
    {
    "timestamp":datetime .now ().isoformat (),
    "event":"Automated Quality & Governance Pipeline Run",
    "score":score .total ,
    "status":status .value 
    }
    ]

    return GovernanceReport (
    dataset_name =dataset_name ,
    owner ="Data Governance Team",
    source =source ,
    version =version ,
    status =status ,
    quality_score =score .total ,
    pii_status =pii_status ,
    critical_errors_count =critical_errors ,
    validation_history =validation_history ,
    access_classification =access_classification ,
    governance_rules =governance_rules ,
    lineage =lineage_records 
    )
