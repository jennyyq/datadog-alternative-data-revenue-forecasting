"""
DDOG vs hyperscaler cloud growth: merge/QA, cloud indices, descriptives, lead-lag diagnostics, charts.
Uses ONLY the two attached CSVs. No new data, no interpolation, no modification of raw observations.

LAG CONVENTION (used everywhere):  k = number of quarters the CLOUD series is shifted BACK.
    k = +1 : corr( Cloud_(t-1), DDOG_t )   -> cloud leads DDOG by 1 quarter
    k = +2 : corr( Cloud_(t-2), DDOG_t )   -> cloud leads DDOG by 2 quarters
    k =  0 : corr( Cloud_t,     DDOG_t )   -> contemporaneous
    k = -1 : corr( Cloud_(t+1), DDOG_t )   -> DIAGNOSTIC ONLY: cloud LAGS DDOG (DDOG leads cloud by 1Q)
"""
import os
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IN_DIR  = "outputs/"
OUT_DIR = "outputs/"
os.makedirs(OUT_DIR, exist_ok=True)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
pd.options.display.float_format = "{:,.3f}".format

# =========================================================== STEP 1: MERGE + QA
ddog  = pd.read_csv(IN_DIR + "ddog_calculated_dataset.csv")
cloud = pd.read_csv(IN_DIR + "cloud_calculated_data.csv")
print("=== STEP 1: QA ===")
print("DDOG file rows:", len(ddog), "| cloud file rows:", len(cloud))
print("DDOG columns :", list(ddog.columns))
print("Cloud columns:", list(cloud.columns))

# duplicates / missing in the columns actually used
d_dup = ddog["Quarter"].duplicated().sum(); c_dup = cloud["Calendar_Quarter"].duplicated().sum()
print("Duplicate quarter keys  DDOG:", d_dup, "| cloud:", c_dup)
used = ["Revenue_YoY"]; cused = ["AWS_YoY_pct", "Azure_YoY_pct", "GoogleCloud_YoY_pct"]
print("Missing in used DDOG cols :", ddog[used].isna().sum().to_dict())
print("Missing in used cloud cols:", cloud[cused].isna().sum().to_dict())
print("Missing in UNUSED DDOG cols (not part of this analysis):",
      {k: int(v) for k, v in ddog.isna().sum().items() if v > 0})

# key format + calendar-consistency checks
fmt_ok = ddog["Quarter"].str.fullmatch(r"\d{4} Q[1-4]").all() and cloud["Calendar_Quarter"].str.fullmatch(r"\d{4} Q[1-4]").all()
qe = pd.to_datetime(ddog["Quarter_End"])
lab_from_end = qe.dt.year.astype(str) + " Q" + qe.dt.quarter.astype(str)
label_matches_qend = (lab_from_end == ddog["Quarter"]).all()
def consecutive(lbls):
    idx = [int(s[:4]) * 4 + int(s[-1]) for s in lbls]
    return all(b - a == 1 for a, b in zip(idx[:-1], idx[1:]))
print("Key format OK:", fmt_ok, "| DDOG label agrees with Quarter_End date:", label_matches_qend)
print("Consecutive quarters, no gaps  DDOG:", consecutive(ddog["Quarter"]), "| cloud:", consecutive(cloud["Calendar_Quarter"]))

m = pd.merge(ddog, cloud, left_on="Quarter", right_on="Calendar_Quarter", how="outer",
             validate="one_to_one", indicator=True)
print("Merge result counts:", m["_merge"].value_counts().to_dict())
assert (m["_merge"] == "both").all()
m = m.sort_values("Quarter").reset_index(drop=True)
assert (m["Quarter"] == m["Calendar_Quarter"]).all()
print("Matched observations:", len(m), "| first:", m["Quarter"].iloc[0], "| last:", m["Quarter"].iloc[-1])
print("Row-by-row label alignment identical:", bool((m["Quarter"] == m["Calendar_Quarter"]).all()))

df = pd.DataFrame({"Quarter": m["Quarter"],
                   "DDOG_Revenue_YoY": m["Revenue_YoY"],
                   "AWS_YoY": m["AWS_YoY_pct"], "Azure_YoY": m["Azure_YoY_pct"],
                   "GoogleCloud_YoY": m["GoogleCloud_YoY_pct"]})
