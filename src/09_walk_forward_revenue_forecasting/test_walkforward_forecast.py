"""
Tests for walkforward_forecast.py. Synthetic data only; brute-force cross-checks against numpy/scipy directly.
Run: python test_walkforward_forecast.py
"""
import numpy as np, pandas as pd
import walkforward_forecast as W

def synth_panel(n=16, seed=0):
    rng = np.random.default_rng(seed)
    q = [f"2022 Q{((i) % 4) + 1}" if i < 2 else f"{2022 + (i + 2) // 4} Q{((i + 2) % 4) + 1}" for i in range(n)]
    # simpler: just build sequential fake quarter labels, order doesn't need to be real calendar, only monotonic for the engine
    q = [f"P{i:02d}" for i in range(n)]
    y = 30 + np.cumsum(rng.normal(0, 2, n))
    cloud = 25 + np.cumsum(rng.normal(0, 1.5, n))
    trend = 40 + np.cumsum(rng.normal(0, 3, n))
    df = pd.DataFrame({"Quarter": q, "Revenue_YoY": y, "Cloud_Index_Raw": cloud, "Trend_YoY": trend})
    df["Y_lag1"] = df.Revenue_YoY.shift(1); df["Cloud_lag2"] = df.Cloud_Index_Raw.shift(2); df["Trend_lag1"] = df.Trend_YoY.shift(1)
    return df.dropna(subset=["Y_lag1", "Cloud_lag2", "Trend_lag1"]).reset_index(drop=True)

def test_ols_predict_matches_numpy_polyfit_simple_regression():
    rng = np.random.default_rng(1)
    x = rng.normal(size=20); y = 2.5 * x - 1.0 + rng.normal(scale=0.01, size=20)
    got = W.ols_predict(x.reshape(-1, 1), y, np.array([1.3]))
    slope, intercept = np.polyfit(x, y, 1)
    assert abs(got - (slope * 1.3 + intercept)) < 1e-8

def test_ols_predict_exact_recovery_noiseless_multivariate():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(30, 2)); beta_true = np.array([2.0, -1.5]); y = 5.0 + X @ beta_true
    got = W.ols_predict(X, y, np.array([1.0, 1.0]))
    assert abs(got - (5.0 + 2.0 - 1.5)) < 1e-8

def test_naive_forecast_equals_last_value_exactly():
    panel = synth_panel(16)
    fc = W.walk_forward(panel, min_train=8)
    assert np.allclose(fc.pred_Naive.values, fc.Y_prev.values)

def test_histmean_matches_expanding_mean_by_hand():
    panel = synth_panel(16)
    fc = W.walk_forward(panel, min_train=8)
    for i, row in fc.iterrows():
        t = 8 + i
        expected = panel.Revenue_YoY.iloc[:t].mean()
        assert abs(row.pred_HistMean - expected) < 1e-9

def test_ar1_matches_manual_ols_each_step():
    panel = synth_panel(16)
    fc = W.walk_forward(panel, min_train=8)
    for i, row in fc.iterrows():
        t = 8 + i
        train = panel.iloc[:t]
        slope, intercept = np.polyfit(train.Y_lag1.values, train.Revenue_YoY.values, 1)
        expected = intercept + slope * row.Y_prev
        assert abs(row.pred_AR1 - expected) < 1e-6

def test_only_past_data_used_no_lookahead():
    """Perturbing a FUTURE row's Cloud_lag2 must not change an earlier forecast."""
    panel = synth_panel(16)
    fc1 = W.walk_forward(panel, min_train=8)
    panel2 = panel.copy(); panel2.loc[12, "Cloud_lag2"] += 500  # a large shock far in the future relative to early forecasts
    fc2 = W.walk_forward(panel2, min_train=8)
    assert np.allclose(fc1.pred_Cloud.iloc[:4], fc2.pred_Cloud.iloc[:4])          # first few OOS forecasts unaffected
    assert not np.isclose(fc1.pred_Cloud.iloc[-1], fc2.pred_Cloud.iloc[-1])       # but a late one (whose training includes row 12) does change

def test_metrics_mae_rmse_mape_hand_computed():
    fc = pd.DataFrame({"Quarter": ["Q1", "Q2", "Q3", "Q4"], "Y_actual": [10.0, 20.0, 30.0, 40.0], "Y_prev": [8.0, 10.0, 20.0, 30.0]})
    for m in W.MODELS: fc[f"pred_{m}"] = [10.0, 22.0, 27.0, 44.0]     # same forecast for every model, for a simple hand check
    met = W.metrics_table(fc)
    err = np.array([0.0, -2.0, 3.0, -4.0])
    assert abs(met.MAE.iloc[0] - np.abs(err).mean()) < 1e-9
    assert abs(met.RMSE.iloc[0] - np.sqrt((err ** 2).mean())) < 1e-9
    assert abs(met.MAPE_pct.iloc[0] - (np.abs(err) / np.array([10, 20, 30, 40])).mean() * 100) < 1e-9

def test_directional_accuracy_naive_is_always_zero_by_construction():
    fc = pd.DataFrame({"Y_actual": [12.0, 8.0, 15.0], "Y_prev": [10.0, 10.0, 8.0]})
    for m in W.MODELS: fc[f"pred_{m}"] = fc.Y_prev            # every model forecasts "no change" here
    met = W.metrics_table(fc)
    assert (met.set_index("model").Directional_Accuracy_pct == 0.0).all()   # predicted delta is always exactly 0 -> never matches a nonzero actual delta

def test_directional_accuracy_perfect_model_scores_100():
    fc = pd.DataFrame({"Y_actual": [12.0, 8.0, 15.0, 15.0], "Y_prev": [10.0, 10.0, 8.0, 15.0]})
    for m in W.MODELS: fc[f"pred_{m}"] = fc.Y_actual            # perfect foresight
    met = W.metrics_table(fc)
    assert (met.set_index("model").Directional_Accuracy_pct == 100.0).all()
    assert (met.set_index("model").MAE == 0.0).all()

def test_mechanism_check_runs_and_uses_lag2_only():
    full = synth_panel(18).rename(columns={})
    full["Trend_lag2"] = full.Trend_YoY.shift(0)  # already has Trend_lag1; fabricate Trend_lag2 & Customers col for the test
    full["Customers_100k_YoY"] = 0.5 * full.Trend_lag2 + 3.0
    out = W.mechanism_check(full)
    assert out.iloc[0]["pearson_r"] > 0.999            # exact linear relation via Trend_lag2 -> should recover ~1.0

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed (synthetic data only).")
