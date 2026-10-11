"""
Smart Storage Optimization for Modern Workloads
Developer 5 - Streamlit Dashboard + Module Integration

Flow:
Upload CSV -> Validation -> Workload Analysis -> Optimization
-> Cost Calculation -> Migration Simulation -> Dashboard

This file ONLY imports and calls the other developers' modules.
If a teammate's function name differs from the ones below, add it to
FUNCTION_MAP (one line) - no other change is needed.
"""

import os 
import tempfile 

import pandas as pd 
import plotly .express as px 
import plotly .graph_objects as go 
import streamlit as st 




IMPORT_ERRORS ={}
try :
    from src import data_loader 
except Exception as e :
    data_loader ,IMPORT_ERRORS ["data_loader"]=None ,e 
try :
    from src import workload_analyzer 
except Exception as e :
    workload_analyzer ,IMPORT_ERRORS ["workload_analyzer"]=None ,e 
try :
    from src import optimizer 
except Exception as e :
    optimizer ,IMPORT_ERRORS ["optimizer"]=None ,e 
try :
    from src import cost_calculator 
except Exception as e :
    cost_calculator ,IMPORT_ERRORS ["cost_calculator"]=None ,e 
try :
    from src import migration_simulator 
except Exception as e :
    migration_simulator ,IMPORT_ERRORS ["migration_simulator"]=None ,e 


FUNCTION_MAP ={
"load":[
"load_data",
"load_csv",
"load_workload",
"load_dataset",
"read_csv",
],

"validate":[
"validate_data",
"validate_dataframe",
"validate_workload",
"validate",
],

"analyze":[
"analyze_workload",
"analyze",
"run_analysis",
"analyse_workload",
],

"optimize":[
"generate_recommendation",
"optimize_storage",
"optimize",
"run_optimization",
"optimize_workload",
"recommend_tiers",
"classify_datasets",
],

"cost":[
"calculate_costs",
"calculate_cost",
"compute_costs",
"cost_summary",
"calculate_savings",
],

"migrate":[
"simulate_migration",
"migration_plan",
"generate_migration_plan",
"run_simulation",
"simulate",
],
}




TIERS =["HOT","WARM","COLD","ARCHIVE"]
TIER_EMOJI ={"HOT":"","WARM":"️","COLD":"️","ARCHIVE":"️"}
TIER_COLORS ={"HOT":"#EF4444","WARM":"#F59E0B","COLD":"#3B82F6","ARCHIVE":"#8B5CF6"}

ALIASES ={
"file_name":["file_name","filename","file","dataset","dataset_name","name","path"],
"size_gb":["size_gb","size","storage_gb","total_size_gb","size_in_gb"],
"current_tier":["current_tier","tier","storage_tier","current_storage_tier"],
"recommended_tier":["recommended_tier","optimized_tier","new_tier","target_tier",
"optimal_tier","classification"],
"optimization_score":["optimization_score","score","opt_score","optimisation_score"],
"reason":["reason","recommendation_reason","explanation","rationale"],
"current_cost":["current_cost","current_monthly_cost","cost_current","current_total_cost"],
"optimized_cost":["optimized_cost","recommended_cost","new_cost","optimised_cost",
"optimized_monthly_cost"],
"estimated_savings":["estimated_savings","savings","potential_savings","monthly_savings"],
}

st .set_page_config (page_title ="Smart Storage Optimizer",page_icon ="",layout ="wide")

st .markdown (
"""
    <style>
    .block-container {padding-top: 1.6rem;}
    .hero {background: linear-gradient(135deg,#4F46E5 0%,#7C3AED 55%,#EC4899 100%);
           padding: 1.6rem 2rem; border-radius: 18px; color: #fff; margin-bottom: 1.2rem;}
    .hero h1 {margin: 0; font-size: 2rem;}
    .hero p {margin: .3rem 0 0 0; opacity: .92;}
    div[data-testid="stMetric"] {background: rgba(124,58,237,.07); border: 1px solid rgba(124,58,237,.18);
           padding: .8rem 1rem; border-radius: 14px;}
    .stButton>button {border-radius: 10px; font-weight: 600;}
    </style>
    <div class="hero">
      <h1> Smart Storage Optimization</h1>
      <p>Upload a workload, classify datasets into HOT / WARM / COLD / ARCHIVE, and see the savings - simulated, never moved.</p>
    </div>
    """,
unsafe_allow_html =True ,
)