# raw values in the merged frame are byte-identical to the source columns
assert np.array_equal(df["DDOG_Revenue_YoY"].values, ddog.sort_values("Quarter")["Revenue_YoY"].values)
assert np.array_equal(df["AWS_YoY"].values, cloud.sort_values("Calendar_Quarter")["AWS_YoY_pct"].values)

# =========================================================== STEP 2: INDICES
P = ["AWS_YoY", "Azure_YoY", "GoogleCloud_YoY"]
df["Cloud_Index_Raw"] = df[P].mean(axis=1)                      # equal-weight, percentage points
Z = (df[P] - df[P].mean()) / df[P].std(ddof=1)                  # full-sample z-score, sample std (ddof=1)
df["Cloud_Index_Z"] = Z.mean(axis=1)                            # mean of the three z-scores
df["Z_AWS"], df["Z_Azure"], df["Z_GoogleCloud"] = Z["AWS_YoY"], Z["Azure_YoY"], Z["GoogleCloud_YoY"]
df["DDOG_Z"] = (df["DDOG_Revenue_YoY"] - df["DDOG_Revenue_YoY"].mean()) / df["DDOG_Revenue_YoY"].std(ddof=1)
print("\n=== STEP 2: z-score parameters (full sample, ddof=1) ===")
print(pd.DataFrame({"mean": df[P].mean(), "std": df[P].std(ddof=1)}))

master = df[["Quarter", "DDOG_Revenue_YoY", "AWS_YoY", "Azure_YoY", "GoogleCloud_YoY",
             "Cloud_Index_Raw", "Cloud_Index_Z"]].copy()
master["Cloud_Index_Raw"] = master["Cloud_Index_Raw"].round(6)
master["Cloud_Index_Z"] = master["Cloud_Index_Z"].round(6)
master.to_csv(OUT_DIR + "ddog_cloud_master.csv", index=False)
print(master.to_string(index=False))

# =========================================================== STEP 3: DESCRIPTIVES
V = ["DDOG_Revenue_YoY", "AWS_YoY", "Azure_YoY", "GoogleCloud_YoY", "Cloud_Index_Raw"]
desc = pd.DataFrame({"mean": df[V].mean(), "std (ddof=1)": df[V].std(ddof=1),
                     "min": df[V].min(), "max": df[V].max(),
                     "argmin": [df.loc[df[c].idxmin(), "Quarter"] for c in V],
                     "argmax": [df.loc[df[c].idxmax(), "Quarter"] for c in V]})
print("\n=== STEP 3a: descriptive statistics (n = %d) ===" % len(df)); print(desc)
desc.to_csv(OUT_DIR + "table_descriptives.csv")

pear = df[V].corr(method="pearson"); spear = df[V].corr(method="spearman")
print("\n=== STEP 3b: Pearson correlation matrix ==="); print(pear)
print("\n=== STEP 3b': Spearman correlation matrix ==="); print(spear)
pear.to_csv(OUT_DIR + "table_corr_pearson.csv"); spear.to_csv(OUT_DIR + "table_corr_spearman.csv")

# persistence of each series (lag-1 autocorrelation) -> effective sample size warning
ac1 = pd.Series({c: df[c].autocorr(1) for c in V + ["Cloud_Index_Z"]})
print("\nLag-1 autocorrelation of each series:"); print(ac1)

# ---- Google Cloud influence on the equal-weight index
df["Cloud_Index_exGoogle"] = df[["AWS_YoY", "Azure_YoY"]].mean(axis=1)      # 2-provider comparison index
last3 = df["Quarter"].isin(["2025 Q4", "2026 Q1", "2026 Q2"])
base_q, end_q = "2025 Q3", "2026 Q2"
b = df.set_index("Quarter")
chg = pd.DataFrame({"start (2025 Q3)": b.loc[base_q, P], "end (2026 Q2)": b.loc[end_q, P]})
chg["change (pp)"] = chg["end (2026 Q2)"] - chg["start (2025 Q3)"]
chg["contribution to index change (pp) = change/3"] = chg["change (pp)"] / 3
chg["share of index change"] = chg["contribution to index change (pp) = change/3"] / (b.loc[end_q, "Cloud_Index_Raw"] - b.loc[base_q, "Cloud_Index_Raw"])
print("\n=== STEP 3c: what drove the index move 2025 Q3 -> 2026 Q2 ===")
print(chg)
print("Index Raw:", round(b.loc[base_q, "Cloud_Index_Raw"], 2), "->", round(b.loc[end_q, "Cloud_Index_Raw"], 2),
      "| ex-Google:", round(b.loc[base_q, "Cloud_Index_exGoogle"], 2), "->", round(b.loc[end_q, "Cloud_Index_exGoogle"], 2))
