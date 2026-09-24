#!/usr/bin/env python3
"""
walkforward_forecast.py - expanding-window out-of-sample comparison and next-quarter forecast of 7 DDOG revenue-YoY models.

PRE-SPECIFIED PREDICTORS (fixed from the prior lead-lag work in this project; NOT re-optimized here):
    Cloud_Index_Raw(t-2)   - hyperscaler cloud growth index, leading DDOG revenue by 2 quarters
    Trend_YoY(t-1)         - Google Trends "Datadog" search YoY, leading DDOG revenue by 1 quarter
Contemporaneous Google Trends (Trend_YoY(t)) is NEVER used as a forecasting input.

MODELS (all refit inside the expanding window at every forecast origin, using ONLY data strictly before t):
    Naive        : Yhat(t) = Y(t-1)
    HistMean     : Yhat(t) = mean(Y(s), s < t)                      (expanding mean)
    AR1          : OLS  Y(t) ~ 1 + Y(t-1)
    Cloud        : OLS  Y(t) ~ 1 + Cloud_Index_Raw(t-2)
    Trends       : OLS  Y(t) ~ 1 + Trend_YoY(t-1)
    Cloud+Trends : OLS  Y(t) ~ 1 + Cloud_Index_Raw(t-2) + Trend_YoY(t-1)
    AR+Cloud+Trends : OLS  Y(t) ~ 1 + Y(t-1) + Cloud_Index_Raw(t-2) + Trend_YoY(t-1)

DESIGN CHOICES (stated explicitly, not hidden):
  * All 7 models are evaluated on the IDENTICAL set of forecast origins, drawn from the widest quarter range where
    Y, Y(t-1), Cloud_Index_Raw(t-2) and Trend_YoY(t-1) are ALL simultaneously available. This means Naive/HistMean/AR1
    could in principle use 2 extra early quarters of revenue history that the multivariate models cannot (because
    Cloud/Trends aren't available that far back) - they are deliberately NOT given that extra data, so every model
    sees exactly the same information at exactly the same points in time and the comparison is apples-to-apples.
    This is a conservative choice for the univariate benchmarks (withholding data can only hurt Naive/HistMean/AR1).
  * Lags are computed on each series' FULL history before the panel is trimmed to the common window, so e.g.
    Cloud_Index_Raw(t-2) for the panel's first quarter correctly uses a real Cloud value from outside the panel.
  * Initial training window = half of the available panel (rounded down), an expanding-window 50/50 split.
    With n=16 (main panel) that is min_train=8, leaving 8 OOS quarters; with n=14 (post-2022 panel) min_train=7,
    leaving 7 OOS quarters. Both are explicit, symmetric, and not tuned to favor any model.
  * With as few as 7-8 OOS points, no formal significance test (e.g. Diebold-Mariano) is reported - the sample is
    too small to support one. Results are comparative and descriptive, not a significance claim.

Trend_YoY(t-2) vs Customers_100k_YoY(t) is tested SEPARATELY as a mechanism-validation correlation check (not a
walk-forward exercise, not a revenue-model input). Integration variables are not used anywhere in this file.
"""
from __future__ import annotations
import os
import re
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IN_DIR = "outputs/"
OUT_DIR = "outputs/"
os.makedirs(OUT_DIR, exist_ok=True)
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)

MODELS = ["Naive", "HistMean", "AR1", "Cloud", "Trends", "Cloud+Trends", "AR+Cloud+Trends"]
PREDICTORS = {"AR1": ["Y_lag1"], "Cloud": ["Cloud_lag2"], "Trends": ["Trend_lag1"],
             "Cloud+Trends": ["Cloud_lag2", "Trend_lag1"], "AR+Cloud+Trends": ["Y_lag1", "Cloud_lag2", "Trend_lag1"]}


