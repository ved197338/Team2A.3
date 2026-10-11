# SmartStore AI — Intelligent Storage Optimization System
KLE Tech Hackfest 2026 · Problem 2A. A **simulation**: it never moves, deletes or modifies real data.
All prices are DEMO values, all results are ESTIMATES, and the bundled data is SYNTHETIC.

## Run on Windows (VS Code terminal, inside the project folder)
```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```
(If PowerShell blocks activation: `Set-ExecutionPolicy -Scope Process Bypass`, then activate again.)
In the app click **Use bundled SYNTHETIC sample data**, then **Run full pipeline**.
Regenerate the sample data any time: `python tools/generate_synthetic_data.py`

## Pipeline
`data_loader` → `workload_analyzer` → `demand_forecaster` → `recommendation_engine`
(wraps `optimizer` + `performance_sla` + `policy_engine`) → `cost_calculator`/`tco_calculator`
→ `migration_simulator` → `strategy_comparison`; `approval_workflow` records operator decisions.
`pipeline.run_pipeline()` runs it all; the dashboard and the tests both use it.

## CSV schema
Required: `file_name, size_gb, last_accessed, access_count, workload_type, performance_requirement (LOW/MEDIUM/HIGH/CRITICAL), current_tier`
Optional (missing ones are skipped or marked "needs data", never invented): `read_frequency, write_frequency, read_iops, write_iops,
throughput_mbps, observed_latency_ms, max_latency_ms, growth_rate_pct, retention_days, recovery_time_hours, legal_hold,
required_region, current_region, security_class, approved_tiers (HOT|WARM), migration_cost, data_source`
History CSV (optional): `date, file_name, access_count, size_gb`

## Honest limitations
Tier performance, regions and security rules are configurable assumptions, not measurements. The policy engine is a
configurable prototype and does not guarantee legal compliance. Forecasts use short histories and are labelled estimates.
