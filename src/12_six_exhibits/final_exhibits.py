#!/usr/bin/env python3
"""
final_exhibits.py - the six presentation exhibits for the final DDOG Alternative Data Research deliverable.

No new data is collected and no new model specification is run: every number here is read from CSVs already
produced and verified in earlier stages of this project (cloud index, Google Trends, DDOG fundamentals, the
walk-forward results, and the Agent Observability catalyst research). This file only computes the summary
statistics needed to LABEL those existing results precisely (e.g. the exact Pearson/Spearman for a scatter) and
renders them as clean, presentation-quality figures.

Outputs (all PNG, outputs/):
  exhibit1_framework.png                - schematic: 3 signal classes across the 4 research threads
  exhibit2_cloud_leadlag_scatter.png     - Cloud_Index_Raw(t-2) vs DDOG Revenue YoY(t)
  exhibit3_trends_mechanism_scatter.png  - Google Trend_YoY(t-2) vs $100k+ Customer YoY(t)
  exhibit4_walkforward_comparison.png    - 6-model OOS comparison (error metrics + directional accuracy)
  exhibit5_flywheel_refined.png          - Agent Observability flywheel, trimmed to 5-6 strongest milestones
  exhibit6_dashboard_mockup.png          - PM-style 5-module operating dashboard (no composite signal)
"""
from __future__ import annotations
import os
import textwrap
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

IN_DIR = "outputs/"
OUT_DIR = "outputs/"
os.makedirs(OUT_DIR, exist_ok=True)
plt.rcParams.update({"font.size": 10.5, "axes.spines.top": False, "axes.spines.right": False})

C_PURPLE, C_ORANGE, C_GREEN, C_BLUE, C_GRAY = "#632CA6", "#E8710A", "#34a853", "#1a73e8", "#8a8a8a"


# =================================================================================================================
# shared stat helper (re-derives exact r/rho from the ALREADY-COLLECTED data; not a new specification)
# =================================================================================================================
def leadlag_xy(df, xcol, ycol, k, qcol="Quarter"):
    d = pd.DataFrame({"x": df[xcol].shift(k), "y": df[ycol], "q": df[qcol]}).dropna().reset_index(drop=True)
    r, _ = stats.pearsonr(d.x, d.y); rho, _ = stats.spearmanr(d.x, d.y)
    return d, r, rho