# =============================================================================================== panel construction
def load_panel(in_dir=IN_DIR):
    ddog = pd.read_csv(in_dir + "ddog_calculated_dataset.csv")[["Quarter", "Revenue_YoY", "Customers_100k_YoY"]]
    cloud = pd.read_csv(in_dir + "cloud_calculated_data.csv").rename(columns={"Calendar_Quarter": "Quarter"})
    cloud["Cloud_Index_Raw"] = cloud[["AWS_YoY_pct", "Azure_YoY_pct", "GoogleCloud_YoY_pct"]].mean(axis=1)
    trends = pd.read_csv(in_dir + "google_trends_quarterly.csv")[["Quarter", "Trend_YoY"]]

    full = ddog.merge(cloud[["Quarter", "Cloud_Index_Raw"]], on="Quarter", how="outer").merge(trends, on="Quarter", how="outer")
    full = full.sort_values("Quarter").reset_index(drop=True)                 # "YYYY QN" (N single-digit) sorts correctly as text
    full["Y_lag1"] = full["Revenue_YoY"].shift(1)                             # lags computed on FULL history first
    full["Cloud_lag2"] = full["Cloud_Index_Raw"].shift(2)
    full["Trend_lag1"] = full["Trend_YoY"].shift(1)
    full["Trend_lag2"] = full["Trend_YoY"].shift(2)                            # for the separate mechanism check only

    need = ["Revenue_YoY", "Y_lag1", "Cloud_lag2", "Trend_lag1"]
    panel = full.dropna(subset=need).reset_index(drop=True)                   # widest window where ALL revenue-model inputs exist
    return full, panel


# =============================================================================================== OLS (no extra deps)
def ols_predict(X_train: np.ndarray, y_train: np.ndarray, x_new: np.ndarray) -> float:
    Xd = np.column_stack([np.ones(len(X_train)), X_train])
    beta, *_ = np.linalg.lstsq(Xd, y_train, rcond=None)
    return float(np.concatenate([[1.0], x_new]) @ beta)


# =============================================================================================== walk-forward engine
def walk_forward(panel: pd.DataFrame, min_train: int) -> pd.DataFrame:
    rows = []
    for t in range(min_train, len(panel)):
        train = panel.iloc[:t]; cur = panel.iloc[t]
        y_actual, y_prev = float(cur.Revenue_YoY), float(cur.Y_lag1)
        preds = {"Naive": y_prev, "HistMean": float(train.Revenue_YoY.mean())}
        for m in ("AR1", "Cloud", "Trends", "Cloud+Trends", "AR+Cloud+Trends"):
            cols = PREDICTORS[m]
            preds[m] = ols_predict(train[cols].values, train.Revenue_YoY.values, cur[cols].values.astype(float))
        row = dict(Quarter=cur.Quarter, Y_actual=y_actual, Y_prev=y_prev, n_train=len(train))
        row.update({f"pred_{k}": v for k, v in preds.items()})
        rows.append(row)
    return pd.DataFrame(rows)

def metrics_table(fc: pd.DataFrame) -> pd.DataFrame:
    y, yprev = fc.Y_actual, fc.Y_prev
    actual_delta = y - yprev
    rows = []
    for m in MODELS:
        yhat = fc[f"pred_{m}"]; err = y - yhat
        pred_delta = yhat - yprev
        dir_acc = float((np.sign(actual_delta) == np.sign(pred_delta)).mean() * 100)
        rows.append(dict(model=m, n_oos=len(fc), MAE=float(err.abs().mean()), RMSE=float(np.sqrt((err ** 2).mean())),
                         MAPE_pct=float((err.abs() / y.abs()).mean() * 100), Directional_Accuracy_pct=dir_acc))
    return pd.DataFrame(rows)

def run_walkforward(panel: pd.DataFrame, label: str):
    min_train = len(panel) // 2
    fc = walk_forward(panel, min_train)
    met = metrics_table(fc)
    base_rate = float((fc.Y_actual > fc.Y_prev).mean() * 100)
    print(f"\n=== {label}: panel n={len(panel)} ({panel.Quarter.iloc[0]}..{panel.Quarter.iloc[-1]}), min_train={min_train}, OOS n={len(fc)} ({fc.Quarter.iloc[0]}..{fc.Quarter.iloc[-1]}) ===")
    print(f"Base rate: actual growth ACCELERATED in {base_rate:.1f}% of OOS quarters (context for directional accuracy)")
    print(met.to_string(index=False))
    return fc, met, min_train, base_rate


