#!/usr/bin/env python3
"""
run_collection.py - execute the package-download collection under the agreed DECISION RULE.

  1. npm  dd-trace : official downloads API (daily, 2021-01-01 .. 2026-06-30).
  2. PyPI ddtrace  : try ClickPy/ClickHouse first; if that fails, try the BigQuery public PyPI dataset; if that fails, STOP
                     (no further PyPI pipelines are attempted).
  3. The two sources are run INDEPENDENTLY: a PyPI failure never discards npm data, and vice-versa.
  4. Nothing is estimated, interpolated or back-filled. A data file is written only if at least one series was really retrieved;
     a series that could not be retrieved is left BLANK (never 0) and reported as FAIL. If both fail, NO data CSV is written.
  5. Verdicts printed and saved:  A. npm SUCCESS/FAIL   B. PyPI SUCCESS/FAIL   C. quarterly file complete for 2022Q1-2026Q2 lead-lag testing YES/NO.

Release coincidence of spikes uses the registry release TIMESTAMPS (same source as registry_release_cadence_context.csv, at day
resolution). The per-quarter cadence CSV alone cannot say whether a given day coincides with a release, so it is used only as a
quarter-level fallback column (release-heavy quarter yes/no).

No DDOG correlations or regressions are run here.

Usage:  python run_collection.py --out-dir ./out [--bq-project MY_GCP_PROJECT] [--cadence-csv registry_release_cadence_context.csv]
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys, time
import numpy as np, pandas as pd, requests
import collect_developer_adoption as C

PROBES = {
    "npm downloads API (api.npmjs.org)": "https://api.npmjs.org/downloads/point/2021-01-01:2021-01-31/dd-trace",
    "ClickPy / ClickHouse SQL": C.CLICKHOUSE_URL + "?user=" + C.CLICKHOUSE_USER + "&query=SELECT%201",
    "BigQuery API": "https://bigquery.googleapis.com/",
    "pypistats.org (180-day cross-check)": "https://pypistats.org/api/packages/ddtrace/recent",
    "npm registry (release metadata)": "https://registry.npmjs.org/dd-trace/latest",
    "PyPI JSON API (release metadata)": "https://pypi.org/pypi/ddtrace/json",
}
TARGET_Q = [f"{p.year} Q{p.quarter}" for p in pd.period_range("2022Q1", "2026Q2", freq="Q")]      # the 18 lead-lag quarters


# ------------------------------------------------------------------------------------------------ helpers
def probe(url, timeout=20):
    """Classify a host: reachable / blocked by an egress allowlist / unreachable. Does not download the body."""
    try:
        r = requests.get(url, timeout=timeout, stream=True, headers={"User-Agent": C.UA}); deny = r.headers.get("x-deny-reason"); code = r.status_code; r.close()
    except requests.RequestException as e:
        return dict(status="UNREACHABLE", http=None, detail=type(e).__name__)
    if deny: return dict(status="BLOCKED_BY_NETWORK_ALLOWLIST", http=code, detail=deny)
    return dict(status="REACHABLE", http=code, detail="")

def attempt(label, fn):
    t0 = time.time()
    try:
        val = fn()
        return dict(label=label, status="SUCCESS", error=None, seconds=round(time.time() - t0, 1)), val
    except Exception as e:
        return dict(label=label, status="FAIL", error=f"{type(e).__name__}: {str(e)[:400]}", seconds=round(time.time() - t0, 1)), None

def get_npm(http, start, end, verify_point=True):
    m, val = attempt("npm official downloads API", lambda: C.fetch_npm_daily(http, C.NPM_PKG, start, end, verify_point=verify_point))
    return m, val

def get_pypi(http, start, end, bq_project, max_gb, bq_fetch=None):
    """ClickPy first, then BigQuery, then stop. Returns (attempt_log, series|None, breakdown|None, source|None)."""
    log = []
    def _ch():
        s = C.fetch_pypi_clickhouse(http, C.PYPI_PKG, start, end)
        if s.empty: raise RuntimeError("ClickPy returned 0 rows for ddtrace")
        return s
    m, s = attempt("PyPI via ClickPy/ClickHouse", _ch); log.append(m)
    if s is not None: return log, s, None, "ClickPy/ClickHouse"
    fn = bq_fetch or (lambda: C.fetch_pypi_bigquery(bq_project, C.PYPI_PKG, start, end, int(max_gb * 1e9)))
    m, val = attempt("PyPI via BigQuery public dataset", fn); log.append(m)
    if val is not None:
        s, brk, info = val
        if s.empty: log[-1].update(status="FAIL", error="BigQuery returned 0 rows"); return log, None, None, None
        return log, s, brk, "BigQuery"
    return log, None, None, None                       # decision rule: stop here, do not build another PyPI pipeline

def series_block(name, s, start, end, events, cadence, cad_col):
    """Completeness figures for one series (s is a full-calendar daily Series or None)."""
    if s is None:
        return dict(series=name, retrieved="NO", expected_days=(end - start).days + 1, observed_days=None, missing_days=None,
                    incomplete_quarters=None, n_spikes=None, n_spikes_with_release_within_3d=None), pd.DataFrame(), pd.DataFrame()
    expected, observed = len(s), int(s.notna().sum())
    q = C.add_yoy(C.quarterly(s)); inc = q.loc[q.days_present < q.days_expected, "Quarter"].tolist()
    spikes, _ = C.spike_table(s, events)
    if len(spikes):
        spikes["quarter"] = pd.to_datetime(spikes["date"]).dt.to_period("Q").map(C.q_label)
        if cadence is not None and cad_col in cadence:
            med = cadence[cad_col].median()
            spikes["spike_quarter_is_release_heavy"] = spikes["quarter"].map(lambda x: bool(cadence[cad_col].get(x, 0) > med))
    coincide = int((spikes.get("release_within_prior_3d", pd.Series(dtype=str)) != "").sum()) if len(spikes) else 0
    row = dict(series=name, retrieved="YES", expected_days=expected, observed_days=observed, missing_days=expected - observed,
               incomplete_quarters=", ".join(inc) if inc else "none", n_spikes=len(spikes), n_spikes_with_release_within_3d=coincide)
    return row, spikes, q

def readiness(qdf):
    """Lead-lag readiness: all 18 quarters 2022Q1-2026Q2 must have a YoY value (which requires the 2021 base quarters too)."""
    if qdf is None or qdf.empty: return dict(n_yoy_2022Q1_2026Q2=0, ready=False)
    n = int(qdf.loc[qdf.Quarter.isin(TARGET_Q), "yoy_pct"].notna().sum())
    return dict(n_yoy_2022Q1_2026Q2=n, ready=(n == len(TARGET_Q)))

def write_data_files(out_dir, start, end, npm_daily, py_daily):
    idx = pd.date_range(start, end, freq="D")
    npm_f = npm_daily if npm_daily is not None else pd.Series(np.nan, index=idx)         # failed source -> blank, never 0
    py_f = py_daily if py_daily is not None else pd.Series(np.nan, index=idx)
    raw = pd.DataFrame({"Date": idx.date, "ddtrace_Python_Downloads": py_f.values, "dd-trace_NPM_Downloads": npm_f.values})
    for c in ("ddtrace_Python_Downloads", "dd-trace_NPM_Downloads"): raw[c] = raw[c].astype("Int64")
    raw.to_csv(os.path.join(out_dir, "developer_adoption_raw.csv"), index=False)
    qp, qn = C.add_yoy(C.quarterly(py_f)), C.add_yoy(C.quarterly(npm_f))
    out = pd.DataFrame({"Quarter": qp.Quarter, "PyPI_ddtrace_Downloads": qp.downloads, "PyPI_Download_YoY": qp.yoy_pct.round(2),
                        "NPM_ddtrace_Downloads": qn.downloads, "NPM_Download_YoY": qn.yoy_pct.round(2)})
    out["PyPI_ddtrace_Downloads"] = out["PyPI_ddtrace_Downloads"].astype("Int64"); out["NPM_ddtrace_Downloads"] = out["NPM_ddtrace_Downloads"].astype("Int64")
    out.to_csv(os.path.join(out_dir, "developer_adoption_quarterly.csv"), index=False)
    cov = pd.DataFrame({"Quarter": qp.Quarter, "days_expected": qp.days_expected, "days_present_pypi": qp.days_present, "days_present_npm": qn.days_present})
    cov.to_csv(os.path.join(out_dir, "developer_adoption_quarterly_coverage.csv"), index=False)
    return out, cov, qp, qn


# ------------------------------------------------------------------------------------------------ main
def main(args, http=None, prober=probe, bq_fetch=None):
    http = http or C.Http(retries=args.retries)
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    os.makedirs(args.out_dir, exist_ok=True)
    status = dict(run_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), start=args.start, end=args.end, code_version=C.CODE_VERSION)

    status["preflight"] = {k: prober(v) for k, v in PROBES.items()}                    # explains WHY a source failed
    m_npm, npm_val = get_npm(http, start, end, verify_point=not args.no_point_check)
    npm_daily = C.to_full_daily(npm_val[0], start, end) if npm_val is not None else None
    if npm_val is not None: status["npm_point_checks_all_match"] = all(c["match"] for c in npm_val[1])
    pypi_log, py_raw, breakdown, pypi_source = get_pypi(http, start, end, args.bq_project, args.max_gb, bq_fetch)
    py_daily = C.to_full_daily(py_raw, start, end) if py_raw is not None else None
    status["attempts"] = [m_npm] + pypi_log

    registry = None
    if npm_daily is not None or py_daily is not None:
        try: registry = C.fetch_registry_metadata(http)
        except Exception as e: status["registry_note"] = f"registry timestamps unavailable, day-level release coincidence skipped: {type(e).__name__}"
    cadence = pd.read_csv(args.cadence_csv, index_col="Quarter") if args.cadence_csv and os.path.exists(args.cadence_csv) else None

    rows, spike_tabs, qframes = [], {}, {}
    for name, s, ev_key, cad_col in (("npm dd-trace", npm_daily, "npm_events", "npm_dd-trace_releases_stable"),
                                     ("PyPI ddtrace", py_daily, "pypi_events", "pypi_ddtrace_releases_stable")):
        row, sp, q = series_block(name, s, start, end, registry[ev_key] if registry else None, cadence, cad_col)
        rows.append(row); spike_tabs[name] = sp; qframes[name] = q
    comp = pd.DataFrame(rows); comp.to_csv(os.path.join(args.out_dir, "developer_adoption_completeness.csv"), index=False)

    # ---- verdicts. SUCCESS requires the FULL period with no missing day; a partial pull is reported as FAIL (partial) but is still written.
    def verdict(s):
        if s is None: return "FAIL"
        miss = int(s.isna().sum()); return "SUCCESS" if miss == 0 else f"FAIL (partial: {miss} of {len(s)} days missing)"
    A, B = verdict(npm_daily), verdict(py_daily)
    rd = {"npm dd-trace": readiness(qframes["npm dd-trace"]), "PyPI ddtrace": readiness(qframes["PyPI ddtrace"])}
    C_ok = any(v["ready"] for v in rd.values())
    ready_which = [k for k, v in rd.items() if v["ready"]]
    status.update(A_npm=A, B_pypi=B, pypi_source=pypi_source, C_quarterly_complete_for_leadlag="YES" if C_ok else "NO",
                  C_series_ready=ready_which, readiness=rd, data_files_written=False)

    if npm_daily is not None or py_daily is not None:
        write_data_files(args.out_dir, start, end, npm_daily, py_daily)
        status["data_files_written"] = True
        qa_cov = pd.read_csv(os.path.join(args.out_dir, "developer_adoption_quarterly_coverage.csv"))
        # The legacy QA reporter assumes both daily series are present.
        # A failed source must not prevent the successful source from being saved.
        if py_daily is not None and npm_daily is not None:
            C.build_qa_report(None, qa_cov, py_daily, npm_daily, registry, {}, args.out_dir)
        else:
            note = ("# Developer Adoption QA\n\n"
                    "One download source was unavailable; the two-series QA report "
                    "was not generated. See developer_adoption_run_report.md and "
                    "developer_adoption_completeness.csv for source-specific QA. "
                    "Unavailable values remain blank (NaN), never zero.\n")
            with open(os.path.join(args.out_dir, "developer_adoption_qa_report.md"), "w") as f:
                f.write(note)
        if breakdown is not None and len(breakdown): breakdown.to_csv(os.path.join(args.out_dir, "pypi_breakdown_daily.csv"), index=False)
    write_report(args.out_dir, status, comp, spike_tabs)
    json.dump(status, open(os.path.join(args.out_dir, "developer_adoption_run_status.json"), "w"), indent=2, default=str)
    return status

def write_report(out_dir, st, comp, spikes):
    L = ["# Developer Adoption collection - run report", f"_run {st['run_utc']} UTC, window {st['start']} .. {st['end']}_", "",
         "## Verdicts", f"* **A. npm historical downloads: {st['A_npm']}**", f"* **B. PyPI historical downloads: {st['B_pypi']}**" + (f" (source: {st['pypi_source']})" if st.get("pypi_source") else ""),
         f"* **C. developer_adoption_quarterly.csv complete enough for 2022Q1-2026Q2 lead-lag testing: {st['C_quarterly_complete_for_leadlag']}**"
         + (f" (via: {', '.join(st['C_series_ready'])})" if st["C_series_ready"] else ""),
         f"* data CSVs written: {st['data_files_written']}  (if False, nothing was retrieved and no file was fabricated)", "",
         "## Network preflight\n", C.md_table(pd.DataFrame([dict(host=k, **v) for k, v in st["preflight"].items()])),
         "## Collection attempts (in order; PyPI stops after ClickPy then BigQuery)\n", C.md_table(pd.DataFrame(st["attempts"])),
         "## Completeness (separately per source)\n", C.md_table(comp.astype(object).where(comp.notna(), "n/a")),
         "## Lead-lag readiness: quarters 2022 Q1 - 2026 Q2 with a YoY value (need 18)\n",
         C.md_table(pd.DataFrame([dict(series=k, **v) for k, v in st["readiness"].items()]))]
    for name, sp in spikes.items():
        L.append(f"## Abnormal spikes - {name} (flagged only, nothing removed)\n"); L.append(C.md_table(sp) if len(sp) else "_none flagged, or series not retrieved_\n")
    open(os.path.join(out_dir, "developer_adoption_run_report.md"), "w").write("\n".join(L))

def banner(st):
    print("\n" + "=" * 78)
    print("A. npm historical downloads:   ", st["A_npm"])
    print("B. PyPI historical downloads:  ", st["B_pypi"], f"[source: {st['pypi_source']}]" if st.get("pypi_source") else "")
    print("C. quarterly.csv complete for 2022Q1-2026Q2 lead-lag testing:", st["C_quarterly_complete_for_leadlag"])
    print("=" * 78)

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2021-01-01"); ap.add_argument("--end", default="2026-06-30"); ap.add_argument("--out-dir", default="./out")
    ap.add_argument("--bq-project", default=None, help="GCP project billed for the BigQuery fallback (needs Application Default Credentials)")
    ap.add_argument("--max-gb", type=float, default=2000); ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--cadence-csv", default="registry_release_cadence_context.csv"); ap.add_argument("--no-point-check", action="store_true")
    return ap.parse_args(argv)

if __name__ == "__main__":
    st = main(parse_args()); banner(st)
    sys.exit(0 if (st["A_npm"] == "SUCCESS" or st["B_pypi"] == "SUCCESS" or st["data_files_written"]) else 1)
