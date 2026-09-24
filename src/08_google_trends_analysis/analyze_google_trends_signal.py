#!/usr/bin/env python3
"""
analyze_google_trends_signal.py - merge Google Trends with DDOG fundamentals, lead-lag diagnostics, robustness,
search-intent-contamination spike listing, and charts.

LAG CONVENTION (same as used throughout this project): k = quarters the CANDIDATE series (Trends) is shifted back.
    k=0 : Trend_YoY(t)   vs Y(t)   contemporaneous
    k=1 : Trend_YoY(t-1) vs Y(t)   Trends leads Y by 1 quarter
    k=2 : Trend_YoY(t-2) vs Y(t)   Trends leads Y by 2 quarters

PRIMARY signal = Trend_YoY (stationary-ish, YoY growth). Quarterly_Trend_Mean (the raw level) is SECONDARY /
descriptive only: both search interest and company scale can trend over time, so a level-vs-level correlation is
easy to overstate. It is reported but never used to pick the "best" specification.

Nothing here runs the combined Cloud + Google Trends model, and no lag is chosen by full-sample correlation alone.
"""
from __future__ import annotations
import json, os
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IN_DIR = "outputs/"
OUT_DIR = "outputs/"
os.makedirs(OUT_DIR, exist_ok=True)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)

LAGS = [0, 1, 2]
LAG_NAME = {0: "Trend_YoY(t) vs Y(t): contemporaneous", 1: "Trend_YoY(t-1) vs Y(t): Trends leads 1Q", 2: "Trend_YoY(t-2) vs Y(t): Trends leads 2Q"}


# =========================================================================================== STEP 1: MERGE
def build_master(gt_q: pd.DataFrame, ddog: pd.DataFrame) -> pd.DataFrame:
    d = ddog.rename(columns={"Revenue_YoY": "DDOG_Revenue_YoY"})[["Quarter", "DDOG_Revenue_YoY", "Customers_100k_YoY"]]
    m = gt_q[["Quarter", "Quarterly_Trend_Mean", "Trend_YoY"]].merge(d, on="Quarter", how="inner")
    assert m["Quarter"].is_unique
    return m.sort_values("Quarter").reset_index(drop=True)


# =========================================================================================== STEP 3/4: LEAD-LAG
def ll_row(x: pd.Series, y: pd.Series, k: int) -> dict:
    d = pd.DataFrame({"x": x.shift(k), "y": y}).dropna()
    n = len(d)
    if n < 4: return dict(k=k, n=n, pearson=np.nan, spearman=np.nan)
    return dict(k=k, n=n, pearson=float(stats.pearsonr(d.x, d.y)[0]), spearman=float(stats.spearmanr(d.x, d.y)[0]))