# =============================================================================================== next-quarter, real-time final fit
# This is a NEW forecast origin, not one of the historical OOS forecasts above.
# Keep the same common training panel and pre-specified lag definitions as walk_forward().
def _next_quarter(q: str) -> str:
    match = re.fullmatch(r"(\d{4}) Q([1-4])", str(q))
    if not match:
        raise ValueError(f"Unexpected quarter label: {q!r}; expected YYYY Q1..Q4")
    year, quarter = map(int, match.groups())
    return f"{year + (quarter == 4)} Q{quarter % 4 + 1}"


def _prior_year_revenue_usd_m(in_dir: str, forecast_quarter: str) -> tuple[float, str]:
    """Read an actual USD-million amount; never infer revenue from Revenue_YoY."""
    source = "ddog_calculated_dataset.csv"
    df = pd.read_csv(os.path.join(in_dir, source))
    prior = f"{int(forecast_quarter[:4]) - 1}{forecast_quarter[4:]}"
    candidate_columns = [
        "Revenue_USDm", "Revenue_USD_M", "Revenue_USD_m", "Revenue_USD_millions",
        "Revenue_USD_Millions", "Revenue_M", "Revenue_m", "Revenue",
        "Revenue_usd_m", "Revenue_usd_millions",
    ]
    matches = df.loc[df["Quarter"] == prior]
    if len(matches) != 1:
        raise ValueError(f"Expected one reported revenue row for {prior} in {source}, found {len(matches)}")
    for column in candidate_columns:
        if column in df.columns:
            raw = str(matches.iloc[0][column]).replace(",", "").replace("$", "").strip()
            try:
                amount = float(raw)
            except ValueError:
                continue
            # Project revenue is expected to be in USD millions, not USD or billions.
            if not np.isfinite(amount) or not (100 <= amount <= 10000):
                raise ValueError(
                    f"{source}:{column} for {prior} = {amount}; cannot verify USD-million units. "
                    "Normalize the revenue column to USD millions before forecasting."
                )
            return amount, f"{source}:{column} ({prior}, USD millions; verify source units)"
    raise ValueError(
        f"No usable reported-revenue USD-million column for {prior} in {source}. "
        f"Columns: {list(df.columns)}. Add a verified Revenue_USD_M column; do not back-solve it from YoY."
    )