print("Google z-score at 2026 Q2: %.2f | AWS z: %.2f | Azure z: %.2f" %
      (b.loc[end_q, "Z_GoogleCloud"], b.loc[end_q, "Z_AWS"], b.loc[end_q, "Z_Azure"]))
gd = pd.DataFrame({
    "corr(Raw, exGoogle) full sample": [df["Cloud_Index_Raw"].corr(df["Cloud_Index_exGoogle"])],
    "corr(Raw, exGoogle) excl. last 3Q": [df.loc[~last3, "Cloud_Index_Raw"].corr(df.loc[~last3, "Cloud_Index_exGoogle"])],
    "corr(Raw, Google) full": [df["Cloud_Index_Raw"].corr(df["GoogleCloud_YoY"])],
    "corr(Raw, Google) excl. last 3Q": [df.loc[~last3, "Cloud_Index_Raw"].corr(df.loc[~last3, "GoogleCloud_YoY"])],
    "corr(DDOG, Raw) full": [df["DDOG_Revenue_YoY"].corr(df["Cloud_Index_Raw"])],
    "corr(DDOG, exGoogle) full": [df["DDOG_Revenue_YoY"].corr(df["Cloud_Index_exGoogle"])],
    "corr(DDOG, Raw) excl. last 3Q": [df.loc[~last3, "DDOG_Revenue_YoY"].corr(df.loc[~last3, "Cloud_Index_Raw"])],
    "corr(DDOG, exGoogle) excl. last 3Q": [df.loc[~last3, "DDOG_Revenue_YoY"].corr(df.loc[~last3, "Cloud_Index_exGoogle"])],
}).T.rename(columns={0: "value"})
print("\n=== STEP 3d: Google-Cloud distortion checks (lag 0) ==="); print(gd)
chg.to_csv(OUT_DIR + "table_google_contribution.csv"); gd.to_csv(OUT_DIR + "table_google_distortion_lag0.csv")

# =========================================================== STEP 4/5: LEAD-LAG
def ll_row(x_full, y_full, k, mask=None):
    """corr(x_(t-k), y_t) on the overlapping, non-missing observations. mask selects the DDOG quarter t."""
    xs = pd.Series(x_full).shift(k)
    d = pd.DataFrame({"x": xs, "y": y_full})
    if mask is not None: d = d[mask]
    d = d.dropna()
    n = len(d)
    if n < 4: return dict(k=k, n=n, pearson=np.nan, spearman=np.nan, p_naive=np.nan)
    r, p = stats.pearsonr(d.x, d.y); rho = stats.spearmanr(d.x, d.y)[0]
    # p_naive assumes independent observations: NOT valid here (series are highly autocorrelated). Reference only.
    return dict(k=k, n=n, pearson=r, spearman=rho, p_naive=p)

LAGS = [1, 2, 0, -1]
NAME = {1: "Lead 1Q: Cloud(t-1) vs DDOG(t)", 2: "Lead 2Q: Cloud(t-2) vs DDOG(t)",
        0: "Lag 0: Cloud(t) vs DDOG(t)", -1: "DIAGNOSTIC: Cloud(t+1) vs DDOG(t)  [cloud lags DDOG]"}
def table(series_name, y="DDOG_Revenue_YoY", **kw):
    rows = []
    for k in LAGS:
        r = ll_row(df[series_name], df[y], k, **kw); r["specification"] = NAME[k]; r["series"] = series_name; rows.append(r)
    return pd.DataFrame(rows)[["series", "specification", "k", "n", "pearson", "spearman", "p_naive"]]

ll_index = table("Cloud_Index_Raw")
print("\n=== STEP 4: lead-lag, Cloud_Index_Raw vs DDOG Revenue YoY (levels) ==="); print(ll_index.to_string(index=False))
ll_index.to_csv(OUT_DIR + "table_leadlag_index.csv", index=False)

ll_prov = pd.concat([table(s) for s in P], ignore_index=True)
print("\n=== STEP 5: lead-lag by provider (DIAGNOSTIC ONLY; not used to set weights) ==="); print(ll_prov.to_string(index=False))
ll_prov.to_csv(OUT_DIR + "table_leadlag_providers.csv", index=False)