# =================================================================================================================
# EXHIBIT 1 — Research framework schematic
# =================================================================================================================
def exhibit1_framework(path):
    fig, ax = plt.subplots(figsize=(12.5, 7.2))
    ax.set_xlim(0, 12); ax.set_ylim(0, 8); ax.axis("off")
    ax.set_title("Exhibit 1.  Datadog Alternative-Data Research Framework", fontsize=15, fontweight="bold", pad=14)

    def box(x, y, w, h, text, color, fontsize=10.5, alpha=0.16):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.10",
                                    linewidth=1.5, edgecolor=color, facecolor=color, alpha=alpha))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, fontweight="bold", color="#222")

    def arrow(x0, y0, x1, y1, color="#555"):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=16, lw=1.8, color=color))

    rowlab_x = 0.15
    # ---- Row 1: Cloud (historical quantitative signal)
    y = 6.3
    ax.text(rowlab_x, y + 0.55, "HISTORICAL\nQUANTITATIVE\nSIGNAL", fontsize=8.7, fontweight="bold", color=C_BLUE, va="center")
    box(1.9, y, 2.1, 0.9, "Cloud\nWorkload", C_BLUE); arrow(4.0, y + 0.45, 4.7, y + 0.45)
    box(4.7, y, 2.4, 0.9, "Usage\nintensity", C_BLUE); arrow(7.1, y + 0.45, 7.8, y + 0.45)
    box(7.8, y, 2.1, 0.9, "Revenue", C_BLUE)
    ax.text(10.2, y + 0.45, "Exhibit 2\n(t-2 lead, evaluated\nout-of-sample)", fontsize=8, color=C_BLUE, va="center", style="italic")

    # ---- Row 2: Google Trends (historical quantitative signal, via a different path)
    y = 4.85
    ax.text(rowlab_x, y + 0.55, "HISTORICAL\nQUANTITATIVE\nSIGNAL", fontsize=8.7, fontweight="bold", color=C_ORANGE, va="center")
    box(1.9, y, 2.1, 0.9, "Datadog\nSearch Interest", C_ORANGE); arrow(4.0, y + 0.45, 4.7, y + 0.45)
    box(4.7, y, 2.4, 0.9, "Commercial interest\n/ adoption", C_ORANGE); arrow(7.1, y + 0.45, 7.8, y + 0.45)
    box(7.8, y, 2.4, 0.9, "$100k+ customer\ngrowth", C_ORANGE); arrow(10.2, y + 0.45, 10.85, y + 0.45)
    ax.text(11.35, y + 0.45, "Revenue", fontsize=9.5, fontweight="bold", color="#222", va="center", ha="center")
    ax.text(6.9, y - 0.35, "Exhibit 3: mechanism validated against customer growth, not revenue directly", fontsize=8, color=C_ORANGE, ha="center", style="italic")

    # ---- Row 3: Integration ecosystem (contextual indicator)
    y = 3.15
    ax.text(rowlab_x, y + 0.45, "CONTEXTUAL\nINDICATOR", fontsize=8.7, fontweight="bold", color=C_GREEN, va="center")
    box(1.9, y, 2.6, 0.9, "Integration\nEcosystem", C_GREEN); arrow(4.5, y + 0.45, 5.2, y + 0.45)
    box(5.2, y, 3.6, 0.9, "Product breadth / cross-sell context\n(not used as a primary predictor)", C_GREEN, fontsize=9.5)

    # ---- Row 4: Agent Observability (emerging catalyst)
    y = 1.45
    ax.text(rowlab_x, y + 0.45, "EMERGING\nCATALYST", fontsize=8.7, fontweight="bold", color=C_PURPLE, va="center")
    box(1.9, y, 3.0, 0.9, "AI / Agent\nObservability", C_PURPLE); arrow(4.9, y + 0.45, 5.6, y + 0.45)
    box(5.6, y, 4.2, 0.9, "Emerging incremental usage catalyst\n(not yet in any revenue model)", C_PURPLE, fontsize=9.5)
    ax.text(6.9, y - 0.35, "Exhibit 5: adoption/usage tracked; monetization not sized from public data", fontsize=8, color=C_PURPLE, ha="center", style="italic")

    # legend
    ax.text(0.15, 0.35, "Signal class:  ", fontsize=9.5, fontweight="bold")
    for x, lbl, c in [(2.0, "Historical quantitative\nsignal", C_BLUE),
                      (5.5, "Contextual indicator\n(not a predictor)", C_GREEN),
                      (8.6, "Emerging catalyst\n(revenue unsized)", C_PURPLE)]:
        ax.add_patch(FancyBboxPatch((x, 0.17), 0.3, 0.3, boxstyle="round,pad=0.02", facecolor=c, edgecolor=c, alpha=0.5))
        ax.text(x+0.4, 0.32, lbl, fontsize=8.0, va="center")
    fig.tight_layout(); fig.savefig(path, dpi=170, facecolor="white"); plt.close(fig)


