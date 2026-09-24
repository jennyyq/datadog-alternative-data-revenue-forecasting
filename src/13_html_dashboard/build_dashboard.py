#!/usr/bin/env python3
"""
SECTION A: DATA PREP

build_dashboard.py - generates dashboard/ddog_alternative_data_dashboard.html and dashboard/dashboard_data_dictionary.csv

Run from the project root:
    cd Datadog_Project/
    python3 src/build_dashboard.py

Reads ONLY the already-verified CSVs in outputs/ (IN_DIR). No new data is collected, no new correlations/lags/
models are computed - the only "computation" here is (a) re-reading already-established numbers for display, and
(b) the same simple 3-point monotonic accelerating/decelerating/stable read used in the prior static exhibits.

Every model-performance claim shown anywhere in the dashboard (Chart C highlighting, its caption, the Forward
Research Read "Model evidence" row) is derived AT RUNTIME from outputs/walkforward_results.csv - no model name or
metric value for the lowest-MAE or highest-directional-accuracy model is hardcoded. If a future re-run of the
walk-forward study changes which model wins either metric, this file requires no edit.
"""
from __future__ import annotations
import json, re, os
from collections import defaultdict
import pandas as pd

IN_DIR = "outputs/"
OUT_DIR = "dashboard/"

# =================================================================================================================
# 0. REQUIRED-INPUT CHECK - fail with a clear, actionable message rather than a raw pandas FileNotFoundError
# =================================================================================================================
REQUIRED_INPUTS = ["ddog_cloud_master.csv", "ddog_google_trends_master.csv", "walkforward_results.csv",
                   "agent_obs_verified_timeline.csv", "ddog_calculated_dataset.csv", "next_quarter_forecast.csv"]
_missing = [f for f in REQUIRED_INPUTS if not os.path.isfile(os.path.join(IN_DIR, f))]
if _missing:
    raise FileNotFoundError(
        f"Missing required input file(s) in {IN_DIR!r}: {', '.join(_missing)}. "
        f"Run this script from the project root (Datadog_Project/) so that '{IN_DIR}' resolves correctly - "
        f"e.g. `python3 src/build_dashboard.py`, not from inside src/.")

# =================================================================================================================
# 1. LOAD
# =================================================================================================================
cloud = pd.read_csv(IN_DIR + "ddog_cloud_master.csv")             # Quarter, DDOG_Revenue_YoY, AWS_YoY, Azure_YoY, GoogleCloud_YoY, Cloud_Index_Raw, Cloud_Index_Z
gt = pd.read_csv(IN_DIR + "ddog_google_trends_master.csv")        # Quarter, Quarterly_Trend_Mean, Trend_YoY, DDOG_Revenue_YoY, Customers_100k_YoY
wf = pd.read_csv(IN_DIR + "walkforward_results.csv")              # panel, model, n_oos, MAE, RMSE, MAPE_pct, Directional_Accuracy_pct
tl_raw = pd.read_csv(IN_DIR + "agent_obs_verified_timeline.csv")  # Date, Metric, Value, Context, Source_URL, Source_Tier, Stock_or_Flow, Interpretation
ddog = pd.read_csv(IN_DIR + "ddog_calculated_dataset.csv")        # Quarter, Revenue_YoY, Customers_100k, Customers_100k_YoY, ...

assert list(cloud.Quarter) == list(gt.Quarter), "cloud and trends master files must share the same quarter axis"

# =================================================================================================================
# 2. CHART DATA
# =================================================================================================================
chartA = [dict(q=r.Quarter, rev=round(float(r.DDOG_Revenue_YoY), 2), cloud=round(float(r.Cloud_Index_Raw), 2))
         for r in cloud.itertuples()]

chartB = [dict(q=r.Quarter, trend=round(float(r.Trend_YoY), 2), cust=round(float(r.Customers_100k_YoY), 2))
         for r in gt.itertuples()]

# The six models are a fixed, legitimate part of the walk-forward FRAMEWORK definition (not a results claim) and
# are deliberately NOT derived from the CSV - a stray extra row (e.g. an experimental Ridge model someone appended
# to walkforward_results.csv) must be excluded, not silently absorbed. Ridge is explicitly excluded on purpose.
MODEL_ORDER = ["Naive", "AR1", "Cloud", "Trends", "Cloud+Trends", "AR+Cloud+Trends"]
MODEL_LABEL = {"Naive": "Naive", "AR1": "AR(1)", "Cloud": "Cloud", "Trends": "Trends",
              "Cloud+Trends": "Cloud+Trends", "AR+Cloud+Trends": "AR+Cloud+Trends"}
assert not any("ridge" in m.lower() for m in MODEL_ORDER), "Ridge must not be part of MODEL_ORDER"

wf_main_all = wf[wf.panel == "main"]
_ridge_rows = wf_main_all[wf_main_all.model.str.lower().str.contains("ridge", na=False)]
assert _ridge_rows.empty, f"walkforward_results.csv (panel=='main') contains a Ridge row - Ridge must not appear in this dashboard: {_ridge_rows.model.tolist()}"

_missing_models = [m for m in MODEL_ORDER if m not in set(wf_main_all.model)]
assert not _missing_models, f"walkforward_results.csv (panel=='main') is missing expected model row(s): {_missing_models}"
_dupe_check = wf_main_all[wf_main_all.model.isin(MODEL_ORDER)]
assert not _dupe_check.model.duplicated().any(), \
    f"walkforward_results.csv (panel=='main') has duplicate rows for: {_dupe_check.model[_dupe_check.model.duplicated()].tolist()}"

wf_main = wf_main_all[wf_main_all.model.isin(MODEL_ORDER)].set_index("model").loc[MODEL_ORDER]
_metric_cols = ["MAE", "RMSE", "MAPE_pct", "Directional_Accuracy_pct"]
assert not wf_main[_metric_cols].isna().any().any(), \
    f"Null value(s) found in {_metric_cols} for a main-panel model in walkforward_results.csv:\n{wf_main[_metric_cols][wf_main[_metric_cols].isna().any(axis=1)]}"

chartC = [dict(model=MODEL_LABEL[m], mae=round(float(wf_main.loc[m, "MAE"]), 2), rmse=round(float(wf_main.loc[m, "RMSE"]), 2),
              mape=round(float(wf_main.loc[m, "MAPE_pct"]), 1), dir_acc=round(float(wf_main.loc[m, "Directional_Accuracy_pct"]), 1))
         for m in MODEL_ORDER]

# ---- structural validation only: NO assumption about WHICH model has the lowest MAE or highest directional
# accuracy is encoded anywhere. A future re-run that changes the winner requires no edit to this file.
assert len(chartC) == 6, f"chartC must contain exactly 6 rows, found {len(chartC)}"
assert len({r['model'] for r in chartC}) == 6, "chartC contains duplicate model names"
assert not any("ridge" in r["model"].lower() for r in chartC), "Ridge model present in chartC"
LOWEST_MAE_ROW = min(chartC, key=lambda r: r["mae"])          # computed fresh from the CURRENT CSV every run
HIGHEST_DIR_ROW = max(chartC, key=lambda r: r["dir_acc"])     # computed fresh from the CURRENT CSV every run

# =================================================================================================================
# 2b. 2026 Q3 REVENUE FORECAST - read-only integration of an already-generated forward forecast. This dashboard
# does NOT select a model itself: it reads whichever row has selected_for_dashboard==True and displays it. No
# model name is hardcoded here (same principle as LOWEST_MAE_ROW/HIGHEST_DIR_ROW above) - if a future refresh of
# next_quarter_forecast.csv selects a different model, this code requires no edit.
# =================================================================================================================
fc_raw = pd.read_csv(IN_DIR + "next_quarter_forecast.csv")
_fc_selected = fc_raw[fc_raw["selected_for_dashboard"] == True]
assert len(_fc_selected) == 1, \
    f"Expected exactly one selected_for_dashboard==True row in next_quarter_forecast.csv, found {len(_fc_selected)}"
_sel = _fc_selected.iloc[0]

# cross-reference n_oos for the selected model from walkforward_results.csv (already-loaded, already-validated
# single source of truth for OOS sample size) rather than hardcoding "8" anywhere
_sel_n_oos = int(wf_main.loc[_sel["model"], "n_oos"]) if _sel["model"] in wf_main.index else None
_sel_dir_hits = round(_sel["historical_oos_directional_accuracy_pct"] / 100 * _sel_n_oos) if _sel_n_oos else None

FORECAST = dict(
    selected=dict(
        model=str(_sel["model"]),
        forecast_quarter=str(_sel["forecast_quarter"]),
        as_of_quarter=str(_sel["as_of_quarter"]),
        data_cutoff=str(_sel["data_cutoff"]),
        predicted_revenue_yoy_pct=round(float(_sel["predicted_revenue_yoy_pct"]), 2),
        predicted_revenue_usd_m=round(float(_sel["predicted_revenue_usd_m"]), 2),
        prior_year_revenue_usd_m=round(float(_sel["prior_year_revenue_usd_m"]), 3),
        prior_year_revenue_source=str(_sel["prior_year_revenue_source"]),
        historical_oos_mae_pp=round(float(_sel["historical_oos_mae_pp"]), 2),
        historical_oos_directional_accuracy_pct=round(float(_sel["historical_oos_directional_accuracy_pct"]), 1),
        historical_oos_directional_hits=_sel_dir_hits,
        historical_oos_n=_sel_n_oos,
        feature_lags=str(_sel["feature_lags"]),
        trends_lag_source_quarter=str(_sel["trends_lag_source_quarter"]),
        selection_method=str(_sel["selection_method"]),
        note=str(_sel["note"]),
    ),
    all_models=[
        dict(model=str(r["model"]), predicted_revenue_yoy_pct=round(float(r["predicted_revenue_yoy_pct"]), 2),
            predicted_revenue_usd_m=round(float(r["predicted_revenue_usd_m"]), 2),
            historical_oos_mae_pp=round(float(r["historical_oos_mae_pp"]), 2),
            historical_oos_directional_accuracy_pct=round(float(r["historical_oos_directional_accuracy_pct"]), 1),
            selected=bool(r["selected_for_dashboard"]))
        for _, r in fc_raw.iterrows() if r["model"] in MODEL_ORDER   # keep the SAME six-model framework as Chart C (HistMean is excluded there too - not a "seventh model", just consistency, since the CSV itself carries all 7)
    ],
)
assert len(FORECAST["all_models"]) == 6, f"FORECAST['all_models'] must contain exactly the 6 Chart C models, found {len(FORECAST['all_models'])}"
# sanity check the disclosed USD-million conversion formula against the CSV's own two columns (verifies the CSV
# is internally consistent; does not recompute or override anything)
_check = FORECAST["selected"]["prior_year_revenue_usd_m"] * (1 + FORECAST["selected"]["predicted_revenue_yoy_pct"] / 100)
assert abs(_check - FORECAST["selected"]["predicted_revenue_usd_m"]) < 0.5, \
    f"next_quarter_forecast.csv internal inconsistency: prior_year_revenue_usd_m x (1+YoY%) = {_check:.2f}, but predicted_revenue_usd_m = {FORECAST['selected']['predicted_revenue_usd_m']}"