# =========================================================== ROBUSTNESS (all diagnostic)
rob_rows = []
def add(label, dfi, **kw):
    for k in LAGS:
        r = ll_row(dfi["Cloud_Index_Raw"], dfi["DDOG_Revenue_YoY"], k, **kw); r["check"] = label; rob_rows.append(r)

# (a) Z-index instead of raw
for k in LAGS:
    r = ll_row(df["Cloud_Index_Z"], df["DDOG_Revenue_YoY"], k); r["check"] = "Cloud_Index_Z (levels)"; rob_rows.append(r)
# (b) ex-Google two-provider index
for k in LAGS:
    r = ll_row(df["Cloud_Index_exGoogle"], df["DDOG_Revenue_YoY"], k); r["check"] = "Index ex-Google (AWS+Azure)/2"; rob_rows.append(r)
# (c) subsamples defined on the DDOG quarter t; cloud lags may reach back into the data
q_idx = df["Quarter"].map(lambda s: int(s[:4]) * 4 + int(s[-1]))
add("Sub-sample t >= 2023 Q1 (drops 2022 hyper-growth decline)", df, mask=(q_idx >= 2023 * 4 + 1))
add("Sub-sample t <= 2025 Q3 (drops last 3Q incl. Google/AWS surge)", df, mask=(q_idx <= 2025 * 4 + 3))
add("Sub-sample 2023 Q1 <= t <= 2025 Q3 (both trimmed)", df, mask=((q_idx >= 2023 * 4 + 1) & (q_idx <= 2025 * 4 + 3)))
# (d) first differences of YoY (percentage-point change vs prior quarter): removes shared level/trend
dd = df.copy()
dd["DDOG_Revenue_YoY"] = df["DDOG_Revenue_YoY"].diff(); dd["Cloud_Index_Raw"] = df["Cloud_Index_Raw"].diff()
add("First differences of YoY (pp change)", dd)
rob = pd.DataFrame(rob_rows)
rob["specification"] = rob["k"].map(NAME)
rob = rob[["check", "specification", "k", "n", "pearson", "spearman", "p_naive"]]
print("\n=== ROBUSTNESS (diagnostic): Cloud_Index_Raw variants vs DDOG ==="); print(rob.to_string(index=False))
rob.to_csv(OUT_DIR + "table_leadlag_robustness.csv", index=False)

# (e) leave-one-out range for each lag
loo_rows = []
for k in LAGS:
    d = pd.DataFrame({"x": df["Cloud_Index_Raw"].shift(k), "y": df["DDOG_Revenue_YoY"], "q": df["Quarter"]}).dropna()
    vals = [(q, stats.pearsonr(d.x.drop(i), d.y.drop(i))[0]) for i, q in zip(d.index, d.q)]
    lo = min(vals, key=lambda t: t[1]); hi = max(vals, key=lambda t: t[1])
    loo_rows.append(dict(specification=NAME[k], full_r=stats.pearsonr(d.x, d.y)[0], loo_min=lo[1], dropped_for_min=lo[0],
                         loo_max=hi[1], dropped_for_max=hi[0]))
loo = pd.DataFrame(loo_rows)
print("\n=== Leave-one-observation-out Pearson range (Cloud_Index_Raw) ==="); print(loo.to_string(index=False))
loo.to_csv(OUT_DIR + "table_leaveoneout.csv", index=False)

# ---------- extended-lag SHAPE diagnostic (NOT part of the specified grid; NOT used to select anything)
ext = pd.DataFrame([dict(ll_row(df["Cloud_Index_Raw"], df["DDOG_Revenue_YoY"], k), spec=f"Cloud(t-{k})" if k > 0 else ("Cloud(t)" if k == 0 else f"Cloud(t+{-k})"))
                    for k in [-1, 0, 1, 2, 3, 4]])[["spec", "k", "n", "pearson", "spearman"]]
print("\n=== Extended-lag SHAPE diagnostic (does the correlation peak inside the tested window?) ==="); print(ext.to_string(index=False))
ext.to_csv(OUT_DIR + "table_extended_lag_shape.csv", index=False)

