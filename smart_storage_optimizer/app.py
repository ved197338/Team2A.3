"""
SmartStore AI -- Intelligent Storage Optimization System (Streamlit dashboard)
==============================================================================
Flow:
  Upload CSV -> validation -> workload analysis -> demand forecast (optional)
  -> recommendations (optimizer + SLA + policy) -> costs/TCO -> migration simulation
  -> strategy comparison -> approval workflow

Everything is a SIMULATION. No data is ever moved, deleted or modified.
All money values are ESTIMATES from the prices you configure (demo prices by default).
Run:  streamlit run app.py
"""

import itertools 
import os 

import numpy as np 
import pandas as pd 
import plotly .express as px 
import plotly .graph_objects as go 
import streamlit as st 

st .set_page_config (page_title ="SmartStore AI",page_icon ="",layout ="wide")

APP_DIR =os .path .dirname (os .path .abspath (__file__ ))




try :
    from src import approval_workflow ,data_loader ,demand_forecaster ,pipeline ,strategy_comparison 
    from src .cost_calculator import DEMO_PRICE_PER_GB_MONTH ,PricingConfig 
    from src .performance_sla import DEFAULT_TIER_PROFILES ,TIER_PROFILE_NOTE 
    from src .policy_engine import POLICY_DISCLAIMER ,PolicyConfig 
    from src .recommendation_engine import EngineSettings 
    from src .tco_calculator import ESTIMATE_LABEL ,CostAssumptions 
except Exception as exc :
    st .error (f"A project module could not be imported: {exc }\n\n"
    "Run the app from the project folder (the one containing app.py and the src folder) "
    "and install the packages with: pip install -r requirements.txt")
    st .stop ()




TIERS =["HOT","WARM","COLD","ARCHIVE"]
TIER_EMOJI ={"HOT":"","WARM":"️","COLD":"️","ARCHIVE":"️"}
TIER_COLORS ={"HOT":"#EF4444","WARM":"#F59E0B","COLD":"#3B82F6","ARCHIVE":"#8B5CF6"}
ACTION_EMOJI ={"KEEP":" KEEP","PROMOTE":"⬆️ PROMOTE","DEMOTE":"⬇️ DEMOTE","REVIEW":" REVIEW","BLOCKED":" BLOCKED"}
ACTION_COLORS ={"KEEP":"#10B981","PROMOTE":"#F59E0B","DEMOTE":"#3B82F6","REVIEW":"#8B5CF6","BLOCKED":"#EF4444"}
STATUS_COLORS ={"PASS":"#10B981","WARN":"#F59E0B","FAIL":"#EF4444",
"MEETS":"#10B981","NEEDS_DATA":"#F59E0B","MAY_VIOLATE":"#EF4444"}
SAMPLE_WORKLOAD =os .path .join (APP_DIR ,"sample_workload.csv")
SAMPLE_HISTORY =os .path .join (APP_DIR ,"sample_demand_history.csv")
INACTIVE_DAYS_DEFAULT =90 

st .markdown (
"""
    <style>
    .block-container {padding-top: 1.6rem;}
    .hero {background: linear-gradient(135deg,#4F46E5 0%,#7C3AED 55%,#EC4899 100%);
           padding: 1.6rem 2rem; border-radius: 18px; color: #fff; margin-bottom: 1.0rem;}
    .hero h1 {margin: 0; font-size: 2rem;}
    .hero p {margin: .3rem 0 0 0; opacity: .92;}
    div[data-testid="stMetric"] {background: rgba(124,58,237,.07); border: 1px solid rgba(124,58,237,.18);
           padding: .8rem 1rem; border-radius: 14px;}
    .stButton>button {border-radius: 10px; font-weight: 600;}
    .sim-banner {background: rgba(16,185,129,.10); border: 1px solid rgba(16,185,129,.35);
           padding: .6rem 1rem; border-radius: 12px; margin-bottom: .8rem;}
    </style>
    <div class="hero">
      <h1> SmartStore AI</h1>
      <p>Intelligent storage optimization: explainable HOT / WARM / COLD / ARCHIVE recommendations that balance
      cost, performance, compliance, future demand and migration overhead - simulated, never moved.</p>
    </div>
    """,
unsafe_allow_html =True ,
)




_chart_ids =itertools .count ()


def plot (fig ,height =None ):
    fig .update_layout (margin =dict (l =10 ,r =10 ,t =50 ,b =10 ))
    if height :
        fig .update_layout (height =height )
    key =f"chart_{next (_chart_ids )}"
    try :
        st .plotly_chart (fig ,width ="stretch",key =key )
    except TypeError :
        st .plotly_chart (fig ,use_container_width =True ,key =key )


def table (df ,height =None ):
    kwargs ={"hide_index":True }
    if height :
        kwargs ["height"]=height 
    try :
        st .dataframe (df ,width ="stretch",**kwargs )
    except TypeError :
        st .dataframe (df ,use_container_width =True ,**kwargs )


def money (v ):
    if v is None or (isinstance (v ,float )and not np .isfinite (v )):
        return "n/a"
    return f"-${abs (v ):,.2f}"if v <0 else f"${v :,.2f}"


def tier_storage (df ,col ):
    if col not in df .columns or df .empty :
        return pd .Series (0.0 ,index =TIERS )
    return df .groupby (col )["size_gb"].sum ().reindex (TIERS ).fillna (0 )


def bad_tier_note (df ):
    n =int ((~df ["current_tier"].isin (TIERS )).sum ())
    return f"{n } dataset(s) have an unknown current tier and are excluded from cost totals."if n else ""