def call_stage (module ,stage ,*args ,required =True ):
    """Call the first matching function of `module` for `stage`."""
    if module is None :
        if required :
            raise RuntimeError (f"Module for stage '{stage }' could not be imported.")
        return None 
    for name in FUNCTION_MAP [stage ]:
        fn =getattr (module ,name ,None )
        if callable (fn ):
            return fn (*args )
    if required :
        public =[n for n in dir (module )if not n .startswith ("_")and callable (getattr (module ,n ))]
        raise AttributeError (
        f"No function found for stage '{stage }'. Tried {FUNCTION_MAP [stage ]}. "
        f"Available in module: {public }. Add the right name to FUNCTION_MAP in app.py."
        )
    return None 


def normalize_columns (df :pd .DataFrame )->pd .DataFrame :
    """Rename teammates' column names to the dashboard's canonical names."""
    df =df .copy ()
    lower ={c :str (c ).strip ().lower ().replace (" ","_")for c in df .columns }
    df .columns =[lower [c ]for c in df .columns ]
    for canon ,options in ALIASES .items ():
        if canon in df .columns :
            continue 
        for opt in options :
            if opt in df .columns :
                df =df .rename (columns ={opt :canon })
                break 

    if "size_gb"not in df .columns :
        if "size_mb"in df .columns :
            df ["size_gb"]=pd .to_numeric (df ["size_mb"],errors ="coerce")/1024 
        elif "size_tb"in df .columns :
            df ["size_gb"]=pd .to_numeric (df ["size_tb"],errors ="coerce")*1024 
        elif "size_bytes"in df .columns :
            df ["size_gb"]=pd .to_numeric (df ["size_bytes"],errors ="coerce")/1024 **3 
    for tier_col in ("current_tier","recommended_tier"):
        if tier_col in df .columns :
            df [tier_col ]=df [tier_col ].astype (str ).str .strip ().str .upper ()
    return df 


def merge_result (base :pd .DataFrame ,result ):
    """Merge a stage output into the working frame. Returns (frame, summary_dict)."""
    summary ={}
    if result is None :
        return base ,summary 
    if isinstance (result ,tuple ):
        for part in result :
            base ,extra =merge_result (base ,part )
            summary .update (extra )
        return base ,summary 
    if isinstance (result ,dict ):
        return base ,result 
    if isinstance (result ,pd .DataFrame ):
        res =normalize_columns (result )
        if len (res )==len (base ):
            res .index =base .index 
            for col in res .columns :
                base [col ]=res [col ]
        return base ,summary 
    return base ,summary 


def find_in_summary (summary :dict ,canon :str ):
    for key ,val in (summary or {}).items ():
        k =str (key ).strip ().lower ().replace (" ","_")
        if k in ALIASES [canon ]or k ==f"total_{canon }":
            if isinstance (val ,(int ,float )):
                return float (val )
    return None 


def load_uploaded (upload )->pd .DataFrame :
    """Use data_loader; fall back to a temp file path if it expects a path."""
    try :
        upload .seek (0 )
        out =call_stage (data_loader ,"load",upload ,required =False )
        if isinstance (out ,pd .DataFrame ):
            return out 
    except Exception :
        pass 
    tmp =tempfile .NamedTemporaryFile (delete =False ,suffix =".csv")
    upload .seek (0 )
    tmp .write (upload .read ())
    tmp .close ()
    try :
        out =call_stage (data_loader ,"load",tmp .name ,required =False )
        if isinstance (out ,pd .DataFrame ):
            return out 
    finally :
        os .unlink (tmp .name )
    upload .seek (0 )
    return pd .read_csv (upload )


def validate (df :pd .DataFrame ):
    out =call_stage (data_loader ,"validate",df ,required =False )
    if isinstance (out ,pd .DataFrame ):
        return out ,True ,"Validation passed"
    if isinstance (out ,tuple )and len (out )>=2 and isinstance (out [0 ],bool ):
        return df ,out [0 ],str (out [1 ])
    if isinstance (out ,tuple )and len (out )>=1 and isinstance (out [0 ],pd .DataFrame ):
        return out [0 ],True ,"Validation passed"
    if isinstance (out ,bool ):
        return df ,out ,"Validation passed"if out else "Validation failed"
    return df ,True ,"Validation passed"


