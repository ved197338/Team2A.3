import os 
import json 
import torch 
import torch .nn as nn 
import torch .nn .functional as F 
import numpy as np 
import pandas as pd 

class TransformerBlock (nn .Module ):
    def __init__ (self ,embed_dim =64 ,num_heads =4 ,ff_dim =128 ,dropout =0.1 ):
        super ().__init__ ()
        self .attn =nn .MultiheadAttention (embed_dim =embed_dim ,num_heads =num_heads ,batch_first =True ,dropout =dropout )
        self .norm1 =nn .LayerNorm (embed_dim )
        self .norm2 =nn .LayerNorm (embed_dim )
        self .ffn =nn .Sequential (
        nn .Linear (embed_dim ,ff_dim ),
        nn .GELU (),
        nn .Dropout (dropout ),
        nn .Linear (ff_dim ,embed_dim )
        )

    def forward (self ,x ):
        attn_out ,_ =self .attn (x ,x ,x )
        x =self .norm1 (x +attn_out )
        ffn_out =self .ffn (x )
        x =self .norm2 (x +ffn_out )
        return x 

class TabularGovNet (nn .Module ):
    """
    100% Pure PyTorch Tabular Multi-Head Transformer.
    No pre-trained weights. Multi-task heads for:
    - Continuous Denoising / Outlier Reconstruction
    - Categorical Imputation & Typo Resolution
    - Outlier Anomaly Classification
    - PII Classification
    - Global Quality KPI Regression
    """
    def __init__ (self ,num_cities =50 ,num_statuses =10 ,embed_dim =64 ,num_layers =3 ):
        super ().__init__ ()
        self .embed_dim =embed_dim 


        self .city_embed =nn .Embedding (num_cities ,embed_dim )
        self .status_embed =nn .Embedding (num_statuses ,embed_dim )


        self .age_proj =nn .Linear (1 ,embed_dim )
        self .pct_proj =nn .Linear (1 ,embed_dim )
        self .qty_proj =nn .Linear (1 ,embed_dim )


        self .layers =nn .ModuleList ([
        TransformerBlock (embed_dim =embed_dim ,num_heads =4 ,ff_dim =embed_dim *2 ,dropout =0.1 )
        for _ in range (num_layers )
        ])


        self .cont_head =nn .Sequential (
        nn .Linear (embed_dim ,64 ),
        nn .GELU (),
        nn .Linear (64 ,2 )
        )


        self .city_head =nn .Linear (embed_dim ,num_cities )


        self .outlier_head =nn .Sequential (
        nn .Linear (embed_dim *5 ,64 ),
        nn .GELU (),
        nn .Linear (64 ,1 )
        )


        self .pii_head =nn .Sequential (
        nn .Linear (embed_dim *5 ,64 ),
        nn .GELU (),
        nn .Linear (64 ,1 )
        )


        self .quality_head =nn .Sequential (
        nn .Linear (embed_dim *5 ,64 ),
        nn .GELU (),
        nn .Linear (64 ,1 ),
        nn .Sigmoid ()
        )

    def forward (self ,city_in ,status_in ,cont_in ):

        c_emb =self .city_embed (city_in ).unsqueeze (1 )
        s_emb =self .status_embed (status_in ).unsqueeze (1 )

        age_tok =self .age_proj (cont_in [:,0 :1 ]).unsqueeze (1 )
        pct_tok =self .pct_proj (cont_in [:,1 :2 ]).unsqueeze (1 )
        qty_tok =self .qty_proj (cont_in [:,2 :3 ]).unsqueeze (1 )

        tokens =torch .cat ([c_emb ,s_emb ,age_tok ,pct_tok ,qty_tok ],dim =1 )

        for layer in self .layers :
            tokens =layer (tokens )

        row_repr =tokens .reshape (tokens .size (0 ),-1 )

        pred_cont =self .cont_head (tokens [:,2 ])
        pred_city =self .city_head (tokens [:,0 ])
        pred_outlier =self .outlier_head (row_repr ).squeeze (-1 )
        pred_pii =self .pii_head (row_repr ).squeeze (-1 )
        pred_quality =self .quality_head (row_repr ).squeeze (-1 )

        return {
        'pred_cont':pred_cont ,
        'pred_city':pred_city ,
        'pred_outlier':pred_outlier ,
        'pred_pii':pred_pii ,
        'pred_quality':pred_quality 
        }