for key ,default in {"wl_df":None ,"wl_issues":[],"history":None ,"history_msgs":[],
"source_name":None ,"ran":False ,"approvals":{},"_wl_sig":None ,"_hist_sig":None }.items ():
    st .session_state .setdefault (key ,default )


def load_workload (source ,name ):
    df ,issues =data_loader .load_and_validate_workload_data (source )
    st .session_state .update (wl_df =df ,wl_issues =issues ,source_name =name ,ran =False ,approvals ={})


def load_history (source ):
    hist ,msgs =demand_forecaster .load_history (source )
    st .session_state .update (history =hist if not hist .empty else None ,history_msgs =msgs )





with st .sidebar :
    st .header (" 1. Load workload")
    upload =st .file_uploader ("Workload CSV",type =["csv"],key ="wl_upload")
    hist_upload =st .file_uploader ("Demand history CSV (optional)",type =["csv"],key ="hist_upload",
    help ="Monthly history: date, file_name, access_count, optional size_gb. Enables demand forecasting.")
    if st .button (" Use bundled SYNTHETIC sample data",key ="btn_sample"):
        try :
            load_workload (SAMPLE_WORKLOAD ,"sample_workload.csv (synthetic)")
            if os .path .exists (SAMPLE_HISTORY ):
                load_history (SAMPLE_HISTORY )
            st .session_state ["_wl_sig"]=st .session_state ["_hist_sig"]="sample"
        except FileNotFoundError as exc :
            st .error (f"Sample file not found: {exc }")

    if upload is not None and st .session_state ["_wl_sig"]!=(upload .name ,upload .size ):
        try :
            load_workload (upload ,upload .name )
            st .session_state ["_wl_sig"]=(upload .name ,upload .size )
        except Exception as exc :
            st .session_state ["wl_df"]=None 
            st .error (f"Could not read the workload file: {exc }")
    if hist_upload is not None and st .session_state ["_hist_sig"]!=(hist_upload .name ,hist_upload .size ):
        try :
            load_history (hist_upload )
            st .session_state ["_hist_sig"]=(hist_upload .name ,hist_upload .size )
        except Exception as exc :
            st .error (f"Could not read the history file: {exc }")

    st .divider ()
    st .header ("️ 2. Pricing & assumptions")
    st .caption ("DEMO values - not real cloud prices. Edit freely; blank performance cells mean 'not configured' "
    "(decisions then become uncertain, never assumed safe).")
    base_tbl =pd .DataFrame ({
    "tier":TIERS ,
    "price_per_gb_month":[DEMO_PRICE_PER_GB_MONTH [t ]for t in TIERS ],
    "retrieval_per_gb":[0.0 ,0.0 ,0.01 ,0.03 ],
    "latency_ms":[DEFAULT_TIER_PROFILES [t ]["latency_ms"]for t in TIERS ],
    "max_iops":[DEFAULT_TIER_PROFILES [t ]["max_iops"]for t in TIERS ],
    "max_throughput_mbps":[DEFAULT_TIER_PROFILES [t ]["max_throughput_mbps"]for t in TIERS ],
    "recovery_hours":[DEFAULT_TIER_PROFILES [t ]["recovery_hours"]for t in TIERS ],
    "capacity_gb":[0.0 ,0.0 ,0.0 ,0.0 ],
    })
    tier_tbl =st .data_editor (base_tbl ,disabled =["tier"],hide_index =True ,key ="tier_tbl")
    st .caption ("capacity_gb: 0 = not configured (no shortage check).")
    transfer_price =st .number_input ("Transfer price per GB",0.0 ,10.0 ,0.02 ,0.005 ,format ="%.3f")
    bandwidth =st .number_input ("Migration bandwidth (Mbps)",1.0 ,400000.0 ,1000.0 ,100.0 )
    efficiency =st .slider ("Usable share of bandwidth",0.1 ,1.0 ,0.7 ,0.05 )
    horizon_months =st .slider ("TCO horizon (months)",1 ,60 ,12 )
    max_be =st .slider ("Max break-even for a demotion (months)",1 ,60 ,12 )
    premium_tier =st .selectbox ("Premium tier for all-fast baseline",TIERS ,index =0 )
    forecast_horizon =st .slider ("Forecast horizon (months)",1 ,12 ,6 )
    ref_mode =st .radio ("Reference date for recency",["Latest access in file + 1 day","Today"],index =0 ,
    help ="Use the first option for stable demos with fixed sample data.")

    st .divider ()
    st .header (" 3. Filters")
    f_tier =st .multiselect ("Current tier",TIERS ,default =TIERS )
    f_wl =st .multiselect ("Workload type",sorted (st .session_state ["wl_df"]["workload_type"].unique ())
    if st .session_state ["wl_df"]is not None and not st .session_state ["wl_df"].empty else [])
    f_action =st .multiselect ("Recommendation action",list (ACTION_EMOJI ),default =list (ACTION_EMOJI ))
    f_policy =st .multiselect ("Policy status",["PASS","WARN","FAIL"],default =["PASS","WARN","FAIL"])
    st .caption ("Filters change the tables and charts that list datasets; cost totals always cover all datasets.")

    st .divider ()
    st .header (" 4. Run")
    has_data =st .session_state ["wl_df"]is not None and not st .session_state ["wl_df"].empty 
    if st .button (" Run full pipeline",type ="primary",disabled =not has_data ,key ="btn_run"):
        st .session_state ["ran"]=True 