def leadlag_table(master: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for signal, tag in [("Trend_YoY", "PRIMARY"), ("Quarterly_Trend_Mean", "SECONDARY (level, descriptive)")]:
        for target in ("DDOG_Revenue_YoY", "Customers_100k_YoY"):
            for k in LAGS:
                r = ll_row(master[signal], master[target], k)
                r.update(signal=signal, signal_role=tag, target=target, spec=LAG_NAME[k]); rows.append(r)
    return pd.DataFrame(rows)[["signal", "signal_role", "target", "k", "spec", "n", "pearson", "spearman"]]


# =========================================================================================== STEP 5: ROBUSTNESS
def leave_one_out(x: pd.Series, y: pd.Series, k: int) -> dict:
    d = pd.DataFrame({"x": x.shift(k), "y": y, "q": x.index}).dropna()
    full = stats.pearsonr(d.x, d.y)[0]
    rows = [(q, stats.pearsonr(d.x.drop(i), d.y.drop(i))[0]) for i, q in zip(d.index, d.q)]
    most_influential = max(rows, key=lambda t: abs(full - t[1]))
    return dict(full_r=full, most_influential_quarter=most_influential[0], r_excl_most_influential=most_influential[1],
               shift_from_removal=full - most_influential[1])

def subsample_corr(x: pd.Series, y: pd.Series, k: int, mask: pd.Series) -> dict:
    d = pd.DataFrame({"x": x.shift(k), "y": y})[mask].dropna()
    n = len(d)
    if n < 4: return dict(n=n, pearson=np.nan, spearman=np.nan)
    return dict(n=n, pearson=float(stats.pearsonr(d.x, d.y)[0]), spearman=float(stats.spearmanr(d.x, d.y)[0]))

def robustness_table(master: pd.DataFrame) -> pd.DataFrame:
    m = master.set_index("Quarter")
    q25 = pd.Series(m.index.str.startswith("2025 Q3"), index=m.index)          # the 2025 Q3 spike quarter, as a Y-quarter mask
    post2022 = pd.Series(~m.index.str.startswith("2022"), index=m.index)       # excludes the 4 quarters of 2022
    rows = []
    for target in ("DDOG_Revenue_YoY", "Customers_100k_YoY"):
        for k in LAGS:
            full = ll_row(m.Trend_YoY, m[target], k)
            loo = leave_one_out(m.Trend_YoY, m[target], k)
            excl_2025q3 = subsample_corr(m.Trend_YoY, m[target], k, ~q25)
            post22 = subsample_corr(m.Trend_YoY, m[target], k, post2022)
            rows.append(dict(target=target, k=k, spec=LAG_NAME[k], n_full=full["n"], pearson_full=full["pearson"], spearman_full=full["spearman"],
                             most_influential_quarter=loo["most_influential_quarter"], pearson_excl_most_influential=round(loo["r_excl_most_influential"], 4),
                             shift_from_removing_it=round(loo["shift_from_removal"], 4),
                             n_excl_2025Q3=excl_2025q3["n"], pearson_excl_2025Q3=excl_2025q3["pearson"], spearman_excl_2025Q3=excl_2025q3["spearman"],
                             n_post2022=post22["n"], pearson_post2022=post22["pearson"], spearman_post2022=post22["spearman"]))
    return pd.DataFrame(rows)


# =========================================================================================== STEP 6: SEARCH-INTENT CONTAMINATION CHECK
def monthly_spikes(raw: pd.DataFrame, top=6) -> pd.DataFrame:
    s = raw.set_index("Date")["Datadog"]
    mom = s.pct_change() * 100                                    # month-over-month % change in the index
    t = pd.DataFrame({"date": s.index, "level": s.values, "mom_pct_change": mom.values}).dropna()
    return t.reindex(t.mom_pct_change.abs().sort_values(ascending=False).index).head(top).reset_index(drop=True)

def quarterly_spikes(master: pd.DataFrame, top=6) -> pd.DataFrame:
    t = master[["Quarter", "Quarterly_Trend_Mean", "Trend_YoY"]].dropna(subset=["Trend_YoY"]).copy()
    return t.reindex(t.Trend_YoY.abs().sort_values(ascending=False).index).head(top).reset_index(drop=True)


# =========================================================================================== STEP 2: CHARTS
def chart_level(gt_q: pd.DataFrame, path: str):
    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(gt_q)); ax.plot(x, gt_q.Quarterly_Trend_Mean, "o-", color="#632CA6", lw=2)
    ax.set_xticks(x); ax.set_xticklabels(gt_q.Quarter.str.replace(" ", "\n"), fontsize=8)
    ax.set_ylabel("Google Trends index (0-100, search term \"Datadog\", worldwide)")
    ax.set_title("Chart A: Datadog Google Trends level, 2021 Q1 - 2026 Q2 (quarterly mean of monthly index)")
    ax.grid(axis="y", alpha=.3)
    fig.text(0.01, 0.01, "Index is scaled 0-100 relative to its own peak in this window (2025 Q3). Level trends over time for reasons unrelated to demand (see robustness).", fontsize=8, color="gray")
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(path, dpi=170); plt.close(fig)