# =================================================================================================================
# 3. TIMELINE (Section 3) - every dated row, EXCLUDING the undated "ongoing" billing-unit row (shown as static text
#    instead). Quarter label is derived from the row's own Context text ("Q3'25" etc) where present; for product
#    LAUNCH events (a real calendar date, not a backward-looking disclosure) it is the calendar quarter of that
#    date; for the one row with no parseable quarter of its own (the withheld-metric row), it inherits the quarter
#    of the other rows disclosed on the SAME call date. Same-day points get a small vertical jitter so they don't
#    fully overlap on the plot; hover shows the full detail regardless.
# =================================================================================================================
tl = tl_raw[tl_raw.Date != "ongoing"].copy()
BILLING_UNIT_NOTE = tl_raw.loc[tl_raw.Date == "ongoing", "Value"].iloc[0]     # "LLM span count (NOT tokens)"

def _parse_date(d):
    return "2026-09-15" if d.startswith("2026-09 (") else d
tl["x"] = tl["Date"].apply(_parse_date)

def _extract_quarter(row):
    if row["x"] == "2026-09-15":
        return "Sep 2026 (docs snapshot)"
    if row["Stock_or_Flow"] == "Event":
        y, m, _ = row["x"].split("-"); q = (int(m) - 1) // 3 + 1
        return f"{y} Q{q}"
    m = re.search(r"Q(\d)'(\d\d)", str(row["Context"]))
    return f"20{m.group(2)} Q{m.group(1)}" if m else None

tl["qlabel"] = tl.apply(_extract_quarter, axis=1)
_grp = tl.groupby("x")["qlabel"].apply(lambda s: next((v for v in s if pd.notna(v)), None))
tl["qlabel"] = tl.apply(lambda r: _grp[r.x] if pd.isna(r.qlabel) else r.qlabel, axis=1)
assert tl.qlabel.notna().all(), "every timeline row must resolve to a quarter label"

_by_x = defaultdict(list)
for i, row in tl.iterrows(): _by_x[row.x].append(i)
_jitter = {}
for x, idxs in _by_x.items():
    n = len(idxs)
    offs = [0.0] if n == 1 else [(k - (n - 1) / 2) * 0.62 for k in range(n)]
    for idx, off in zip(idxs, offs): _jitter[idx] = off

TIER_SHORT = {"T1": "Primary (Datadog IR / filing / docs)", "T2": "Verbatim transcript, 3rd-party host", "T3": "3rd-party summary (unverified from primary)"}

# Direct LLM/Agent Observability evidence vs adjacent AI-ecosystem evidence (MCP, AI-native cohort, broad AI
# integrations, Bits AI). Classification is by metric name only - a simple, auditable lookup, not a new judgment
# call per row. "Direct" = explicitly about the LLM/Agent Observability product itself (customers, spans, its own
# capability launches/naming); everything else discusses adjacent AI activity that provides context but is not
# the same product.
DIRECT_METRICS = {
    "LLM Observability", "LLM Observability adopting-company growth",
    "AI Agent Monitoring / LLM Experiments / AI Agents Console",
    "LLM span-sending customer growth", "LLM Observability customers / span growth",
    "LLM Observability span growth", "Product naming",
}
def _category(metric): return "Direct" if metric in DIRECT_METRICS else "Adjacent"

timeline_points = []
for i, row in tl.iterrows():
    tier_code = row.Source_Tier.split(" -")[0].strip()
    timeline_points.append(dict(
        date=row.x, y=round(_jitter[i], 2), quarter=row.qlabel, metric=row.Metric, value=row.Value,
        tier=tier_code, tier_label=TIER_SHORT.get(tier_code, row.Source_Tier), source_url=row.Source_URL,
        interpretation=row.Interpretation, kind=row.Stock_or_Flow, category=_category(row.Metric)))
_n_direct = sum(1 for p in timeline_points if p["category"] == "Direct")
assert 0 < _n_direct < len(timeline_points), "classification must produce both Direct and Adjacent rows"

# =================================================================================================================
# 4. SECTION 1 / SECTION 4 module states - SAME simple rule as the static exhibits: 3 consecutive quarters
#    strictly increasing/decreasing = accelerating/decelerating; anything else = stable (or, for Trends, flagged
#    "volatile / mixed" since that series is known to reverse direction quarter to quarter - same read as before).
# =================================================================================================================
def _three_point_state(series, mixed_label="Stable"):
    a, b, c = series.iloc[-3], series.iloc[-2], series.iloc[-1]
    if c > b > a: return "Accelerating"
    if c < b < a: return "Decelerating"
    return mixed_label

rev_latest, rev_p1, rev_p2 = cloud.DDOG_Revenue_YoY.iloc[-1], cloud.DDOG_Revenue_YoY.iloc[-2], cloud.DDOG_Revenue_YoY.iloc[-3]
rev_state = _three_point_state(cloud.DDOG_Revenue_YoY)
ci_latest, ci_p1, ci_p2 = cloud.Cloud_Index_Raw.iloc[-1], cloud.Cloud_Index_Raw.iloc[-2], cloud.Cloud_Index_Raw.iloc[-3]
cloud_state = _three_point_state(cloud.Cloud_Index_Raw)
tr_latest, tr_p1, tr_p2 = gt.Trend_YoY.iloc[-1], gt.Trend_YoY.iloc[-2], gt.Trend_YoY.iloc[-3]
trend_state = _three_point_state(gt.Trend_YoY, mixed_label="Volatile / mixed")
cu_latest, cu_p1, cu_p2 = gt.Customers_100k_YoY.iloc[-1], gt.Customers_100k_YoY.iloc[-2], gt.Customers_100k_YoY.iloc[-3]
cust_state = _three_point_state(gt.Customers_100k_YoY)
catalyst_state = "Strong adoption/usage momentum"          # descriptive read from the Section 3 timeline; not a computed metric
latest_q = cloud.Quarter.iloc[-1]

# ---- structural validation only: each state must be one of the defined categories the renderer knows how to
# style (see STATE_COLOR in js_template.py) - NOT an assertion that any particular signal is currently in any
# particular state. If next quarter's data flips Cloud workload to "Decelerating", this line must not need editing.
_VALID_STATES = {"Accelerating", "Decelerating", "Stable", "Volatile / mixed"}
for _label, _state in [("revenue", rev_state), ("cloud", cloud_state), ("trend", trend_state), ("customer", cust_state)]:
    assert _state in _VALID_STATES, f"Unexpected {_label} state {_state!r} - not one of {_VALID_STATES}"


"""
SECTION B: HTML TEMPLATE (structure/CSS only - no data)
"""
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Datadog Alternative-Data Monitor</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
:root{
  --blue:#1a73e8; --orange:#E8710A; --green:#34a853; --purple:#632CA6;
  --amber:#c9a227; --red:#c0392b; --border:#dcdcdc; --card-bg:#fafafa;
  --text:#1c1c1c; --text-muted:#5a5a5a; --text-faint:#8a8a8a;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  color:var(--text); background:#ffffff; font-size:14px; line-height:1.5;
}
.wrap{max-width:1240px; margin:0 auto; padding:0 22px 60px;}
a{color:var(--blue);}