def build_settings (payload ):
    t =pd .DataFrame (payload ["tiers"]).set_index ("tier")
    prices ={k :float (t .loc [k ,"price_per_gb_month"])for k in TIERS }
    pricing =PricingConfig (prices_per_gb_month =prices ,source_note =(
    "Prices entered in the sidebar. DEMO defaults unless changed; not real cloud-provider prices."))
    cost =CostAssumptions (
    transfer_price_per_gb =payload ["transfer_price"],
    retrieval_price_per_gb ={k :float (t .loc [k ,"retrieval_per_gb"])for k in TIERS },
    bandwidth_mbps =payload ["bandwidth"],bandwidth_efficiency =payload ["efficiency"],
    horizon_months =payload ["horizon"],max_break_even_months =payload ["max_be"],
    premium_tier =payload ["premium"])
    profiles ={k :{c :(float (t .loc [k ,c ])if pd .notna (t .loc [k ,c ])else np .nan )
    for c in ["latency_ms","max_iops","max_throughput_mbps","recovery_hours"]}for k in TIERS }
    return EngineSettings (pricing =pricing ,cost =cost ,policy =PolicyConfig (tier_profiles =profiles ),
    tier_profiles =profiles ,reference_date =pd .Timestamp (payload ["reference_date"]))


@st .cache_data (show_spinner =False )
def compute (df ,history ,payload ):
    settings =build_settings (payload )
    caps ={k :float (v )for k ,v in zip (payload ["tiers"]["tier"],payload ["tiers"]["capacity_gb"])}
    return pipeline .run_pipeline (df ,history ,settings ,payload ["forecast_horizon"],caps )





df =st .session_state ["wl_df"]
st .markdown ('<div class="sim-banner"> <b>Simulation only.</b> '+approval_workflow .SIMULATION_NOTICE +
' All costs are <b>estimates</b> from the configured (demo) prices.</div>',unsafe_allow_html =True )

if df is None :
    st .info (" Upload a workload CSV, or click **Use bundled SYNTHETIC sample data** in the sidebar, to get started.")
    st .markdown ("**Required columns:** `file_name, size_gb, last_accessed, access_count, workload_type, "
    "performance_requirement, current_tier`  \n"
    "**Optional columns** (enable SLA, policy and cost checks): `read_frequency, write_frequency, read_iops, "
    "write_iops, throughput_mbps, observed_latency_ms, max_latency_ms, growth_rate_pct, retention_days, "
    "recovery_time_hours, legal_hold, required_region, current_region, security_class, approved_tiers, "
    "migration_cost`")
    st .stop ()

issues =st .session_state ["wl_issues"]
errors =[m for m in issues if m .startswith ("[ERROR]")]
warns =[m for m in issues if m .startswith ("[WARNING]")]
if df .empty :
    st .error (" No usable rows. Please fix the file and upload it again.")
    for m in issues :
        st .write (m )
    st .stop ()
info_line =next ((m for m in reversed (issues )if m .startswith ("[INFO]")and "valid"in m ),"Validation finished")
st .success (f" {info_line .replace ('[INFO] ','')} - source: {st .session_state ['source_name']}")
if errors or warns or st .session_state ["history_msgs"]:
    with st .expander (f"Validation messages ({len (errors )} errors, {len (warns )} warnings)"):
        for m in issues +st .session_state ["history_msgs"]:
            st .write (m )
if "data_source"in df .columns and df ["data_source"].astype (str ).str .upper ().eq ("SYNTHETIC").any ():
    st .warning (" This workload is SYNTHETIC test data (invented for demonstration). It does not describe real systems.")

if not st .session_state ["ran"]:
    st .subheader ("Data preview")
    table (df .head (50 ),height =320 )
    st .info ("Click ** Run full pipeline** in the sidebar.")
    st .stop ()

payload ={
"tiers":tier_tbl .to_dict (orient ="list"),
"transfer_price":float (transfer_price ),"bandwidth":float (bandwidth ),"efficiency":float (efficiency ),
"horizon":int (horizon_months ),"max_be":float (max_be ),"premium":premium_tier ,
"forecast_horizon":int (forecast_horizon ),
"reference_date":str (pipeline .resolve_reference_date (df ,use_today =(ref_mode =="Today")).date ()),
}
price_vals =pd .to_numeric (tier_tbl ["price_per_gb_month"],errors ="coerce")
if price_vals .isna ().any ()or (price_vals <0 ).any ():
    st .error ("Every storage price must be a non-negative number. Fix the pricing table in the sidebar.")
    st .stop ()
try :
    with st .spinner ("Running analysis, recommendations, costing and simulation..."):
        res =compute (df ,st .session_state ["history"],payload )
except Exception as exc :
    st .error (f"Pipeline error: {exc }")
    st .stop ()

recs ,cs ,demand =res ["recommendations"],res ["cost_summary"],res ["demand"]


def apply_filters (frame ):
    mask =frame ["current_tier"].isin (f_tier +["UNKNOWN"]if len (f_tier )==len (TIERS )else f_tier )
    if f_wl :
        mask &=frame ["workload_type"].isin (f_wl )
    mask &=frame ["action"].isin (f_action )&frame ["policy_status"].isin (f_policy )
    return frame [mask ]


view =apply_filters (recs )

(t_over ,t_work ,t_rec ,t_cost ,t_comp ,t_fore ,t_mig ,t_cmp )=st .tabs ([
" Overview"," Workload Analysis"," Recommendations"," Cost Optimization",
"️ Compliance & SLA"," Demand Forecasting"," Migration Simulation","️ Strategy Comparison"])