class NeuralAnomalyDetector :
    _instance =None 

    @classmethod 
    def get_instance (cls ,model_path =None ):
        if cls ._instance is None :
            cls ._instance =cls (model_path =model_path )
        return cls ._instance 

    def __init__ (self ,model_path =None ):
        project_root =os .path .dirname (os .path .dirname (os .path .abspath (__file__ )))
        if model_path is None :
            model_path =os .path .join (project_root ,"models","tabular_gov_net.pth")
        meta_path =os .path .join (project_root ,"models","tabular_gov_net_meta.json")

        self .loaded =False 
        self .device =torch .device ("cpu")

        if os .path .exists (model_path )and os .path .exists (meta_path ):
            with open (meta_path ,"r",encoding ="utf-8")as f :
                self .meta =json .load (f )

            self .city2idx =self .meta ["city2idx"]
            self .idx2city ={int (v ):k for k ,v in self .city2idx .items ()}
            self .status2idx =self .meta ["status2idx"]
            self .age_mean =self .meta ["age_mean"]
            self .age_std =self .meta ["age_std"]
            self .pct_mean =self .meta ["pct_mean"]
            self .pct_std =self .meta ["pct_std"]

            self .model =TabularGovNet (
            num_cities =len (self .city2idx )+2 ,
            num_statuses =len (self .status2idx )+2 ,
            embed_dim =64 ,
            num_layers =3 
            ).to (self .device )

            checkpoint =torch .load (model_path ,map_location =self .device )
            self .model .load_state_dict (checkpoint ["model_state_dict"])
            self .model .eval ()
            self .loaded =True 

    def predict (self ,df :pd .DataFrame ):
        if not self .loaded :
            return {"error":"Model weights not yet trained or loaded"}

        outlier_flags =[]
        pii_flags =[]
        quality_scores =[]
        repaired_rows =[]

        for idx ,row in df .iterrows ():
            c_val =str (row .get ("city","Bangalore")).strip ()
            s_val =str (row .get ("status","ACTIVE")).strip ()
            c_idx =torch .tensor ([self .city2idx .get (c_val ,self .city2idx .get (c_val .title (),0 ))],dtype =torch .long )
            s_idx =torch .tensor ([self .status2idx .get (s_val ,0 )],dtype =torch .long )

            try :
                raw_age =float (row .get ("age",35 ))
            except Exception :
                raw_age =35.0 

            try :
                raw_pct =float (row .get ("completion_pct",50 ))
            except Exception :
                raw_pct =50.0 

            try :
                raw_qty =float (row .get ("quantity",5 ))
            except Exception :
                raw_qty =5.0 

            norm_age =(raw_age -self .age_mean )/self .age_std 
            norm_pct =(raw_pct -self .pct_mean )/self .pct_std 
            cont_in =torch .tensor ([[norm_age ,norm_pct ,raw_qty ]],dtype =torch .float32 )

            with torch .no_grad ():
                out =self .model (c_idx ,s_idx ,cont_in )
                p_outlier =torch .sigmoid (out ["pred_outlier"]).item ()
                p_pii =torch .sigmoid (out ["pred_pii"]).item ()
                q_score =out ["pred_quality"].item ()*100.0 

                clean_city_idx =torch .argmax (out ["pred_city"],dim =-1 ).item ()
                clean_city =self .idx2city .get (clean_city_idx ,c_val .title ())

                clean_age =(out ["pred_cont"][0 ,0 ].item ()*self .age_std )+self .age_mean 
                clean_pct =(out ["pred_cont"][0 ,1 ].item ()*self .pct_std )+self .pct_mean 

            is_out =p_outlier >0.5 or raw_age <0 or raw_age >120 or raw_pct <0 or raw_pct >100 
            outlier_flags .append (is_out )
            pii_flags .append (p_pii >0.5 )
            quality_scores .append (q_score )


            repaired_row =dict (row )
            repaired_row ["city"]=clean_city 
            if is_out :
                repaired_row ["age"]=round (clean_age ,0 )
                repaired_row ["completion_pct"]=round (clean_pct ,1 )
            repaired_rows .append (repaired_row )

        return {
        "outlier_indices":[i for i ,f in enumerate (outlier_flags )if f ],
        "pii_indices":[i for i ,f in enumerate (pii_flags )if f ],
        "average_quality_score":round (float (np .mean (quality_scores )),1 ),
        "repaired_df":pd .DataFrame (repaired_rows )
        }
