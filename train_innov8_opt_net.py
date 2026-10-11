import os 
import sys 
import math 
import time 
import random 
import argparse 
import urllib .request 
import numpy as np 
import pandas as pd 
import torch 
import torch .nn as nn 
import torch .nn .functional as F 
from torch .utils .data import Dataset ,DataLoader 

try :
    from tqdm .auto import tqdm 
except ImportError :
    class tqdm :
        def __init__ (self ,iterable ,desc ="",total =None ,leave =True ,dynamic_ncols =True ,**kwargs ):
            self .iterable =iterable 
            self .desc =desc 
            self .total =total or len (iterable )
            self .n =0 
            self .start_time =time .time ()
            self .postfix_str =""
        def __iter__ (self ):
            for item in self .iterable :
                yield item 
                self .n +=1 
                if self .n %max (1 ,self .total //25 )==0 or self .n ==self .total :
                    pct =int (self .n /self .total *100 )
                    elapsed =time .time ()-self .start_time 
                    speed =self .n /max (0.001 ,elapsed )
                    bar_len =20 
                    filled =int (bar_len *self .n /self .total )
                    bar ="="*filled +(">"if filled <bar_len else "")+"."*(bar_len -filled -(1 if filled <bar_len else 0 ))
                    stat =f" {self .postfix_str }"if self .postfix_str else ""
                    sys .stdout .write (f"\r{self .desc } [{bar }] {pct }% ({self .n }/{self .total }) {speed :.1f} it/s{stat }")
                    sys .stdout .flush ()
            sys .stdout .write ("\n")
        def set_postfix (self ,**kwargs ):
            parts =[f"{k }={v }"for k ,v in kwargs .items ()]
            self .postfix_str =" | ".join (parts )

from optinet_innov8 import (
TIER_COSTS ,
TIER_NAMES ,
QUANTIZATION_POLICIES ,
WORKLOAD_TYPES ,
CSI_ACTIONS ,
AGENT_ACTIONS ,
REMOTE_DATA_URL ,
fetch_or_build_telemetry_data ,
StorageTelemetryDataset ,
Innov8OptNet ,
StorageSandboxExecutor ,
AutonomousStorageAgent 
)

def parse_training_args ():
    parser =argparse .ArgumentParser (description ="Innov8OptNet 80M Autonomous Storage Optimizer Training")
    parser .add_argument ("--epochs",type =int ,default =8 )
    parser .add_argument ("--batch-size",type =int ,default =64 )
    parser .add_argument ("--grad-accum",type =int ,default =4 )
    parser .add_argument ("--lr",type =float ,default =1e-4 )
    parser .add_argument ("--d-model",type =int ,default =1024 )
    parser .add_argument ("--nhead",type =int ,default =16 )
    parser .add_argument ("--num-layers",type =int ,default =6 )
    parser .add_argument ("--dim-feedforward",type =int ,default =4196 )
    parser .add_argument ("--records",type =int ,default =50000 )
    parser .add_argument ("--data-url",type =str ,default =REMOTE_DATA_URL )
    parser .add_argument ("--save-path",type =str ,default ="./checkpoints/optinet_innov8.pth")
    parser .add_argument ("--auto-download",action ="store_true",default =True )
    if "ipykernel"in sys .modules :
        return parser .parse_args (args =[])
    return parser .parse_args ()

def train_storage_optimizer ():
    args =parse_training_args ()
    device =torch .device ("cuda"if torch .cuda .is_available ()else "cpu")
    is_cuda =(device .type =="cuda")
    if is_cuda :
        torch .set_float32_matmul_precision ("high")
        torch .backends .cudnn .benchmark =True 
    print (f"Active Device: {device } | CUDA Available: {is_cuda }")
    is_colab =False 
    try :
        import google .colab 
        is_colab =True 
        print ("Detected Google Colab environment")
    except ImportError :
        pass 
    os .makedirs ("./checkpoints",exist_ok =True )
    df =fetch_or_build_telemetry_data (num_records =args .records ,seed =42 ,url =args .data_url )
    dataset =StorageTelemetryDataset (df )
    val_len =max (10 ,int (len (dataset )*0.1 ))
    train_len =len (dataset )-val_len 
    train_set ,val_set =torch .utils .data .random_split (
    dataset ,[train_len ,val_len ],
    generator =torch .Generator ().manual_seed (42 )
    )
    train_loader =DataLoader (train_set ,batch_size =args .batch_size ,shuffle =True ,pin_memory =is_cuda ,num_workers =0 )
    val_loader =DataLoader (val_set ,batch_size =args .batch_size ,shuffle =False ,pin_memory =is_cuda ,num_workers =0 )
    model =Innov8OptNet (
    d_model =args .d_model ,
    nhead =args .nhead ,
    num_layers =args .num_layers ,
    dim_feedforward =args .dim_feedforward 
    ).to (device )
    total_params =sum (p .numel ()for p in model .parameters ())
    print (f"Innov8OptNet (80M Parameters): {total_params :,} ({total_params /1e6 :.2f}M params)")
    criterion_ce =nn .CrossEntropyLoss ()
    criterion_bce =nn .BCEWithLogitsLoss ()
    criterion_mse =nn .MSELoss ()
    fused_opt =is_cuda and hasattr (torch .optim .AdamW ,"__init__")and "fused"in torch .optim .AdamW .__init__ .__code__ .co_varnames 
    optimizer =torch .optim .AdamW (model .parameters (),lr =args .lr ,weight_decay =1e-2 ,betas =(0.9 ,0.98 ),eps =1e-8 ,fused =fused_opt )
    scheduler =torch .optim .lr_scheduler .CosineAnnealingLR (optimizer ,T_max =args .epochs ,eta_min =1e-6 )
    scaler =torch .amp .GradScaler ("cuda",enabled =is_cuda )
    best_val_loss =float ("inf")
    best_save_path =args .save_path 
    best_save_base =os .path .splitext (best_save_path )[0 ]
    cwd_save_pth ="optinet_innov8.pth"
    cwd_save_base ="optinet_innov8"
    grad_accum_steps =args .grad_accum 
    for epoch in range (args .epochs ):
        model .train ()
        train_loss_total =0.0 
        optimizer .zero_grad (set_to_none =True )
        start_time =time .time ()
        pbar =tqdm (train_loader ,desc =f"Epoch {epoch +1 :02d}/{args .epochs :02d}",leave =True ,dynamic_ncols =True )
        for step ,batch in enumerate (pbar ):
            num_feats =batch ["num_feats"].to (device ,non_blocking =True )
            workload_idx =batch ["workload_idx"].to (device ,non_blocking =True )
            tier_idx =batch ["tier_idx"].to (device ,non_blocking =True )
            encryption =batch ["encryption"].to (device ,non_blocking =True )
            target_tier =batch ["target_tier"].to (device ,non_blocking =True )
            target_quant =batch ["target_quant"].to (device ,non_blocking =True )
            target_anomaly =batch ["target_anomaly"].to (device ,non_blocking =True )
            target_compliance =batch ["target_compliance"].to (device ,non_blocking =True )
            target_savings =batch ["target_savings"].to (device ,non_blocking =True )
            action_idx =batch ["action_idx"].to (device ,non_blocking =True )
            target_agent_action =batch ["target_agent_action"].to (device ,non_blocking =True )
            target_agent_confidence =batch ["target_agent_confidence"].to (device ,non_blocking =True )
            with torch .amp .autocast (device_type ="cuda"if is_cuda else "cpu",dtype =torch .float16 if is_cuda else torch .bfloat16 ):
                out =model (num_feats ,workload_idx ,tier_idx ,encryption )
                l_tier =criterion_ce (out ["logits_tier"],target_tier )
                l_quant =criterion_ce (out ["logits_quant"],target_quant )
                l_anom =criterion_bce (out ["logits_anomaly"],target_anomaly )
                l_comp =criterion_bce (out ["logits_compliance"],target_compliance )
                l_save =criterion_mse (out ["pred_savings"],target_savings )
                l_csi =criterion_ce (out ["logits_action"],action_idx )
                l_act =criterion_ce (out ["logits_agent_action"],target_agent_action )
                l_conf =criterion_mse (out ["agent_confidence"],target_agent_confidence )
                batch_loss =(1.5 *l_tier )+(1.5 *l_quant )+(1.0 *l_anom )+(1.0 *l_comp )+(2.0 *l_save )+(1.0 *l_csi )+(1.5 *l_act )+(0.5 *l_conf )
                loss_scaled =batch_loss /grad_accum_steps 
            scaler .scale (loss_scaled ).backward ()
            train_loss_total +=batch_loss .item ()
            if (step +1 )%grad_accum_steps ==0 or (step +1 )==len (train_loader ):
                scaler .unscale_ (optimizer )
                torch .nn .utils .clip_grad_norm_ (model .parameters (),max_norm =1.0 )
                scaler .step (optimizer )
                scaler .update ()
                optimizer .zero_grad (set_to_none =True )
            curr_lr =optimizer .param_groups [0 ]["lr"]
            pred_tier_acc =(torch .argmax (out ["logits_tier"],dim =-1 )==target_tier ).float ().mean ().item ()
            pred_quant_acc =(torch .argmax (out ["logits_quant"],dim =-1 )==target_quant ).float ().mean ().item ()
            pred_act_acc =(torch .argmax (out ["logits_agent_action"],dim =-1 )==target_agent_action ).float ().mean ().item ()
            pbar .set_postfix (loss =f"{batch_loss .item ():.3f}",tier =f"{pred_tier_acc :.0%}",quant =f"{pred_quant_acc :.0%}",agent =f"{pred_act_acc :.0%}",lr =f"{curr_lr :.2e}")
        scheduler .step ()
        train_loss =train_loss_total /len (train_loader )
        model .eval ()
        val_loss_total =0.0 
        c_tier =0 
        c_quant =0 
        c_anom =0 
        c_csi =0 
        c_agent =0 
        mae_sum =0.0 
        total_val =0 
        with torch .no_grad ():
            for batch in val_loader :
                num_feats =batch ["num_feats"].to (device )
                workload_idx =batch ["workload_idx"].to (device )
                tier_idx =batch ["tier_idx"].to (device )
                encryption =batch ["encryption"].to (device )
                target_tier =batch ["target_tier"].to (device )
                target_quant =batch ["target_quant"].to (device )
                target_anomaly =batch ["target_anomaly"].to (device )
                target_compliance =batch ["target_compliance"].to (device )
                target_savings =batch ["target_savings"].to (device )
                action_idx =batch ["action_idx"].to (device )
                target_agent_action =batch ["target_agent_action"].to (device )
                target_agent_confidence =batch ["target_agent_confidence"].to (device )
                with torch .amp .autocast (device_type ="cuda"if is_cuda else "cpu",dtype =torch .float16 if is_cuda else torch .bfloat16 ):
                    out =model (num_feats ,workload_idx ,tier_idx ,encryption )
                    l_tier =criterion_ce (out ["logits_tier"],target_tier )
                    l_quant =criterion_ce (out ["logits_quant"],target_quant )
                    l_anom =criterion_bce (out ["logits_anomaly"],target_anomaly )
                    l_comp =criterion_bce (out ["logits_compliance"],target_compliance )
                    l_save =criterion_mse (out ["pred_savings"],target_savings )
                    l_csi =criterion_ce (out ["logits_action"],action_idx )
                    l_act =criterion_ce (out ["logits_agent_action"],target_agent_action )
                    l_conf =criterion_mse (out ["agent_confidence"],target_agent_confidence )
                    v_loss =(1.5 *l_tier )+(1.5 *l_quant )+(1.0 *l_anom )+(1.0 *l_comp )+(2.0 *l_save )+(1.0 *l_csi )+(1.5 *l_act )+(0.5 *l_conf )
                val_loss_total +=v_loss .item ()
                b_size =target_tier .size (0 )
                total_val +=b_size 
                c_tier +=(torch .argmax (out ["logits_tier"],dim =-1 )==target_tier ).sum ().item ()
                c_quant +=(torch .argmax (out ["logits_quant"],dim =-1 )==target_quant ).sum ().item ()
                c_anom +=((torch .sigmoid (out ["logits_anomaly"])>0.5 ).float ()==target_anomaly ).sum ().item ()
                c_csi +=(torch .argmax (out ["logits_action"],dim =-1 )==action_idx ).sum ().item ()
                c_agent +=(torch .argmax (out ["logits_agent_action"],dim =-1 )==target_agent_action ).sum ().item ()
                mae_sum +=torch .abs (out ["pred_savings"]-target_savings ).sum ().item ()
        val_loss =val_loss_total /len (val_loader )
        t_acc =(c_tier /total_val )*100.0 
        q_acc =(c_quant /total_val )*100.0 
        an_acc =(c_anom /total_val )*100.0 
        csi_acc =(c_csi /total_val )*100.0 
        ag_acc =(c_agent /total_val )*100.0 
        tco_mae =(mae_sum /total_val )*100.0 
        elapsed =time .time ()-start_time 
        print (f"Epoch [{epoch +1 :02d}/{args .epochs :02d}] ({elapsed :.1f}s) | Train: {train_loss :.4f} | Val: {val_loss :.4f} | Tier: {t_acc :.1f}% | Quant: {q_acc :.1f}% | Agent: {ag_acc :.1f}% | Anom: {an_acc :.1f}% | CSI: {csi_acc :.1f}% | MAE: {tco_mae :.2f}%")
        if val_loss <best_val_loss :
            best_val_loss =val_loss 
            ckpt_dict ={
            "model_state_dict":model .state_dict (),
            "config":{
            "d_model":args .d_model ,
            "nhead":args .nhead ,
            "num_layers":args .num_layers ,
            "dim_feedforward":args .dim_feedforward ,
            "num_workloads":6 ,
            "num_tiers":4 ,
            "num_quants":4 ,
            "num_actions":7 ,
            "num_agent_actions":8 ,
            "parameter_count":total_params 
            }
            }
            torch .save (ckpt_dict ,best_save_path )
            torch .save (ckpt_dict ,best_save_base )
            torch .save (ckpt_dict ,cwd_save_pth )
            torch .save (ckpt_dict ,cwd_save_base )
            print (f"Saved: {best_save_path } and {best_save_base }")
    agent =AutonomousStorageAgent (model ,device =device )
    test_cases =[
    {"name":"Stale AI Checkpoint on NVMe","workload":0 ,"iops":45 ,"tp":2.5 ,"lat":18.0 ,"qd":1 ,"cap":85.0 ,"freq":0.05 ,"inact":120.0 ,"tier":0 ,"sla":20.0 ,"ret":90 ,"enc":1 },
    {"name":"Active OLTP Database (SLA Sensitive)","workload":1 ,"iops":32000 ,"tp":480.0 ,"lat":1.4 ,"qd":16 ,"cap":12.0 ,"freq":65000 ,"inact":0.0 ,"tier":0 ,"sla":3.0 ,"ret":365 ,"enc":1 },
    {"name":"Saturated Storage Queue Bottleneck","workload":2 ,"iops":4200 ,"tp":110.0 ,"lat":48.0 ,"qd":64 ,"cap":45.0 ,"freq":800 ,"inact":1.0 ,"tier":1 ,"sla":15.0 ,"ret":365 ,"enc":1 },
    {"name":"7-Year Financial Compliance Archive","workload":4 ,"iops":8 ,"tp":1.0 ,"lat":120.0 ,"qd":1 ,"cap":250.0 ,"freq":0.001 ,"inact":450.0 ,"tier":1 ,"sla":500.0 ,"ret":2555 ,"enc":1 },
    {"name":"Unencrypted Healthcare Database Backup","workload":3 ,"iops":50 ,"tp":12.0 ,"lat":25.0 ,"qd":2 ,"cap":35.0 ,"freq":0.5 ,"inact":40.0 ,"tier":1 ,"sla":50.0 ,"ret":730 ,"enc":0 }
    ]
    for tc in test_cases :
        res =agent .evaluate_volume (tc )
        print (f"PROFILE: {tc ['name']} ({tc ['cap']} TB | Cur: {TIER_NAMES [tc ['tier']]})")
        print (f"AGENT ACTION: [{res ['agent_action']}] | Confidence: {res ['agent_confidence']}")
        print (f"THOUGHT: {res ['agent_thought']}")
        print (f"DECISION: Tier: [{res ['recommended_tier']}] | Quantization: [{res ['quantization_policy']}] | TCO Cut: {res ['tco_savings']}")
        print (f"FLAGS: SLA Anomaly={res ['anomaly_detected']} | Compliance Risk={res ['compliance_risk']}")
        print (f"COMMAND: $ {res ['terminal_directive']}")
        print ("-"*85 )
    if is_colab and args .auto_download :
        try :
            from google .colab import files 
            print (f"Auto-downloading checkpoint: {best_save_path }")
            files .download (best_save_path )
            if os .path .exists (best_save_base ):
                files .download (best_save_base )
        except Exception as e :
            print (f"Auto-download notice: {e }")

if __name__ =="__main__":
    train_storage_optimizer ()