with t_over :
    st .subheader ("Overview")
    c =st .columns (5 )
    c [0 ].metric ("Datasets",f"{len (recs ):,}")
    c [1 ].metric ("Total storage",f"{recs ['size_gb'].sum ()/1000 :,.2f} TB")
    c [2 ].metric ("Current cost / month",money (cs ["total_current_cost"]))
    c [3 ].metric ("Optimized cost / month",money (cs ["total_optimized_cost"]))
    c [4 ].metric ("Est. monthly savings",money (cs ["monthly_savings"]),f"{cs ['savings_percent']:.1f}%")
    c =st .columns (5 )
    n_moves =int (recs ["action"].isin (["PROMOTE","DEMOTE"]).sum ())
    c [0 ].metric ("Moves proposed",n_moves )
    c [1 ].metric (" Blocked",int ((recs ["action"]=="BLOCKED").sum ()))
    c [2 ].metric (" Need review",int ((recs ["action"]=="REVIEW").sum ()))
    c [3 ].metric ("Policy failures",int ((recs ["policy_status"]=="FAIL").sum ()))
    c [4 ].metric ("Net after migration (TCO)",money (cs ["tco_savings"]),f"{cs ['horizon_months']} months")
    st .caption (ESTIMATE_LABEL )
    note =bad_tier_note (recs )
    if note :
        st .caption ("️ "+note )

    l ,r =st .columns (2 )
    with l :
        cur ,rec_s =tier_storage (recs ,"current_tier"),tier_storage (recs ,"recommended_tier")
        fig =go .Figure ()
        fig .add_bar (name ="Current",x =TIERS ,y =cur .values ,marker_color ="#94A3B8")
        fig .add_bar (name ="Recommended",x =TIERS ,y =rec_s .values ,marker_color ="#7C3AED")
        fig .update_layout (barmode ="group",title ="Storage by tier (GB): current vs recommended")
        plot (fig )
    with r :
        counts =recs ["action"].value_counts ().reindex (list (ACTION_EMOJI )).fillna (0 ).reset_index ()
        counts .columns =["action","datasets"]
        fig =px .bar (counts ,x ="action",y ="datasets",color ="action",color_discrete_map =ACTION_COLORS ,
        text ="datasets",title ="Recommended actions")
        fig .update_layout (showlegend =False ,xaxis_title =None )
        plot (fig )

    st .markdown ("**Key findings (calculated from this workload)**")
    top =recs .sort_values ("net_monthly_savings",ascending =False ).head (3 )
    for _ ,row in top [top ["net_monthly_savings"]>0 ].iterrows ():
        st .write (f"- {row ['file_name']}: {row ['action'].title ()} {row ['current_tier']} → {row ['recommended_tier']} "
        f"saves about {money (row ['net_monthly_savings'])}/month.")
    blocked_save =recs ["potential_savings_if_unblocked"].sum ()
    if blocked_save >0 :
        st .write (f"- {int ((recs ['action']=='BLOCKED').sum ())} proposed moves are blocked by rules; "
        f"{money (blocked_save )}/month of potential savings is NOT counted.")
    if not demand ["has_history"]:
        st .write ("- No demand history loaded: no predictions shown; recommendations use access counts, recency and rules.")


with t_work :
    st .subheader ("Workload analysis")
    an =res ["analyzed"]
    inactive_days =st .slider ("Inactive means no access for at least (days)",7 ,365 ,INACTIVE_DAYS_DEFAULT ,key ="inact")
    q75 =an ["access_count"].quantile (0.75 )
    freq =an [(an ["access_count"]>=q75 )&(an ["access_count"]>0 )&(an ["days_since_last_access"]<=30 )]
    inactive =an [an ["days_since_last_access"]>=inactive_days ]
    critical =an [an ["performance_requirement"].isin (["HIGH","CRITICAL"])]
    c =st .columns (5 )
    c [0 ].metric ("Total datasets",f"{len (an ):,}")
    c [1 ].metric ("Storage used",f"{an ['size_gb'].sum ():,.1f} GB")
    c [2 ].metric ("Average size",f"{an ['size_gb'].mean ():,.1f} GB")
    c [3 ].metric ("Inactive datasets",len (inactive ))
    c [4 ].metric ("Performance-critical",len (critical ))
    st .caption (f"Frequently accessed = top quartile of access_count (>= {q75 :,.0f}) and used in the last 30 days "
    f"({len (freq )} datasets). Performance-critical = HIGH or CRITICAL requirement.")

    def avg (col ,unit ):
        return f"{pd .to_numeric (an [col ],errors ='coerce').mean ():,.1f} {unit }"if col in an .columns and pd .to_numeric (an [col ],errors ="coerce").notna ().any ()else "n/a"
    c =st .columns (4 )
    c [0 ].metric ("Avg read+write IOPS",avg ("read_iops","read")if "write_iops"not in an .columns else 
    f"{(pd .to_numeric (an ['read_iops'],errors ='coerce').fillna (0 )+pd .to_numeric (an ['write_iops'],errors ='coerce').fillna (0 )).mean ():,.0f}"
    if "read_iops"in an .columns else "n/a")
    c [1 ].metric ("Avg throughput",avg ("throughput_mbps","MB/s"))
    c [2 ].metric ("Avg observed latency",avg ("observed_latency_ms","ms"))
    c [3 ].metric ("Avg growth",avg ("growth_rate_pct","%/month"))

    l ,r =st .columns (2 )
    with l :
        cur =tier_storage (an ,"current_tier").reset_index ()
        cur .columns =["tier","storage_gb"]
        fig =px .pie (cur ,names ="tier",values ="storage_gb",hole =0.55 ,color ="tier",
        color_discrete_map =TIER_COLORS ,title ="Current storage distribution")
        plot (fig )
    with r :
        by_type =an .groupby ("workload_type")["size_gb"].sum ().sort_values (ascending =False ).reset_index ()
        fig =px .bar (by_type ,x ="workload_type",y ="size_gb",title ="Storage by workload type (GB)")
        fig .update_layout (xaxis_title =None )
        plot (fig )
    top_sizes =an .sort_values ("size_gb",ascending =False ).head (20 )
    fig =px .bar (top_sizes ,x ="file_name",y ="size_gb",color ="current_tier",color_discrete_map =TIER_COLORS ,
    title ="Largest datasets (GB)")
    fig .update_layout (xaxis_title =None )
    plot (fig )
    fig =px .scatter (an ,x ="days_since_last_access",y ="access_count",size ="size_gb",color ="current_tier",
    color_discrete_map =TIER_COLORS ,hover_name ="file_name",log_y =True ,
    title ="Recency vs access count (bubble = size)")
    plot (fig )
    cols =[c for c in ["file_name","workload_type","size_gb","current_tier","days_since_last_access",
    "access_count","performance_requirement"]if c in an .columns ]
    for label ,frame in ((" Frequently accessed datasets",freq ),(" Inactive datasets",inactive ),
    (" Performance-critical workloads",critical )):
        with st .expander (f"{label } ({len (frame )})"):
            table (frame [cols ].sort_values ("access_count",ascending =False ))
    with st .expander ("All analysed data"):
        table (an ,height =320 )