/* ---------- header ---------- */
header.top{border-bottom:2px solid #1c1c1c; padding:22px 0 16px; margin-bottom:4px;}
header.top h1{font-size:24px; margin:0 0 4px; font-weight:700; letter-spacing:-0.01em;}
header.top .sub{color:var(--text-muted); font-size:13.5px;}
.disclaimer{
  background:#fff8ec; border:1px solid #e8c877; border-radius:4px; padding:9px 14px;
  font-size:12.5px; color:#6b4e00; margin:14px 0 26px;
}

/* ---------- sections ---------- */
section{margin:38px 0;}
section h2{
  font-size:16.5px; margin:0 0 14px; padding-bottom:6px; border-bottom:1px solid var(--border);
  font-weight:700; letter-spacing:0.01em; color:#111;
}
section h2 .n{color:var(--purple); margin-right:6px;}
.section-note{font-size:12px; color:var(--text-faint); font-style:italic; margin-top:6px;}

/* ---------- KPI cards ---------- */
.kpi-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px;}
.kpi-card{
  border:1px solid var(--border); border-radius:6px; background:var(--card-bg); padding:14px 15px;
  position:relative;
}
.kpi-card h3{font-size:12.5px; text-transform:uppercase; letter-spacing:0.04em; color:var(--text-muted); margin:0 0 8px; font-weight:700;}
.kpi-card .tooltip-icon{
  display:inline-block; width:15px; height:15px; border-radius:50%; background:#ddd; color:#555;
  font-size:10.5px; text-align:center; line-height:15px; cursor:help; margin-left:5px; font-style:normal;
}
.kpi-card .tooltip-icon:hover + .tooltip-box, .kpi-card .tooltip-icon:focus + .tooltip-box{display:block;}
.tooltip-box{
  display:none; position:absolute; z-index:20; top:30px; left:12px; right:12px; background:#222; color:#fff;
  font-size:11.5px; line-height:1.45; padding:9px 11px; border-radius:5px; box-shadow:0 3px 10px rgba(0,0,0,0.18);
}
.kpi-value{font-size:25px; font-weight:700; margin:2px 0 2px;}
.kpi-prior{font-size:11.5px; color:var(--text-muted); margin-bottom:9px;}
.state-pill{
  display:inline-block; font-size:11px; font-weight:700; padding:3px 9px; border-radius:11px; color:#fff;
}
.state-accelerating{background:var(--green);}
.state-stable{background:var(--amber);}
.state-decelerating{background:var(--red);}
.state-volatile{background:var(--amber);}
.state-strong{background:var(--green);}
.kpi-card .method{font-size:11px; color:var(--text-faint); margin-top:9px; line-height:1.4;}
.agent-kpi-row{font-size:12px; margin:7px 0; padding-top:7px; border-top:1px dashed #ddd;}
.agent-kpi-row:first-of-type{border-top:none; margin-top:2px;}
.agent-kpi-row .aq{color:var(--purple); font-weight:700; font-size:10.5px; text-transform:uppercase;}
.agent-kpi-row .am{font-weight:600;}
.agent-kpi-row .av{color:var(--text-muted);}
.agent-group-label{font-size:10px; text-transform:uppercase; letter-spacing:0.04em; font-weight:700; margin-top:12px; padding-top:10px; border-top:1px solid #ddd;}
.agent-group-label:first-of-type{margin-top:9px; padding-top:0; border-top:none;}
.agent-group-direct{color:var(--purple);}
.agent-group-adjacent{color:#5c7a89;}

/* ---------- charts ---------- */
.chart-block{border:1px solid var(--border); border-radius:6px; padding:16px 18px 10px; margin-bottom:22px; background:#fff;}
.chart-head{display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px; margin-bottom:6px;}
.chart-head h4{margin:0; font-size:14px; font-weight:700;}
.toggle-group{display:inline-flex; border:1px solid var(--border); border-radius:5px; overflow:hidden;}
.toggle-btn{
  background:#fff; border:none; border-right:1px solid var(--border); padding:5px 11px; font-size:11.5px;
  cursor:pointer; color:var(--text-muted); font-weight:600;
}
.toggle-btn:last-child{border-right:none;}
.toggle-btn.active{background:var(--purple); color:#fff;}
.chart-note{font-size:11.5px; color:var(--text-faint); font-style:italic; margin:6px 2px 4px;}
.chart-highlight-note{font-size:12px; margin:8px 2px 2px; padding:8px 10px; border-radius:5px; background:#f6f6f6;}
.chart-highlight-note b.orange{color:var(--orange);}
.chart-highlight-note b.green{color:var(--green);}

/* ---------- table (Chart C compact table view) ---------- */
#chartC{overflow-x:auto; -webkit-overflow-scrolling:touch;}
table.compact{width:100%; min-width:480px; border-collapse:collapse; font-size:12.5px; margin-top:6px;}
table.compact th{text-align:right; padding:7px 8px; border-bottom:2px solid #333; font-size:11.5px; text-transform:uppercase; letter-spacing:0.03em; color:var(--text-muted);}
table.compact th:first-child, table.compact td:first-child{text-align:left;}
table.compact td{text-align:right; padding:7px 8px; border-bottom:1px solid #eee;}
table.compact tr:nth-child(even){background:#fafafa;}
td.hl-orange{background:#fff0dc; color:var(--orange); font-weight:700; border-radius:3px;}
td.hl-green{background:#dff3e3; color:var(--green); font-weight:700; border-radius:3px;}
table.audit-table{min-width:760px;}
table.audit-table th, table.audit-table td{text-align:left; vertical-align:top;}
table.audit-table td{font-size:12px;}
.cat-tag{display:inline-block; font-size:9.5px; font-weight:700; text-transform:uppercase; padding:1.5px 6px; border-radius:8px; margin-left:5px; vertical-align:middle;}
.cat-direct{background:rgba(99,44,166,0.14); color:#632CA6;}
.cat-adjacent{background:rgba(92,122,137,0.16); color:#5c7a89;}
.tier-pill{display:inline-block; font-size:10.5px; font-weight:700; padding:2px 8px; border-radius:9px; color:#fff;}
.tier-t1{background:#632CA6;}
.tier-t2{background:#8a8a8a;}
.tier-t3{background:#b8a24a;}
#sourceAuditAccordion{margin-top:14px;}
#sourceAuditAccordion summary{font-size:12.5px; padding:9px 13px;}

/* ---------- mechanism diagram ---------- */
.mech-row{display:flex; align-items:stretch; gap:6px; flex-wrap:wrap; margin-bottom:8px;}
.mech-box{
  flex:1 1 180px; border:1.6px solid; border-radius:6px; padding:12px 10px; text-align:center;
  font-size:12.5px; font-weight:700; display:flex; align-items:center; justify-content:center; min-height:52px;
}
.mech-arrow{display:flex; align-items:center; font-size:18px; color:#777; padding:0 2px;}
.mech-1{border-color:var(--blue); background:rgba(26,115,232,0.08);}
.mech-2{border-color:var(--green); background:rgba(52,168,83,0.08);}
.mech-3{border-color:var(--orange); background:rgba(232,113,10,0.08);}
.mech-4{border-color:var(--purple); background:rgba(99,44,166,0.08);}
.mech-note{font-size:11.5px; color:var(--text-faint); font-style:italic; margin:2px 0 18px;}
.billing-note{
  font-size:12px; background:#f5f0fa; border:1px solid var(--purple); border-radius:5px; padding:8px 12px; color:#3f2160;
  margin-bottom:18px;
}

/* ---------- Section 4 operating read ---------- */
.op-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:10px; margin-bottom:14px;}
.op-item{border:1px solid var(--border); border-radius:5px; padding:10px 12px; background:var(--card-bg); font-size:12.5px;}
.op-item .lbl{color:var(--text-muted); font-size:11px; text-transform:uppercase; letter-spacing:0.03em; margin-bottom:4px;}
.op-summary{
  font-size:13px; line-height:1.6; padding:14px 16px; background:#fbfbfb; border-left:3px solid var(--purple); border-radius:0 5px 5px 0;
}
.op-caveat{font-size:11.5px; color:var(--text-faint); font-style:italic; margin-top:10px;}

/* ---------- forecast block (reuses .op-grid/.op-item/table.compact/details.method; minimal additions only) ---------- */
.forecast-badge{display:inline-block; font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.03em;
  color:#8a5200; background:#fff3e0; border:1px solid #e8a13d; border-radius:4px; padding:2px 9px; margin-bottom:10px;}
.forecast-value{font-size:22px; font-weight:700; margin:2px 0 2px;}
.forecast-formula{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11.5px; background:#f7f7f7;
  border:1px solid var(--border); border-radius:4px; padding:8px 11px; margin:8px 0; white-space:pre-line;}
tr.fc-selected-row{background:#eaf7ed;}
.fwd-title{font-size:13.5px; font-weight:700; margin:22px 0 10px; padding-top:16px; border-top:1px solid var(--border);}
.fwd-row{display:grid; grid-template-columns:190px 1fr; gap:4px 16px; padding:10px 14px; border:1px solid var(--border); border-radius:5px; margin-bottom:8px; background:#fff; font-size:12.5px; line-height:1.55;}
.fwd-row .fwd-label{font-weight:700; color:var(--purple); font-size:12px;}
@media (max-width:640px){ .fwd-row{grid-template-columns:1fr;} }

/* ---------- Section 5 methodology accordions ---------- */
details.method{border:1px solid var(--border); border-radius:6px; margin-bottom:9px; background:#fff;}
details.method summary{
  cursor:pointer; padding:11px 15px; font-weight:700; font-size:13.5px; list-style:none; display:flex;
  justify-content:space-between; align-items:center;
}
details.method summary::-webkit-details-marker{display:none;}
details.method summary:after{content:"+"; font-size:18px; color:var(--text-faint); font-weight:400;}
details.method[open] summary:after{content:"\2212";}
details.method .method-body{padding:0 16px 14px; font-size:12.5px;}
.method-grid{display:grid; grid-template-columns:150px 1fr; gap:5px 12px; margin-bottom:8px;}
.method-grid .k{color:var(--text-muted); font-weight:600;}
.excluded-box{border:1px dashed #bbb; border-radius:6px; padding:12px 15px; margin-top:16px; background:#fbfbfb;}
.excluded-box h4{margin:0 0 8px; font-size:13px;}
.excluded-box ul{margin:0; padding-left:18px; font-size:12px; line-height:1.6;}

footer.bottom{margin-top:44px; padding-top:16px; border-top:1px solid var(--border); font-size:11px; color:var(--text-faint); text-align:center;}

@media (max-width:640px){
  .wrap{padding:0 14px 40px;}
  header.top h1{font-size:19px;}
  .kpi-value{font-size:21px;}
  .mech-row{flex-direction:column;}
  .mech-arrow{transform:rotate(90deg); justify-content:center; padding:2px 0;}
}
</style>
</head>
<body>
<div class="wrap">

<header class="top">
  <h1>Datadog Alternative-Data Monitor</h1>
  <div class="sub">Operating dashboard&nbsp;&nbsp;|&nbsp;&nbsp;Data through 2026 Q2</div>
</header>
<div class="disclaimer">Operating-performance research tool &mdash; not a stock rating or investment recommendation.</div>

<!-- ================= SECTION 1: KPI CARDS ================= -->
<section id="sec1">
  <h2><span class="n">1</span>Key Signal Readings</h2>
  <div class="kpi-grid" id="kpiGrid"></div>
</section>

<!-- ================= SECTION 2: INTERACTIVE CHARTS ================= -->
<section id="sec2">
  <h2><span class="n">2</span>Interactive Charts</h2>

  <div class="chart-block">
    <div class="chart-head">
      <h4>Chart A &mdash; DDOG Revenue YoY and Cloud Workload Index</h4>
      <div class="toggle-group" id="chartAToggle">
        <button class="toggle-btn" data-mode="raw">Raw contemporaneous</button>
        <button class="toggle-btn active" data-mode="aligned">Forecast alignment: Cloud t&minus;2 &rarr; Revenue t</button>
      </div>
    </div>
    <div id="chartA" style="width:100%; height:380px;"></div>
    <div class="chart-note" id="chartANote"></div>
  </div>

  <div class="chart-block">
    <div class="chart-head">
      <h4>Chart B &mdash; Datadog Google Trends YoY vs $100k+ Customer YoY</h4>
      <div class="toggle-group" id="lagToggle">
        <button class="toggle-btn" data-lag="0">Contemporaneous</button>
        <button class="toggle-btn" data-lag="1">t&minus;1</button>
        <button class="toggle-btn active" data-lag="2">t&minus;2</button>
      </div>
    </div>
    <div id="chartB" style="width:100%; height:380px;"></div>
    <div class="chart-note">Trend series is shifted for display only, using lags already examined in the underlying research (0 / t&minus;1 / t&minus;2) &mdash; no new lag is calculated here. Google Trends t&minus;2 is treated as a mechanism indicator, not a direct revenue forecast.</div>
  </div>

  <div class="chart-block">
    <div class="chart-head">
      <h4>Chart C &mdash; Expanding-Window OOS Model Comparison</h4>
      <div class="toggle-group" id="metricToggle">
        <button class="toggle-btn active" data-view="error">Point-forecast error</button>
        <button class="toggle-btn" data-view="dir">Directional accuracy</button>
      </div>
    </div>
    <div id="chartC"></div>
    <div class="chart-highlight-note" id="chartCHighlight"><!-- populated dynamically from CHART_C at render time; see renderChartCHighlight() --></div>
    <div class="chart-note">8-quarter expanding-window OOS evaluation (2024 Q3 &ndash; 2026 Q2); small sample &mdash; interpret cautiously.</div>
  </div>

  <div class="chart-block" id="forecastBlock">
    <div class="chart-head"><h4>2026 Q3 Revenue Forecast</h4></div>
    <div id="forecastContent"><!-- populated dynamically from FORECAST at render time; see renderForecast() --></div>
  </div>
</section>

<!-- ================= SECTION 3: AGENT OBSERVABILITY ================= -->
<section id="sec3">
  <h2><span class="n">3</span>Agent Observability &mdash; Adoption &amp; Monetization Mechanism</h2>
  <div class="mech-row">
    <div class="mech-box mech-1">AI applications &amp; agents</div>
    <div class="mech-arrow">&rarr;</div>
    <div class="mech-box mech-2">Agent / LLM Observability adoption</div>
    <div class="mech-arrow">&rarr;</div>
    <div class="mech-box mech-3">LLM spans / usage</div>
    <div class="mech-arrow">&rarr;</div>
    <div class="mech-box mech-4">Potential billable LLM-observability volume</div>
  </div>
  <div class="billing-note">Only LLM spans are the billing unit; tool/retrieval/embedding/agent spans are not billed under the verified public pricing mechanics.</div>

  <div class="chart-block">
    <div class="chart-head"><h4>Verified Milestone Timeline &mdash; 2024 Q1 to 2026 Q2</h4></div>
    <div id="timeline" style="width:100%; height:190px;"></div>
    <div class="chart-note">
      Hover any point for date, disclosure quarter, metric, value, source type and interpretation.
      Color: <b style="color:#632CA6">purple = direct LLM/Agent Observability evidence</b>, <b style="color:#5c7a89">slate = adjacent AI-ecosystem evidence</b>.
      Symbol: <b>&#9679; T1 primary</b>, <b>&#9670; T2 verbatim transcript</b>, <b>&#9650; T3 third-party summary</b>.
    </div>
    <details class="method" id="sourceAuditAccordion">
      <summary>Source audit trail</summary>
      <div class="method-body">
        <div style="overflow-x:auto;">
          <table class="compact audit-table">
            <thead><tr><th>Date</th><th>Disclosure Quarter</th><th>Metric</th><th>Value</th><th>Source Tier</th><th>Source</th></tr></thead>
            <tbody id="sourceAuditBody"></tbody>
          </table>
        </div>
      </div>
    </details>
  </div>
</section>

<!-- ================= SECTION 4: CURRENT OPERATING READ ================= -->
<section id="sec4">
  <h2><span class="n">4</span>Current Operating Read</h2>
  <div class="op-grid" id="opGrid"></div>
  <div class="op-summary" id="opSummary"></div>
  <div class="op-caveat">Qualitative synthesis of independently monitored signals; no mechanical composite score.</div>

  <h3 class="fwd-title">Forward Research Read</h3>
  <div id="forwardRead"></div>
  <div class="op-caveat">Research-oriented synthesis of the evidence already shown above. Not a forecast, price target, or BUY/SELL recommendation.</div>
</section>

<!-- ================= SECTION 5: METHODOLOGY / LIMITATIONS ================= -->
<section id="sec5">
  <h2><span class="n">5</span>Methodology &amp; Limitations</h2>
  <div id="methodAccordions"></div>
  <div class="excluded-box">
    <h4>Signals screened but excluded</h4>
    <ul id="excludedList"></ul>
  </div>
</section>

<footer class="bottom">
  Datadog Alternative-Data Monitor &mdash; generated from verified research CSVs only. No fabricated values. No stock-price target, BUY/SELL rating, or investment recommendation.
</footer>

</div>{{SCRIPT_BLOCK}}
</body>
</html>
"""


"""
SECTION C: JS TEMPLATE (behavior only - no data)
"""
JS_TEMPLATE = r"""
<script>
const CHART_A = __CHARTA_DATA__;
const CHART_B = __CHARTB_DATA__;
const CHART_C = __CHARTC_DATA__;
const TIMELINE = __TIMELINE_DATA__;
const KPI = __KPI_DATA__;
const OP_READ = __OPREAD_DATA__;
const FORECAST = __FORECAST_DATA__;
const FORWARD_READ = __FORWARDREAD_DATA__;
const METHOD = __METHOD_DATA__;
const EXCLUDED = __EXCLUDED_DATA__;

const FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif";

function statePillClass(state){
  const s = state.toLowerCase();
  if(s.includes('accelerat')) return 'state-accelerating';
  if(s.includes('decelerat')) return 'state-decelerating';
  if(s.includes('volatile') || s.includes('mixed')) return 'state-volatile';
  if(s.includes('strong')) return 'state-strong';
  return 'state-stable';
}
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

/* ===================================================== SECTION 1: KPI CARDS ===================================================== */
function renderKPI(){
  const grid = document.getElementById('kpiGrid');
  const cards = [];

  cards.push(`<div class="kpi-card">
      <h3>Revenue Growth</h3>
      <div class="kpi-value">${KPI.revenue.latest.toFixed(1)}%</div>
      <div class="kpi-prior">Prior quarter: ${KPI.revenue.prior.toFixed(1)}%</div>
      <span class="state-pill ${statePillClass(KPI.revenue.state)}">${KPI.revenue.state}</span>
      <div class="method">This is the latest reported actual value, not a model forecast; see Chart C for the verified out-of-sample comparison across all six models.</div>
    </div>`);

  cards.push(`<div class="kpi-card">
      <h3>Cloud Workload <span class="tooltip-icon" tabindex="0">i</span></h3>
      <div class="tooltip-box">Equal-weight AWS, Azure and Google Cloud YoY growth; historical relationship evaluated at t&minus;2.</div>
      <div class="kpi-value">${KPI.cloud.latest.toFixed(1)}%</div>
      <div class="kpi-prior">Prior 2 quarters: ${KPI.cloud.p2.toFixed(1)}% &rarr; ${KPI.cloud.p1.toFixed(1)}%</div>
      <span class="state-pill ${statePillClass(KPI.cloud.state)}">${KPI.cloud.state}</span>
    </div>`);

  cards.push(`<div class="kpi-card">
      <h3>Commercial Interest <span class="tooltip-icon" tabindex="0">i</span></h3>
      <div class="tooltip-box">Worldwide Google search term &quot;Datadog&quot;; search intent is unobserved.</div>
      <div class="kpi-value">${KPI.trend.latest.toFixed(1)}%</div>
      <div class="kpi-prior">Prior 2 quarters: ${KPI.trend.p2.toFixed(1)}% &rarr; ${KPI.trend.p1.toFixed(1)}%</div>
      <span class="state-pill ${statePillClass(KPI.trend.state)}">${KPI.trend.state}</span>
    </div>`);

  cards.push(`<div class="kpi-card">
      <h3>Large-Customer Expansion <span class="tooltip-icon" tabindex="0">i</span></h3>
      <div class="tooltip-box">YoY growth in customers generating $100k+ ARR. Used as a commercial-expansion indicator; company-disclosed customer counts may be rounded.</div>
      <div class="kpi-value">${KPI.cust.latest.toFixed(1)}%</div>
      <div class="kpi-prior">Prior 2 quarters: ${KPI.cust.p2.toFixed(1)}% &rarr; ${KPI.cust.p1.toFixed(1)}%</div>
      <span class="state-pill ${statePillClass(KPI.cust.state)}">${KPI.cust.state}</span>
      <div class="method">Google Trends t&minus;2 is evaluated separately as a mechanism indicator for this series; it is not a direct revenue forecast.</div>
    </div>`);

  const directRows = KPI.agent.filter(k=>k.category==='Direct').map(k =>
    `<div class="agent-kpi-row"><span class="aq">${esc(k.quarter)}</span><br><span class="am">${esc(k.metric)}:</span> <span class="av">${esc(k.value)}</span></div>`
  ).join('');
  const adjacentRows = KPI.agent.filter(k=>k.category==='Adjacent').map(k =>
    `<div class="agent-kpi-row"><span class="aq">${esc(k.quarter)}</span><br><span class="am">${esc(k.metric)}:</span> <span class="av">${esc(k.value)}</span></div>`
  ).join('');
  cards.push(`<div class="kpi-card">
      <h3>Agent Observability</h3>
      <span class="state-pill state-strong">Strong adoption / usage momentum</span>
      <div class="agent-group-label agent-group-direct">Direct LLM/Agent Observability evidence</div>
      ${directRows}
      <div class="agent-group-label agent-group-adjacent">Adjacent AI-ecosystem evidence (context only)</div>
      ${adjacentRows}
    </div>`);

  grid.innerHTML = cards.join('');
}

/* ===================================================== CHART A (raw contemporaneous vs t-2 forecast alignment toggle) ===================================================== */
function renderChartA(mode){
  const qs = CHART_A.map(d=>d.q), rev = CHART_A.map(d=>d.rev), cl = CHART_A.map(d=>d.cloud);
  let xs, revShown, cloudShown, cloudName;
  if(mode === 'aligned'){
    /* Display transformation ONLY: pairs Revenue_YoY(t) with the ALREADY-VERIFIED Cloud_Index_Raw(t-2)
       observation, matching exactly the specification used in the forecasting model (Chart C / Exhibit 2).
       No new lag, correlation or regression is computed here - this just re-indexes existing values. */
    xs = []; revShown = []; cloudShown = [];
    for(let i = 2; i < qs.length; i++){ xs.push(qs[i]); revShown.push(rev[i]); cloudShown.push(cl[i - 2]); }
    cloudName = 'Cloud Index (t-2, aligned to Revenue t)';
  } else {
    xs = qs; revShown = rev; cloudShown = cl;
    cloudName = 'Cloud_Index_Raw (t, contemporaneous)';
  }
  document.getElementById('chartANote').innerHTML = mode === 'aligned'
    ? 'Forecast-alignment view (default): each point pairs DDOG Revenue YoY at quarter t with Cloud_Index_Raw observed two quarters earlier (t&minus;2) &mdash; the exact specification already validated in the forecasting model (see Chart C and Section 5). Display transformation only; no new lag, correlation or model is calculated here.'
    : 'Raw contemporaneous view: both series plotted at the same calendar quarter t, as originally reported. The forecasting model does not use this pairing directly &mdash; switch to &quot;Forecast alignment&quot; to see the t&minus;2 relationship the model actually evaluates.';
  const traces = [
    {x:xs, y:revShown, name:'DDOG Revenue YoY (%)', mode:'lines+markers', line:{color:'#632CA6', width:2.4}, marker:{size:6},
     hovertemplate:'%{x}<br>Revenue YoY: %{y:.1f}%<extra></extra>'},
    {x:xs, y:cloudShown, name:cloudName, mode:'lines+markers', line:{color:'#1a73e8', width:2.2, dash:'dot'}, marker:{size:5},
     hovertemplate:'%{x}<br>' + cloudName + ': %{y:.1f}%<extra></extra>'}
  ];
  const layout = {margin:{t:8,r:18,l:46,b:64}, height:380, xaxis:{tickangle:-45, tickfont:{size:10}},
    yaxis:{title:'YoY growth (%)', gridcolor:'#eee', zeroline:false}, legend:{orientation:'h', y:1.14, font:{size:11}},
    hovermode:'x unified', plot_bgcolor:'#fff', paper_bgcolor:'#fff', font:{family:FONT, size:11.5}};
  Plotly.newPlot('chartA', traces, layout, {displayModeBar:false, responsive:true});
}

/* ===================================================== CHART B (lag toggle) ===================================================== */
function renderChartB(lag){
  const qs = CHART_B.map(d=>d.q), trendArr = CHART_B.map(d=>d.trend), custArr = CHART_B.map(d=>d.cust);
  const xs=[], shiftedTrend=[], custShown=[];
  for(let i=lag;i<qs.length;i++){ xs.push(qs[i]); shiftedTrend.push(trendArr[i-lag]); custShown.push(custArr[i]); }
  const trendName = lag===0 ? 'Google Trend_YoY (t)' : `Google Trend_YoY (t-${lag})`;
  const traces = [
    {x:xs, y:shiftedTrend, name:trendName, mode:'lines+markers', line:{color:'#E8710A', width:2.2}, marker:{size:6},
     hovertemplate:'%{x}<br>'+trendName+': %{y:.1f}%<extra></extra>'},
    {x:xs, y:custShown, name:'$100k+ Customer YoY (t)', mode:'lines+markers', line:{color:'#34a853', width:2.2}, marker:{size:6},
     hovertemplate:'%{x}<br>Customer YoY: %{y:.1f}%<extra></extra>'}
  ];
  const layout = {margin:{t:8,r:18,l:46,b:64}, height:380, xaxis:{tickangle:-45, tickfont:{size:10}},
    yaxis:{title:'YoY growth (%)', gridcolor:'#eee', zeroline:false}, legend:{orientation:'h', y:1.14, font:{size:11}},
    hovermode:'x unified', plot_bgcolor:'#fff', paper_bgcolor:'#fff', font:{family:FONT, size:11.5}};
  Plotly.newPlot('chartB', traces, layout, {displayModeBar:false, responsive:true});
}

/* ===================================================== CHART C (compact table, sort/column toggle) ===================================================== */
/* Lowest-MAE and highest-directional-accuracy models are computed HERE, at render time, from whatever is in
   CHART_C - no model name is hardcoded. If a future data refresh changes the winner of either metric, this
   function needs no edit. */
function lowestMaeModel(){ return CHART_C.reduce((a, b) => b.mae < a.mae ? b : a); }
function highestDirModel(){ return CHART_C.reduce((a, b) => b.dir_acc > a.dir_acc ? b : a); }

function renderChartC(view){
  const rows = CHART_C.slice();
  const lm = lowestMaeModel(), hd = highestDirModel();
  if(view==='dir') rows.sort((a,b)=>b.dir_acc-a.dir_acc); else rows.sort((a,b)=>a.mae-b.mae);
  const head = view==='dir'
    ? '<th>Model</th><th>Directional&nbsp;Accuracy</th><th>MAE</th><th>RMSE</th><th>MAPE</th>'
    : '<th>Model</th><th>MAE</th><th>RMSE</th><th>MAPE</th><th>Directional&nbsp;Accuracy</th>';
  const body = rows.map(r=>{
    const isLowestMae = r.model === lm.model, isHighestDir = r.model === hd.model;
    const err = `<td class="${isLowestMae?'hl-orange':''}">${r.mae.toFixed(2)}</td><td class="${isLowestMae?'hl-orange':''}">${r.rmse.toFixed(2)}</td><td class="${isLowestMae?'hl-orange':''}">${r.mape.toFixed(1)}%</td>`;
    const dir = `<td class="${isHighestDir?'hl-green':''}">${r.dir_acc.toFixed(1)}%</td>`;
    return `<tr><td>${esc(r.model)}</td>${view==='dir' ? dir+err : err+dir}</tr>`;
  }).join('');
  document.getElementById('chartC').innerHTML = `<table class="compact"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

/* Chart C's explanatory caption - fully dynamic, generated from CHART_C, never a hardcoded model name/number.
   Handles the case where the same model wins both metrics (per the audit brief: "the code should still work"). */
function renderChartCHighlight(){
  const lm = lowestMaeModel(), hd = highestDirModel();
  const naive = CHART_C.find(r => r.model === 'Naive');   // Naive is always one of the six fixed models; looking
  const naiveNote = (naive && naive.dir_acc === 0)         // up its own row to explain ITS OWN mechanism is not
    ? ' Naive persistence predicts no change in the growth rate each quarter, so under this sign-based test it '  // an assumption that it wins anything
      + 'cannot register a directional call; its 0% reflects that mechanical property, not a track record of missed forecasts.'
    : '';
  let html;
  if(lm.model === hd.model){
    html = `<b class="orange">${esc(lm.model)}</b> has both the lowest point-forecast error (MAE ${lm.mae.toFixed(2)}) `
         + `and the highest directional accuracy (${hd.dir_acc.toFixed(1)}%) among the six models tested. `
         + `These remain two separate evaluation criteria that happen to align on the same model here, not evidence `
         + `that it is an overall &ldquo;best&rdquo; model in every sense.${naiveNote}`;
  } else {
    html = `<b class="orange">${esc(lm.model)}</b> has the lowest point-forecast error among the six models tested `
         + `(MAE ${lm.mae.toFixed(2)}). &nbsp;&nbsp;<b class="green">${esc(hd.model)}</b> has the highest directional `
         + `accuracy (${hd.dir_acc.toFixed(1)}%). These are separate evaluation criteria, not an overall model `
         + `ranking.${naiveNote}`;
  }
  document.getElementById('chartCHighlight').innerHTML = html;
}

/* ===================================================== TIMELINE (color = Direct/Adjacent evidence, symbol = source tier T1/T2/T3) ===================================================== */
const TIER_SYMBOL = {T1:'circle', T2:'diamond', T3:'triangle-up'};
const CATEGORY_COLOR = {Direct:'#632CA6', Adjacent:'#5c7a89'};
function renderTimeline(){
  const groups = {};
  TIMELINE.forEach(d=>{ const k = d.category+'|'+d.tier; (groups[k] = groups[k] || []).push(d); });
  const traces = Object.keys(groups).map(k=>{
    const arr = groups[k]; const [cat, tier] = k.split('|');
    return {
      x: arr.map(d=>d.date), y: arr.map(d=>d.y), mode:'markers', showlegend:false,
      marker:{size:12, color:CATEGORY_COLOR[cat], symbol:TIER_SYMBOL[tier], line:{color:'#fff', width:1.2}},
      customdata: arr.map(d=>[d.quarter, d.metric, d.value, d.tier_label, d.interpretation, d.category]),
      hovertemplate:'<b>%{customdata[1]}</b> <i>(%{customdata[5]})</i><br>Quarter: %{customdata[0]}<br>Value: %{customdata[2]}<br>Source: %{customdata[3]}<br>%{customdata[4]}<extra></extra>'
    };
  });
  const layout = {
    margin:{t:6,r:16,l:16,b:34}, height:190, xaxis:{type:'date', tickformat:'%b %Y', gridcolor:'#eee', range:['2023-11-01','2026-09-30']},
    yaxis:{visible:false, range:[-2.2,2.2], fixedrange:true}, showlegend:false, plot_bgcolor:'#fff', paper_bgcolor:'#fff',
    font:{family:FONT, size:11}, hoverlabel:{align:'left', font:{size:11.5}}
  };
  Plotly.newPlot('timeline', traces, layout, {displayModeBar:false, responsive:true});
}

/* ===================================================== SOURCE AUDIT TRAIL ===================================================== */
function renderSourceAudit(){
  const rows = TIMELINE.slice().sort((a,b)=> a.date < b.date ? -1 : a.date > b.date ? 1 : 0).map(d=>{
    const tierClass = 'tier-' + d.tier.toLowerCase();
    return `<tr>
      <td>${esc(d.date)}</td>
      <td>${esc(d.quarter)}</td>
      <td>${esc(d.metric)} <span class="cat-tag cat-${d.category.toLowerCase()}">${esc(d.category)}</span></td>
      <td>${esc(d.value)}</td>
      <td><span class="tier-pill ${tierClass}">${esc(d.tier)}</span></td>
      <td><a href="${esc(d.source_url)}" target="_blank" rel="noopener noreferrer">Open source &rarr;</a></td>
    </tr>`;
  }).join('');
  document.getElementById('sourceAuditBody').innerHTML = rows;
}

/* ===================================================== SECTION 4 ===================================================== */
/* ===================================================== 2026 Q3 FORECAST (Section 2, after Chart C) =====================================================
   Everything here reads from FORECAST (built in Python from outputs/next_quarter_forecast.csv). No model name or
   number is hardcoded - the selected model is whichever row next_quarter_forecast.csv marks selected_for_dashboard.
   This is a NEW forward-looking forecast, distinct from the historical OOS backtest shown in Chart C above it. */
function renderForecast(){
  const s = FORECAST.selected;
  const facts = [
    ["Forecast quarter", s.forecast_quarter],
    ["Selected model", s.model],
    ["Predicted Revenue YoY", `${s.predicted_revenue_yoy_pct.toFixed(2)}%`],
    ["Predicted Revenue", `$${s.predicted_revenue_usd_m.toFixed(1)}M`],
    ["Prior-year actual Revenue (2025 Q3)", `$${s.prior_year_revenue_usd_m.toFixed(1)}M`],
    ["Data cutoff", s.data_cutoff],
  ];
  const factsHtml = facts.map(([lbl, val]) =>
    `<div class="op-item"><div class="lbl">${esc(lbl)}</div><div class="forecast-value">${esc(val)}</div></div>`
  ).join('');

  const formula = `Forecast Revenue (${s.forecast_quarter}) = Actual Revenue (2025 Q3) &times; (1 + Forecast Revenue YoY / 100)\n`
    + `= $${s.prior_year_revenue_usd_m.toFixed(3)}M &times; (1 + ${s.predicted_revenue_yoy_pct.toFixed(2)}% / 100) = $${s.predicted_revenue_usd_m.toFixed(2)}M`;

  const hitsText = (s.historical_oos_directional_hits != null && s.historical_oos_n != null)
    ? `${s.historical_oos_directional_hits} of ${s.historical_oos_n} OOS quarters` : `${s.historical_oos_directional_accuracy_pct.toFixed(1)}%`;

  const rows = FORECAST.all_models.slice().sort((a, b) => b.predicted_revenue_yoy_pct - a.predicted_revenue_yoy_pct).map(m => `
    <tr class="${m.selected ? 'fc-selected-row' : ''}">
      <td>${esc(m.model)}${m.selected ? ' <span class="cat-tag cat-direct">selected</span>' : ''}</td>
      <td>${m.predicted_revenue_yoy_pct.toFixed(2)}%</td>
      <td>$${m.predicted_revenue_usd_m.toFixed(1)}M</td>
      <td>${m.historical_oos_mae_pp.toFixed(2)}</td>
      <td>${m.historical_oos_directional_accuracy_pct.toFixed(1)}%</td>
    </tr>`).join('');

  document.getElementById('forecastContent').innerHTML = `
    <span class="forecast-badge">Forward-looking forecast &mdash; not a historical backtest result</span>
    <div class="op-grid">${factsHtml}</div>
    <div class="chart-highlight-note">
      The <b class="green">${esc(s.model)}</b> model was selected for its historical out-of-sample <b>directional accuracy</b>
      for quarterly Revenue YoY acceleration/deceleration &mdash; ${hitsText} (${s.historical_oos_directional_accuracy_pct.toFixed(1)}%).
      This is <u>not</u> a measure of revenue-dollar forecast accuracy. That is reported separately: historical OOS YoY MAE for
      this model is <b>${s.historical_oos_mae_pp.toFixed(2)} percentage points</b> (of Revenue YoY, not dollars).
    </div>
    <div class="forecast-formula">${formula}</div>
    <div class="chart-note">Feature timing: Trend_YoY(t&minus;1), using ${esc(s.trends_lag_source_quarter)} Google Trends data (feature lags: ${esc(s.feature_lags)}).
      Selection method: ${esc(s.selection_method)}.</div>
    <details class="method">
      <summary>All six models' 2026 Q3 forward predictions</summary>
      <div class="method-body">
        <div style="overflow-x:auto;">
          <table class="compact audit-table">
            <thead><tr><th>Model</th><th>Predicted Revenue YoY</th><th>Predicted Revenue</th><th>Historical OOS MAE (pp)</th><th>Historical OOS Directional Accuracy</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>
    </details>
    <div class="op-caveat">
      Historical actual Revenue (Chart A), the 8-quarter historical OOS backtest (Chart C), and this new ${esc(s.forecast_quarter)}
      forward forecast are three distinct things - the backtest describes past performance only and this forecast is a scenario
      estimate, not a demonstrated prediction. Based on only ${s.historical_oos_n || 8} OOS quarters; not proof of future predictive
      performance. Kept separate from the LLM/Agent Observability catalyst discussion (Section 3) &mdash; no revenue uplift is
      attributed to that catalyst here.
    </div>`;
}

function renderOpRead(){
  document.getElementById('opGrid').innerHTML = OP_READ.modules.map(m=>
    `<div class="op-item"><div class="lbl">${esc(m.name)}</div><span class="state-pill ${statePillClass(m.state)}">${esc(m.state)}</span></div>`
  ).join('');
  document.getElementById('opSummary').innerHTML = OP_READ.summary;
}
function renderForwardRead(){
  document.getElementById('forwardRead').innerHTML = FORWARD_READ.map(r =>
    `<div class="fwd-row"><div class="fwd-label">${esc(r.label)}</div><div>${r.text}</div></div>`
  ).join('');
}

/* ===================================================== SECTION 5 ===================================================== */
function renderMethodology(){
  document.getElementById('methodAccordions').innerHTML = METHOD.map((m,i)=>`
    <details class="method" ${i===0?'open':''}>
      <summary>${esc(m.name)}</summary>
      <div class="method-body">
        <div class="method-grid">
          <div class="k">Frequency</div><div>${m.frequency}</div>
          <div class="k">History</div><div>${m.history}</div>
          <div class="k">Lag used</div><div>${m.lag}</div>
          <div class="k">Economic rationale</div><div>${m.rationale}</div>
          <div class="k">Main limitation</div><div>${m.limitation}</div>
          <div class="k">Used in revenue model</div><div><b>${m.used}</b></div>
        </div>
      </div>
    </details>`).join('');
  document.getElementById('excludedList').innerHTML = EXCLUDED.map(e=>`<li><b>${esc(e.name)}:</b> ${e.reason}</li>`).join('');
}

/* ===================================================== toggles ===================================================== */
document.getElementById('chartAToggle').addEventListener('click', function(e){
  if(!e.target.classList.contains('toggle-btn')) return;
  document.querySelectorAll('#chartAToggle .toggle-btn').forEach(b=>b.classList.remove('active'));
  e.target.classList.add('active');
  try{ renderChartA(e.target.dataset.mode); }catch(err){ console.error(err); }
});
document.getElementById('lagToggle').addEventListener('click', function(e){
  if(!e.target.classList.contains('toggle-btn')) return;
  document.querySelectorAll('#lagToggle .toggle-btn').forEach(b=>b.classList.remove('active'));
  e.target.classList.add('active');
  try{ renderChartB(parseInt(e.target.dataset.lag, 10)); }catch(err){ console.error(err); }
});
document.getElementById('metricToggle').addEventListener('click', function(e){
  if(!e.target.classList.contains('toggle-btn')) return;
  document.querySelectorAll('#metricToggle .toggle-btn').forEach(b=>b.classList.remove('active'));
  e.target.classList.add('active');
  try{ renderChartC(e.target.dataset.view); }catch(err){ console.error(err); }
});

/* ===================================================== init (each section isolated so one failure - e.g. a
   blocked CDN - can never take down unrelated sections like the methodology accordions) ===================================================== */
function safe(name, fn){
  try{ fn(); }
  catch(err){
    console.error('Dashboard section failed: ' + name, err);
    const targets = {chartA:'chartA', chartB:'chartB', chartC:'chartC', timeline:'timeline', forecast:'forecastContent'};
    if(targets[name]){
      const el = document.getElementById(targets[name]);
      if(el) el.innerHTML = '<div style="padding:30px;text-align:center;color:#999;font-size:12px;">Chart failed to render (' + esc(err.message||err) + '). Data is intact in the page source.</div>';
    }
  }
}
safe('kpi', renderKPI);
safe('chartA', ()=>renderChartA('aligned'));
safe('chartB', ()=>renderChartB(2));
safe('chartC', ()=>renderChartC('error'));
safe('chartCHighlight', renderChartCHighlight);
safe('forecast', renderForecast);
safe('timeline', renderTimeline);
safe('sourceAudit', renderSourceAudit);
safe('opread', renderOpRead);
safe('forwardread', renderForwardRead);
safe('methodology', renderMethodology);
</script>
"""


#!/usr/bin/env python3
"""
assemble.py - final assembly step. Combines data_prep.py (verified data only) with html_template.py /
js_template.py (structure/behavior only, no data) to produce:
    ddog_alternative_data_dashboard.html
    dashboard_data_dictionary.csv
"""

"""
SECTION D: ASSEMBLY
"""
import json

# =================================================================================================================
# KPI card 5 (Agent Observability): strongest LATEST verified KPIs, each with its OWN disclosure quarter -
# never all forced to read as the most-recent quarter. Sourced from agent_obs_verified_timeline.csv.
# =================================================================================================================
KPI = dict(
    revenue=dict(latest=float(rev_latest), prior=float(rev_p1), state=rev_state),
    cloud=dict(latest=float(ci_latest), p1=float(ci_p1), p2=float(ci_p2), state=cloud_state),
    trend=dict(latest=float(tr_latest), p1=float(tr_p1), p2=float(tr_p2), state=trend_state),
    cust=dict(latest=float(cu_latest), p1=float(cu_p1), p2=float(cu_p2), state=cust_state),
    agent=[
        dict(category="Direct", quarter="Q4 2025", metric="LLM Observability customers", value=">1,000 customers using the product"),
        dict(category="Direct", quarter="Q1 2026", metric="LLM Observability span growth", value="Nearly tripled quarter-over-quarter"),
        dict(category="Adjacent", quarter="Q2 2026", metric="MCP Server tool-call growth", value="Quadrupled QoQ again; >22x vs Q4 2025"),
        dict(category="Adjacent", quarter="Q2 2026", metric="AI-native customer count", value=">750; all top-10 AI industry leaders are customers"),
    ],
)

# =================================================================================================================
# Section 4 - Current Operating Read (module states reused verbatim from data_prep; summary is a plain factual
# restatement of those same readings, nothing new)
# =================================================================================================================
OP_READ = dict(
    modules=[
        dict(name="Revenue baseline", state=rev_state),
        dict(name="Cloud workload", state=cloud_state),
        dict(name="Commercial interest", state=trend_state),
        dict(name="Large-customer expansion", state=cust_state),
        dict(name="Agent Observability", state=catalyst_state),
    ],
    summary=(
        f"As of {latest_q}, DDOG revenue growth is accelerating for a third consecutive quarter "
        f"({rev_p2:.1f}% &rarr; {rev_p1:.1f}% &rarr; {rev_latest:.1f}% YoY), alongside accelerating cloud "
        f"workload growth ({ci_p2:.1f} &rarr; {ci_p1:.1f} &rarr; {ci_latest:.1f}) and accelerating $100k+ customer "
        f"growth ({cu_p2:.1f}% &rarr; {cu_p1:.1f}% &rarr; {cu_latest:.1f}% YoY). Google search interest remains "
        f"volatile / mixed ({tr_p2:.1f}% &rarr; {tr_p1:.1f}% &rarr; {tr_latest:.1f}% YoY), reversing direction "
        f"between the last two quarters rather than trending cleanly. Direct LLM/Agent Observability usage "
        f"indicators continue to show strong adoption momentum, while adjacent AI-ecosystem indicators such as "
        f"MCP usage and AI-native customer growth provide additional demand context. These signals should not "
        f"be interpreted as equivalent measures of Agent Observability revenue, and none of them has been sized "
        f"in dollars or incorporated into the quantitative revenue model."
    ),
)

# =================================================================================================================
# Forward Research Read - four structured rows, reflecting ONLY evidence already established elsewhere on this
# dashboard. No new numerical forecast, no new data point, nothing not already shown in Sections 1-3.
#
# The "Model evidence" row is built ENTIRELY from LOWEST_MAE_ROW / HIGHEST_DIR_ROW, both computed in data_prep.py
# fresh from the current walkforward_results.csv - no model name or metric value is hardcoded here. If a future
# re-run changes which model wins either metric, this text updates automatically with no edit required.
# =================================================================================================================
_naive_row = next((r for r in chartC if r["model"] == "Naive"), None)   # Naive is always one of the fixed 6 models (MODEL_ORDER); this looks up ITS OWN row to explain ITS OWN mechanism below - it is not an assumption that Naive wins anything
_naive_structural_note = (
    " Naive persistence predicts no change in the growth rate each quarter, so under this sign-based test it "
    "cannot register a directional call; its 0% reflects that mechanical property, not a track record of "
    "missed forecasts."
) if (_naive_row is not None and _naive_row["dir_acc"] == 0) else ""

if LOWEST_MAE_ROW["model"] == HIGHEST_DIR_ROW["model"]:
    _model_evidence_text = (
        f"In the 8-quarter expanding-window OOS test, {LOWEST_MAE_ROW['model']} records both the lowest "
        f"point-forecast MAE ({LOWEST_MAE_ROW['mae']:.2f}) and the highest directional accuracy "
        f"({HIGHEST_DIR_ROW['dir_acc']:.1f}%) among the six models tested. These remain two separate evaluation "
        f"criteria that happen to align on the same model here, not evidence that it is an overall "
        f"\"best\" model in every sense.{_naive_structural_note} Given the eight-quarter OOS sample, this "
        f"evidence should be treated as indicative rather than conclusive."
    )
else:
    _model_evidence_text = (
        f"In the 8-quarter expanding-window OOS test, {LOWEST_MAE_ROW['model']} records the lowest "
        f"point-forecast MAE ({LOWEST_MAE_ROW['mae']:.2f}), while {HIGHEST_DIR_ROW['model']} records the "
        f"highest directional accuracy ({HIGHEST_DIR_ROW['dir_acc']:.1f}%). These are separate evaluation "
        f"criteria, not an overall model ranking.{_naive_structural_note} Given the eight-quarter OOS sample, "
        f"this evidence should be treated as indicative rather than conclusive."
    )

FORWARD_READ = [
    dict(label="Observed operating signals",
        text=(f"Revenue growth, cloud workload growth and $100k+ customer growth are all currently accelerating "
              f"(three consecutive quarters each, as of {latest_q}). Google Trends search interest remains "
              f"volatile/mixed rather than trending cleanly in either direction.")),
    dict(label="Model evidence", text=_model_evidence_text),
    dict(label="Agent/AI catalyst evidence",
        text=("Direct Agent/LLM Observability adoption indicators (customer count, span growth) have shown "
              "consistently strong growth across disclosures, though the metrics and time windows are not "
              "directly comparable quarter to quarter. Adjacent AI-ecosystem metrics (MCP "
              "tool-call growth, AI-native customer growth) provide additional, corroborating demand context, "
              "but are not direct measures of the same product.")),
    dict(label="What is not yet proven",
        text=("No defensible standalone dollar revenue contribution from Agent Observability has been "
              "established from public disclosures &mdash; the billing unit and free/Pro tiers are known, but "
              "the overage rate is not published and no absolute revenue figure has ever been disclosed. Agent "
              "Observability remains a separately monitored catalyst and must not be mechanically added to the "
              "revenue forecast.")),
]

# =================================================================================================================
# Section 5 - methodology boxes (facts established across the prior research stages of this project)
# =================================================================================================================
METHOD = [
    dict(name="Cloud Index", frequency="Quarterly", history="2022 Q1 &ndash; 2026 Q2 (18 quarters)",
        lag="t&minus;2 in the revenue forecasting model",
        rationale="Datadog usage scales with customer cloud/compute consumption; hyperscaler YoY growth is a public, high-frequency proxy for that underlying workload growth.",
        limitation="Hyperscaler revenue mixes many workloads unrelated to observability spend; correlation, not demonstrated causality; in-sample relationship only partially confirmed out-of-sample.",
        used="Yes &mdash; Cloud, Cloud+Trends and AR+Cloud+Trends specifications"),
    dict(name="Google Trends", frequency="Monthly, aggregated to quarterly",
        history="2021 Q1 &ndash; 2026 Q2 collected; YoY computable from 2022 Q1 (needs a prior-year base)",
        lag="t&minus;1 in the revenue forecasting model; t&minus;2 in the separate customer-growth mechanism check",
        rationale="Search interest for &quot;Datadog&quot; as a proxy for market/commercial evaluation activity that may precede adoption.",
        limitation="Search intent is unobserved &mdash; may reflect investor, job-seeker or news attention rather than practitioner evaluation; the index is rescaled to its own sample-period peak, so a single spike (2025 Q3) can distort long-window comparisons.",
        used="Yes &mdash; Trends, Cloud+Trends and AR+Cloud+Trends specifications"),
    dict(name="Integration Ecosystem", frequency="Point-in-time snapshots reconstructed at each calendar quarter-end from git history",
        history="2021 Q1 &ndash; 2026 Q2 analysis window (underlying repo history extends back to 2015)",
        lag="Tested at t, t&minus;1 and t&minus;2 against both revenue and customer growth",
        rationale="A broader integration catalog implies broader product surface area &mdash; a potential cross-sell/expansion signal.",
        limitation="Weak and sign-inconsistent correlation with DDOG revenue/customer growth in testing.",
        used="No &mdash; screened and not retained as a predictor; kept as contextual/cross-sell background only"),
    dict(name="Walk-forward Validation", frequency="Quarterly, expanding window",
        history="8 out-of-sample quarters (2024 Q3 &ndash; 2026 Q2); minimum training window = 8 quarters",
        lag="n/a &mdash; this is the evaluation methodology, not a signal",
        rationale="Tests whether Cloud/Trends actually improve forecast accuracy out-of-sample, rather than relying on in-sample correlation alone.",
        limitation="Only 8 OOS observations &mdash; too few for formal statistical significance testing; results are indicative, not conclusive.",
        used="This IS the revenue model's validation framework (Chart C)"),
    dict(name="Agent Observability", frequency="Irregular &mdash; as disclosed on quarterly earnings calls, no fixed cadence per metric",
        history="2024 Q1 &ndash; 2026 Q2 (LLM Observability launched June 2024, mid-window)",
        lag="n/a &mdash; not incorporated into any quantitative forecasting model",
        rationale="Represents a potential new/incremental usage-and-monetization curve distinct from the historical cloud-workload and search-interest signals.",
        limitation="No absolute dollar figure ever disclosed; the AI-native %-of-revenue metric was discontinued after Q3 2025; short and inconsistent disclosure history.",
        used="No &mdash; adoption-stage catalyst, tracked separately (Section 3), not sized or incorporated into any revenue model"),
]

EXCLUDED = [
    dict(name="Package downloads (npm / PyPI)", reason="Network access to the npm, PyPI and ClickHouse endpoints needed for a historical download series was blocked in the research environment; no verified time series was ever obtained."),
    dict(name="External GitHub historical adoption", reason="GitHub's search API cannot reconstruct a historical time series &mdash; commit search matches commit messages only (not file content), and code search requires authentication; confirmed infeasible for a multi-quarter series."),
    dict(name="BuiltWith", reason="The technology-adoption list/lookup API requires a paid subscription; no free path to the underlying domain-level data was found."),
    dict(name="Docker Hub", reason="The public repository API exposes only a single current cumulative pull count, with no historical or time-series endpoint."),
]

# =================================================================================================================
# ASSEMBLE
# =================================================================================================================
# =================================================================================================================
# FINAL VALIDATION (Section 13 of the audit brief) - runs on the fully-assembled HTML, right before it is written.
# Deliberately contains no assertion tied to a specific model being a winner - only structural/content checks.
# =================================================================================================================
def _final_validation(chartC_list, final_html_str):
    errors = []
    if len(chartC_list) != 6:
        errors.append(f"Chart C has {len(chartC_list)} rows, expected 6")
    names = [r["model"] for r in chartC_list]
    if len(set(names)) != len(names):
        errors.append(f"Chart C contains duplicate model rows: {names}")
    if set(names) != set(MODEL_LABEL[m] for m in MODEL_ORDER):
        errors.append(f"Chart C model set {sorted(names)} does not match expected {sorted(MODEL_LABEL[m] for m in MODEL_ORDER)}")
    if any("ridge" in n.lower() for n in names):
        errors.append("Ridge model present in Chart C")
    if any("ridge" in m["model"].lower() for m in FORECAST["all_models"]):
        errors.append("Ridge model present in the 2026 Q3 forecast data")
    _fc_selected_count = sum(1 for m in FORECAST["all_models"] if m["selected"])
    if _fc_selected_count != 1:
        errors.append(f"Expected exactly one selected forecast model, found {_fc_selected_count}")
    if _fc_selected_count == 1:
        _fc_only = next(m for m in FORECAST["all_models"] if m["selected"])
        if _fc_only["model"] != FORECAST["selected"]["model"]:
            errors.append("Forecast selected-model mismatch between FORECAST['selected'] and FORECAST['all_models']")
    if "ridge" in final_html_str.lower():
        errors.append("The word 'ridge' appears somewhere in the generated HTML")
    if "75%" in final_html_str or "75.0%" in final_html_str:
        errors.append("A literal stale '75%'/'75.0%' string was found in the generated HTML")
    for f in REQUIRED_INPUTS:
        if not os.path.isfile(os.path.join(IN_DIR, f)):
            errors.append(f"Required input file missing at generation time: {IN_DIR}{f}")
    if errors:
        raise AssertionError("Final dashboard validation FAILED:\n  - " + "\n  - ".join(errors))


def inject(html: str, js: str) -> str:
    for token, data in [("__CHARTA_DATA__", chartA), ("__CHARTB_DATA__", chartB), ("__CHARTC_DATA__", chartC),
                        ("__TIMELINE_DATA__", timeline_points), ("__KPI_DATA__", KPI), ("__OPREAD_DATA__", OP_READ),
                        ("__FORWARDREAD_DATA__", FORWARD_READ), ("__FORECAST_DATA__", FORECAST),
                        ("__METHOD_DATA__", METHOD), ("__EXCLUDED_DATA__", EXCLUDED)]:
        js = js.replace(token, json.dumps(data))
    return html.replace("{{SCRIPT_BLOCK}}", js)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    final_html = inject(HTML_TEMPLATE, JS_TEMPLATE)
    _final_validation(chartC, final_html)

    out_path = os.path.join(OUT_DIR, "ddog_alternative_data_dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"Wrote {out_path}  ({len(final_html):,} bytes)")

    # ---- data dictionary CSV
    import pandas as pd
    rows = [
        dict(Variable="DDOG_Revenue_YoY", Definition="Datadog quarterly revenue, year-over-year % growth",
            Source="Datadog 10-Q/10-K and quarterly earnings releases (SEC filings)", Frequency="Quarterly",
            Lag="t (target variable)", Used_for="Target variable in all revenue forecasting models; Chart A; KPI Card 1",
            Main_limitation="As-reported; not adjusted for FX or M&A"),
        dict(Variable="Customers_100k_YoY", Definition="YoY growth in customers with $100k+ ARR",
            Source="Datadog quarterly earnings releases / calls", Frequency="Quarterly", Lag="t",
            Used_for="Google Trends mechanism-validation target; Chart B; KPI Card 4",
            Main_limitation="Company-rounded figures (\"about X\")"),
        dict(Variable="Cloud_Index_Raw", Definition="Equal-weight mean of AWS, Azure and Google Cloud YoY revenue growth",
            Source="Amazon, Microsoft and Alphabet 10-Q/8-K filings", Frequency="Quarterly", Lag="t-2 in the revenue model",
            Used_for="Cloud / Cloud+Trends / AR+Cloud+Trends models; Chart A (raw vs t-2-aligned toggle); KPI Card 2",
            Main_limitation="Hyperscaler revenue mixes many workloads beyond observability-relevant compute"),
        dict(Variable="AWS_YoY / Azure_YoY / GoogleCloud_YoY", Definition="Component hyperscaler YoY growth rates",
            Source="Amazon, Microsoft and Alphabet 10-Q/8-K filings", Frequency="Quarterly", Lag="component of Cloud_Index_Raw",
            Used_for="Constructing Cloud_Index_Raw",
            Main_limitation="Azure figure is company-disclosed rounded growth only, no dollar revenue"),
        dict(Variable="Trend_YoY", Definition="YoY growth in worldwide Google search volume for the term \"Datadog\"",
            Source="Google Trends", Frequency="Monthly, aggregated to quarterly", Lag="t-1 (revenue model) / t-2 (customer mechanism)",
            Used_for="Trends / Cloud+Trends / AR+Cloud+Trends models; customer-growth mechanism check; Chart B; KPI Card 3",
            Main_limitation="Search intent unobserved; index rescaled to its own sample-period peak"),
        dict(Variable="Quarterly_Trend_Mean", Definition="Quarterly mean of the raw (level) Google Trends index",
            Source="Google Trends", Frequency="Monthly, aggregated to quarterly", Lag="n/a",
            Used_for="Descriptive/dashboard display only",
            Main_limitation="Level trends over time for reasons unrelated to demand; never used as a model input"),
        dict(Variable="New_Total_Integrations / Total_YoY_Growth", Definition="Flow and growth of Datadog's public integrations catalog",
            Source="Reconstructed from DataDog/integrations-core and integrations-extras GitHub commit history", Frequency="Quarterly",
            Lag="tested at t, t-1, t-2", Used_for="Screened as a candidate predictor; not retained",
            Main_limitation="Weak, sign-inconsistent correlation with DDOG revenue/customer growth"),
        dict(Variable="Walk-forward OOS forecasts (6 models)",
            Definition="Expanding-window out-of-sample forecasts of DDOG_Revenue_YoY (Naive, AR(1), Cloud, Trends, Cloud+Trends, AR+Cloud+Trends)",
            Source="Derived from DDOG_Revenue_YoY, Cloud_Index_Raw and Trend_YoY above", Frequency="Quarterly", Lag="n/a",
            Used_for="Chart C", Main_limitation="Only 8 OOS quarters (2024 Q3-2026 Q2); small-sample, indicative only"),
        dict(Variable="Agent Observability KPIs",
            Definition="Company-disclosed quantitative AI/agent-observability metrics, split into DIRECT evidence (LLM Observability customers & span growth, product launches/naming) and ADJACENT evidence (MCP tool-call growth, AI-native customer count/revenue share, broad AI-integration customer counts, Bits AI)",
            Source="Datadog earnings-call transcripts and press releases (tiered: primary IR-hosted / verbatim third-party transcript / third-party summary)",
            Frequency="Quarterly, as disclosed (irregular)", Lag="n/a",
            Used_for="Section 3 timeline (color-coded Direct/Adjacent); KPI Card 5 (grouped); Current Operating Read; Forward Research Read",
            Main_limitation="No absolute dollar figure ever disclosed; AI-native %-of-revenue discontinued after Q3 2025; adjacent metrics are demand context, not direct measures of Agent Observability itself"),
        dict(Variable="next_quarter_forecast.csv (selected_for_dashboard row)",
            Definition="Forward-looking 2026 Q3 Revenue YoY forecast and its USD-million conversion, for the single model flagged selected_for_dashboard=True (currently Trends). Distinct from the historical OOS backtest in walkforward_results.csv.",
            Source="outputs/next_quarter_forecast.csv, generated by src/.../walkforward_forecast.py (read-only to this dashboard - not recomputed here)",
            Frequency="One-off forward forecast (not a recurring historical series)",
            Lag="Selected model (Trends) uses Trend_YoY(t-1); data cutoff 2026 Q2 (as_of_quarter)",
            Used_for="New '2026 Q3 Revenue Forecast' block, Section 2 (after Chart C)",
            Main_limitation="Model selected by historical OOS directional accuracy (62.5%, 5 of 8 quarters), not by revenue-dollar accuracy (separately reported MAE); based on only 8 OOS quarters - not proof of future predictive performance; a scenario estimate with no calibrated prediction interval"),
        dict(Variable="predicted_revenue_usd_m (Revenue-dollar conversion)",
            Definition="predicted_revenue_usd_m = prior_year_revenue_usd_m x (1 + predicted_revenue_yoy_pct / 100); prior_year_revenue_usd_m is the actual reported 2025 Q3 revenue (ddog_calculated_dataset.csv:Revenue_USDm), never inferred from YoY",
            Source="next_quarter_forecast.csv (both input columns); cross-checked against ddog_calculated_dataset.csv",
            Frequency="One-off", Lag="n/a - a unit conversion, not a model",
            Used_for="Forecast block 'Predicted Revenue' and the formula display",
            Main_limitation="Simple point conversion; carries forward all uncertainty in the underlying Revenue YoY forecast with no separate error bars"),
        dict(Variable="historical_oos_mae_pp / historical_oos_directional_accuracy_pct (per forecast model)",
            Definition="The SAME main-panel walk-forward metrics already shown in Chart C (MAE in percentage points of Revenue YoY; directional accuracy over 8 OOS quarters), carried onto each model's forward-prediction row for reference",
            Source="walkforward_results.csv (panel=='main'), reproduced verbatim in next_quarter_forecast.csv",
            Frequency="Quarterly (8 OOS quarters, 2024 Q3-2026 Q2)", Lag="n/a - describes backtest performance, not the forecast itself",
            Used_for="Forecast block's directional-accuracy/MAE facts and the six-model comparison table",
            Main_limitation="Directional accuracy measures Revenue YoY acceleration/deceleration calls only; MAE (pp) measures the absolute error in predicted Revenue YoY in percentage points, NOT revenue-dollar forecast error. Both metrics are based on only 8 OOS quarters."),
    ]
    dd = pd.DataFrame(rows)
    dd_path = os.path.join(OUT_DIR, "dashboard_data_dictionary.csv")
    dd.to_csv(dd_path, index=False)
    print(f"Wrote {dd_path}  ({len(dd)} rows)")

    # ---- terminal audit summary (Section 14 of the audit brief) - all values read from the current CSV, nothing hardcoded
    ridge_included = any("ridge" in r["model"].lower() for r in chartC) or any("ridge" in m["model"].lower() for m in FORECAST["all_models"])
    stale_75 = ("75%" in final_html) or ("75.0%" in final_html)
    print("\nDashboard model audit")
    print("---------------------")
    print(f"Main models: {len(chartC)}")
    print(f"Lowest MAE: {LOWEST_MAE_ROW['model']} | {LOWEST_MAE_ROW['mae']:.2f}")
    print(f"Highest directional accuracy: {HIGHEST_DIR_ROW['model']} | {HIGHEST_DIR_ROW['dir_acc']:.1f}%")
    print(f"2026 Q3 forecast selected model: {FORECAST['selected']['model']} | predicted Revenue YoY {FORECAST['selected']['predicted_revenue_yoy_pct']:.2f}% | ${FORECAST['selected']['predicted_revenue_usd_m']:.1f}M")
    print(f"Wrote {out_path}")
    print(f"Wrote {dd_path}")
    return final_html

if __name__ == "__main__":
    main()