def tier_storage (df ,tier_col ):
    if tier_col not in df .columns or "size_gb"not in df .columns :
        return pd .Series (0.0 ,index =TIERS )
    s =df .groupby (tier_col )["size_gb"].sum ().reindex (TIERS ).fillna (0 )
    return s 


def tier_counts (df ,tier_col ):
    if tier_col not in df .columns :
        return pd .Series (0 ,index =TIERS )
    return df [tier_col ].value_counts ().reindex (TIERS ).fillna (0 ).astype (int )





def step_load_validate (upload ):
    raw =load_uploaded (upload )
    raw ,ok ,msg =validate (raw )
    df =normalize_columns (raw )
    st .session_state .update (df =df ,valid =ok ,valid_msg =msg ,analyzed =False ,optimized =False ,
    summary ={},migration =None )


def step_analyze ():
    df =st .session_state ["df"].copy ()
    result =call_stage (workload_analyzer ,"analyze",df )
    df ,summary =merge_result (df ,result )
    st .session_state .update (df =df ,analyzed =True ,analysis_summary =summary )


def step_optimize ():
    df =st .session_state ["df"].copy ()
    result =call_stage (optimizer ,"optimize",df )
    df ,_ =merge_result (df ,result )

    cost_result =call_stage (cost_calculator ,"cost",df ,required =False )
    df ,summary =merge_result (df ,cost_result )

    mig =call_stage (migration_simulator ,"migrate",df ,required =False )
    mig_df =None 
    if isinstance (mig ,pd .DataFrame ):
        mig_df =normalize_columns (mig )
    elif isinstance (mig ,tuple ):
        mig_df =next ((normalize_columns (p )for p in mig if isinstance (p ,pd .DataFrame )),None )

    st .session_state .update (df =df ,optimized =True ,summary =summary ,migration =mig_df )





with st .sidebar :
    st .header (" 1. Upload workload")
    upload =st .file_uploader ("Workload CSV",type =["csv"])
    if upload is not None and st .session_state .get ("_file")!=(upload .name ,upload .size ):
        try :
            with st .spinner ("Loading & validating..."):
                step_load_validate (upload )
            st .session_state ["_file"]=(upload .name ,upload .size )
        except Exception as exc :
            st .session_state .pop ("df",None )
            st .error (f"Could not load file: {exc }")

    st .divider ()
    st .header ("️ 2. Pipeline")
    has_data ="df"in st .session_state and st .session_state .get ("valid",False )
    run_all =st .button (" Run full pipeline",type ="primary",disabled =not has_data ,
    use_container_width =True )
    run_analysis =st .button (" Run workload analysis",disabled =not has_data ,
    use_container_width =True )
    run_opt =st .button (" Run optimization engine",
    disabled =not (has_data and st .session_state .get ("analyzed")),
    use_container_width =True )

    if IMPORT_ERRORS :
        st .warning ("Module import problems:\n\n"+"\n".join (f"- {k }: {v }"for k ,v in IMPORT_ERRORS .items ()))

try :
    if run_all or run_analysis :
        with st .spinner ("Analyzing workload..."):
            step_analyze ()
    if run_all or run_opt :
        with st .spinner ("Optimizing, calculating costs, simulating migration..."):
            step_optimize ()
except Exception as exc :
    st .error (f"Pipeline error: {exc }")




if "df"not in st .session_state :
    st .info (" Upload a workload CSV in the sidebar to get started.")
    st .stop ()

df =st .session_state ["df"]
if not st .session_state .get ("valid",True ):
    st .error (f" Data validation failed: {st .session_state .get ('valid_msg')}")
    st .stop ()
st .success (f" {st .session_state .get ('valid_msg','Validation passed')}")


st .subheader (" Workload overview")
total_storage =float (df ["size_gb"].sum ())if "size_gb"in df .columns else 0.0 
c1 ,c2 ,c3 =st .columns (3 )
c1 .metric ("Files / datasets",f"{len (df ):,}")
c2 .metric ("Total storage",f"{total_storage :,.2f} GB")
c3 .metric ("Tiers in use",int (df ["current_tier"].nunique ())if "current_tier"in df .columns else "n/a")