with t_rec :
    st .subheader ("Storage recommendations")
    st .caption ("Recommendations only - nothing is executed. "+approval_workflow .SIMULATION_NOTICE )
    show =view [["file_name","workload_type","size_gb","current_tier","recommended_tier","action",
    "optimization_score","demand_outlook","policy_status","sla_status",
    "manual_approval_required","recommendation_reason"]].copy ()
    show ["action"]=show ["action"].map (ACTION_EMOJI )
    st .write (f"Showing {len (show )} of {len (recs )} datasets (sidebar filters apply).")
    table (show ,height =380 )

    st .markdown ("###  Inspect one dataset")
    if view .empty :
        st .info ("No datasets match the current filters.")
    else :
        pick =st .selectbox ("Dataset",list (view ["file_name"]),key ="pick_ds")
        row =recs [recs ["file_name"]==pick ].iloc [0 ]
        h =st .columns (4 )
        h [0 ].metric ("Action",ACTION_EMOJI [row ["action"]])
        h [1 ].metric ("Tier",f"{row ['current_tier']} → {row ['recommended_tier']}")
        h [2 ].metric ("Optimization score",f"{row ['optimization_score']:.1f}")
        h [3 ].metric ("Est. monthly impact",money (row ["net_monthly_savings"]))
        st .markdown (f"**What:** {row ['what_text']}")
        st .markdown (f"**Why:** {row ['why_text']}")
        st .markdown (f"**Financial impact:** {row ['financial_text']}")
        st .markdown (f"**Performance:** {row ['performance_text']}")
        st .markdown (f"**Policy checks:** {row ['policy_text']}")
        st .markdown (f"**Remaining uncertainties:** {row ['uncertainty_text']}")
        if row ["blocked_reason"]:
            st .error (f" Reason blocked: {row ['blocked_reason']}")
        if row ["manual_approval_required"]:
            st .warning ("Manual approval is required for this recommendation.")
        if not row ["deletion_allowed"]:
            st .caption ("️ Deletion is not permitted by the metadata (legal hold or retention). This app never deletes data.")

        st .markdown ("#### Review decision")
        existing =st .session_state ["approvals"].get (pick )
        if existing :
            st .info (f"Current decision: **{existing ['decision'].replace ('_',' ')}** ({existing ['decided_at']})")
        note =st .text_input ("Note (optional)",key =f"note_{pick }")
        b =st .columns (4 )
        ok ,why =approval_workflow .can_decide (row )
        decision =None 
        if b [0 ].button (" Approve",disabled =not ok ,key =f"ap_{pick }",help =why or None ):
            decision =approval_workflow .APPROVED 
        if b [1 ].button (" Reject",key =f"rj_{pick }"):
            decision =approval_workflow .REJECTED 
        if b [2 ].button (" Mark for review",key =f"rv_{pick }"):
            decision =approval_workflow .MARKED_REVIEW 
        if b [3 ].button ("↩️ Clear decision",key =f"cl_{pick }"):
            approval_workflow .clear_decision (st .session_state ["approvals"],pick )
            st .rerun ()
        if not ok :
            st .caption (f"Approve is disabled. {why }")
        if decision :
            _ ,msg =approval_workflow .record_decision (st .session_state ["approvals"],row ,decision ,note )
            st .success (msg +" "+"No data was moved.")
            st .rerun ()

    st .markdown ("### Decisions so far")
    summ =approval_workflow .decision_summary (st .session_state ["approvals"],recs )
    c =st .columns (4 )
    c [0 ].metric ("Approved",summ ["approved"])
    c [1 ].metric ("Rejected",summ ["rejected"])
    c [2 ].metric ("Marked for review",summ ["marked_for_review"])
    c [3 ].metric ("Simulated savings of approved",money (summ ["simulated_monthly_savings_of_approved"]))
    eligible =recs [recs ["action"].isin (["PROMOTE","DEMOTE"])&~recs ["manual_approval_required"]]
    if st .button (f"Approve all {len (eligible )} low-risk moves (no warnings, no manual approval needed)",
    disabled =eligible .empty ,key ="bulk"):
        for _ ,r_ in eligible .iterrows ():
            approval_workflow .record_decision (st .session_state ["approvals"],r_ ,approval_workflow .APPROVED ,"bulk approval (simulated)")
        st .rerun ()
    dec =approval_workflow .decisions_frame (st .session_state ["approvals"])
    if dec .empty :
        st .caption ("No decisions recorded yet.")
    else :
        table (dec )
        st .download_button ("⬇️ Download decisions (CSV)",dec .to_csv (index =False ).encode ("utf-8"),
        "storage_decisions_simulated.csv","text/csv",key ="dl_dec")


