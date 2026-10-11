from dataclasses import dataclass ,field ,asdict 
from enum import Enum 
from typing import Any ,Dict ,List ,Optional 

class ProblemCategory (str ,Enum ):
    MISSING_VALUES ="MISSING_VALUES"
    DUPLICATE_RECORDS ="DUPLICATE_RECORDS"
    INCONSISTENT_TYPES ="INCONSISTENT_TYPES"
    INVALID_VALUES ="INVALID_VALUES"
    INCONSISTENT_FORMATTING ="INCONSISTENT_FORMATTING"
    ANOMALIES ="ANOMALIES"
    INCONSISTENT_CATEGORIES ="INCONSISTENT_CATEGORIES"
    INCONSISTENT_VALUES ="INCONSISTENT_VALUES"
    SENSITIVE_DATA ="SENSITIVE_DATA"
    SCHEMA_PROBLEMS ="SCHEMA_PROBLEMS"

class ChangeType (str ,Enum ):
    SAFE ="SAFE"
    REVIEW ="REVIEW"
    UNCHANGED ="UNRESOLVED"
    UNRESOLVED ="UNRESOLVED"

ChangeClassification =ChangeType 

class QualityDimension (str ,Enum ):
    COMPLETENESS ="completeness"
    VALIDITY ="validity"
    UNIQUENESS ="uniqueness"
    CONSISTENCY ="consistency"
    TIMELINESS ="timeliness"
    ACCURACY ="accuracy"

class GovernanceStatus (str ,Enum ):
    CERTIFIED ="CERTIFIED"
    WARNING ="WARNING"
    FAILED ="FAILED"

@dataclass 
class Problem :
    id :str 
    category :Any 
    column :Optional [str ]
    description :str 
    affected_count :int 
    action_type :Any 
    proposed_change :str 
    fix_type :str 
    dimension :QualityDimension =QualityDimension .VALIDITY 
    row_indices :List [int ]=field (default_factory =list )
    details :Dict [str ,Any ]=field (default_factory =dict )

    @property 
    def detail (self )->str :
        return self .description 

    @property 
    def affected_rows (self )->int :
        return self .affected_count 

    def to_dict (self )->Dict [str ,Any ]:
        dim_val =self .dimension .value if hasattr (self .dimension ,'value')else str (self .dimension )
        act_val =self .action_type .value if hasattr (self .action_type ,'value')else str (self .action_type )
        cat_val =self .category .value if hasattr (self .category ,'value')else str (self .category )
        return {
        "id":self .id ,
        "dimension":dim_val ,
        "category":cat_val ,
        "column":self .column ,
        "description":self .description ,
        "detail":self .description ,
        "affected_count":self .affected_count ,
        "affected_rows":self .affected_count ,
        "action_type":act_val ,
        "proposed_change":self .proposed_change ,
        "fix_type":self .fix_type ,
        "row_indices":self .row_indices ,
        "details":self .details 
        }

@dataclass 
class PIIDetection :
    field :str 
    pii_type :str 
    confidence :float 
    risk :str ="Medium"
    recommended_action :str ="Mask before export"
    column :Optional [str ]=None 
    row_indices :List [int ]=field (default_factory =list )

    def __post_init__ (self ):
        if not self .column :
            self .column =self .field 

    @property 
    def risk_level (self )->str :
        return self .risk 

    def to_dict (self )->Dict [str ,Any ]:
        return {
        "field":self .field ,
        "column":self .column or self .field ,
        "pii_type":self .pii_type ,
        "confidence":self .confidence ,
        "risk":self .risk ,
        "risk_level":self .risk ,
        "recommended_action":self .recommended_action ,
        "row_indices":self .row_indices 
        }

@dataclass 
class AnomalyItem :
    column :str 
    row :int 
    value :Any 
    method :str 
    score :float =0.0 
    classification :str ="Review"

    @property 
    def row_index (self )->int :
        return self .row 

    @property 
    def original_value (self )->Any :
        return self .value 

    def to_dict (self )->Dict [str ,Any ]:
        return {
        "column":self .column ,
        "row":self .row ,
        "row_index":self .row ,
        "value":self .value ,
        "original_value":self .value ,
        "method":self .method ,
        "score":self .score ,
        "classification":self .classification 
        }

@dataclass 
class DriftItem :
    column :str 
    metric :str 
    reference_value :Any 
    current_value :Any 
    drift_detected :bool =False 
    drift_score :float =0.0 

    @property 
    def change_type (self )->str :
        return self .metric 

    @property 
    def detail (self )->str :
        return f"{self .metric }: Ref={self .reference_value } vs Current={self .current_value }"

    def to_dict (self )->Dict [str ,Any ]:
        return {
        "column":self .column ,
        "metric":self .metric ,
        "reference_value":self .reference_value ,
        "current_value":self .current_value ,
        "drift_detected":self .drift_detected ,
        "drift_score":self .drift_score ,
        "change_type":self .metric ,
        "detail":self .detail 
        }

