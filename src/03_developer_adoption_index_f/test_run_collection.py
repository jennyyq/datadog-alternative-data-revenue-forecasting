"""
Tests for run_collection.py - every branch of the decision rule.
!!! ALL DATA IS SYNTHETIC and lives only in temporary directories. It is NOT npm / PyPI / Datadog data. !!!
Run:  python test_run_collection.py
"""
import datetime as dt, json, os, tempfile
import numpy as np, pandas as pd
import collect_developer_adoption as C
import run_collection as R
import test_offline_pipeline as T

OK_PROBE = lambda url: dict(status="REACHABLE", http=200, detail="")
class Fake(T.FakeHttp):
    """npm always served unless npm_fail; ClickPy served without gaps unless gap / clickhouse_fail."""
    def __init__(self, npm_fail=False, clickhouse_fail=False, gap=False):
        super().__init__(); self.npm_fail, self.ch_fail, self.gap = npm_fail, clickhouse_fail, gap
    def request(self, method, url, params=None, data=None, **kw):
        if "/downloads/" in url and self.npm_fail: raise RuntimeError(f"GET {url} -> HTTP 403: Host not in allowlist: api.npmjs.org")
        if url == C.CLICKHOUSE_URL:
            if self.ch_fail: raise RuntimeError("POST clickhouse -> HTTP 403: Host not in allowlist")
            sql = data.decode()
            if "system.columns" in sql: return T.Resp({"data": [["date"], ["project"], ["count"]]})
            import re; a, b = re.findall(r"'(\d{4}-\d\d-\d\d)'", sql)
            skip = T.GAP_DAYS if self.gap else set()
            return T.Resp({"data": [[str(d), T.py_val(d)] for d in T.daterange(dt.date.fromisoformat(a), dt.date.fromisoformat(b)) if d not in skip]})
        return super().request(method, url, params=params, data=data, **kw)

def bq_ok():
    idx = pd.date_range("2021-01-01", "2026-06-30", freq="D")
    return pd.Series([float(T.py_val(d.date())) for d in idx], index=idx), None, dict(bytes_scanned_estimate=1, has_ci_column=False)
def bq_fail(): raise RuntimeError("DefaultCredentialsError: no credentials")

def go(http, bq=bq_fail):
    tmp = tempfile.mkdtemp(); a = R.parse_args(["--out-dir", tmp, "--cadence-csv", ""])
    return tmp, R.main(a, http=http, prober=OK_PROBE, bq_fetch=bq)

def test_all_succeed():
    tmp, st = go(Fake())
    assert (st["A_npm"], st["B_pypi"], st["C_quarterly_complete_for_leadlag"]) == ("SUCCESS", "SUCCESS", "YES") and st["pypi_source"] == "ClickPy/ClickHouse"
    q = pd.read_csv(os.path.join(tmp, "developer_adoption_quarterly.csv"))
    assert len(q) == 22 and q.loc[q.Quarter.str.startswith("2021"), ["PyPI_Download_YoY", "NPM_Download_YoY"]].isna().all().all()
    assert q.loc[q.Quarter.isin(R.TARGET_Q), ["PyPI_Download_YoY", "NPM_Download_YoY"]].notna().all().all()
    assert list(q.columns) == ["Quarter", "PyPI_ddtrace_Downloads", "PyPI_Download_YoY", "NPM_ddtrace_Downloads", "NPM_Download_YoY"]

def test_bigquery_fallback_used_when_clickpy_fails():
    tmp, st = go(Fake(clickhouse_fail=True), bq=bq_ok)
    assert st["B_pypi"] == "SUCCESS" and st["pypi_source"] == "BigQuery"
    labels = [(a["label"], a["status"]) for a in st["attempts"]]
    assert ("PyPI via ClickPy/ClickHouse", "FAIL") in labels and ("PyPI via BigQuery public dataset", "SUCCESS") in labels