def forecast_next_quarter(full: pd.DataFrame, panel: pd.DataFrame,
                          met_main: pd.DataFrame, in_dir: str = IN_DIR) -> pd.DataFrame:
    """Fit each existing model through the latest actual quarter; forecast t+1."""
    reported = full.dropna(subset=["Revenue_YoY"]).copy()
    if reported.empty:
        raise ValueError("No historical reported Revenue_YoY data")
    as_of = str(reported.iloc[-1]["Quarter"])
    forecast_quarter = _next_quarter(as_of)
    # Explicit chronology: missing quarters would make row shifts INVALID as calendar lags.
    quarters = full["Quarter"].astype(str).tolist()
    for prev, cur in zip(quarters, quarters[1:]):
        if cur != _next_quarter(prev):
            raise ValueError(f"Missing/non-consecutive quarter between {prev} and {cur}; row shifts are unsafe")
    if panel.empty or str(panel.iloc[-1]["Quarter"]) != as_of:
        raise ValueError("Common training panel does not finish at the latest reported actual quarter")
    if len(panel) < 8:
        raise ValueError("Insufficient complete historical quarters for final fit")
    if forecast_quarter in set(full["Quarter"].astype(str)):
        raise ValueError(f"{forecast_quarter} already exists in source series; refusing to forecast over existing data")
    # No Q3 data entered: only Q2 actual revenue, Q1 observed cloud, Q2 observed Trends.
    preceding = str(full.loc[full["Quarter"] == as_of, "Quarter"].iloc[0])
    i = full.index[full["Quarter"] == preceding][0]
    if i < 1:
        raise ValueError("Need at least two preceding quarters to calculate Cloud(t-2)")
    q_cloud_source = str(full.loc[i - 1, "Quarter"])
    x = {
        "Y_lag1": float(full.loc[i, "Revenue_YoY"]),
        "Cloud_lag2": float(full.loc[i - 1, "Cloud_Index_Raw"]),
        "Trend_lag1": float(full.loc[i, "Trend_YoY"]),
    }
    if not all(np.isfinite(v) for v in x.values()):
        raise ValueError(f"Missing real-time inputs for {forecast_quarter}: {x}; no imputation/look-ahead permitted")
    revenue_prior, prior_source = _prior_year_revenue_usd_m(in_dir, forecast_quarter)
    forecasts = {"Naive": x["Y_lag1"], "HistMean": float(panel["Revenue_YoY"].mean())}
    for model in PREDICTORS:
        columns = PREDICTORS[model]
        forecasts[model] = ols_predict(
            panel[columns].to_numpy(dtype=float),
            panel["Revenue_YoY"].to_numpy(dtype=float),
            np.array([x[col] for col in columns], dtype=float),
        )
    # Presentation selection by MAIN-panel directional accuracy (acceleration/deceleration),
    # not the lowest revenue-YoY MAE. With just 8 OOS quarters this is descriptive,
    # not a statistically validated or nested model-selection procedure.
    metric_by_model = met_main.set_index("model")
    scores = metric_by_model["MAE"]
    directional = metric_by_model["Directional_Accuracy_pct"]
    chosen = min(MODELS, key=lambda m: (-float(directional.loc[m]), float(scores.loc[m]), MODELS.index(m)))
    rows = []
    for model in MODELS:
        yoy = float(forecasts[model])
        rows.append(dict(
            forecast_quarter=forecast_quarter,
            as_of_quarter=as_of,
            model=model,
            selected_for_dashboard=(model == chosen),
            selection_method="highest main-panel OOS directional accuracy; MAE tie-break (exploratory, not nested)",
            historical_oos_mae_pp=float(scores.loc[model]),
            historical_oos_directional_accuracy_pct=float(directional.loc[model]),
            predicted_revenue_yoy_pct=yoy,
            prior_year_revenue_usd_m=revenue_prior,
            predicted_revenue_usd_m=revenue_prior * (1 + yoy / 100),
            n_train=len(panel),
            revenue_lag_source_quarter=as_of,
            cloud_lag_source_quarter=q_cloud_source,
            trends_lag_source_quarter=as_of,
            feature_lags="RevenueYoY t-1; Cloud t-2; Trends t-1",
            data_cutoff=as_of,
            prior_year_revenue_source=prior_source,
            note="Scenario/model estimate; selected on acceleration/deceleration accuracy, not revenue-amount error; 8 main OOS quarters; no calibrated prediction interval",
        ))
    return pd.DataFrame(rows)


# =============================================================================================== mechanism validation (NOT a revenue-model input)
def mechanism_check(full: pd.DataFrame) -> pd.DataFrame:
    d = full.dropna(subset=["Trend_lag2", "Customers_100k_YoY"])
    r, p_r = stats.pearsonr(d.Trend_lag2, d.Customers_100k_YoY)
    rho, p_rho = stats.spearmanr(d.Trend_lag2, d.Customers_100k_YoY)
    # leave-one-out, for the same light robustness read applied everywhere else in this project
    full_r = r; infl = []
    for i in d.index:
        dd = d.drop(i); infl.append((full.loc[i, "Quarter"], stats.pearsonr(dd.Trend_lag2, dd.Customers_100k_YoY)[0]))
    most = max(infl, key=lambda x: abs(full_r - x[1]))
    return pd.DataFrame([dict(x="Trend_YoY(t-2)", y="Customers_100k_YoY(t)", n=len(d), pearson_r=r, spearman_rho=rho,
                              most_influential_quarter=most[0], pearson_excl_most_influential=most[1])])