if "current_tier"in df .columns :
    cur =tier_storage (df ,"current_tier").reset_index ()
    cur .columns =["tier","storage_gb"]
    left ,right =st .columns ([1 ,1 ])
    with left :
        fig =px .pie (cur ,names ="tier",values ="storage_gb",hole =0.55 ,color ="tier",
        color_discrete_map =TIER_COLORS ,title ="Current storage distribution")
        st .plotly_chart (fig ,use_container_width =True )
    with right :
        st .markdown ("**Data preview**")
        st .dataframe (df .head (50 ),use_container_width =True ,height =330 )
else :
    st .dataframe (df .head (50 ),use_container_width =True )

if st .session_state .get ("analyzed"):
    st .subheader (" Workload analysis")
    st .caption ("Output of workload_analyzer is merged into the table below.")
    summ =st .session_state .get ("analysis_summary")or {}
    if summ :
        st .json (summ ,expanded =False )
    st .dataframe (df ,use_container_width =True ,height =300 )


if not st .session_state .get ("optimized"):
    st .info ("Run the workload analysis, then the optimization engine from the sidebar "
    "(or use **Run full pipeline**).")
    st .stop ()

if "recommended_tier"not in df .columns :
    st .error ("The optimizer did not return a recommended tier column. "
    "Expected one of: "+", ".join (ALIASES ["recommended_tier"]))
    st .stop ()

summary =st .session_state .get ("summary",{})
name_col ="file_name"if "file_name"in df .columns else None 
if name_col is None :
    df =df .copy ()
    df .insert (0 ,"file_name",[f"dataset_{i +1 }"for i in range (len (df ))])

st .divider ()
st .subheader ("️ Tier classification")
counts =tier_counts (df ,"recommended_tier")
cols =st .columns (4 )
for col ,tier in zip (cols ,TIERS ):
    col .metric (f"{TIER_EMOJI [tier ]} {tier }",int (counts [tier ]))

tabs =st .tabs ([f"{TIER_EMOJI [t ]} {t }"for t in TIERS ])
show_cols =[c for c in ["file_name","size_gb","current_tier","recommended_tier",
"optimization_score","reason"]if c in df .columns ]
for tab ,tier in zip (tabs ,TIERS ):
    with tab :
        sub =df [df ["recommended_tier"]==tier ][show_cols ]
        if sub .empty :
            st .caption ("No datasets in this tier.")
        else :
            st .dataframe (sub ,use_container_width =True ,hide_index =True )


if "optimization_score"in df .columns :
    st .subheader (" Optimization score per dataset")
    sc =df [["file_name","optimization_score","recommended_tier"]].sort_values (
    "optimization_score",ascending =False )
    top =sc .head (30 )
    fig =px .bar (top ,x ="file_name",y ="optimization_score",color ="recommended_tier",
    color_discrete_map =TIER_COLORS ,title ="Optimization score (top 30)")
    fig .update_layout (xaxis_title =None )
    st .plotly_chart (fig ,use_container_width =True )
    with st .expander ("See all scores"):
        st .dataframe (sc ,use_container_width =True ,hide_index =True )


st .subheader (" Recommendations")
rec_cols =[c for c in ["file_name","current_tier","recommended_tier","reason"]if c in df .columns ]
rec =df [rec_cols ].copy ()
if "reason"not in rec .columns :
    rec ["reason"]="Not provided by optimizer"
rec =rec .rename (columns ={"file_name":"File","current_tier":"Current Tier",
"recommended_tier":"Recommended Tier","reason":"Reason"})
only_changes =st .toggle ("Show only datasets that change tier",value =False )
if only_changes and "Current Tier"in rec .columns :
    rec =rec [rec ["Current Tier"]!=rec ["Recommended Tier"]]
st .dataframe (rec ,use_container_width =True ,hide_index =True )


st .subheader (" Cost metrics")
cur_cost =df ["current_cost"].sum ()if "current_cost"in df .columns else find_in_summary (summary ,"current_cost")
opt_cost =df ["optimized_cost"].sum ()if "optimized_cost"in df .columns else find_in_summary (summary ,"optimized_cost")
savings =(df ["estimated_savings"].sum ()if "estimated_savings"in df .columns 
else find_in_summary (summary ,"estimated_savings"))
if savings is None and cur_cost is not None and opt_cost is not None :
    savings =cur_cost -opt_cost 