# ---------- AR(1) surrogate simulation: how often do two INDEPENDENT persistent series produce r this large?
def ar1_sim(phi, sd, n, size, rng):
    e = rng.normal(0, sd * np.sqrt(1 - phi ** 2), (size, n)); x = np.empty((size, n))
    x[:, 0] = rng.normal(0, sd, size)
    for t in range(1, n): x[:, t] = phi * x[:, t - 1] + e[:, t]
    return x
def sim_pvals(xs, ys, ks=(0, 1, 2), phi_x=None, phi_y=None, nsim=20000, seed=12345):
    rng = np.random.default_rng(seed); n = len(xs)
    phx = float(np.clip(pd.Series(xs).autocorr(1) if phi_x is None else phi_x, -0.99, 0.99))
    phy = float(np.clip(pd.Series(ys).autocorr(1) if phi_y is None else phi_y, -0.99, 0.99))
    X = ar1_sim(phx, np.std(xs, ddof=1), n, nsim, rng); Y = ar1_sim(phy, np.std(ys, ddof=1), n, nsim, rng)
    def corr_rows(A, B):
        A = A - A.mean(1, keepdims=True); B = B - B.mean(1, keepdims=True)
        return (A * B).sum(1) / np.sqrt((A ** 2).sum(1) * (B ** 2).sum(1))
    sim_r = {k: corr_rows(X[:, :n - k], Y[:, k:]) for k in ks}          # x_(t-k) vs y_t
    obs = {k: stats.pearsonr(pd.Series(xs).shift(k).dropna(), pd.Series(ys).iloc[k:])[0] for k in ks}
    rows = [dict(k=k, obs_r=obs[k], p_sim_two_sided=np.mean(np.abs(sim_r[k]) >= abs(obs[k]))) for k in ks]
    mx = np.max(np.abs(np.vstack([sim_r[k] for k in ks])), axis=0)
    rows.append(dict(k="max over k=0,1,2", obs_r=max(abs(v) for v in obs.values()), p_sim_two_sided=np.mean(mx >= max(abs(v) for v in obs.values()))))
    return pd.DataFrame(rows), phx, phy
xs, ys = df["Cloud_Index_Raw"].values, df["DDOG_Revenue_YoY"].values
simA, px, py_ = sim_pvals(xs, ys); simA.insert(0, "case", f"levels, AR(1) phi fitted (index {px:.2f}, DDOG {py_:.2f})")
simB, _, _ = sim_pvals(xs, ys, phi_x=0.85, phi_y=0.85); simB.insert(0, "case", "levels, stress phi = 0.85 both")
xd, yd = np.diff(xs), np.diff(ys)
simC, px2, py2 = sim_pvals(xd, yd); simC.insert(0, "case", f"first differences, phi fitted ({px2:.2f}, {py2:.2f})")
sim = pd.concat([simA, simB, simC], ignore_index=True)
print("\n=== AR(1) surrogate test: share of independent persistent pairs with |r| >= observed (20,000 sims each) ===")
print(sim.to_string(index=False)); sim.to_csv(OUT_DIR + "table_ar1_simulation.csv", index=False)

# =========================================================== STEP 6: CHARTS
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
x = np.arange(len(df)); ticks = df["Quarter"].str.replace(" ", "\n")

# Chart 1: levels, same axis (both series are YoY growth in %)
fig, ax = plt.subplots(figsize=(11, 5.2))
ax.plot(x, df["DDOG_Revenue_YoY"], "o-", color="#632CA6", lw=2, label="Datadog revenue YoY (%)")
ax.plot(x, df["Cloud_Index_Raw"], "s-", color="#E8710A", lw=2, label="Cloud_Index_Raw: mean of AWS/Azure/Google Cloud YoY (%)")
ax.set_xticks(x); ax.set_xticklabels(ticks, fontsize=8); ax.set_ylabel("YoY growth (%)")
ax.set_title("Chart 1: Datadog revenue YoY vs equal-weight hyperscaler cloud growth index (calendar quarters)")
ax.grid(axis="y", alpha=.3); ax.legend(frameon=False, loc="upper right")
fig.text(0.01, 0.01, "Same axis, same units. n = 18. Correlation of two persistent series; see tables before reading anything into co-movement.", fontsize=8, color="gray")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(OUT_DIR + "chart1_ddog_vs_cloud_index_raw.png", dpi=170); plt.close(fig)

