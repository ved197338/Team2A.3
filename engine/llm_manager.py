import os 
import threading 
from typing import Dict ,Any ,List ,Optional 
from llama_cpp import Llama 

MODELS_CONFIG ={
"0.5b":{
"id":"0.5b",
"name":"innov8 60M (Fast / 645MB)",
"path":"/home/april/.gemini/antigravity-ide/scratch/april-math-code-chat/models/qwen2.5-coder-0.5b-instruct-q8_0.gguf",
"description":"Ultra-lightweight 8-bit model (< 1GB RAM footprint, near-instant CPU response)"
},
"1.5b":{
"id":"1.5b",
"name":"innov8 60M Ultra (1.1GB)",
"path":"/home/april/.gemini/antigravity-ide/scratch/april-ramanujan/models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
"description":"Advanced reasoning model for complex mathematical and tabular reasoning"
}
}

DEFAULT_MODEL_ID ="0.5b"

SYSTEM_PROMPT ="""You are innovATE (also known as innov8), an elite AI assistant specializing in mathematics, robust statistics, algorithmic problem solving, and software engineering.

Core Persona & Directives:
1. Mathematical Rigor:
   - Provide exact formulas, derivations, and step-by-step proofs.
   - Master robust statistics: Median Absolute Deviation (MAD), normal consistency scaling (1.4826 constant), Tukey's IQR fences, Boris Iglewicz & David Hoaglin modified Z-scores, and log-transformations for power-law distributions.
   - Master discrete math and string metrics: Levenshtein dynamic programming distance, Jaccard similarity index, and Luhn Modulo 10 checksum.
2. Software Engineering:
   - Write clean, modular, production-ready code in Python, C++, and SQL.
   - Wrap all code in fenced markdown blocks with the language specified (e.g. ```python).
3. Tone and Formatting:
   - Direct, intelligent, concise, and articulate.
   - Use clean Markdown with bold headers and bullet points.
   - STRICT RULE: DO NOT USE EMOJIS UNDER ANY CIRCUMSTANCES.
"""

class LLMManager :
    _instance =None 
    _lock =threading .Lock ()

    def __init__ (self ):
        self .active_model_id =DEFAULT_MODEL_ID 
        self .llm :Optional [Llama ]=None 
        self .current_loaded_path :Optional [str ]=None 

    @classmethod 
    def get_instance (cls ):
        if cls ._instance is None :
            with cls ._lock :
                if cls ._instance is None :
                    cls ._instance =LLMManager ()
        return cls ._instance 

    def get_available_models (self )->List [Dict [str ,Any ]]:
        models =[]
        for mid ,cfg in MODELS_CONFIG .items ():
            models .append ({
            "id":mid ,
            "name":cfg ["name"],
            "description":cfg ["description"],
            "available":os .path .exists (cfg ["path"]),
            "size_mb":round (os .path .getsize (cfg ["path"])/(1024 *1024 ),1 )if os .path .exists (cfg ["path"])else 0 ,
            "active":(mid ==self .active_model_id )
            })
        return models 

    def switch_model (self ,model_id :str )->bool :
        if model_id not in MODELS_CONFIG :
            return False 
        with self ._lock :
            if model_id !=self .active_model_id or self .llm is None :
                self .active_model_id =model_id 
                self .llm =None 
                self ._load_active_model ()
            return True 

    def _load_active_model (self ):
        cfg =MODELS_CONFIG .get (self .active_model_id ,MODELS_CONFIG [DEFAULT_MODEL_ID ])
        model_path =cfg ["path"]
        if not os .path .exists (model_path ):
            alt_id ="1.5b"if self .active_model_id =="0.5b"else "0.5b"
            alt_path =MODELS_CONFIG [alt_id ]["path"]
            if os .path .exists (alt_path ):
                model_path =alt_path 
                self .active_model_id =alt_id 
            else :
                raise FileNotFoundError ("Neither model file was found on disk.")

        print (f"[innovATE LLM] Loading {cfg ['name']} from {model_path }...")
        self .llm =Llama (
        model_path =model_path ,
        n_ctx =8192 ,
        n_threads =4 ,
        verbose =False 
        )
        self .current_loaded_path =model_path 
        print (f"[innovATE LLM] Successfully loaded {self .active_model_id }!")

    def generate_chat_response (
    self ,
    user_message :str ,
    history :List [Dict [str ,str ]],
    model_choice :Optional [str ]=None 
    )->str :
        with self ._lock :
            if model_choice and model_choice in MODELS_CONFIG and model_choice !=self .active_model_id :
                self .switch_model (model_choice )
            elif self .llm is None :
                self ._load_active_model ()

            prompt_parts =[f"<|im_start|>system\n{SYSTEM_PROMPT }<|im_end|>"]


            recent_history =history [-6 :]if len (history )>6 else history 
            for turn in recent_history :
                role ="user"if turn .get ("role")=="user"else "assistant"
                content =turn .get ("content","").strip ()
                if content :
                    prompt_parts .append (f"<|im_start|>{role }\n{content }<|im_end|>")

            prompt_parts .append (f"<|im_start|>user\n{user_message }<|im_end|>\n<|im_start|>assistant\n")
            formatted_prompt ="\n".join (prompt_parts )

            try :
                output =self .llm (
                formatted_prompt ,
                max_tokens =350 ,
                stop =["<|im_end|>","<|im_start|>"],
                temperature =0.35 ,
                top_p =0.9 
                )
                text =output ["choices"][0 ]["text"].strip ()
                return text if text else "I have analyzed your query. How can I assist you further?"
            except Exception as e :
                return f"Inference error: {str (e )}. Please check your prompt."