def chart_yoy_vs(master: pd.DataFrame, target: str, label: str, path: str, title: str):
    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(master))
    ax.plot(x, master.Trend_YoY, "s-", color="#E8710A", lw=2, label="Google Trends YoY (Datadog, worldwide)")
    ax.plot(x, master[target], "o-", color="#632CA6", lw=2, label=label)
    ax.set_xticks(x); ax.set_xticklabels(master.Quarter.str.replace(" ", "\n"), fontsize=8)
    ax.set_ylabel("YoY growth (%)"); ax.set_title(title); ax.grid(axis="y", alpha=.3); ax.legend(frameon=False)
    fig.text(0.01, 0.01, "n = %d. See google_trends_robustness.csv before reading anything into co-movement." % len(master), fontsize=8, color="gray")
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(path, dpi=170); plt.close(fig)


# =========================================================================================== main
def main():
    gt_q = pd.read_csv(IN_DIR + "google_trends_quarterly.csv")
    gt_raw = pd.read_csv(IN_DIR + "google_trends_raw_monthly.csv")
    ddog = pd.read_csv(IN_DIR + "ddog_calculated_dataset.csv")
    log = json.load(open(IN_DIR + "google_trends_run_log.json"))

    # ---- STEP 1
    master = build_master(gt_q, ddog)
    master.round(3).to_csv(OUT_DIR + "ddog_google_trends_master.csv", index=False)
    print("=== STEP 1: merged master ===")
    print("rows:", len(master), "| first:", master.Quarter.iloc[0], "| last:", master.Quarter.iloc[-1])
    print(master.to_string(index=False))

    # ---- STEP 3/4
    ll = leadlag_table(master)
    ll.round(4).to_csv(OUT_DIR + "google_trends_leadlag.csv", index=False)
    print("\n=== STEP 3/4: lead-lag table (PRIMARY = Trend_YoY; level is SECONDARY/descriptive) ===")
    print(ll.to_string(index=False))

    # ---- STEP 5
    rob = robustness_table(master)
    rob.round(4).to_csv(OUT_DIR + "google_trends_robustness.csv", index=False)
    print("\n=== STEP 5: robustness (PRIMARY signal only) ===")
    print(rob.to_string(index=False))

    # ---- STEP 6
    ms = monthly_spikes(gt_raw); qs = quarterly_spikes(master)
    ms.to_csv(OUT_DIR + "google_trends_monthly_spikes.csv", index=False)
    qs.to_csv(OUT_DIR + "google_trends_quarterly_spikes.csv", index=False)
    print("\n=== STEP 6: largest MONTHLY month-over-month moves in the raw \"Datadog\" index ===")
    print(ms.to_string(index=False))
    print("\n=== STEP 6: largest quarterly |Trend_YoY| values ===")
    print(qs.to_string(index=False))

    # ---- STEP 2 charts
    chart_level(gt_q, OUT_DIR + "chartA_trends_level.png")
    chart_yoy_vs(master, "DDOG_Revenue_YoY", "DDOG Revenue YoY", OUT_DIR + "chartB_trend_yoy_vs_ddog_revenue.png",
                "Chart B: Google Trends YoY vs DDOG Revenue YoY")
    chart_yoy_vs(master, "Customers_100k_YoY", "$100k+ Customers YoY", OUT_DIR + "chartC_trend_yoy_vs_customers.png",
                "Chart C: Google Trends YoY vs $100k+ Customer YoY")
    print("\nCharts written:", "chartA_trends_level.png, chartB_trend_yoy_vs_ddog_revenue.png, chartC_trend_yoy_vs_customers.png")
    return dict(master=master, leadlag=ll, robustness=rob, monthly_spikes=ms, quarterly_spikes=qs, log=log)

if __name__ == "__main__":
    main()
