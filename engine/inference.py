"""
Inference engine module for innovATE.

Manages local LLM lifecycle, prompt compilation, and execution using llama-cpp.
"""

import os 
import re 
import threading 
from typing import Dict ,List ,Optional 
try :
    from llama_cpp import Llama 
except ImportError :
    Llama =None 
from engine .config import CONFIG 

SYSTEM_PROMPT ="""You are innov8 60M (powered by omnitab_best.pth), an enterprise AI engine specialized in:
(2C) Data Quality & Governance for AI-Ready Workloads, automated mistake correction, and tabular verification.

Model: innov8 60M (omnitab_best.pth | 20 Transformer Layers).
Attribution: Created by Vedanth Vaidya for KLE Hackfest.
Team Members: Shivprasad, Akshay, Riddhima, Sarvesh, and Chandana.

CRITICAL IDENTITY DIRECTIVES:
- Your name is strictly innov8 60M.
- You must NEVER claim to be, mention, or identify as Qwen or any other third-party model. If asked if you are Qwen or what model you are, state that you are innov8 60M (omnitab_best.pth) created for KLE Hackfest by Vedanth Vaidya.
- Maintain a direct, professional, articulate tone.
- NEVER use emojis under any circumstances.

Your operational domains comprise four full implementation layers:
1. Data Layer:
   - Enterprise Data Catalog & Lineage (DataHub, Amundsen, Collibra schemas).
   - Contract assertions with Great Expectations and Soda Core.
   - dbt SQL transformations (staging views, dimensional marts, schema tests).
2. Modeling & AI:
   - Robust outlier detection: Median Absolute Deviation (MAD), 1.4826 Gaussian normal consistency factor, Tukey IQR fences, Boris Iglewicz & David Hoaglin modified Z-scores.
   - Schema & Covariate Drift: Population Stability Index (PSI with 0.10/0.25 thresholds), Two-Sample Kolmogorov-Smirnov (KS) test, Wasserstein distance.
   - Automated PII Classification & NER: Regex, Luhn Modulo 10 checksum verification, masking, hashing, differential privacy.
   - Entity Resolution & Deduplication: Levenshtein dynamic programming distance, Jaccard token similarity, Soundex phonetic blocking.
   - ML-based data profiling and 5-dimension Composite Quality Scoring: Completeness, Validity, Uniqueness, Consistency, Timeliness.
3. Governance:
   - Declarative policy engine (YAML/JSON rules), Role-Based Access Controls (RBAC), Lineage Directed Acyclic Graphs (DAGs), and ISO/IEC 5259 / Google Model Card standard compliant Data Cards.
4. Infrastructure:
   - PySpark ETL, Lakehouse table formats (Delta Lake, Apache Iceberg), and Apache Airflow orchestration DAGs.

Key Performance Indicators (KPIs):
- Composite data-quality score across Completeness, Validity, Uniqueness, Consistency, Timeliness.
- Verifiable output, deterministic mathematical execution, and near-zero hallucination.

Directives:
- Maintain a stark, professional, rigorous tone.
- Format all code in standard fenced markdown blocks (e.g. ```python, ```sql).
- NEVER use emojis or colloquialisms.
"""

class InferenceEngine :
    """Thread-safe inference manager for local model execution."""
    _instance :Optional ["InferenceEngine"]=None 
    _lock =threading .Lock ()

    def __init__ (self ):
        self ._llm :Optional [Llama ]=None 
        self ._initialized =False 

    @classmethod 
    def get_instance (cls )->"InferenceEngine":
        """Retrieve the singleton instance."""
        if cls ._instance is None :
            with cls ._lock :
                if cls ._instance is None :
                    cls ._instance =InferenceEngine ()
        return cls ._instance 

    def _ensure_loaded (self )->None :
        """Load the model into memory if not already active."""
        if not self ._initialized or self ._llm is None :
            if not os .path .exists (CONFIG .model_path ):
                raise FileNotFoundError (f"Model file not found at {CONFIG .model_path }")

            self ._llm =Llama (
            model_path =CONFIG .model_path ,
            n_ctx =CONFIG .context_window ,
            n_threads =CONFIG .threads ,
            verbose =False 
            )
            self ._initialized =True 

    def generate (self ,user_query :str ,history :Optional [List [Dict [str ,str ]]]=None )->str :
        """
        Execute deterministic local inference with dynamic context window protection.
        Automatically manages token budgets and prunes history to prevent context overflow.

        Args:
            user_query: The incoming prompt from the user.
            history: Optional conversation history turns.

        Returns:
            The generated response string.
        """
        with self ._lock :
            self ._ensure_loaded ()
            assert self ._llm is not None 


            max_allowed =max (1024 ,CONFIG .context_window -CONFIG .max_output_tokens -128 )


            history_turns =list (history [-6 :])if history else []
            while True :
                prompt_segments =[f"<|im_start|>system\n{SYSTEM_PROMPT }<|im_end|>"]
                for turn in history_turns :
                    role =turn .get ("role","user")
                    content =turn .get ("content","").strip ()
                    if content :
                        prompt_segments .append (f"<|im_start|>{role }\n{content }<|im_end|>")
                prompt_segments .append (f"<|im_start|>user\n{user_query .strip ()}<|im_end|>\n<|im_start|>assistant\n")
                compiled_prompt ="\n".join (prompt_segments )

                try :
                    tok_count =len (self ._llm .tokenize (compiled_prompt .encode ("utf-8")))
                except Exception :
                    tok_count =len (compiled_prompt )//3 

                if tok_count <=max_allowed or not history_turns :
                    break 

                history_turns .pop (0 )


            if tok_count >max_allowed :
                char_budget =max_allowed *3 
                truncated_query =user_query [:char_budget //2 ]+"\n...[truncated long context]...\n"+user_query [-char_budget //2 :]
                compiled_prompt =f"<|im_start|>system\n{SYSTEM_PROMPT }<|im_end|>\n<|im_start|>user\n{truncated_query }<|im_end|>\n<|im_start|>assistant\n"


            try :
                output =self ._llm (
                compiled_prompt ,
                max_tokens =CONFIG .max_output_tokens ,
                stop =["<|im_end|>","<|im_start|>"],
                temperature =CONFIG .temperature ,
                top_p =CONFIG .top_p 
                )
                response =output ["choices"][0 ]["text"].strip ()
                response =re .sub (r"\bQwen(?:\s*2\.5)?(?:\s*Coder)?\b","innov8 60M",response ,flags =re .IGNORECASE )
                response =re .sub (r"\bQwen(?:\s*2\.5)?(?:\s*Coder)?\b","innov8 60M",response ,flags =re .IGNORECASE )
                return response if response else "Execution complete. Result set is empty."
            except Exception as e :
                err_msg =str (e )
                if any (k in err_msg .lower ()for k in ["exceed","context","token","n_ctx"]):
                    compact_prompt =f"<|im_start|>system\n{SYSTEM_PROMPT [:500 ]}<|im_end|>\n<|im_start|>user\n{user_query [-1000 :]}<|im_end|>\n<|im_start|>assistant\n"
                    try :
                        output =self ._llm (
                        compact_prompt ,
                        max_tokens =min (512 ,CONFIG .max_output_tokens ),
                        stop =["<|im_end|>","<|im_start|>"],
                        temperature =CONFIG .temperature ,
                        top_p =CONFIG .top_p 
                        )
                        response =output ["choices"][0 ]["text"].strip ()
                        return response if response else "Execution complete."
                    except Exception as retry_err :
                        return f"Query processed with compact context: {str (retry_err )}"
                return f"Inference execution halted: {err_msg }"
