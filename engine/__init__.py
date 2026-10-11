"""
innovATE — Production Intelligence & Data Quality Governance Platform.

Specification: (2C) Data Quality & Governance for AI-Ready Workloads.
Architecture:
- Data Layer: catalog.py, expectations.py, dbt_generator.py
- Modeling/AI: stats.py, drift.py, pii_ner.py, dedup.py, profiler.py
- Governance: governance.py
- Infrastructure: infrastructure.py
- Stage 1 Logic Cleaning: logic_cleaner.py
- Stage 2 AI Data Editing: ai_editor.py
- Inference: inference.py
"""

from engine .config import CONFIG 
from engine .inference import InferenceEngine 
from engine .catalog import EnterpriseCatalog ,CatalogDataset ,ColumnMetadata 
from engine .expectations import ExpectationSuite ,ExpectationResult ,SuiteValidationReport 
from engine .dbt_generator import DbtTransformGenerator 
from engine .stats import find_outlier_indices ,compute_numerical_stats 
from engine .drift import DriftDetector ,DatasetDriftReport ,FeatureDriftResult 
from engine .pii_ner import PIINERClassifier ,PIIColumnClassification 
from engine .dedup import EntityDeduplicator ,DuplicateEntityMatch 
from engine .profiler import DataProfiler ,CompositeQualityScore ,DatasetProfileReport 
from engine .governance import PolicyEngine ,GovernanceAuditReport ,AccessControlRBAC ,DataCardGenerator 
from engine .infrastructure import LakehouseEngine ,AirflowDAGGenerator 
from engine .logic_cleaner import DeterministicLogicCleaner ,LogicCleaningResult 
from engine .ai_editor import AIDataEditor 

__all__ =[
"CONFIG",
"InferenceEngine",
"EnterpriseCatalog",
"CatalogDataset",
"ColumnMetadata",
"ExpectationSuite",
"ExpectationResult",
"SuiteValidationReport",
"DbtTransformGenerator",
"find_outlier_indices",
"compute_numerical_stats",
"DriftDetector",
"DatasetDriftReport",
"FeatureDriftResult",
"PIINERClassifier",
"PIIColumnClassification",
"EntityDeduplicator",
"DuplicateEntityMatch",
"DataProfiler",
"CompositeQualityScore",
"DatasetProfileReport",
"PolicyEngine",
"GovernanceAuditReport",
"AccessControlRBAC",
"DataCardGenerator",
"LakehouseEngine",
"AirflowDAGGenerator",
"DeterministicLogicCleaner",
"LogicCleaningResult",
"AIDataEditor"
]