with t_cost :
    st .subheader ("Cost optimization")
    st .caption (ESTIMATE_LABEL )
    c =st .columns (5 )
    c [0 ].metric ("Current monthly storage cost",money (cs ["total_current_cost"]))
    c [1 ].metric ("Optimized monthly storage cost",money (cs ["total_optimized_cost"]))
    c [2 ].metric ("Monthly savings",money (cs ["monthly_savings"]))
    c [3 ].metric ("Annual savings",money (cs ["annual_savings"]))
    c [4 ].metric ("Savings %",f"{cs ['savings_percent']:.1f}%")
    c =st .columns (5 )
    c [0 ].metric ("Retrieval charges (now / after)",f"{money (cs ['current_retrieval_cost'])} / {money (cs ['optimized_retrieval_cost'])}")
    c [1 ].metric ("Net monthly saving (incl. retrieval)",money (cs ["net_monthly_savings"]))
    c [2 ].metric ("One-time migration cost",money (cs ["one_time_migration_cost"]))
    be =cs ["overall_break_even_months"]
    c [3 ].metric ("Break-even","never"if not np .isfinite (be )else f"{be :,.1f} months")
    c [4 ].metric (f"{cs ['horizon_months']}-month TCO saving",money (cs ["tco_savings"]))
    st .caption (f"TCO ({cs ['horizon_months']} months): current {money (cs ['tco_current'])} vs optimized incl. migration {money (cs ['tco_optimized'])}.")
    if recs ["potential_savings_if_unblocked"].sum ()>0 :
        st .info (f"Savings held back by rules or missing information (NOT counted): {money (recs ['potential_savings_if_unblocked'].sum ())}/month.")
    note =bad_tier_note (recs )
    if note :
        st .caption ("️ "+note )

    l ,r =st .columns (2 )
    with l :
        bt =cs ["cost_by_tier"].melt (id_vars ="tier",var_name ="which",value_name ="cost")
        fig =px .bar (bt ,x ="tier",y ="cost",color ="which",barmode ="group",
        color_discrete_map ={"current_cost":"#94A3B8","optimized_cost":"#10B981"},
        title ="Monthly storage cost by tier")
        plot (fig )
    with r :
        sav =recs .dropna (subset =["net_monthly_savings"])
        sav =sav [sav ["net_monthly_savings"]!=0 ].sort_values ("net_monthly_savings")
        fig =px .bar (sav ,x ="net_monthly_savings",y ="file_name",orientation ="h",
        color =sav ["net_monthly_savings"]>0 ,
        color_discrete_map ={True :"#10B981",False :"#EF4444"},
        title ="Net monthly saving per dataset (red = extra cost)")
        fig .update_layout (showlegend =False ,yaxis_title =None ,height =max (320 ,22 *len (sav )))
        plot (fig )
    cols =["file_name","action","current_tier","recommended_tier","size_gb","current_monthly_cost",
    "recommended_monthly_cost","net_monthly_savings","one_time_cost","break_even_months"]
    table (view [cols ].round (2 ),height =320 )
    with st .expander ("Formulas and prices used"):
        st .markdown ("""
- **Current cost** = Σ (size_gb × price of current tier)
- **Optimized cost** = Σ (size_gb × price of recommended tier)
- **Monthly savings** = Current − Optimized;  **Savings %** = Monthly savings ÷ Current × 100 (0 when current cost is 0)
- **Total cost of ownership** adds retrieval charges and one-time migration cost (transfer + retrieval-out + fixed overhead)
- Retrieval volume is an *assumption*: reads per month ÷ reads-per-full-retrieval, capped at one full read
        """)
        st .json (cs ["prices_per_gb_month"])
        st .caption (cs ["pricing_note"])