def test_pypi_fails_everywhere_npm_is_preserved_and_pypi_left_blank():
    tmp, st = go(Fake(clickhouse_fail=True), bq=bq_fail)
    assert (st["A_npm"], st["B_pypi"], st["C_quarterly_complete_for_leadlag"]) == ("SUCCESS", "FAIL", "YES")
    assert st["C_series_ready"] == ["npm dd-trace"]
    q = pd.read_csv(os.path.join(tmp, "developer_adoption_quarterly.csv")); r = pd.read_csv(os.path.join(tmp, "developer_adoption_raw.csv"))
    assert q["PyPI_ddtrace_Downloads"].isna().all() and q["PyPI_Download_YoY"].isna().all()          # blank, NOT zero
    assert r["ddtrace_Python_Downloads"].isna().all() and r["dd-trace_NPM_Downloads"].notna().all()
    errs = [a["error"] for a in st["attempts"] if a["status"] == "FAIL"]
    assert len(errs) == 2 and "clickhouse" in errs[0].lower() and "credentials" in errs[1].lower()      # both reasons recorded
    assert not any(a["label"].startswith("PyPI") and a["label"] not in ("PyPI via ClickPy/ClickHouse", "PyPI via BigQuery public dataset") for a in st["attempts"])  # rule: no 3rd PyPI method

def test_npm_fails_pypi_preserved():
    tmp, st = go(Fake(npm_fail=True))
    assert (st["A_npm"], st["B_pypi"], st["C_quarterly_complete_for_leadlag"]) == ("FAIL", "SUCCESS", "YES") and st["C_series_ready"] == ["PyPI ddtrace"]
    q = pd.read_csv(os.path.join(tmp, "developer_adoption_quarterly.csv")); assert q["NPM_ddtrace_Downloads"].isna().all()

def test_both_fail_no_data_files_are_fabricated():
    tmp, st = go(Fake(npm_fail=True, clickhouse_fail=True), bq=bq_fail)
    assert (st["A_npm"], st["B_pypi"], st["C_quarterly_complete_for_leadlag"]) == ("FAIL", "FAIL", "NO") and st["data_files_written"] is False
    for f in ("developer_adoption_raw.csv", "developer_adoption_quarterly.csv", "developer_adoption_quarterly_coverage.csv"):
        assert not os.path.exists(os.path.join(tmp, f)), f
    for f in ("developer_adoption_run_report.md", "developer_adoption_run_status.json", "developer_adoption_completeness.csv"):
        assert os.path.exists(os.path.join(tmp, f)), f                                                # the evidence of the failure IS written
    assert "FAIL" in open(os.path.join(tmp, "developer_adoption_run_report.md")).read()

def test_partial_pypi_is_reported_fail_but_kept_unfilled():
    tmp, st = go(Fake(gap=True))
    assert st["B_pypi"].startswith("FAIL (partial: 3 of 2007 days missing)")
    r = pd.read_csv(os.path.join(tmp, "developer_adoption_raw.csv")); assert r["ddtrace_Python_Downloads"].isna().sum() == 3
    q = pd.read_csv(os.path.join(tmp, "developer_adoption_quarterly.csv")); assert pd.isna(q.loc[q.Quarter == "2023 Q2", "PyPI_ddtrace_Downloads"].iloc[0])
    assert st["readiness"]["PyPI ddtrace"]["ready"] is False and st["readiness"]["npm dd-trace"]["ready"] is True and st["C_quarterly_complete_for_leadlag"] == "YES"
    comp = pd.read_csv(os.path.join(tmp, "developer_adoption_completeness.csv")).set_index("series")
    assert comp.loc["PyPI ddtrace", "missing_days"] == 3 and comp.loc["PyPI ddtrace", "incomplete_quarters"] == "2023 Q2" and comp.loc["npm dd-trace", "missing_days"] == 0

def test_spike_release_coincidence_reported_and_spike_not_removed():
    tmp, st = go(Fake())
    comp = pd.read_csv(os.path.join(tmp, "developer_adoption_completeness.csv")).set_index("series")
    assert comp.loc["npm dd-trace", "n_spikes"] >= 1 and comp.loc["npm dd-trace", "n_spikes_with_release_within_3d"] >= 1   # fake release 2023-05-16 precedes the injected 2023-05-17 spike
    r = pd.read_csv(os.path.join(tmp, "developer_adoption_raw.csv"))
    assert int(r.loc[r.Date == str(T.SPIKE_DAY), "dd-trace_NPM_Downloads"].iloc[0]) == T.npm_val(T.SPIKE_DAY)

def test_readiness_requires_2021_base_quarters():
    idx = pd.date_range("2021-01-01", "2026-06-30", freq="D"); s = pd.Series(100.0, index=idx); s.loc["2021-08-01":"2021-08-03"] = np.nan   # 2021 Q3 incomplete
    q = C.add_yoy(C.quarterly(s)); rd = R.readiness(q)
    assert rd["ready"] is False and rd["n_yoy_2022Q1_2026Q2"] == 17            # 2022 Q3 YoY lost because its base quarter is incomplete

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} orchestrator tests passed (synthetic data, temp directories only).")