# =================================================================================================================
# EXHIBIT 2 — Cloud leading relationship
# =================================================================================================================
def exhibit2_cloud_scatter(cloud, path):
    d, r, rho = leadlag_xy(cloud, "Cloud_Index_Raw", "DDOG_Revenue_YoY", 2)
    fig, ax = plt.subplots(figsize=(9.4, 7.2))
    ax.scatter(d.x, d.y, s=70, color=C_BLUE, zorder=3, edgecolor="white", linewidth=0.6)
    for _, row in d.iterrows():
        ax.annotate(row.q.replace(" ", ""), (row.x, row.y), textcoords="offset points", xytext=(6, 5), fontsize=8.3)
    sl, ic, *_ = stats.linregress(d.x, d.y); xx = np.linspace(d.x.min(), d.x.max(), 40)
    ax.plot(xx, ic + sl * xx, "--", color="gray", lw=1.2, zorder=1, label="OLS fit (descriptive)")
    ax.set_xlabel("Cloud_Index_Raw at t-2  (%, mean of AWS/Azure/Google Cloud YoY)")
    ax.set_ylabel("DDOG Revenue YoY at t  (%)")
    ax.set_title("Cloud Growth vs DDOG Revenue Growth (Cloud at t−2)", fontsize=15, fontweight="bold", pad=30)
    ax.text(0.5, 1.045, "Cloud_Index_Raw(t-2) vs DDOG Revenue YoY(t)  —  Exhibit 2", transform=ax.transAxes,
           fontsize=9.8, color="#555", ha="center", style="italic")
    ax.text(0.03, 0.97, f"Pearson r = {r:.2f}\nSpearman ρ = {rho:.2f}\nn = {len(d)} quarters", transform=ax.transAxes,
           fontsize=11, va="top", ha="left", bbox=dict(boxstyle="round,pad=0.4", facecolor="#eef3fc", edgecolor=C_BLUE))
    ax.grid(alpha=0.25); ax.legend(frameon=False, loc="lower right", fontsize=9)
    fig.text(0.5, 0.015, "Strong in-sample relationship; predictive value evaluated separately OOS. Correlation, not causality.",
            ha="center", fontsize=9.3, style="italic", color="#444")
    fig.tight_layout(rect=(0, 0.035, 1, 1)); fig.savefig(path, dpi=170, facecolor="white"); plt.close(fig)


# =================================================================================================================
# EXHIBIT 3 — Google Trends mechanism
# =================================================================================================================
def exhibit3_trends_scatter(gt, path):
    d, r_full, rho_full = leadlag_xy(gt, "Trend_YoY", "Customers_100k_YoY", 2)
    post = d[d.q >= "2023 Q1"]
    r_post, _ = stats.pearsonr(post.x, post.y); rho_post, _ = stats.spearmanr(post.x, post.y)

    fig, ax = plt.subplots(figsize=(9.4, 7.2))
    is_2022 = d.q.str.startswith("2022")
    ax.scatter(d.x[~is_2022], d.y[~is_2022], s=70, color=C_ORANGE, zorder=3, edgecolor="white", linewidth=0.6, label="2023 Q1 - 2026 Q2 (post-2022)")
    ax.scatter(d.x[is_2022], d.y[is_2022], s=80, color=C_GRAY, marker="D", zorder=3, edgecolor="white", linewidth=0.6, label="2022 (hyper-growth/search-normalization regime)")
    sl, ic, *_ = stats.linregress(post.x, post.y); xx = np.linspace(post.x.min(), post.x.max(), 40)
    ax.plot(xx, ic + sl * xx, "--", color="gray", lw=1.2, zorder=1, label="OLS fit, post-2022 only (descriptive)")
    ax.set_xlabel("Google Trend_YoY at t-2  (%, search term \"Datadog\", worldwide)")
    ax.set_ylabel("$100k+ Customer YoY at t  (%)")
    ax.set_title("Search Growth vs Large-Customer Growth (Search at t−2)", fontsize=13.6, fontweight="bold", pad=32)
    ax.text(0.5, 1.045, "Google Trend_YoY(t-2) vs $100k+ Customer YoY(t)  —  Exhibit 3", transform=ax.transAxes,
           fontsize=9.8, color="#555", ha="center", style="italic")
    stats_box = ax.text(0.03, 0.97, f"Full sample:  r = {r_full:.2f}, ρ = {rho_full:.2f}  (n={len(d)})\nPost-2022:    r = {r_post:.2f}, ρ = {rho_post:.2f}  (n={len(post)})",
           transform=ax.transAxes, fontsize=10.5, va="top", ha="left", bbox=dict(boxstyle="round,pad=0.4", facecolor="#fdf1e6", edgecolor=C_ORANGE))
    ax.grid(alpha=0.25)
    leg = ax.legend(frameon=False, loc="lower right", fontsize=8.5)

    # ---- non-overlapping quarter labels: greedy candidate-offset placement, avoiding other labels AND the stats box/legend
    fig.canvas.draw(); rend = fig.canvas.get_renderer()
    placed = [stats_box.get_window_extent(rend), leg.get_window_extent(rend)]
    cands = [(6, 5), (6, -11), (-40, 5), (-40, -11), (6, 14), (6, -20), (-40, 14), (-40, -20), (-16, 18), (-16, -24), (18, -4), (-45, -4)]
    for _, row in d.sort_values("x").iterrows():
        for off in cands:
            a = ax.annotate(row.q.replace(" ", ""), (row.x, row.y), textcoords="offset points", xytext=off, fontsize=8.1)
            bb = a.get_window_extent(rend).expanded(1.03, 1.08)
            if not any(bb.overlaps(p) for p in placed): placed.append(bb); break
            a.remove()
        else:
            a = ax.annotate(row.q.replace(" ", ""), (row.x, row.y), textcoords="offset points", xytext=cands[0], fontsize=8.1)
            placed.append(a.get_window_extent(rend))

    fig.text(0.5, 0.015, "Search intent is unobserved; signal may include investor/news/job-seeker attention, not only practitioner evaluation.",
            ha="center", fontsize=9.3, style="italic", color="#444")
    fig.tight_layout(rect=(0, 0.035, 1, 1)); fig.savefig(path, dpi=170, facecolor="white"); plt.close(fig)
    return dict(r_full=r_full, rho_full=rho_full, r_post=r_post, rho_post=rho_post)