# Chart 2: standardized
fig, ax = plt.subplots(figsize=(11, 5.2))
ax.axhline(0, color="gray", lw=.8)
ax.plot(x, df["DDOG_Z"], "o-", color="#632CA6", lw=2, label="DDOG revenue YoY, full-sample z-score")
ax.plot(x, df["Cloud_Index_Z"], "s-", color="#E8710A", lw=2, label="Cloud_Index_Z (mean of three provider z-scores)")
ax.set_xticks(x); ax.set_xticklabels(ticks, fontsize=8); ax.set_ylabel("z-score (full sample, sample std)")
ax.set_title("Chart 2: standardized Datadog revenue YoY vs Cloud_Index_Z")
ax.grid(axis="y", alpha=.3); ax.legend(frameon=False, loc="upper right")
fig.text(0.01, 0.01, "Cloud_Index_Z is an average of z-scores, so its own std is < 1 (as specified). Full-sample standardization uses future data: descriptive only.", fontsize=8, color="gray")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(OUT_DIR + "chart2_ddog_z_vs_cloud_index_z.png", dpi=170); plt.close(fig)

# Chart 3: best economically plausible LEADING spec (k=1 or 2 only; k=-1 and k=0 excluded by construction)
lead = ll_index[ll_index.k.isin([1, 2])].sort_values("pearson", ascending=False).iloc[0]
kbest = int(lead.k)
d3 = pd.DataFrame({"x": df["Cloud_Index_Raw"].shift(kbest), "y": df["DDOG_Revenue_YoY"], "q": df["Quarter"]}).dropna()
fig, ax = plt.subplots(figsize=(8.6, 7))
recent = d3.q.isin(["2025 Q4", "2026 Q1", "2026 Q2"])
early = d3.q.str.startswith("2022")
ax.scatter(d3.x[~recent & ~early], d3.y[~recent & ~early], s=55, color="#632CA6", label="2023 Q1 – 2025 Q3")
ax.scatter(d3.x[early], d3.y[early], s=55, color="#1a73e8", label="2022 (hyper-growth base effects)")
ax.scatter(d3.x[recent], d3.y[recent], s=70, color="#d93025", marker="D", label="DDOG quarters 2025 Q4 – 2026 Q2")
# greedy label placement: try several offsets, keep the first that does not overlap already-placed labels
fig.canvas.draw(); rend = fig.canvas.get_renderer(); placed = []
cands = [(6, 5), (6, -11), (-40, 5), (-40, -11), (6, 14), (6, -20), (-40, 14), (-40, -20), (-16, 18), (-16, -24)]
for _, r in d3.sort_values("x").iterrows():
    for off in cands:
        a = ax.annotate(r.q.replace(" ", ""), (r.x, r.y), textcoords="offset points", xytext=off, fontsize=8)
        bb = a.get_window_extent(rend).expanded(1.02, 1.05)
        if not any(bb.overlaps(p) for p in placed): placed.append(bb); break
        a.remove()
    else:
        a = ax.annotate(r.q.replace(" ", ""), (r.x, r.y), textcoords="offset points", xytext=cands[0], fontsize=8)
        placed.append(a.get_window_extent(rend))
sl, ic, rr, pp, _ = stats.linregress(d3.x, d3.y)
xx = np.linspace(d3.x.min(), d3.x.max(), 50); ax.plot(xx, ic + sl * xx, "--", color="gray", lw=1, label="OLS line (descriptive only)")
ax.set_xlabel(f"Cloud_Index_Raw at t-{kbest}  (%, quarter t-{kbest})"); ax.set_ylabel("DDOG revenue YoY at t (%)")
ax.set_title(f"Chart 3: Cloud_Index_Raw(t-{kbest}) vs DDOG revenue YoY(t)\nPearson r = {lead.pearson:.2f}, Spearman = {lead.spearman:.2f}, n = {int(lead.n)}  (labels = DDOG quarter t)")
ax.grid(alpha=.3); ax.legend(frameon=False, fontsize=8, loc="lower right")
fig.text(0.01, 0.01, f"Lead {kbest}Q chosen as the higher-correlation of the two economically plausible LEADING specs (in-sample, descriptive; not a selection for modelling).", fontsize=7.5, color="gray")
fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(OUT_DIR + "chart3_scatter_leading_index.png", dpi=170); plt.close(fig)
print(f"\nChart 3 uses lead k={kbest}; OLS slope={sl:.3f}, intercept={ic:.2f}, r={rr:.3f}")
print("Files written to", OUT_DIR)