with t_comp :
    st .subheader ("Compliance and SLA")
    st .info (POLICY_DISCLAIMER )
    st .caption (TIER_PROFILE_NOTE +" Observed/maximum latency come from your CSV; this app does not measure hardware.")
    c =st .columns (6 )
    for i ,s_ in enumerate (["PASS","WARN","FAIL"]):
        c [i ].metric (f"Policy {s_ }",int ((recs ["policy_status"]==s_ ).sum ()))
    for i ,s_ in enumerate (["MEETS","NEEDS_DATA","MAY_VIOLATE"]):
        c [3 +i ].metric (f"SLA {s_ .replace ('_',' ').title ()}",int ((recs ["sla_status"]==s_ ).sum ()))
    c =st .columns (3 )
    c [0 ].metric ("Blocked actions",int ((recs ["action"]=="BLOCKED").sum ()))
    c [1 ].metric ("Manual approval required",int (recs ["manual_approval_required"].sum ()))
    c [2 ].metric ("Deletion not permitted",int ((~recs ["deletion_allowed"]).sum ()))

    l ,r =st .columns (2 )
    with l :
        ps =recs ["policy_status"].value_counts ().reset_index ()
        ps .columns =["status","datasets"]
        plot (px .pie (ps ,names ="status",values ="datasets",color ="status",color_discrete_map =STATUS_COLORS ,
        hole =0.5 ,title ="Policy status"))
    with r :
        ss =recs ["sla_status"].value_counts ().reset_index ()
        ss .columns =["status","datasets"]
        plot (px .pie (ss ,names ="status",values ="datasets",color ="status",color_discrete_map =STATUS_COLORS ,
        hole =0.5 ,title ="SLA status (recommended placement / proposal)"))

    st .markdown ("#### Blocked actions and reasons")
    blocked =view [(view ["action"]=="BLOCKED")|(view ["blocked_reason"]!="")]
    if blocked .empty :
        st .success ("No blocked actions for the current filters.")
    else :
        table (blocked [["file_name","current_tier","proposed_tier","recommended_tier","action","blocked_reason"]])
    st .markdown ("#### Policy details per dataset")
    table (view [["file_name","recommended_tier","policy_status","policy_failed_checks","policy_warnings",
    "manual_approval_required","deletion_allowed"]],height =300 )
    st .markdown ("#### SLA details per dataset")
    table (view [["file_name","recommended_tier","sla_status","observed_latency_status","sla_issues","sla_gaps"]],height =300 )
    with st .expander ("Configured tier assumptions (simulation)"):
        table (tier_tbl )
        pc =PolicyConfig ()
        st .write ("Tier availability by region (demo rule):",pc .tier_regions )
        st .write ("Highest security class allowed per tier (demo rule):",pc .tier_max_security )


with t_fore :
    st .subheader ("Demand forecasting")
    for m in demand ["messages"]:
        st .info (m )
    cap =demand ["capacity"]
    hist =st .session_state ["history"]
    if cap ["available"]:
        hs ,fc ,mt =cap ["history"],cap ["forecast"],cap ["metrics"]
        fig =go .Figure ()
        fig .add_scatter (x =hs ["date"],y =hs ["size_gb"],name ="Historical GB",mode ="lines+markers")
        fig .add_scatter (x =fc ["date"],y =fc ["baseline_gb"],name ="Baseline (3-month avg)",mode ="lines",line =dict (dash ="dot"))
        fig .add_scatter (x =fc ["date"],y =fc ["model_gb"],name ="Linear model",mode ="lines",line =dict (dash ="dash"))
        fig .add_scatter (x =fc ["date"],y =fc ["selected_gb"],name ="Selected forecast",mode ="lines+markers",line =dict (width =3 ))
        fig .update_layout (title =f"Total storage demand: history and {mt ['horizon_months']}-month forecast (GB)")
        plot (fig )
        c =st .columns (4 )
        c [0 ].metric ("Selected method","Model"if mt ["model_beats_baseline"]else "Baseline")
        c [1 ].metric ("Baseline MAE",f"{mt ['baseline_mae_gb']:,.0f} GB")
        c [2 ].metric ("Model MAE",f"{mt ['model_mae_gb']:,.0f} GB")
        c [3 ].metric ("Validation points",mt ["validation_points"])
        if mt ["model_beats_baseline"]:
            st .success (f"On walk-forward validation the model beat the baseline by {mt ['improvement_vs_baseline_pct']:.1f}% (MAE). "
            "That is evidence for this history only, not a guarantee.")
        else :
            st .warning ("The model did NOT beat the simple baseline, so the baseline is used.")
    elif hist is not None :
        st .warning (cap ["message"]or "Capacity forecast not available.")

    act ,am =demand ["activity"],demand ["activity_metrics"]
    if hist is not None :
        st .markdown ("#### Dataset activity outlook")
        if "baseline_wape_pct"in am :
            st .caption (f"Walk-forward error (WAPE): baseline {am ['baseline_wape_pct']}% vs trend method {am ['trend_method_wape_pct']}%. "
            f"Used: {am ['selected_method']}.")
        counts =act ["demand_outlook"].value_counts ().reset_index ()
        counts .columns =["outlook","datasets"]
        plot (px .bar (counts ,x ="outlook",y ="datasets",color ="outlook",title ="Predicted outlook per dataset"))
        table (act )
        sel =st .selectbox ("Show history of",list (act ["file_name"]),key ="hist_pick")
        h1 =hist [hist ["file_name"]==sel ].dropna (subset =["access_count"]).sort_values ("date")
        if len (h1 ):
            ma =h1 ["access_count"].rolling (3 ).mean ()
            fig =go .Figure ()
            fig .add_scatter (x =h1 ["date"],y =h1 ["access_count"],name ="Monthly accesses",mode ="lines+markers")
            fig .add_scatter (x =h1 ["date"],y =ma ,name ="3-month average",line =dict (dash ="dot"))
            fig .update_layout (title =f"Access history: {sel }")
            plot (fig )
        pot_active =act [act ["demand_outlook"].isin (["LIKELY_ACTIVE","POSSIBLE_REACTIVATION"])]
        likely_inactive =act [act ["demand_outlook"]=="LIKELY_INACTIVE"]
        c =st .columns (2 )
        c [0 ].metric ("Potentially active datasets",len (pot_active ))
        c [1 ].metric ("Likely to become/stay inactive",len (likely_inactive ))
    else :
        st .markdown ("No history loaded, so no predictions are shown. Showing a **rule-based growth projection** "
        "(size × (1 + growth_rate_pct)^months) instead - a projection, not a prediction.")
    proj =res ["projection"]
    if not proj .empty :
        fig =px .line (proj ,x ="month",y ="projected_gb",color ="tier",color_discrete_map =TIER_COLORS ,
        title ="Projected GB per tier after applying recommendations (from growth_rate_pct)")
        plot (fig )
        if not res ["shortages"].empty :
            st .error ("Potential capacity shortages (against capacity_gb set in the sidebar):")
            table (res ["shortages"])
        elif (pd .to_numeric (tier_tbl ["capacity_gb"],errors ="coerce").fillna (0 )>0 ).any ():
            st .success ("No tier is projected to exceed its configured capacity within 12 months.")
        else :
            st .caption ("Set capacity_gb per tier in the sidebar table to check for capacity shortages.")
    else :
        st .caption ("growth_rate_pct is not in the data, so no growth projection is available.")
    with st .expander ("Important limitations"):
        for lim in demand ["limitations"]:
            st .write ("- "+lim )