# =================================================================================================================
# EXHIBIT 4 — Walk-forward model comparison
# =================================================================================================================
MODEL_ORDER = ["Naive", "AR1", "Cloud", "Trends", "Cloud+Trends", "AR+Cloud+Trends"]
MODEL_LABEL = {"Naive": "Naive", "AR1": "AR(1)", "Cloud": "Cloud", "Trends": "Trends",
              "Cloud+Trends": "Cloud+\nTrends", "AR+Cloud+Trends": "AR+Cloud\n+Trends"}

def exhibit4_walkforward(wf_main, path):
    """Render directly from the *current* main-panel CSV: zero hard-coded model scores or winners."""
    m = wf_main[(wf_main.panel == "main") & (wf_main.model.isin(MODEL_ORDER))].set_index("model").loc[MODEL_ORDER]
    error_cols = ["MAE", "RMSE", "MAPE_pct"]
    min_errors = {col: m[col].min() for col in error_cols}
    eligible_dir = m.drop(index="Naive")  # naive always predicts zero change; its directional score is mechanical
    max_dir = eligible_dir.Directional_Accuracy_pct.max()
    dir_models = eligible_dir.index[np.isclose(eligible_dir.Directional_Accuracy_pct, max_dir)].tolist()
    error_model = m.MAE.idxmin()

    fig, ax = plt.subplots(figsize=(13.3, 7.4))
    fig.patch.set_facecolor("#ffffff")
    ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.text(0.06, 0.94, "EXHIBIT 04  /  MODEL VALIDATION", fontsize=10, color=C_PURPLE, weight="bold")
    fig.text(0.06, 0.88, "Expanding-window, out-of-sample comparison", fontsize=20, weight="bold", color="#182336")
    start_q, end_q = "2024 Q3", "2026 Q2"
    n = int(m.n_oos.iloc[0])
    fig.text(0.06, 0.835, f"Revenue YoY (percentage points)  •  {start_q} – {end_q}  •  {n} held-out quarters",
             fontsize=11, color="#607080")
    headings = ["MODEL", "MAE ↓", "RMSE ↓", "MAPE ↓", "DIRECTION ↑"]
    xs = [0.04, 0.40, 0.55, 0.70, 0.86]
    for x, h in zip(xs, headings):
        ax.text(x, 0.78, h, transform=ax.transAxes, ha="left" if x == xs[0] else "center",
                color="#64748b", fontsize=11, weight="bold", va="center")
    ax.plot([0.035, 0.965], [0.735, 0.735], transform=ax.transAxes, color="#cbd5e1", lw=1.4)
    aliases = {"AR1":"AR(1)","Cloud+Trends":"Cloud + Trends", "AR+Cloud+Trends":"AR + Cloud + Trends"}
    for i, model in enumerate(MODEL_ORDER):
        y = 0.675 - 0.088 * i
        if i % 2 == 0:
            ax.add_patch(plt.Rectangle((0.035, y - 0.037), 0.93, 0.076, transform=ax.transAxes,
                                       color="#f3f6fa", zorder=0, ec="none"))
        row=m.loc[model]
        ax.text(xs[0],y,aliases.get(model,model),transform=ax.transAxes,fontsize=12,
                weight="bold" if model==error_model or model in dir_models else "normal",
                va="center",color="#1e293b")
        vals=[float(row.MAE),float(row.RMSE),float(row.MAPE_pct),float(row.Directional_Accuracy_pct)]
        formats=["{:.2f}","{:.2f}","{:.1f}%","{:.1f}%"]
        for j,(v,fmt) in enumerate(zip(vals,formats)):
            highlight = (j<3 and np.isclose(v,min_errors[error_cols[j]])) or (j==3 and model in dir_models)
            if highlight:
                col="#fff0dc" if j<3 else "#def5ea"
                ax.add_patch(FancyBboxPatch((xs[j+1]-0.050,y-0.029),0.10,0.058,
                             transform=ax.transAxes, boxstyle="round,pad=0.004,rounding_size=0.012",
                             facecolor=col,edgecolor="none",zorder=1))
            ax.text(xs[j+1],y,fmt.format(v),transform=ax.transAxes,fontsize=12,va="center",ha="center",
                    weight="bold" if highlight else "normal",
                    color=("#a94d04" if j<3 else "#166b49") if highlight else "#273449",zorder=2)
    ax.plot([0.035, 0.965], [0.175, 0.175], transform=ax.transAxes, color="#cbd5e1", lw=1.1)
    ax.text(0.045,0.127,f"Lowest error: {aliases.get(error_model,error_model)} (MAE {m.loc[error_model,'MAE']:.2f} pp)",
            transform=ax.transAxes,fontsize=11,weight="bold",color="#a94d04")
    dir_label=", ".join(aliases.get(z,z) for z in dir_models)
    ax.text(0.55,0.127,f"Most correct direction calls: {dir_label} ({max_dir:.1f}%)",
            transform=ax.transAxes,fontsize=10.5,weight="bold",color="#166b49")
    ax.text(0.045,0.067,"Naive holds last quarter's YoY constant: its 0% direction score is mechanical, not failed point forecasting.",
            transform=ax.transAxes,fontsize=9.5,color="#607080")
    ax.text(0.045,0.036,"Exploratory comparison (8 OOS observations); no statistical significance or claimed OOS improvement over baseline.",
            transform=ax.transAxes,fontsize=9.5,color="#607080")
    fig.savefig(path,dpi=175,facecolor="white",bbox_inches="tight");plt.close(fig)
    return {"lowest_mae_model":error_model,"highest_direction_models":dir_models,"highest_direction_pct":float(max_dir)}


