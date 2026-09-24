"""
Tests for analyze_google_trends_signal.py logic. Synthetic data only.
Run: python test_analyze_google_trends_signal.py
"""
import numpy as np, pandas as pd
import analyze_google_trends_signal as A

Q = [f"{y} Q{q}" for y in range(2022, 2027) for q in range(1, 5)][:18]   # 2022Q1..2026Q2

def test_leadlag_convention_and_arithmetic():
    x = pd.Series(np.sin(np.arange(len(Q)) * 1.1) + 0.03 * np.arange(len(Q)), index=Q)
    y = pd.Series(index=Q, dtype=float)
    for i in range(len(Q)):
        y.iloc[i] = 3 * x.iloc[i - 1] - 2 if i >= 1 else np.nan     # y(t) EXACT linear function of x(t-1)
    r0, r1, r2 = A.ll_row(x, y, 0), A.ll_row(x, y, 1), A.ll_row(x, y, 2)
    assert r1["pearson"] > 0.999 and r1["n"] == 17
    assert abs(r0["pearson"]) < 0.99 and abs(r2["pearson"]) < 0.99   # markedly worse at the wrong lag
    xs = x.shift(1).dropna(); ys = y.reindex(xs.index)
    assert abs(np.corrcoef(xs, ys)[0, 1] - r1["pearson"]) < 1e-9     # brute-force cross-check

def test_leave_one_out_finds_the_injected_outlier():
    x = pd.Series(np.random.default_rng(3).normal(size=18), index=Q)
    y = x.copy()
    y.iloc[5] = y.iloc[5] + 20                                       # inject one large outlier
    lo = A.leave_one_out(x, y, 0)
    assert lo["most_influential_quarter"] == Q[5]
    assert lo["r_excl_most_influential"] > lo["full_r"]               # removing the outlier should raise the (deflated) fit

def test_subsample_masks_post2022_and_excl_2025q3():
    master = pd.DataFrame({"Quarter": Q, "Trend_YoY": np.arange(len(Q), dtype=float), "DDOG_Revenue_YoY": np.arange(len(Q), dtype=float) * 2})
    m = master.set_index("Quarter")
    post22 = pd.Series(~m.index.str.startswith("2022"), index=m.index)
    excl_q3 = pd.Series(~m.index.str.startswith("2025 Q3"), index=m.index)
    r_post22 = A.subsample_corr(m.Trend_YoY, m.DDOG_Revenue_YoY, 0, post22)
    r_exclq3 = A.subsample_corr(m.Trend_YoY, m.DDOG_Revenue_YoY, 0, excl_q3)
    assert r_post22["n"] == 14 and r_exclq3["n"] == 17                 # 18 - 4(2022) = 14; 18 - 1(2025Q3) = 17
    assert abs(r_post22["pearson"] - 1.0) < 1e-9                       # perfectly linear subsample -> r=1

def test_master_merge_is_inner_and_unique():
    gt_q = pd.DataFrame({"Quarter": ["2021 Q1", "2022 Q1", "2022 Q2"], "Quarterly_Trend_Mean": [10.0, 20.0, 21.0], "Trend_YoY": [np.nan, 100.0, 5.0]})
    ddog = pd.DataFrame({"Quarter": ["2022 Q1", "2022 Q2"], "Revenue_YoY": [80.0, 70.0], "Customers_100k_YoY": [60.0, 55.0]})
    m = A.build_master(gt_q, ddog)
    assert len(m) == 2 and list(m.Quarter) == ["2022 Q1", "2022 Q2"]    # 2021 Q1 dropped (no DDOG row), inner join
    assert list(m.columns) == ["Quarter", "Quarterly_Trend_Mean", "Trend_YoY", "DDOG_Revenue_YoY", "Customers_100k_YoY"]

def test_monthly_spike_detection_finds_injected_spike():
    dates = pd.date_range("2024-01-01", periods=24, freq="MS")
    vals = np.full(24, 30.0); vals[15] = 100.0                          # a single huge spike
    raw = pd.DataFrame({"Date": dates.strftime("%Y-%m-%d"), "Datadog": vals})
    ms = A.monthly_spikes(raw, top=3)
    assert ms.iloc[0]["date"] == dates[15].strftime("%Y-%m-%d")
    assert ms.iloc[0]["mom_pct_change"] > 100                            # +233% jump 30->100

def test_quarterly_spike_detection_ranks_by_abs_yoy():
    master = pd.DataFrame({"Quarter": Q, "Quarterly_Trend_Mean": np.linspace(10, 50, 18),
                           "Trend_YoY": [np.nan] * 4 + [5, -3, 200, 4, -80, 2, 1, 3, 2, 1, 4, 3, 2, 1]})
    qs = A.quarterly_spikes(master, top=2)
    assert list(qs.Trend_YoY) == [200, -80]                              # ranked by |value|, largest first

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed (synthetic data only).")
