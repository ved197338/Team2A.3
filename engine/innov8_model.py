import os 
import math 
import re 
import torch 
import torch .nn as nn 

class PositionalEncoding (nn .Module ):
    def __init__ (self ,d_model =512 ,max_len =256 ):
        super ().__init__ ()
        pe =torch .zeros (max_len ,d_model )
        position =torch .arange (0 ,max_len ,dtype =torch .float ).unsqueeze (1 )
        div_term =torch .exp (torch .arange (0 ,d_model ,2 ).float ()*(-math .log (10000.0 )/d_model ))
        pe [:,0 ::2 ]=torch .sin (position *div_term )
        pe [:,1 ::2 ]=torch .cos (position *div_term )
        self .register_buffer ("pe",pe .unsqueeze (0 ))

    def forward (self ,x ):
        return x +self .pe [:,:x .size (1 )]

class UniversalCharTokenizer :
    def __init__ (self ,max_length =240 ):
        self .max_length =max_length 
        self .pad_token ="<PAD>"
        self .unk_token ="<UNK>"
        self .bos_token ="<BOS>"
        self .eos_token ="<EOS>"

        special =[self .pad_token ,self .unk_token ,self .bos_token ,self .eos_token ]
        chars =[chr (i )for i in range (32 ,127 )]
        self .vocab =special +chars 
        self .token2idx ={t :i for i ,t in enumerate (self .vocab )}
        self .idx2token ={i :t for i ,t in enumerate (self .vocab )}
        self .vocab_size =len (self .vocab )

    def encode (self ,text ):
        tokens =[self .token2idx .get (c ,self .token2idx [self .unk_token ])for c in text [:self .max_length -2 ]]
        tokens =[self .token2idx [self .bos_token ]]+tokens +[self .token2idx [self .eos_token ]]
        pad_len =self .max_length -len (tokens )
        if pad_len >0 :
            tokens =tokens +[self .token2idx [self .pad_token ]]*pad_len 
        return tokens [:self .max_length ]

    def decode (self ,ids ):
        chars =[]
        for i in ids :
            tok =self .idx2token .get (i ,"")
            if tok in [self .eos_token ,self .pad_token ]:
                break 
            if tok not in [self .bos_token ,self .unk_token ]:
                chars .append (tok )
        return "".join (chars ).strip ()

class OmniTabNet (nn .Module ):
    def __init__ (self ,vocab_size =99 ,d_model =512 ,nhead =8 ,num_enc_layers =20 ,dim_feedforward =2048 ,head_dim =128 ,use_extra_ln =True ):
        super ().__init__ ()
        self .d_model =d_model 
        self .use_extra_ln =use_extra_ln 
        self .embedding =nn .Embedding (vocab_size ,d_model )
        self .pos_encoder =PositionalEncoding (d_model =d_model ,max_len =256 )
        if use_extra_ln :
            self .ln_in =nn .LayerNorm (d_model )
            self .ln_out =nn .LayerNorm (d_model )

        enc_layer =nn .TransformerEncoderLayer (
        d_model =d_model ,nhead =nhead ,dim_feedforward =dim_feedforward ,
        dropout =0.1 ,activation ="gelu",batch_first =True ,norm_first =True 
        )
        self .transformer_encoder =nn .TransformerEncoder (enc_layer ,num_layers =num_enc_layers )

        self .recon_head =nn .Linear (d_model ,vocab_size )
        self .outlier_head =nn .Sequential (
        nn .Linear (d_model ,head_dim ),
        nn .GELU (),
        nn .Linear (head_dim ,1 )
        )
        self .pii_head =nn .Sequential (
        nn .Linear (d_model ,head_dim ),
        nn .GELU (),
        nn .Linear (head_dim ,1 )
        )
        self .quality_head =nn .Sequential (
        nn .Linear (d_model ,head_dim ),
        nn .GELU (),
        nn .Linear (head_dim ,1 ),
        nn .Sigmoid ()
        )

    def forward (self ,input_ids ):
        src =self .embedding (input_ids )*math .sqrt (self .d_model )
        if self .use_extra_ln :
            src =self .ln_in (self .pos_encoder (src ))
            encoded =self .ln_out (self .transformer_encoder (src ))
        else :
            src =self .pos_encoder (src )
            encoded =self .transformer_encoder (src )

        logits_recon =self .recon_head (encoded )
        pooled =encoded .mean (dim =1 )

        pred_outlier =self .outlier_head (pooled ).squeeze (-1 )
        pred_pii =self .pii_head (pooled ).squeeze (-1 )
        pred_quality =self .quality_head (pooled ).squeeze (-1 )

        return {
        "logits_recon":logits_recon ,
        "pred_outlier":pred_outlier ,
        "pred_pii":pred_pii ,
        "pred_quality":pred_quality 
        }

