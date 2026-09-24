#!/usr/bin/env python3
"""
build_google_trends_signal.py - Candidate 3 (Google Trends search demand for Datadog), built ONLY because
Candidate 1 (BuiltWith) and Candidate 2 (Docker Hub) both failed the feasibility screen (see FEASIBILITY.md).

Design, per the task brief:
  * A SINGLE monthly request spanning ~2021-01-01..2026-06-30 (~5.5 years) - avoids the multi-window
    weekly-rescaling problem entirely, since Google returns monthly granularity in one consistent 0-100
    scale for any span longer than ~5.25 years (documented behaviour; also load-bearing in this design).
  * "Datadog" is tried as a TOPIC first. A topic is used only if EXACTLY ONE suggestion has title=="Datadog"
    (never guessed from several candidates). Otherwise the plain search TERM "Datadog" is used.
  * Low-volume qualifier terms ("Datadog APM", "Datadog logs", "Datadog monitoring") are pulled and reported,
    but excluded from the primary series unless NONZERO_SHARE_MIN of their months are non-zero.
  * Multiple identical pulls of the primary series are compared to quantify Google's sampling noise.
  * Quarterly_Trend_Mean = mean of the monthly index within a quarter (only quarters with all 3 months present).
  * Trend_YoY computed only where both the quarter and its t-4 base quarter exist and the base is > 0.
  * NOTHING here runs a DDOG correlation.

Usage:
  python build_google_trends_signal.py --out-dir ./out --repeats 3
"""
from __future__ import annotations
import argparse, json, os, time
import numpy as np
import pandas as pd

START, END = "2021-01-01", "2026-06-30"
QUALIFIERS = ["Datadog APM", "Datadog logs", "Datadog monitoring"]
NONZERO_SHARE_MIN = 0.5           # a qualifier term needs >=50% non-zero months to join the primary series
FIRST_Q, LAST_Q = "2021Q1", "2026Q2"


# =================================================================================== Google Trends access
def get_trendreq():
    from pytrends.request import TrendReq
    return TrendReq(hl="en-US", tz=0)                    # do NOT pass retries=/backoff_factor= - crashes on urllib3>=2

def pull_monthly(tr, keyword: str, timeframe: str = f"{START} {END}", geo: str = "", tries: int = 4, pause: float = 2.0) -> pd.Series:
    """One single-keyword, single-request pull. Raises on repeated failure rather than silently returning empty."""
    for i in range(tries):
        try:
            tr.build_payload([keyword], timeframe=timeframe, geo=geo); time.sleep(pause)
            d = tr.interest_over_time()
            if d is None or len(d) == 0 or keyword not in d: raise RuntimeError("empty response")
            return d[keyword].astype(float)
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(max(pause, 5) * 2 ** i)

def resolve_topic_or_term(tr, name: str = "Datadog"):
    """Returns (label, google_query_value, suggestions). Uses a TOPIC only if exactly one suggestion title matches
    the name exactly; a topic value is a 'mid' string (e.g. '/g/xyz'), a term is just the plain keyword."""
    sug = tr.suggestions(name)
    exact = [s for s in sug if str(s.get("title", "")).lower() == name.lower()]
    if len(exact) == 1:
        return f"topic:{name}", exact[0]["mid"], sug
    return f"term:{name}", name, sug


# =================================================================================== transformation
def quarterly_mean(monthly: pd.Series, first_q=FIRST_Q, last_q=LAST_Q) -> pd.DataFrame:
    rows = []
    for p in pd.period_range(first_q, last_q, freq="Q"):
        seg = monthly[(monthly.index >= p.start_time) & (monthly.index <= p.end_time)]
        present = int(seg.notna().sum())
        rows.append(dict(Quarter=f"{p.year} Q{p.quarter}", n_months=present, Quarterly_Trend_Mean=(seg.mean() if present == 3 else np.nan)))
    return pd.DataFrame(rows)

