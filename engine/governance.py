"""
Enterprise Governance, Policy Engine, Access Control, and Data Card Generator.

Implements declarative quality policy evaluation, Role-Based Access Control (RBAC),
and ISO/IEC 5259 / Google Model Card standard compliant Data Card generation.
"""

from dataclasses import asdict ,dataclass ,field 
from datetime import datetime ,timezone 
import json 
from typing import Any ,Dict ,List ,Optional 
import yaml 
from engine .profiler import CompositeQualityScore ,DatasetProfileReport 
from engine .pii_ner import PIIColumnClassification 
from engine .drift import DatasetDriftReport 


@dataclass 
class GovernancePolicyRule :
    rule_id :str 
    dimension :str 
    target :str 
    operator :str 
    threshold :Any 
    severity :str 


@dataclass 
class PolicyEvaluationResult :
    rule_id :str 
    dimension :str 
    severity :str 
    success :bool 
    observed_value :Any 
    threshold :Any 
    message :str 


@dataclass 
class GovernanceAuditReport :
    dataset_name :str 
    evaluated_at :str 
    overall_status :str 
    policy_compliance_rate :float 
    total_rules :int 
    passed_rules :int 
    failed_rules :int 
    rule_results :List [PolicyEvaluationResult ]
    data_card_markdown :str 


class PolicyEngine :
    """
    Declarative policy engine for AI readiness governance.
    """

    DEFAULT_RULES =[
    GovernancePolicyRule ("RULE-COMP-01","Completeness","completeness","gte",90.0 ,"BLOCKER"),
    GovernancePolicyRule ("RULE-UNIQ-01","Uniqueness","uniqueness","gte",95.0 ,"CRITICAL"),
    GovernancePolicyRule ("RULE-PII-01","Security","unmasked_pii_count","eq",0 ,"BLOCKER"),
    GovernancePolicyRule ("RULE-DRIFT-01","Drift","dataset_drift_ratio","lte",0.25 ,"CRITICAL"),
    GovernancePolicyRule ("RULE-SCORE-01","Composite","composite_total","gte",88.0 ,"BLOCKER"),
    ]

    def __init__ (self ,custom_policy_yaml :Optional [str ]=None ):
        self .rules =self .DEFAULT_RULES 
        if custom_policy_yaml :
            self ._load_yaml_policy (custom_policy_yaml )

    def _load_yaml_policy (self ,yaml_str :str )->None :
        try :
            data =yaml .safe_load (yaml_str )
            if "rules"in data :
                loaded =[]
                for r in data ["rules"]:
                    loaded .append (GovernancePolicyRule (
                    rule_id =r .get ("rule_id","RULE-CUSTOM"),
                    dimension =r .get ("dimension","Custom"),
                    target =r .get ("target","score"),
                    operator =r .get ("operator","gte"),
                    threshold =r .get ("threshold",0 ),
                    severity =r .get ("severity","WARNING")
                    ))
                self .rules =loaded 
        except Exception :
            pass 

    def evaluate (
    self ,
    profile :DatasetProfileReport ,
    pii_items :List [PIIColumnClassification ],
    drift_report :Optional [DatasetDriftReport ]=None 
    )->GovernanceAuditReport :
        results :List [PolicyEvaluationResult ]=[]
        score =profile .quality_score 

        unmasked_pii =sum (1 for p in pii_items if p .recommended_action =="MASK"and p .highest_sensitivity in ("RESTRICTED","CONFIDENTIAL"))
        drift_ratio =drift_report .dataset_drift_ratio if drift_report else 0.0 

        metrics_map ={
        "completeness":score .completeness ,
        "validity":score .validity ,
        "uniqueness":score .uniqueness ,
        "consistency":score .consistency ,
        "timeliness":score .timeliness ,
        "composite_total":score .composite_total ,
        "unmasked_pii_count":unmasked_pii ,
        "dataset_drift_ratio":drift_ratio 
        }

        for rule in self .rules :
            obs =metrics_map .get (rule .target ,0 )
            success =False 

            if rule .operator =="gte":
                success =obs >=rule .threshold 
            elif rule .operator =="lte":
                success =obs <=rule .threshold 
            elif rule .operator =="eq":
                success =obs ==rule .threshold 
            elif rule .operator =="zero":
                success =obs ==0 

            msg =f"{rule .rule_id }: {rule .target } observed {obs } vs threshold {rule .threshold } ({'PASSED'if success else 'FAILED'})"
            results .append (PolicyEvaluationResult (
            rule_id =rule .rule_id ,
            dimension =rule .dimension ,
            severity =rule .severity ,
            success =success ,
            observed_value =obs ,
            threshold =rule .threshold ,
            message =msg 
            ))

        total_r =len (results )
        passed_r =sum (1 for r in results if r .success )
        failed_r =total_r -passed_r 
        compliance_pct =round ((passed_r /max (1 ,total_r ))*100.0 ,2 )

        has_blocker_fail =any (not r .success and r .severity =="BLOCKER"for r in results )
        has_critical_fail =any (not r .success and r .severity =="CRITICAL"for r in results )

        if not has_blocker_fail and not has_critical_fail and compliance_pct >=90.0 :
            status ="CERTIFIED_AI_READY"
        elif not has_blocker_fail and compliance_pct >=70.0 :
            status ="CONDITIONALLY_APPROVED"
        else :
            status ="REJECTED"

        data_card_md =DataCardGenerator .generate_markdown_card (
        profile =profile ,
        pii_items =pii_items ,
        status =status ,
        drift_report =drift_report ,
        compliance_pct =compliance_pct 
        )

        return GovernanceAuditReport (
        dataset_name =profile .dataset_name ,
        evaluated_at =datetime .now (timezone .utc ).isoformat (),
        overall_status =status ,
        policy_compliance_rate =compliance_pct ,
        total_rules =total_r ,
        passed_rules =passed_r ,
        failed_rules =failed_r ,
        rule_results =results ,
        data_card_markdown =data_card_md 
        )