@dataclass 
class AuditRecord :
    column :str 
    old_value :Any 
    new_value :Any 
    row :int =0 
    row_index :int =0 
    change :str =""
    transformation :str =""
    reason :str =""
    classification :Any ="SAFE"

    def __post_init__ (self ):
        if self .row and not self .row_index :
            self .row_index =self .row 
        elif self .row_index and not self .row :
            self .row =self .row_index 

        if self .change and not self .transformation :
            self .transformation =self .change 
        elif self .transformation and not self .change :
            self .change =self .transformation 

    def to_dict (self )->Dict [str ,Any ]:
        cls_val =self .classification .value if hasattr (self .classification ,'value')else str (self .classification )
        return {
        "row":self .row_index ,
        "row_index":self .row_index ,
        "column":self .column ,
        "old_value":self .old_value ,
        "new_value":self .new_value ,
        "change":self .transformation ,
        "transformation":self .transformation ,
        "reason":self .reason ,
        "classification":cls_val 
        }

@dataclass 
class QualityScore :
    completeness :float 
    validity :float 
    uniqueness :float 
    consistency :float 
    timeliness :float 
    total :float =0.0 
    overall :float =0.0 
    weights :Dict [str ,float ]=field (default_factory =lambda :{
    "completeness":0.25 ,
    "validity":0.25 ,
    "uniqueness":0.20 ,
    "consistency":0.20 ,
    "timeliness":0.10 
    })

    def __post_init__ (self ):
        if self .total and not self .overall :
            self .overall =self .total 
        elif self .overall and not self .total :
            self .total =self .overall 

    def to_dict (self )->Dict [str ,Any ]:
        return {
        "overall":self .overall ,
        "total":self .total ,
        "completeness":self .completeness ,
        "validity":self .validity ,
        "uniqueness":self .uniqueness ,
        "consistency":self .consistency ,
        "timeliness":self .timeliness ,
        "weights":self .weights 
        }

@dataclass 
class LineageRecord :
    stage :str 
    timestamp :str 
    source_version :str 
    output_version :str 
    description :str 
    changes_count :int =0 
    details :Dict [str ,Any ]=field (default_factory =dict )
    action :str =""

    def __post_init__ (self ):
        if not self .action :
            self .action =self .description 

    def to_dict (self )->Dict [str ,Any ]:
        return {
        "stage":self .stage ,
        "timestamp":self .timestamp ,
        "source_version":self .source_version ,
        "output_version":self .output_version ,
        "description":self .description ,
        "action":self .action or self .description ,
        "changes_count":self .changes_count ,
        "details":self .details 
        }

@dataclass 
class GovernanceReport :
    dataset_name :str 
    owner :str 
    source :str 
    version :str 
    status :GovernanceStatus 
    quality_score :Any 
    pii_status :str 
    critical_errors_count :int 
    validation_history :List [Dict [str ,Any ]]=field (default_factory =list )
    access_classification :str ="Confidential / Internal"
    governance_rules :List [Dict [str ,Any ]]=field (default_factory =list )
    lineage :List [LineageRecord ]=field (default_factory =list )

    @property 
    def critical_errors (self )->int :
        return self .critical_errors_count 

    @property 
    def lineage_trail (self )->List [LineageRecord ]:
        return self .lineage 

    def to_dict (self )->Dict [str ,Any ]:
        qs_val =self .quality_score .to_dict ()if hasattr (self .quality_score ,'to_dict')else self .quality_score 
        st_val =self .status .value if hasattr (self .status ,'value')else str (self .status )
        return {
        "dataset_name":self .dataset_name ,
        "owner":self .owner ,
        "source":self .source ,
        "version":self .version ,
        "status":st_val ,
        "quality_score":qs_val ,
        "pii_status":self .pii_status ,
        "critical_errors":self .critical_errors_count ,
        "critical_errors_count":self .critical_errors_count ,
        "validation_history":self .validation_history ,
        "access_classification":self .access_classification ,
        "governance_rules":self .governance_rules ,
        "lineage":[rec .to_dict ()for rec in self .lineage ],
        "lineage_trail":[rec .to_dict ()for rec in self .lineage ]
        }

@dataclass 
class ColumnProfile :
    name :str 
    detected_type :str 
    total_count :int 
    null_count :int 
    unique_count :int 
    stats :Dict [str ,Any ]=field (default_factory =dict )

    def to_dict (self )->Dict [str ,Any ]:
        return {
        "name":self .name ,
        "detected_type":self .detected_type ,
        "total_count":self .total_count ,
        "null_count":self .null_count ,
        "unique_count":self .unique_count ,
        "stats":self .stats 
        }