def add_yoy(q: pd.DataFrame) -> pd.DataFrame:
    q = q.copy(); base = q.Quarterly_Trend_Mean.shift(4)
    yoy = (q.Quarterly_Trend_Mean / base - 1) * 100
    yoy[(base <= 0) | base.isna() | q.Quarterly_Trend_Mean.isna()] = np.nan
    q["Trend_YoY"] = yoy
    return q

def repeat_stats(runs: list[pd.Series]) -> dict:
    """Quantifies Google's sampling noise: identical requests return slightly different numbers."""
    df = pd.concat(runs, axis=1, join="inner")
    pc = [df.iloc[:, i].corr(df.iloc[:, j]) for i in range(df.shape[1]) for j in range(i + 1, df.shape[1])]
    spread = df.max(axis=1) - df.min(axis=1)
    return dict(n_points=int(len(df)), n_repeats=df.shape[1], mean_spread=float(spread.mean()), max_spread=float(spread.max()),
               min_pairwise_corr=(float(min(pc)) if pc else None), mean_of_means=float(df.mean(axis=1).mean()))


# =================================================================================== pipeline
def run(out_dir: str, repeats: int = 3, geo: str = "", tr=None):
    os.makedirs(out_dir, exist_ok=True)
    tr = tr or get_trendreq()
    log = {"start": START, "end": END, "geo": geo or "worldwide"}

    label, query, suggestions = resolve_topic_or_term(tr, "Datadog")
    log["primary_query"] = dict(label=label, google_query_value=query, suggestions=suggestions)

    primary_runs = [pull_monthly(tr, query, geo=geo) for _ in range(repeats)]
    log["primary_repeat_stability"] = repeat_stats(primary_runs)
    primary = pd.concat(primary_runs, axis=1).mean(axis=1).rename("Datadog")

    qualifiers = {}
    for term in QUALIFIERS:
        try:
            s = pull_monthly(tr, term, geo=geo)
            nz = float((s > 0).mean())
            qualifiers[term] = dict(series=s, nonzero_share=nz, included_in_primary=(nz >= NONZERO_SHARE_MIN))
        except Exception as e:
            qualifiers[term] = dict(series=None, nonzero_share=None, included_in_primary=False, error=str(e))
    log["qualifier_terms"] = {k: {kk: vv for kk, vv in v.items() if kk != "series"} for k, v in qualifiers.items()}

    raw = pd.DataFrame({"Date": primary.index.date, "Datadog": primary.values})
    for term, info in qualifiers.items():
        if info["series"] is not None: raw[term] = info["series"].reindex(primary.index).values
    raw.to_csv(os.path.join(out_dir, "google_trends_raw_monthly.csv"), index=False)

    included = [t for t, v in qualifiers.items() if v["included_in_primary"]]
    if included:
        combo = pd.concat([primary] + [qualifiers[t]["series"].reindex(primary.index) for t in included], axis=1).mean(axis=1)
        log["primary_series_used"] = f"mean of Datadog + {included}"
    else:
        combo = primary; log["primary_series_used"] = "Datadog alone (all qualifier terms too sparse)"

    q = add_yoy(quarterly_mean(combo))
    q.round(3).to_csv(os.path.join(out_dir, "google_trends_quarterly.csv"), index=False)
    json.dump(log, open(os.path.join(out_dir, "google_trends_run_log.json"), "w"), indent=2, default=str)
    return dict(quarterly=q, raw=raw, log=log)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="./out"); ap.add_argument("--repeats", type=int, default=3); ap.add_argument("--geo", default="")
    return ap.parse_args(argv)

if __name__ == "__main__":
    a = parse_args()
    res = run(a.out_dir, a.repeats, a.geo)
    print("Primary query:", res["log"]["primary_query"]["label"])
    print("Sampling stability:", res["log"]["primary_repeat_stability"])
    print("Qualifier terms:", res["log"]["qualifier_terms"])
    print(res["quarterly"].to_string(index=False))