with t_mig :
    st .subheader ("Migration simulation")
    st .caption (" Simulation only - no real files are moved. Times and costs use the bandwidth, prices and tier profiles you configured.")
    plan =res ["migration_plan"]
    only_approved =st .checkbox ("Show only moves I approved",value =False ,key ="only_appr")
    if only_approved :
        approved =[k for k ,v in st .session_state ["approvals"].items ()if v ["decision"]==approval_workflow .APPROVED ]
        plan =plan [plan ["file_name"].isin (approved )]
    else :
        plan =plan [plan ["file_name"].isin (view ["file_name"])]
    c =st .columns (5 )
    c [0 ].metric ("Datasets to migrate",len (plan ))
    c [1 ].metric ("Data to move",f"{plan ['size_gb'].sum ():,.1f} GB")
    c [2 ].metric ("Transfer time (sequential)",f"{plan ['transfer_hours'].sum ():,.1f} h")
    c [3 ].metric ("One-time cost",money (plan ["one_time_cost"].sum ()))
    c [4 ].metric ("Monthly savings",money (plan ["monthly_savings"].sum ()))
    if plan .empty :
        st .success ("No migrations to show for the current selection.")
    else :
        d =plan .copy ()
        d ["break_even_months"]=d ["break_even_months"].replace (np .inf ,np .nan )
        table (d .round (2 ),height =360 )
        l ,r =st .columns (2 )
        with l :
            route =(plan .assign (route =plan ["source_tier"]+" → "+plan ["destination_tier"])
            .groupby ("route",as_index =False ).agg (datasets =("file_name","size"),size_gb =("size_gb","sum"),
            monthly_savings =("monthly_savings","sum")))
            plot (px .bar (route ,x ="route",y ="size_gb",color ="monthly_savings",title ="Data moved per route (GB)"))
        with r :
            risk =plan ["migration_risk"].value_counts ().reset_index ()
            risk .columns =["risk","datasets"]
            plot (px .bar (risk ,x ="risk",y ="datasets",color ="risk",
            color_discrete_map ={"LOW":"#10B981","MEDIUM":"#F59E0B","HIGH":"#EF4444"},title ="Migration risk"))
    mig =res ["migration"]
    st .markdown ("#### Storage before vs after (all recommendations)")
    b ,a =mig ["before_distribution"],mig ["after_distribution"]
    fig =go .Figure ()
    fig .add_bar (name ="Before",x =b ["tier"],y =b ["total_size_gb"],marker_color ="#94A3B8")
    fig .add_bar (name ="After",x =a ["tier"],y =a ["total_size_gb"],marker_color ="#7C3AED")
    fig .update_layout (barmode ="group",title ="GB per tier")
    plot (fig )
    st .caption (mig ["summary"]["note"])


with t_cmp :
    st .subheader ("Strategy comparison")
    st .caption ("All strategies run on the same workload with the same prices and assumptions. "
    "Cost and movement are calculated from your data; SLA risk and policy violations are simulated "
    "against the configured tier profiles and rules. "+strategy_comparison .RULES_TEXT )
    cmp_ =res ["comparison"]
    if cmp_ .empty :
        st .warning (res ["verdict"][0 ])
        st .stop ()
    nice =cmp_ .rename (columns ={
    "strategy":"Strategy","monthly_cost":"Monthly cost","monthly_savings_vs_current":"Savings vs current / month",
    "savings_percent":"Savings %","datasets_moved":"Datasets moved","data_moved_gb":"Data moved (GB)",
    "migration_overhead":"Migration overhead","tco_over_horizon":f"TCO {cs ['horizon_months']} mo.",
    "sla_may_violate":"SLA may violate","sla_needs_data":"SLA needs data","policy_violations":"Policy violations"})
    table (nice )
    l ,r =st .columns (2 )
    with l :
        plot (px .bar (cmp_ ,x ="strategy",y =["monthly_cost","migration_overhead"],barmode ="group",
        title ="Monthly cost and one-time migration overhead"))
    with r :
        plot (px .bar (cmp_ ,x ="strategy",y =["sla_may_violate","policy_violations"],barmode ="group",
        title ="SLA risk and policy violations (count of datasets)"))
    st .markdown ("#### What the numbers say")
    for line in res ["verdict"]:
        st .write ("- "+line )
    st .caption ("SmartStore AI here is a transparent scoring + policy engine; machine learning is only used in the optional "
    "capacity forecast, and only when it beats the baseline. It is credited only where the table above shows an advantage.")
    with st .expander ("Measured vs simulated"):
        table (strategy_comparison .BASIS )


st .divider ()
st .subheader (" Final optimization report")
report =recs .drop (columns =[c for c in ["what_text","why_text"]if c in recs .columns ]).copy ()
st .download_button ("⬇️ Download report (CSV)",report .to_csv (index =False ).encode ("utf-8"),
"storage_optimization_report.csv","text/csv",type ="primary",key ="dl_report")