# =============================================================================================== chart
def chart_forecasts(fc: pd.DataFrame, path: str):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = np.arange(len(fc))
    ax.plot(x, fc.Y_actual, "o-", color="black", lw=2.5, label="Actual DDOG Revenue YoY", zorder=5)
    for m, c in zip(["Naive", "AR1", "Cloud", "Trends", "Cloud+Trends", "AR+Cloud+Trends"],
                    ["#999999", "#1a73e8", "#E8710A", "#34a853", "#d93025", "#632CA6"]):
        ax.plot(x, fc[f"pred_{m}"], "s--", color=c, lw=1.3, ms=4, alpha=.85, label=m)
    ax.set_xticks(x); ax.set_xticklabels(fc.Quarter.str.replace(" ", "\n"), fontsize=8)
    ax.set_ylabel("Revenue YoY (%)"); ax.set_title("Expanding-window OOS forecasts vs actual DDOG Revenue YoY")
    ax.grid(axis="y", alpha=.3); ax.legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)


# =============================================================================================== main
def main():
    full, panel = load_panel()
    fc_main, met_main, mt_main, base_main = run_walkforward(panel, "MAIN PANEL")

    post22 = panel[panel.Quarter >= "2023 Q1"].reset_index(drop=True)
    fc_post, met_post, mt_post, base_post = run_walkforward(post22, "POST-2022 ROBUSTNESS PANEL")

    mech = mechanism_check(full)
    print("\n=== Mechanism validation (NOT a revenue-model input): Trend_YoY(t-2) vs Customers_100k_YoY(t) ===")
    print(mech.to_string(index=False))

    def compare(met, tag):
        ct = met.set_index("model").loc["Cloud+Trends"]; cl = met.set_index("model").loc["Cloud"]; nv = met.set_index("model").loc["Naive"]
        print(f"\n=== {tag}: does Cloud+Trends improve OOS error vs Cloud-only and vs Naive? ===")
        for metr in ("MAE", "RMSE"):
            d_cloud = (ct[metr] - cl[metr]) / cl[metr] * 100
            d_naive = (ct[metr] - nv[metr]) / nv[metr] * 100
            print(f"  {metr}: Cloud+Trends={ct[metr]:.3f} | Cloud-only={cl[metr]:.3f} ({d_cloud:+.1f}%) | Naive={nv[metr]:.3f} ({d_naive:+.1f}%)  [negative % = Cloud+Trends is better]")

    compare(met_main, "MAIN"); compare(met_post, "POST-2022")

    # ---- outputs
    met_main.insert(0, "panel", "main"); met_post.insert(0, "panel", "post2022")
    pd.concat([met_main, met_post], ignore_index=True).round(4).to_csv(OUT_DIR + "walkforward_results.csv", index=False)
    fc_main.round(4).to_csv(OUT_DIR + "walkforward_forecasts_main.csv", index=False)
    fc_post.round(4).to_csv(OUT_DIR + "walkforward_forecasts_post2022.csv", index=False)
    mech.round(4).to_csv(OUT_DIR + "trend_customer_mechanism_check.csv", index=False)
    chart_forecasts(fc_main, OUT_DIR + "chart_walkforward_forecasts.png")
    next_fc = forecast_next_quarter(full, panel, met_main)
    next_fc.round(4).to_csv(OUT_DIR + "next_quarter_forecast.csv", index=False)
    print("\n=== NEW next-quarter revenue forecast (USD millions; distinct from historical OOS) ===")
    print(next_fc[["forecast_quarter", "model", "predicted_revenue_yoy_pct", "predicted_revenue_usd_m", "selected_for_dashboard"]].to_string(index=False))
    print("\nFiles written: walkforward_results.csv, walkforward_forecasts_main.csv, walkforward_forecasts_post2022.csv, "
         "trend_customer_mechanism_check.csv, chart_walkforward_forecasts.png, next_quarter_forecast.csv")
    return dict(full=full, panel=panel, fc_main=fc_main, met_main=met_main, fc_post=fc_post, met_post=met_post, mech=mech, next_quarter_forecast=next_fc)

if __name__ == "__main__":
    main()
