"""
Tests for build_google_trends_signal.py. ALL DATA IS SYNTHETIC (a mock TrendReq). Not real Google Trends data.
Run: python test_google_trends_signal.py
"""
import tempfile, os
import numpy as np, pandas as pd
import build_google_trends_signal as G

class FakeTR:
    """Mimics: single monthly request over a >5.25y span returns one consistent 0-100-scaled series;
    each call has small random sampling noise; qualifier terms are sparse (many zero months)."""
    def __init__(self, seed=0, ambiguous=False, sparse_qualifiers=True):
        self.rng = np.random.default_rng(seed); self.ambiguous = ambiguous; self.sparse = sparse_qualifiers
    def suggestions(self, name):
        s = [{"mid": "/g/xyz", "title": "Datadog", "type": "Software"}]
        return s + ([{"mid": "/m/abc", "title": "Datadog", "type": "Company"}] if self.ambiguous else [])
    def build_payload(self, kw_list, cat=0, timeframe="", geo="", gprop=""): self._kw, self._tf = kw_list[0], timeframe
    def interest_over_time(self):
        a, b = [pd.Timestamp(x) for x in self._tf.split()]
        idx = pd.date_range(a, b, freq="MS")
        n = len(idx)
        if self._kw in ("Datadog APM", "Datadog logs", "Datadog monitoring") and self.sparse:
            base = np.where(self.rng.random(n) < 0.3, self.rng.integers(1, 5, n), 0).astype(float)
        else:
            base = 40 + 20 * np.arange(n) / n + self.rng.normal(0, 1.5, n)
        return pd.DataFrame({self._kw: np.clip(np.round(base), 0, 100), "isPartial": False}, index=idx)

def test_single_monthly_request_covers_full_span_no_stitching():
    s = G.pull_monthly(FakeTR(), "/g/xyz", pause=0)
    assert len(s) == 66 and s.index[0] == pd.Timestamp("2021-01-01") and s.index[-1] == pd.Timestamp("2026-06-01")

def test_topic_resolved_only_when_unambiguous():
    label, q, sug = G.resolve_topic_or_term(FakeTR(), "Datadog")
    assert label == "topic:Datadog" and q == "/g/xyz"
    label2, q2, _ = G.resolve_topic_or_term(FakeTR(ambiguous=True), "Datadog")
    assert label2 == "term:Datadog" and q2 == "Datadog"          # falls back to the plain term, never guesses

def test_quarterly_mean_requires_all_three_months():
    idx = pd.date_range("2021-01-01", "2021-12-01", freq="MS")
    s = pd.Series([10, 20, 30, np.nan, 50, 60, 70, 80, 90, 100, 110, 120], index=idx)
    q = G.quarterly_mean(s, "2021Q1", "2021Q4")
    assert q.set_index("Quarter").loc["2021 Q1", "Quarterly_Trend_Mean"] == 20
    assert np.isnan(q.set_index("Quarter").loc["2021 Q2", "Quarterly_Trend_Mean"])   # one NaN month -> whole quarter blank

def test_yoy_only_where_base_available_and_positive():
    q = pd.DataFrame({"Quarterly_Trend_Mean": [0.0, 10.0, 10.0, 10.0, 20.0, np.nan, 10.0, 10.0]})
    q = G.add_yoy(q)
    assert np.isnan(q.Trend_YoY.iloc[0]) and np.isnan(q.Trend_YoY.iloc[1])   # no t-4 available yet
    assert np.isnan(q.Trend_YoY.iloc[4])                                    # base (index0) is 0 -> YoY blocked, not divide-by-zero
    assert np.isnan(q.Trend_YoY.iloc[5])                                    # y itself is NaN
    assert q.Trend_YoY.iloc[6] == 0.0                                       # base (index2=10) fine, y=10 -> 0% exactly

def test_repeat_stats_quantifies_sampling_noise():
    idx = pd.date_range("2021-01-01", "2021-06-01", freq="MS")
    runs = [pd.Series([10, 20, 30, 40, 50, 60], index=idx) + i for i in range(3)]
    st = G.repeat_stats(runs)
    assert st["n_repeats"] == 3 and st["max_spread"] == 2.0 and st["min_pairwise_corr"] > 0.99

def test_sparse_qualifier_terms_excluded_from_primary():
    with tempfile.TemporaryDirectory() as tmp:
        res = G.run(tmp, repeats=2, tr=FakeTR(sparse_qualifiers=True))
        assert res["log"]["primary_series_used"] == "Datadog alone (all qualifier terms too sparse)"
        for term, info in res["log"]["qualifier_terms"].items():
            assert info["included_in_primary"] is False and info["nonzero_share"] < G.NONZERO_SHARE_MIN

def test_dense_qualifier_terms_included_in_primary():
    with tempfile.TemporaryDirectory() as tmp:
        res = G.run(tmp, repeats=2, tr=FakeTR(sparse_qualifiers=False))
        assert "Datadog + " in res["log"]["primary_series_used"] or res["log"]["primary_series_used"].startswith("mean of")
        assert all(v["included_in_primary"] for v in res["log"]["qualifier_terms"].values())

def test_end_to_end_output_files_and_schema():
    with tempfile.TemporaryDirectory() as tmp:
        res = G.run(tmp, repeats=2, tr=FakeTR())
        for f in ("google_trends_raw_monthly.csv", "google_trends_quarterly.csv", "google_trends_run_log.json"):
            assert os.path.exists(os.path.join(tmp, f)), f
        q = pd.read_csv(os.path.join(tmp, "google_trends_quarterly.csv"))
        assert list(q.columns) == ["Quarter", "n_months", "Quarterly_Trend_Mean", "Trend_YoY"]
        assert len(q) == 22 and q.Quarter.iloc[0] == "2021 Q1" and q.Quarter.iloc[-1] == "2026 Q2"
        assert q.loc[q.Quarter.str.startswith("2021"), "Trend_YoY"].isna().all()
        assert q.loc[q.Quarter == "2022 Q1", "Trend_YoY"].notna().all()

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed (synthetic mock only, not real Google Trends data).")