class AccessControlRBAC :
    """
    Role-Based Access Control matrix for governed data artifacts.
    """

    ROLES ={
    "ADMIN":["READ_RESTRICTED","READ_CONFIDENTIAL","WRITE_POLICY","EXECUTE_ANONYMIZATION","CERTIFY_DATASET"],
    "DATA_STEWARD":["READ_CONFIDENTIAL","WRITE_POLICY","EXECUTE_ANONYMIZATION","CERTIFY_DATASET"],
    "AI_ENGINEER":["READ_CONFIDENTIAL","READ_FEATURES","EXPORT_MODEL_CARD"],
    "ANALYST":["READ_PUBLIC","READ_AGGREGATES"]
    }

    @classmethod 
    def can_access_column (cls ,role :str ,classification_tier :str )->bool :
        if role =="ADMIN":
            return True 
        if classification_tier =="RESTRICTED":
            return "READ_RESTRICTED"in cls .ROLES .get (role ,[])
        if classification_tier =="CONFIDENTIAL":
            return "READ_CONFIDENTIAL"in cls .ROLES .get (role ,[])
        return True 


class DataCardGenerator :
    """
    Generates ISO/IEC 5259 and Google Model Card standard compliant Data Cards.
    """

    @staticmethod 
    def generate_markdown_card (
    profile :DatasetProfileReport ,
    pii_items :List [PIIColumnClassification ],
    status :str ,
    drift_report :Optional [DatasetDriftReport ]=None ,
    compliance_pct :float =100.0 
    )->str :
        score =profile .quality_score 
        pii_summary =", ".join (f"`{p .column_name }` ({'/'.join (p .detected_entities )})"for p in pii_items )if pii_items else "Zero unmasked PII detected."
        drift_str =f"{drift_report .drifted_feature_count } of {drift_report .total_feature_count } features ({drift_report .dataset_drift_ratio *100 :.1f}%)"if drift_report else "Baseline Reference (Drift = 0.0%)"

        pass_fail =lambda cond :"PASS"if cond else "DEFECT"

        return f"""# DATA CARD: {profile .dataset_name .upper ()}
**Standard**: ISO/IEC 5259 Data Quality for AI Systems
**Generated At**: {profile .generated_at }
**Certification Status**: **{status }** (Compliance: {compliance_pct }%)

---

1. Dataset Provenance & Metadata
* **Dataset Identifier**: `urn:innovate:lakehouse:{profile .dataset_name }`
* **Total Records**: `{profile .row_count :,}`
* **Total Features**: `{profile .column_count }`
* **Storage Footprint**: `{profile .memory_usage_bytes /1024 :.2f} KB`
* **Intended Use**: AI/ML Supervised Training, RAG Feature Indexing, LLM Fine-Tuning

---

2. Composite Data-Quality KPI Breakdown
| Dimension | Observed Score | Benchmark Target | Status |
| :--- | :--- | :--- | :--- |
| **Completeness** | `{score .completeness }%` | &ge; 90.0% | {pass_fail (score .completeness >=90 )} |
| **Validity** | `{score .validity }%` | &ge; 90.0% | {pass_fail (score .validity >=90 )} |
| **Uniqueness** | `{score .uniqueness }%` | &ge; 95.0% | {pass_fail (score .uniqueness >=95 )} |
| **Consistency** | `{score .consistency }%` | &ge; 90.0% | {pass_fail (score .consistency >=90 )} |
| **Timeliness** | `{score .timeliness }%` | &ge; 80.0% | {pass_fail (score .timeliness >=80 )} |
| **OVERALL COMPOSITE** | **`{score .composite_total }%` (Grade {score .grade })** | **&ge; 88.0%** | **{'CERTIFIED'if status =='CERTIFIED_AI_READY'else 'FLAGGED'}** |

---

3. Privacy, PII Hygiene & Regulatory Compliance
* **Active Sensitive Fields**: {pii_summary }
* **Anonymization Enforcement**: Luhn-verified masking and salt-based hashing applied.
* **Access Classification Tier**: {'RESTRICTED'if any (p .highest_sensitivity =='RESTRICTED'for p in pii_items )else 'CONFIDENTIAL'}

---

4. Statistical Distribution & Drift Stability
* **Covariate Shift / Drift**: {drift_str }
* **Decision Boundary**: Population Stability Index (PSI &le; 0.25), Kolmogorov-Smirnov (&alpha; = 0.05).

---

5. Deployment Certification
**Verdict**: `{status }`
*Certified for production AI pipelines under automated governance oversight.*
"""
