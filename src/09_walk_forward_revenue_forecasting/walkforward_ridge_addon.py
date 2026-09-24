#!/usr/bin/env python3
"""Exploratory, post-hoc Ridge sensitivity alongside (not replacing) original OLS walk-forward.

Same inputs, lags, initial train size and OOS origins as walkforward_forecast.py.
Fixed alpha=10 on training-standardized X; NO selection against the held-out 8/7 quarters.
Results are exploratory because Ridge was introduced after original OOS inspection.
Outputs have distinct names; original walkforward_results.csv is never overwritten.
"""
from __future__ import annotations
import os, json
import numpy as np
import pandas as pd
import walkforward_forecast as W

ALPHA = 10.0
RIDGE_SPECS = {
    "Ridge_Cloud+Trends": ["Cloud_lag2", "Trend_lag1"],
    "Ridge_AR+Cloud+Trends": ["Y_lag1", "Cloud_lag2", "Trend_lag1"],
}

def ridge_predict(X_train, y_train, x_new, alpha=ALPHA):
    """Training-only feature scaling, unpenalized intercept; no future values in fit."""
    X = np.asarray(X_train, dtype=float)
    y = np.asarray(y_train, dtype=float)
    x = np.asarray(x_new, dtype=float)
    mean = X.mean(axis=0)
    sd = X.std(axis=0, ddof=0)
    sd = np.where(sd > 1e-12, sd, 1.0)
    z = (X - mean) / sd
    z_new = (x - mean) / sd
    y_mean = y.mean()
    beta = np.linalg.solve(z.T @ z + alpha * np.eye(X.shape[1]), z.T @ (y-y_mean))
    return float(y_mean + z_new @ beta)

def forecast(panel, min_train):
    rows=[]
    for t in range(min_train, len(panel)):
        train=panel.iloc[:t]
        current=panel.iloc[t]
        row=dict(Quarter=current.Quarter,Y_actual=float(current.Revenue_YoY),
                 Y_prev=float(current.Y_lag1),n_train=len(train))
        for name,cols in RIDGE_SPECS.items():
            row[f"pred_{name}"]=ridge_predict(train[cols].values,
                         train.Revenue_YoY.values,current[cols].values,ALPHA)
        rows.append(row)
    return pd.DataFrame(rows)

def metrics(fc, panel_name):
    results=[]
    for name in RIDGE_SPECS:
        y=fc.Y_actual.to_numpy();pred=fc[f"pred_{name}"].to_numpy()
        prev=fc.Y_prev.to_numpy()
        results.append(dict(panel=panel_name,model=name,n_oos=len(fc),
                            MAE=np.abs(y-pred).mean(),RMSE=np.sqrt(np.mean((y-pred)**2)),
                            MAPE_pct=np.mean(np.abs(y-pred)/np.abs(y))*100,
                            Directional_Accuracy_pct=np.mean(np.sign(y-prev)==np.sign(pred-prev))*100,
                            alpha=ALPHA))
    return pd.DataFrame(results)

def main():
    full,panel=W.load_panel()
    post=panel[panel.Quarter >= "2023 Q1"].reset_index(drop=True)
    out=W.OUT_DIR
    os.makedirs(out,exist_ok=True)
    f_main=forecast(panel,len(panel)//2)
    f_post=forecast(post,len(post)//2)
    ms=pd.concat([metrics(f_main,"main"),metrics(f_post,"post2022")],ignore_index=True)
    f_main.round(4).to_csv(os.path.join(out,"walkforward_ridge_forecasts_main.csv"),index=False)
    f_post.round(4).to_csv(os.path.join(out,"walkforward_ridge_forecasts_post2022.csv"),index=False)
    ms.round(4).to_csv(os.path.join(out,"walkforward_ridge_results.csv"),index=False)
    with open(os.path.join(out,"walkforward_ridge_method.json"),"w") as f:
        json.dump({"alpha":ALPHA,"feature_scaling":"train-window only",
                   "intercept":"not penalized","lags":"unchanged from OLS",
                   "interpretation":"post-hoc exploratory; do not claim independent confirmatory OOS validation"},f,indent=2)
    print(ms.round(4).to_string(index=False))
    print("Ridge files written separately; original OLS output is unchanged.")
    return ms

if __name__ == "__main__":
    main()