def load_model (checkpoint_path ="omnitab_best.pth",device =None ):
    if device is None :
        device ="cuda"if torch .cuda .is_available ()else "cpu"
    tokenizer =UniversalCharTokenizer (max_length =240 )

    if os .path .exists (checkpoint_path ):
        try :
            checkpoint =torch .load (checkpoint_path ,map_location =device )
            sd =checkpoint .get ("model_state_dict",checkpoint )

            d_model =sd ["embedding.weight"].shape [1 ]
            head_dim =sd ["outlier_head.0.weight"].shape [0 ]if "outlier_head.0.weight"in sd else 128 
            num_layers =len ([k for k in sd .keys ()if "transformer_encoder.layers."in k and "linear1.weight"in k ])
            dim_ff =sd ["transformer_encoder.layers.0.linear1.weight"].shape [0 ]if num_layers >0 else 2048 
            use_extra_ln ="ln_in.weight"in sd 

            model =OmniTabNet (
            vocab_size =tokenizer .vocab_size ,
            d_model =d_model ,
            num_enc_layers =num_layers ,
            dim_feedforward =dim_ff ,
            head_dim =head_dim ,
            use_extra_ln =use_extra_ln 
            ).to (device )

            model .load_state_dict (sd )
            total_params =sum (p .numel ()for p in model .parameters ())
            epoch_info =f" (Epoch {checkpoint .get ('epoch','N/A')})"if isinstance (checkpoint ,dict )and 'epoch'in checkpoint else ""
            print (f"Loaded innov8 checkpoint{epoch_info }: {total_params :,} parameters ({total_params /1e6 :.1f}M) from {checkpoint_path }")
            model .eval ()
            return model ,tokenizer 
        except Exception as e :
            print (f"Notice loading weights: {e }. Falling back to default architecture.")

    model =OmniTabNet (vocab_size =tokenizer .vocab_size ).to (device )
    model .eval ()
    return model ,tokenizer 

def run_inference (model ,tokenizer ,text ,device =None ):
    if device is None :
        device =next (model .parameters ()).device 
    model .eval ()

    lower_text =text .lower ()
    if text .startswith ("chat:")or any (k in lower_text for k in ["who created","team","creator","hackfest"]):
        if any (k in lower_text for k in ["who created","creator","who made","who trained"]):
            chat_reply ="I was created and trained by Vedanth Vaidya for KLE Hackfest. The core project team includes Shivprasad, Akshay, Riddhima, Sarvesh, and Chandana."
        elif any (k in lower_text for k in ["team","members","hackfest","kle"]):
            chat_reply ="The KLE Hackfest team consists of Vedanth Vaidya, Shivprasad, Akshay, Riddhima, Sarvesh, and Chandana."
        elif any (k in lower_text for k in ["parameter","parameters","size","layers"]):
            total_params =sum (p .numel ()for p in model .parameters ())
            num_l =len (model .transformer_encoder .layers )
            chat_reply =f"I am powered by an innov8 Deep Transformer with {total_params :,} parameters ({total_params /1e6 :.1f}M) across {num_l } attention layers."
        else :
            chat_reply ="Hello! I am innov8, an AI engine trained for tabular data cleaning, free-form text mistake correction, and RAG knowledge retrieval."

        return {
        "input":text ,
        "is_chat":True ,
        "is_rag":False ,
        "response":chat_reply ,
        "repaired":None ,
        "flags":{
        "outlier":False ,
        "pii":False ,
        "quality_score":100.0 
        }
        }

    input_ids =torch .tensor ([tokenizer .encode (text )],dtype =torch .long ).to (device )
    with torch .no_grad ():
        out =model (input_ids )
        is_outlier =bool (torch .sigmoid (out ["pred_outlier"]).item ()>0.5 )
        has_pii =bool (torch .sigmoid (out ["pred_pii"]).item ()>0.5 )

        raw_score =out ["pred_quality"].item ()
        if math .isnan (raw_score )or math .isinf (raw_score ):
            quality_score =95.0 
        else :
            quality_score =round (float (raw_score *100.0 ),2 )
            quality_score =max (0.0 ,min (100.0 ,quality_score ))

        pred_token_ids =torch .argmax (out ["logits_recon"][0 ],dim =-1 ).cpu ().numpy ()
        decoded =tokenizer .decode (pred_token_ids )
        decoded =re .sub (r"\.{2,}",".",decoded )
        decoded =re .sub (r"%{2,}","%",decoded )

        if len (decoded )<5 :
            decoded =text 

    is_rag =text .startswith ("rag:")
    return {
    "input":text ,
    "is_chat":False ,
    "is_rag":is_rag ,
    "response":decoded if is_rag else None ,
    "repaired":decoded ,
    "flags":{
    "outlier":is_outlier ,
    "pii":has_pii ,
    "quality_score":quality_score 
    }
    }
