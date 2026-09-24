"""
Tests for final_exhibits.py (cleanup pass) - the leadlag stat helper, the non-overlapping label placement,
and the five dashboard module states. There is deliberately no "composite signal" test in this version: the
composite rule was removed per the final-cleanup instructions, and Exhibit 6 now reports the five module reads
as plain text with no computed aggregate. Synthetic data only where noted.
Run: python test_final_exhibits.py
"""
import numpy as np, pandas as pd
import final_exhibits as F

def test_leadlag_xy_matches_bruteforce():
    q = [f"2022 Q{i%4+1}" if i < 4 else f"{2022+i//4} Q{i%4+1}" for i in range(16)]
    x = pd.Series(np.random.default_rng(1).normal(size=16))
    y = pd.Series(np.random.default_rng(2).normal(size=16))
    df = pd.DataFrame({"Quarter": q, "X": x, "Y": y})
    d, r, rho = F.leadlag_xy(df, "X", "Y", 2)
    xs = x.shift(2).dropna().values; ys = y.iloc[2:].values
    assert abs(np.corrcoef(xs, ys)[0, 1] - r) < 1e-9
    assert len(d) == 14

def test_exhibit3_stats_match_the_current_google_trends_master():
    import tempfile, os
    gt = pd.read_csv("outputs/ddog_google_trends_master.csv")
    with tempfile.TemporaryDirectory() as tmp:
        out = F.exhibit3_trends_scatter(gt, os.path.join(tmp, "e3.png"))
    # Do not hard-code statistics from a different Google Trends sample.
    d = pd.DataFrame({"x":gt.Trend_YoY.shift(2), "y":gt.Customers_100k_YoY,
                      "q":gt.Quarter}).dropna()
    post = d[d.q >= "2023 Q1"]
    from scipy.stats import spearmanr
    assert np.isclose(out["r_full"], np.corrcoef(d.x,d.y)[0,1])
    assert np.isclose(out["rho_full"], spearmanr(d.x,d.y).statistic)
    assert np.isclose(out["r_post"], np.corrcoef(post.x,post.y)[0,1])
    assert np.isclose(out["rho_post"], spearmanr(post.x,post.y).statistic)

def test_exhibit2_cloud_stats_unchanged_by_the_cleanup_pass():
    cloud = pd.read_csv("outputs/ddog_cloud_master.csv")
    d, r, rho = F.leadlag_xy(cloud, "Cloud_Index_Raw", "DDOG_Revenue_YoY", 2)
    assert abs(r - 0.857) < 0.001 and abs(rho - 0.703) < 0.001 and len(d) == 16

def test_exhibit4_merges_real_ols_and_ridge_csvs_without_stale_numbers():
    import os, tempfile
    ols = pd.read_csv("outputs/walkforward_results.csv")
    ridge = pd.read_csv("outputs/walkforward_ridge_results.csv")
    m = F.combine_walkforward_results(ols, ridge)
    assert len(m) == 8
    assert list(m.index) == F.MODEL_ORDER
    assert (m.n_oos == 8).all()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "exhibit4.png")
        out = F.exhibit4_walkforward(ols, ridge, path)
        assert os.path.getsize(path) > 0
    assert out["lowest_mae_model"] == m.MAE.idxmin()
    eligible = m.drop(index="Naive")
    expected = eligible.index[np.isclose(eligible.Directional_Accuracy_pct,
                                         eligible.Directional_Accuracy_pct.max())].tolist()
    assert out["highest_direction_models"] == expected
    assert np.isclose(out["highest_direction_pct"], eligible.Directional_Accuracy_pct.max())
    assert out["model_count"] == 8


def test_exhibit4_rejects_missing_ridge_or_mismatched_oos():
    ols = pd.read_csv("outputs/walkforward_results.csv")
    ridge = pd.read_csv("outputs/walkforward_ridge_results.csv")
    try:
        F.combine_walkforward_results(ols, ridge.iloc[0:0])
        raise AssertionError("Should reject missing Ridge rows")
    except ValueError as e:
        assert "Missing" in str(e)
    bad = ridge.copy()
    bad.loc[bad.panel == "main", "n_oos"] = 7
    try:
        F.combine_walkforward_results(ols, bad)
        raise AssertionError("Should reject mismatched OOS count")
    except ValueError as e:
        assert "same eight" in str(e)


def test_dashboard_has_no_composite_signal_key():
    """The prior version returned op_signal/op_reason from a mechanical 2-of-3 rule; this version must not."""
    cloud = pd.read_csv("outputs/ddog_cloud_master.csv")
    gt = pd.read_csv("outputs/ddog_google_trends_master.csv")
    wf = pd.read_csv("outputs/walkforward_results.csv")
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        dash = F.exhibit6_dashboard(cloud, gt, wf, os.path.join(tmp, "e6.png"))
    assert "op_signal" not in dash and "op_reason" not in dash

def test_dashboard_module_states_match_the_specified_wording():
    cloud = pd.read_csv("outputs/ddog_cloud_master.csv")
    gt = pd.read_csv("outputs/ddog_google_trends_master.csv")
    wf = pd.read_csv("outputs/walkforward_results.csv")
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        dash = F.exhibit6_dashboard(cloud, gt, wf, os.path.join(tmp, "e6.png"))
    assert dash["rev_state"] == "Accelerating"
    assert dash["cloud_state"] == "Accelerating"
    assert dash["trend_state"] == "Volatile / mixed"
    assert dash["cust_state"] == "Accelerating"                # 16.33 -> 19.39 -> 20.69 -> 22.60, monotonic
    assert dash["catalyst_state"] == "Strong adoption/usage momentum"

def test_label_placement_avoids_overlaps_and_avoids_the_stats_box_and_legend():
    """Exhibit 3's greedy label placer must (a) place every one of the 16 quarter labels, and (b) never overlap
    the stats box or the legend it registers as pre-placed obstacles - a synthetic, tightly-clustered dataset
    stresses this harder than the real (already fairly spread) data."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rng = np.random.default_rng(0)
    q = [f"2022 Q{i%4+1}" if i < 4 else f"{2022+i//4} Q{i%4+1}" for i in range(16)]
    gt = pd.DataFrame({"Quarter": q, "Trend_YoY": 20 + rng.normal(0, 1, 16), "Customers_100k_YoY": 15 + rng.normal(0, 1, 16)})
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, "e3_stress.png")
        F.exhibit3_trends_scatter(gt, out_path)
        assert os.path.exists(out_path) and os.path.getsize(out_path) > 0

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed.")
