"""
Configuration module for the innovATE production engine.

Handles environment paths, model parameters, and execution settings.
"""

import os 
from dataclasses import dataclass 

@dataclass (frozen =True )
class EngineConfig :
    """Immutable engine configuration parameters."""
    app_name :str ="innovATE"
    version :str ="3.1.0-prod"
    model_path :str =os .path .join (os .path .dirname (os .path .dirname (os .path .abspath (__file__ ))),"models","innov8_engine.gguf")
    context_window :int =8192 
    threads :int =4 
    max_output_tokens :int =1024 
    temperature :float =0.2 
    top_p :float =0.9 

CONFIG =EngineConfig ()