# =================================================================================================================
# EXHIBIT 5 — Agent Observability flywheel (refined: 5-6 strongest milestones, no GitHub metrics)
# =================================================================================================================
MILESTONES_REFINED = [
    ("2024-06-26", "LLM Observability\nGA launch", 1),
    ("2025-06-10", "AI Agent Monitoring +\nAgents Console GA (DASH)", -1),
    ("2025-11-06", ">500 AI-native customers;\n12% of revenue (Q3'25)", 1),
    ("2026-02-10", "LLM Obs: >1,000 customers,\nspans 10x/6mo (Q4'25)", -1),
    ("2026-03-09", "MCP Server\nGA launch", 1),
    ("2026-08-06", "MCP calls >22x vs Q4'25;\n>750 AI-native customers (Q2'26)", -1),
]

def exhibit5_flywheel(path):
    fig = plt.figure(figsize=(16, 8.3))
    ax_top = fig.add_axes([0.03, 0.58, 0.90, 0.36])
    ax_bot = fig.add_axes([0.03, 0.06, 0.90, 0.44])
    for ax in (ax_top, ax_bot): ax.set_xlim(-0.3, 10.9); ax.axis("off")

    stages = [("AI applications\n& agents", C_BLUE), ("Agent / LLM\nObservability adoption", C_GREEN),
             ("LLM spans /\nusage volume", C_ORANGE), ("Potential billable\nLLM-observability volume", C_PURPLE)]
    box_w, box_h, gap = 1.9, 1.5, 0.55
    total_w = len(stages) * box_w + (len(stages) - 1) * gap; x0 = (10 - total_w) / 2
    for i, (label, color) in enumerate(stages):
        x = x0 + i * (box_w + gap)
        ax_top.add_patch(FancyBboxPatch((x, 0.9), box_w, box_h, boxstyle="round,pad=0.05,rounding_size=0.12",
                                        linewidth=1.6, edgecolor=color, facecolor=color, alpha=0.15))
        ax_top.text(x + box_w / 2, 0.9 + box_h / 2, label, ha="center", va="center", fontsize=11.5, fontweight="bold", color="#222")
        if i < len(stages) - 1:
            xa = x + box_w; xb = xa + gap
            ax_top.annotate("", xy=(xb - 0.05, 0.9 + box_h / 2), xytext=(xa + 0.05, 0.9 + box_h / 2),
                            arrowprops=dict(arrowstyle="-|>", lw=2.2, color="#555"))
    ax_top.text(5, 0.42, "Only step 3 (LLM spans) is the billed unit - tool, retrieval, embedding and agent spans are explicitly not billed.",
               ha="center", va="center", fontsize=9.8, color="#444", style="italic")
    ax_top.text(5, 0.10, "Free allowances, customer mix, and enterprise/negotiated pricing prevent direct conversion of observed spans into revenue.",
               ha="center", va="center", fontsize=9.3, color="#7a3d9e", style="italic", fontweight="medium")
    ax_top.set_ylim(0, 3)
    ax_top.set_title("Exhibit 5.  AI / Agent Observability Adoption Flywheel  (2024 Q1 - Aug 2026)", fontsize=15.5, fontweight="bold", pad=12)

    from datetime import date
    d0, d1 = date(2024, 1, 1), date(2026, 8, 31); span = (d1 - d0).days
    def to_x(dstr):
        y, mo, da = map(int, dstr.split("-")); return (date(y, mo, da) - d0).days / span * 9.2 + 0.3
    ax_bot.axhline(0, color="#333", lw=2, xmin=0.02, xmax=0.92)
    for q in range(2024, 2027):
        for qm in (1, 4, 7, 10):
            if date(q, qm, 1) < d0 or date(q, qm, 1) > d1: continue
            xq = to_x(f"{q}-{qm:02d}-01")
            ax_bot.plot([xq, xq], [-0.05, 0.05], color="#999", lw=1)
            ax_bot.text(xq, -0.20, f"{q}\nQ{(qm - 1)//3 + 1}", ha="center", va="top", fontsize=8.3, color="#666")
    TIER_Y = {1: 0.55, -1: -0.55}
    for dstr, label, tier in MILESTONES_REFINED:
        x = to_x(dstr); y_lab = TIER_Y[tier]
        ax_bot.plot([x, x], [0, y_lab * 0.78], color="#888", lw=1, zorder=1)
        ax_bot.scatter([x], [0], s=60, color=C_PURPLE, zorder=5, edgecolor="white", linewidth=0.8)
        va = "bottom" if tier > 0 else "top"
        ax_bot.text(x, y_lab, label, ha="center", va=va, fontsize=9.6,
                    bbox=dict(boxstyle="round,pad=0.38", facecolor="#F5F0FA", edgecolor=C_PURPLE, linewidth=0.9))
    ax_bot.set_xlim(-0.3, 10.9); ax_bot.set_ylim(-1.15, 1.15)
    ax_bot.text(5, -1.08, "Strongest primary-sourced milestones only. Public GitHub adoption snapshot omitted here as noisy/experimental (see catalyst scorecard).",
               ha="center", va="bottom", fontsize=9.3, color="#555", style="italic")
    fig.savefig(path, dpi=170, facecolor="white"); plt.close(fig)