m1 ,m2 ,m3 ,m4 =st .columns (4 )
fmt =lambda v :f"${v :,.2f}"if v is not None else "n/a"
m1 .metric ("Current cost",fmt (cur_cost ))
m2 .metric ("Optimized cost",fmt (opt_cost ))
m3 .metric ("Potential savings",fmt (savings ))
m4 .metric ("Savings %",f"{(savings /cur_cost *100 ):.1f}%"if cur_cost and savings is not None else "n/a")
if cur_cost is None :
    st .warning ("cost_calculator did not return cost values the dashboard could read. "
    "Expected columns like current_cost / optimized_cost or a summary dict.")


st .subheader (" Charts")
cur_store =tier_storage (df ,"current_tier")
rec_store =tier_storage (df ,"recommended_tier")
ch1 ,ch2 =st .columns (2 )

with ch1 :
    fig =px .bar (rec_store .reset_index ().rename (columns ={"index":"tier","recommended_tier":"tier",
    "size_gb":"GB"}),
    x ="tier",y ="GB",color ="tier",color_discrete_map =TIER_COLORS ,
    title ="Storage by tier (recommended)")
    fig .update_layout (showlegend =False ,xaxis_title =None ,yaxis_title ="GB")
    st .plotly_chart (fig ,use_container_width =True )

with ch2 :
    fig =go .Figure ()
    fig .add_bar (name ="Current",x =TIERS ,y =cur_store .values ,marker_color ="#94A3B8")
    fig .add_bar (name ="Recommended",x =TIERS ,y =rec_store .values ,marker_color ="#7C3AED")
    fig .update_layout (barmode ="group",title ="Current vs recommended storage (GB)")
    st .plotly_chart (fig ,use_container_width =True )

ch3 ,ch4 =st .columns (2 )
with ch3 :
    if cur_cost is not None and opt_cost is not None :
        fig =go .Figure (go .Bar (x =["Current","Optimized"],y =[cur_cost ,opt_cost ],
        marker_color =["#EF4444","#10B981"],
        text =[f"${cur_cost :,.2f}",f"${opt_cost :,.2f}"],textposition ="outside"))
        fig .update_layout (title ="Cost comparison",yaxis_title ="Cost")
        st .plotly_chart (fig ,use_container_width =True )
    else :
        st .info ("Cost comparison unavailable (no cost data).")
with ch4 :
    cnt =pd .DataFrame ({"tier":TIERS ,"datasets":counts .values })
    fig =px .bar (cnt ,x ="tier",y ="datasets",color ="tier",color_discrete_map =TIER_COLORS ,
    text ="datasets",title ="Number of datasets per tier")
    fig .update_layout (showlegend =False ,xaxis_title =None )
    st .plotly_chart (fig ,use_container_width =True )


st .divider ()
st .subheader (" Migration simulation")
st .caption (" Simulation only - no real files are moved.")
st .markdown ("### Recommended Migration Plan")

mig =st .session_state .get ("migration")
if mig is None or mig .empty :
    mig =df .copy ()
if "file_name"not in mig .columns :
    mig .insert (0 ,"file_name",df ["file_name"].values if len (mig )==len (df )else range (len (mig )))
plan_cols =["file_name","current_tier","recommended_tier","estimated_savings"]
for c in plan_cols :
    if c not in mig .columns :
        mig [c ]=df [c ].values if (c in df .columns and len (df )==len (mig ))else None 
plan =mig [plan_cols ]
plan =plan [plan ["current_tier"]!=plan ["recommended_tier"]]

p1 ,p2 =st .columns (2 )
p1 .metric ("Datasets to migrate",len (plan ))
p2 .metric ("Estimated savings from plan",
fmt (pd .to_numeric (plan ["estimated_savings"],errors ="coerce").sum ())
if plan ["estimated_savings"].notna ().any ()else "n/a")
if plan .empty :
    st .success ("Everything is already in its optimal tier. ")
else :
    st .dataframe (plan ,use_container_width =True ,hide_index =True )


st .divider ()
st .subheader (" Final optimization report")
report =df .copy ()
if "estimated_savings"not in report .columns and {"current_cost","optimized_cost"}<=set (report .columns ):
    report ["estimated_savings"]=report ["current_cost"]-report ["optimized_cost"]
st .download_button ("⬇️ Download report (CSV)",data =report .to_csv (index =False ).encode ("utf-8"),
file_name ="storage_optimization_report.csv",mime ="text/csv",type ="primary")