# =================================================================================================================
# EXHIBIT 6 — Dashboard mockup
# =================================================================================================================
def exhibit6_dashboard(cloud, gt, wf_main, path):
    """Compact presentation mockup, descriptive module reads only; never a composite trading signal."""
    rev_latest,rev_p1,rev_p2 = map(float,cloud.DDOG_Revenue_YoY.iloc[-3:][::-1])
    rev_state = "Accelerating" if rev_latest>rev_p1>rev_p2 else ("Decelerating" if rev_latest<rev_p1<rev_p2 else "Mixed")
    ci_latest,ci_p1,ci_p2 = map(float,cloud.Cloud_Index_Raw.iloc[-3:][::-1])
    cloud_state = "Accelerating" if ci_latest>ci_p1>ci_p2 else ("Decelerating" if ci_latest<ci_p1<ci_p2 else "Stable / mixed")
    tr_latest,tr_p1,tr_p2 = map(float,gt.Trend_YoY.iloc[-3:][::-1])
    trend_state = "Accelerating" if tr_latest>tr_p1>tr_p2 else ("Decelerating" if tr_latest<tr_p1<tr_p2 else "Volatile / mixed")
    cu_latest,cu_p1,cu_p2 = map(float,gt.Customers_100k_YoY.iloc[-3:][::-1])
    cust_state = "Accelerating" if cu_latest>cu_p1>cu_p2 else ("Decelerating" if cu_latest<cu_p1<cu_p2 else "Stable / mixed")
    catalyst_state = "Strong adoption/usage momentum"  # curated reading from module 11, NOT inferred from numeric data here
    latest_q = str(cloud.Quarter.iloc[-1]); main=wf_main[wf_main.panel=="main"].set_index("model")
    naive_mae=float(main.loc["Naive","MAE"])
    fig=plt.figure(figsize=(16,9.1),facecolor="#f4f7fb")
    fig.text(.047,.952,"DATADOG  /  OPERATING MONITOR",fontsize=11,color=C_PURPLE,weight="bold")
    fig.text(.047,.909,f"Alternative-data research dashboard    ·    {latest_q}",fontsize=23,weight="bold",color="#182336")
    fig.text(.047,.872,"Observed quarterly indicators, backtested baseline, and emerging-catalyst disclosures — no composite rating.",
             fontsize=11,color="#637184")
    cards=[
     ("01  REVENUE GROWTH",f"{rev_latest:.1f}%", "reported YoY",rev_state,
      f"Prior: {rev_p2:.1f}%  →  {rev_p1:.1f}%  →  {rev_latest:.1f}%",
      f"Persistence reference: {rev_latest:.1f}%  ·  OOS MAE {naive_mae:.2f} pp",C_BLUE),
     ("02  CLOUD WORKLOAD",f"{ci_latest:.1f}%", "equal-weight provider YoY",cloud_state,
      f"Prior: {ci_p2:.1f}%  →  {ci_p1:.1f}%  →  {ci_latest:.1f}%",
      "t−2 relationship is in-sample; forecast separately validated",C_BLUE),
     ("03  SEARCH INTEREST",f"{tr_latest:.1f}%", "Google Trends YoY",trend_state,
      f"Prior: {tr_p2:.1f}%  →  {tr_p1:.1f}%  →  {tr_latest:.1f}%",
      "Sampled index; search intent and spikes are unobserved",C_ORANGE),
     ("04  LARGE CUSTOMER EXPANSION",f"{cu_latest:.1f}%", "$100k+ customer YoY",cust_state,
      f"Prior: {cu_p2:.1f}%  →  {cu_p1:.1f}%  →  {cu_latest:.1f}%",
      "Reported customer count growth, not product revenue",C_GREEN),
     ("05  AGENT OBSERVABILITY","1,000+", "LLM Obs customers (Q4'25)",catalyst_state,
      "LLM span growth disclosed; usage ≠ realized revenue",
      "AI-native revenue mix undisclosed since Q4'25",C_PURPLE),
    ]
    state_color={"Accelerating":"#12805a","Decelerating":"#b44949", "Volatile / mixed":"#996c07",
                 "Stable / mixed":"#996c07","Mixed":"#996c07",catalyst_state:C_PURPLE}
    positions=[(.047,.482),(.368,.482),(.689,.482),(.047,.095),(.368,.095)]
    for (head,big,unit,state,trail,note,accent),(x,y) in zip(cards,positions):
        ax=fig.add_axes([x,y,.285,.342]);ax.set_axis_off();ax.set_xlim(0,1);ax.set_ylim(0,1)
        ax.add_patch(FancyBboxPatch((.006,.01),.987,.98,boxstyle="round,pad=0.006,rounding_size=.028",
                     facecolor="white",edgecolor="#dce4ef",linewidth=1.2))
        ax.add_patch(plt.Rectangle((.05,.83),.011,.085,facecolor=accent,edgecolor="none"))
        ax.text(.088,.889,head,fontsize=10.5,weight="bold",color="#435267",va="center")
        ax.text(.067,.715,big,fontsize=26,weight="bold",color="#14233a",va="center")
        ax.text(.067,.593,unit,fontsize=10,color="#64748b",va="center")
        badge_width=min(.87,max(.30,.026*len(state)+.10))
        ax.add_patch(FancyBboxPatch((.067,.465),badge_width,.091,boxstyle="round,pad=.008,rounding_size=.022",
                     facecolor=state_color[state],edgecolor="none"))
        ax.text(.067+badge_width/2,.510,state,fontsize=9.3,color="white",weight="bold",ha="center",va="center")
        ax.plot([.067,.93],[.422,.422],color="#e8edf4",lw=1)
        ax.text(.067,.345,trail,fontsize=9.0,color="#26384d",va="center")
        ax.text(.067,.16,note,fontsize=8.5,color="#617286",va="center",wrap=True)
    ax=fig.add_axes([.689,.095,.285,.342]);ax.set_axis_off();ax.set_xlim(0,1);ax.set_ylim(0,1)
    ax.add_patch(FancyBboxPatch((.006,.01),.987,.98,boxstyle="round,pad=.006,rounding_size=.028",
                 facecolor="#ede9fb",edgecolor="#cfc4f0",lw=1.3))
    ax.text(.065,.88,"06  RESEARCH READOUT",fontsize=11,weight="bold",color=C_PURPLE)
    notes=[("Revenue","persistent; low-error baseline"),("Cloud","in-sample lead, modest OOS"),
           ("Trends","volatile alternative signal"),("Customers","reported growth improving"),
           ("Agent Obs","adoption-stage; revenue unsized")]
    for i,(label,detail) in enumerate(notes):
        yy=.74-i*.121
        ax.text(.075,yy,label.upper(),fontsize=9,weight="bold",color="#34265f",va="center")
        ax.text(.075,yy-.052,detail,fontsize=9,color="#53627c",va="center")
    ax.text(.075,.08,"No composite score or investment call",fontsize=9,color=C_PURPLE,weight="bold")
    fig.text(.048,.045,"Sources: DDOG quarterly fundamentals; cloud-provider filings; Google Trends (sampled); curated company disclosures."
             "  |  See exhibits 2–5 for data and limits.",fontsize=9.2,color="#65758c")
    fig.savefig(path,dpi=170,facecolor=fig.get_facecolor());plt.close(fig)
    return dict(rev_state=rev_state,cloud_state=cloud_state,trend_state=trend_state,
                cust_state=cust_state,catalyst_state=catalyst_state)


def main():
    cloud = pd.read_csv(IN_DIR + "ddog_cloud_master.csv")
    gt = pd.read_csv(IN_DIR + "ddog_google_trends_master.csv")
    wf_main = pd.read_csv(IN_DIR + "walkforward_results.csv")

    exhibit1_framework(OUT_DIR + "exhibit1_framework.png")
    exhibit2_cloud_scatter(cloud, OUT_DIR + "exhibit2_cloud_leadlag_scatter.png")
    trend_stats = exhibit3_trends_scatter(gt, OUT_DIR + "exhibit3_trends_mechanism_scatter.png")
    exhibit4_walkforward(wf_main, OUT_DIR + "exhibit4_walkforward_comparison.png")
    exhibit5_flywheel(OUT_DIR + "exhibit5_flywheel_refined.png")
    dash = exhibit6_dashboard(cloud, gt, wf_main, OUT_DIR + "exhibit6_dashboard_mockup.png")

    print("Exhibit 3 stats:", trend_stats)
    print("Exhibit 6 module states:", dash)
    print("\nAll 6 exhibits written to", OUT_DIR)

if __name__ == "__main__":
    main()
