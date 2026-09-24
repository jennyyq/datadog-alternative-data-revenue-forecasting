#!/usr/bin/env python3
"""
build_integration_ecosystem.py - Datadog Integration Ecosystem Expansion dataset, built from the git history of the two
public repos already validated in the feasibility screen: DataDog/integrations-core and DataDog/integrations-extras.

WHAT THIS IS: a product-breadth / ecosystem-expansion proxy (number of maintained integrations), NOT a customer-adoption
measure. Cumulative levels are non-stationary and mechanically trend upward; the flow (New_*) and YoY series are the
candidates carried into the lead-lag section.

An "integration" = a top-level directory containing a manifest.json file (depth exactly 2: "<name>/manifest.json"),
tracked with git's rename detection (-M) so a product rename (e.g. fluent_bit -> fluentbit) is NOT double-counted as a
removal plus a new addition, and with same-path delete-then-re-add "flicker" corrections within FLICKER_DAYS collapsed
into the original entry (see MERGE_FLICKER_DAYS below) so a same-week onboarding fix is not double-counted either.
Both choices are logged so every merge is auditable, not hidden.

Marketplace-tier integrations live in a private Datadog repo and are NOT reconstructible from public git history
(confirmed in the feasibility screen: git demands credentials). This script covers core + extras only.

Usage:
  python build_integration_ecosystem.py --out-dir ./out --ddog-csv ddog_calculated_dataset.csv --workdir ./gitprobe
"""
from __future__ import annotations
import argparse, collections, dataclasses, datetime as dt, json, os, re, subprocess
import numpy as np
import pandas as pd

REPOS = {"core": "https://github.com/DataDog/integrations-core.git", "extras": "https://github.com/DataDog/integrations-extras.git"}
RX_TOP_MANIFEST = re.compile(r"^[^/]+/manifest\.json$")           # depth-2 only: excludes nested test/tooling fixtures
MERGE_FLICKER_DAYS = 30    # a same-path delete immediately followed by a re-add within this many days is treated as one
                            # continuous entry (a same-week onboarding correction), not a removal + a fresh addition.
                            # Verified against real cases before choosing this value (see build notes / QA report):
                            # extras/avi_vantage was deleted and re-added 1 day apart in Aug 2021 (a correction);
                            # core's rename-chain oddities are all pre-2021 and unaffected by this threshold.
RENAME_MIN_SIMILARITY = 0   # git's own -M threshold (default ~50%) already gates what counts as R; every rename inside
                            # the 2021-2026 output window was manually reviewed (see QA report) and is a same-product
                            # name change. Pre-2021 renames were not scrutinised further since they don't affect output.

QSTART, QEND = "2021Q1", "2026Q2"
QUARTERS = [f"{p.year} Q{p.quarter}" for p in pd.period_range(QSTART, QEND, freq="Q")]                 # 22, the required output window
QUARTERS_WITH_ANCHOR = ["2020 Q4"] + QUARTERS                                                            # +1 prior quarter, needed ONLY to
                                                                                                          # compute Net_Additions for 2021 Q1
QEND_DATES = {f"{p.year} Q{p.quarter}": p.end_time.date().isoformat() for p in pd.period_range("2020Q4", QEND, freq="Q")}


# =================================================================================== git plumbing
def git(*a, cwd=None, inp=None, check=True):
    r = subprocess.run(["git", *a], cwd=cwd, input=inp, capture_output=True, timeout=900)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a)} (cwd={cwd}) -> {r.stderr.decode(errors='replace')[:400]}")
    return r.stdout

def ensure_clone(url, dest, blobless=True):
    """Bare clone. Blobless keeps every commit and tree (all quarter-end counts need) without file contents: seconds, tens of MB."""
    if not os.path.isdir(dest):
        git("clone", "--bare", "--no-tags", *(["--filter=blob:none"] if blobless else []), url, dest)
    else:
        git("fetch", "--prune", cwd=dest)                    # keep an existing clone current rather than re-cloning
    return dest

def default_branch(repo):
    ref = git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=repo, check=False).decode().strip()
    if ref: return ref.rsplit("/", 1)[-1]
    for cand in ("master", "main"):
        if git("rev-parse", "--verify", "--quiet", cand, cwd=repo, check=False).strip(): return cand
    raise RuntimeError(f"cannot determine default branch for {repo}")

def commit_before(repo, branch, day):
    """Last first-parent commit on/before the end of `day` (UTC). First-parent = mainline history: dates stay monotonic."""
    return git("rev-list", "-1", "--first-parent", f"--before={day} 23:59:59 +0000", branch, cwd=repo).decode().strip() or None

def manifests_at(repo, commit):
    if not commit: return []
    return [l.split("\t", 1)[1] for l in git("ls-tree", "-r", commit, cwd=repo).decode().splitlines()
            if "\t" in l and RX_TOP_MANIFEST.match(l.split("\t", 1)[1])]

def quarter_end_snapshot(repo, branch, quarters=QUARTERS_WITH_ANCHOR):
    rows = []
    for label in quarters:
        c = commit_before(repo, branch, QEND_DATES[label])
        paths = manifests_at(repo, c)
        rows.append(dict(quarter=label, quarter_end=QEND_DATES[label], commit=(c or "")[:9], n_integrations=(len(paths) if c else None),
                         n_unique_integrations=(len(set(paths)) if c else None)))
    return pd.DataFrame(rows)


# =================================================================================== rename-aware, flicker-merged audit reconstruction
@dataclasses.dataclass
class Ident:
    id: int; repo: str; first_path: str; first_date: str; first_commit: str
    cur_path: str; removed: bool = False; removed_date: str | None = None; removed_commit: str | None = None
    renamed: bool = False; rename_events: int = 0; flicker_merges: int = 0

def parse_namestatus(raw: bytes):
    """Yields (commit_sha, commit_date, [(status, path, new_path_or_None), ...]) in file order, oldest first."""
    lines = raw.decode(errors="replace").splitlines()
    i, cur = 0, None
    while i < len(lines):
        line = lines[i]
        if line.startswith("COMMIT|"):
            if cur: yield cur
            _, sha, date = line.split("|"); cur = (sha, date, [])
        elif line.strip():
            parts = line.split("\t")
            status = parts[0]
            if status.startswith("R") or status.startswith("C"): cur[2].append((status[0], parts[1], parts[2]))
            else: cur[2].append((status[0], parts[1], None))
        i += 1
    if cur: yield cur

def qlabel(date_str: str) -> str:
    p = pd.Period(pd.Timestamp(date_str), freq="Q"); return f"{p.year} Q{p.quarter}"

def reconstruct_audit(repo, branch, reponame, flicker_days=MERGE_FLICKER_DAYS):
    """Rename-aware, flicker-merged reconstruction of every integration's first-added / removed date from full mainline
    history (not limited to the output window - the audit trail is meant to cover everything the repo has ever held).

    Algorithm (single chronological pass over first-parent history, -M rename detection on):
      A path            -> if `path` has a pending removal still inside the flicker window, REOPEN that identity
                            (same first_added_date; this is a same-week correction, not a new integration); else
                            open a brand-new identity.
      D path             -> move the active identity for `path` into a pending-removal holding area, stamped with
                            the removal date, instead of closing it immediately.
      R oldpath newpath  -> the SAME identity continues under `newpath` with its ORIGINAL first_added_date
                            (a product rename is not a removal + a new addition).
      M path             -> content change only; identity untouched.
    A pending removal is finalised (removed_later=True) once `flicker_days` have elapsed with no re-add on that path,
    or once processing reaches the end of history."""
    raw = git("log", "--first-parent", "-M", "--format=COMMIT|%H|%cs", "--name-status", "--reverse", "--",
              ":(glob)*/manifest.json", cwd=repo)
    active: dict[str, Ident] = {}                            # current path -> live identity
    pending: dict[str, tuple[Ident, str]] = {}                # path -> (identity, removal_date), awaiting the flicker window
    closed: list[Ident] = []
    next_id = [0]
    def new_ident(path, date, sha):
        next_id[0] += 1
        return Ident(id=next_id[0], repo=reponame, first_path=path, first_date=date, first_commit=sha, cur_path=path)
    def finalize(path):
        ident, rdate = pending.pop(path); ident.removed, ident.removed_date = True, rdate
        closed.append(ident)

    for sha, date, events in parse_namestatus(raw):
        for p in [p for p, (ident, rdate) in pending.items() if (pd.Timestamp(date) - pd.Timestamp(rdate)).days > flicker_days]:
            finalize(p)                                                               # flush anything now past the flicker window
        for status, path, newpath in events:
            if status == "A":
                if path in pending:                                                   # re-add within the flicker window -> same identity
                    ident, _ = pending.pop(path); ident.flicker_merges += 1; active[path] = ident
                else:
                    active[path] = new_ident(path, date, sha)
            elif status == "D":
                ident = active.pop(path, None)
                if ident is None: continue                                            # defensive: delete of a path we never saw added
                ident.removed_commit = sha; pending[path] = (ident, date)
            elif status in ("R", "C"):
                ident = active.pop(path, None)
                if ident is None:                                                     # rename source predates our log window -> treat dest as new
                    active[newpath] = new_ident(newpath, date, sha); continue
                ident.cur_path = newpath; ident.renamed = True; ident.rename_events += 1; active[newpath] = ident
            # "M" (content modify): no identity change

    for p in list(pending): finalize(p)                                               # anything still pending at HEAD: never re-added -> removed

    rows = []
    for ident in list(active.values()) + closed:
        rows.append(dict(integration_name=ident.cur_path.split("/")[0], repository=ident.repo, first_added_date=ident.first_date,
                         first_added_quarter=qlabel(ident.first_date), first_added_commit=ident.first_commit[:9],
                         removed_later=ident.removed, removal_date=ident.removed_date,
                         removal_quarter=(qlabel(ident.removed_date) if ident.removed_date else None),
                         removal_commit=(ident.removed_commit[:9] if ident.removed_commit else None),
                         was_renamed=ident.renamed, rename_events=ident.rename_events, flicker_merges_applied=ident.flicker_merges))
    return pd.DataFrame(rows).sort_values("first_added_date").reset_index(drop=True)


# =================================================================================== quarterly assembly
def flow_counts(audit: pd.DataFrame, reponame: str, quarters=QUARTERS) -> pd.DataFrame:
    a = audit[audit.repository == reponame]
    new = a.groupby("first_added_quarter").size().reindex(quarters, fill_value=0)
    rem = a[a.removed_later].groupby("removal_quarter").size().reindex(quarters, fill_value=0)
    return pd.DataFrame({"quarter": quarters, f"New_{reponame}": new.values, f"Removed_{reponame}": rem.values})

def build_quarterly(workdir, ddog_csv, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    snaps, audits, branches, repo_paths = {}, {}, {}, {}
    for name, url in REPOS.items():
        repo = ensure_clone(url, os.path.join(workdir, f"{name}.git")); branch = default_branch(repo)
        repo_paths[name], branches[name] = repo, branch
        snaps[name] = quarter_end_snapshot(repo, branch)
        audits[name] = reconstruct_audit(repo, branch, name)

    audit_all = pd.concat(audits.values(), ignore_index=True)
    audit_out = audit_all[["integration_name", "repository", "first_added_date", "first_added_quarter",
                           "removed_later", "removal_date", "removal_quarter", "was_renamed", "rename_events",
                           "flicker_merges_applied", "first_added_commit", "removal_commit"]].sort_values(
        ["repository", "first_added_date"])
    audit_out.to_csv(os.path.join(out_dir, "integration_additions_audit.csv"), index=False)

    m = pd.DataFrame({"quarter": QUARTERS_WITH_ANCHOR})
    for name in REPOS:
        s = snaps[name].set_index("quarter")["n_integrations"]
        m[f"{name.capitalize()}_Integrations"] = m.quarter.map(s)
    m["Total_Integrations"] = m.Core_Integrations + m.Extras_Integrations
    for col in ("Core_Integrations", "Extras_Integrations", "Total_Integrations"):
        m[col.replace("Integrations", "Net_Additions")] = m[col].diff()

    m = m[m.quarter != "2020 Q4"].reset_index(drop=True)                     # drop the anchor row: not part of the requested output
    for name in REPOS:
        col = f"{name.capitalize()}_Integrations"
        m[f"{name.capitalize()}_YoY_Growth"] = (m[col] / m[col].shift(4) - 1) * 100
    m["Total_YoY_Growth"] = (m.Total_Integrations / m.Total_Integrations.shift(4) - 1) * 100

    for name in REPOS:
        f = flow_counts(audit_all, name)
        m = m.merge(f.rename(columns={f"New_{name}": f"New_{name.capitalize()}_Integrations",
                                      f"Removed_{name}": f"Removed_{name.capitalize()}_Integrations"}), on="quarter", how="left")
    m["New_Total_Integrations"] = m.New_Core_Integrations + m.New_Extras_Integrations
    m["Removed_Total_Integrations"] = m.Removed_Core_Integrations + m.Removed_Extras_Integrations
    m.to_csv(os.path.join(out_dir, "integration_ecosystem_quarterly.csv"), index=False)

    qa = run_qa(m, snaps, audit_all, out_dir)

    ddog = pd.read_csv(ddog_csv)
    keep = ["Quarter", "Revenue_YoY", "Customers_100k_YoY"]
    dd = ddog[keep].rename(columns={"Revenue_YoY": "DDOG_Revenue_YoY", "Customers_100k_YoY": "Customers_100k_YoY"})
    master = dd.merge(m[["quarter", "Core_Integrations", "Extras_Integrations", "Total_Integrations",
                         "Core_YoY_Growth", "Extras_YoY_Growth", "Total_YoY_Growth",
                         "New_Core_Integrations", "New_Extras_Integrations", "New_Total_Integrations"]],
                      left_on="Quarter", right_on="quarter", how="inner").drop(columns="quarter")
    for c in master.columns:
        if c != "Quarter": master[c] = master[c].round(3) if master[c].dtype != "int64" else master[c]
    master.to_csv(os.path.join(out_dir, "ddog_integration_master.csv"), index=False)
    return dict(quarterly=m, audit=audit_all, qa=qa, master=master, ddog_rows=len(ddog), master_rows=len(master))


# =================================================================================== QA
def run_qa(m: pd.DataFrame, snaps: dict, audit_all: pd.DataFrame, out_dir: str) -> dict:
    out = {}
    out["all_22_quarters_present"] = (list(m.quarter) == QUARTERS)
    dup = {}
    for name, snap in snaps.items():
        for _, row in snap.iterrows():
            if row.quarter == "2020 Q4" or pd.isna(row.n_integrations): continue
            if row.n_integrations != row.n_unique_integrations:
                dup.setdefault(name, []).append(row.quarter)
    out["duplicate_integrations_at_any_quarter_end"] = dup

    recon_rows = []
    for name in REPOS:
        cap = name.capitalize()
        for _, r in m.iterrows():
            net = r[f"{cap}_Net_Additions"]; new = r[f"New_{cap}_Integrations"]; rem = r[f"Removed_{cap}_Integrations"]
            if pd.isna(net): continue
            recon_rows.append(dict(repository=name, quarter=r.quarter, net_additions_from_counts=int(net),
                                   new_minus_removed_from_audit=int(new - rem), match=(int(net) == int(new - rem))))
    recon = pd.DataFrame(recon_rows); out["net_additions_reconciliation_all_match"] = bool(recon.match.all())
    out["net_additions_reconciliation_mismatches"] = recon[~recon.match].to_dict("records")
    recon.to_csv(os.path.join(out_dir, "qa_reconciliation.csv"), index=False)

    inc = m.loc[m.Total_Net_Additions.notna(), ["quarter", "Core_Net_Additions", "Extras_Net_Additions", "Total_Net_Additions"]]
    largest = inc.loc[inc.Total_Net_Additions.idxmax()]
    out["largest_quarterly_total_increase"] = dict(quarter=largest.quarter, total_net_additions=int(largest.Total_Net_Additions))

    bulk = audit_all.groupby(["repository", "first_added_commit", "first_added_quarter"]).size().reset_index(name="n")
    bulk = bulk[bulk.n >= 5].sort_values("n", ascending=False)                       # >=5 integrations added in ONE commit
    out["bulk_addition_commits_ge5"] = bulk.to_dict("records")
    q_new_total = m[["quarter", "New_Total_Integrations"]].set_index("quarter")["New_Total_Integrations"]
    flagged = []
    for _, row in bulk.iterrows():
        share = row.n / max(q_new_total.get(row.first_added_quarter, np.nan), 1)
        if share >= 0.4: flagged.append(dict(**row.to_dict(), share_of_that_quarters_New_Total=round(float(share), 2)))
    out["bulk_commits_dominating_a_quarter_(>=40pct_of_that_quarters_New_Total)"] = flagged

    json.dump(out, open(os.path.join(out_dir, "qa_report.json"), "w"), indent=2, default=str)
    return out


# =================================================================================== lead-lag diagnostics (X leads Y by k quarters: X_(t-k) vs Y_t)
from scipy import stats

LAGS = [0, 1, 2]
LAG_NAME = {0: "X(t) vs Y(t) contemporaneous", 1: "X(t-1) vs Y(t): X leads by 1Q", 2: "X(t-2) vs Y(t): X leads by 2Q"}

def ll_row(x: pd.Series, y: pd.Series, k: int):
    d = pd.DataFrame({"x": x.shift(k), "y": y}).dropna()
    n = len(d)
    if n < 4: return dict(k=k, n=n, pearson=np.nan, spearman=np.nan)
    return dict(k=k, n=n, pearson=float(stats.pearsonr(d.x, d.y)[0]), spearman=float(stats.spearmanr(d.x, d.y)[0]))

def leadlag_table(master: pd.DataFrame, x_cols, y_cols=("DDOG_Revenue_YoY", "Customers_100k_YoY")):
    rows = []
    for xc in x_cols:
        for yc in y_cols:
            for k in LAGS:
                r = ll_row(master[xc], master[yc], k); r.update(X=xc, Y=yc, spec=LAG_NAME[k]); rows.append(r)
    return pd.DataFrame(rows)[["X", "Y", "k", "spec", "n", "pearson", "spearman"]]

def leave_one_out(x: pd.Series, y: pd.Series, k: int):
    d = pd.DataFrame({"x": x.shift(k), "y": y, "q": x.index}).dropna()
    full = stats.pearsonr(d.x, d.y)[0]
    rows = [(q, stats.pearsonr(d.x.drop(i), d.y.drop(i))[0]) for i, q in zip(d.index, d.q)]
    lo = min(rows, key=lambda t: t[1]); hi = max(rows, key=lambda t: t[1])
    return dict(full_r=full, loo_min_r=lo[1], loo_min_dropped=lo[0], loo_max_r=hi[1], loo_max_dropped=hi[0],
               max_abs_shift=max(abs(full - lo[1]), abs(full - hi[1])))


# =================================================================================== charts (matplotlib, saved as PNG)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def chart_timeseries(master, x_col, y_col, path, title):
    fig, ax1 = plt.subplots(figsize=(11, 5))
    x = np.arange(len(master)); ticks = master.Quarter.str.replace(" ", "\n")
    ax1.bar(x, master[x_col], color="#E8710A", alpha=.75, label=x_col)
    ax1.set_ylabel(x_col, color="#E8710A"); ax1.set_xticks(x); ax1.set_xticklabels(ticks, fontsize=8)
    ax2 = ax1.twinx(); ax2.plot(x, master[y_col], "o-", color="#632CA6", lw=2, label=y_col)
    ax2.set_ylabel(y_col, color="#632CA6")
    ax1.set_title(title); fig.tight_layout(); fig.savefig(path, dpi=170); plt.close(fig)

def chart_scatter(master, x_col, y_col, k, path, title, highlight_years=None):
    d = pd.DataFrame({"x": master[x_col].shift(k), "y": master[y_col], "q": master.Quarter}).dropna()
    fig, ax = plt.subplots(figsize=(8, 7.2))
    if highlight_years:
        hi = d.q.str[:4].isin(highlight_years)
        ax.scatter(d.x[~hi], d.y[~hi], s=60, color="#632CA6", label="other quarters")
        ax.scatter(d.x[hi], d.y[hi], s=70, color="#d93025", marker="D", label=f"{'/'.join(highlight_years)} quarters")
    else:
        ax.scatter(d.x, d.y, s=60, color="#632CA6")
    for _, r in d.iterrows(): ax.annotate(r.q.replace(" ", ""), (r.x, r.y), textcoords="offset points", xytext=(5, 4), fontsize=8)
    if len(d) >= 3:
        sl, ic, r, p, _ = stats.linregress(d.x, d.y); xx = np.linspace(d.x.min(), d.x.max(), 40)
        ax.plot(xx, ic + sl * xx, "--", color="gray", lw=1, label=f"OLS (descriptive), r={r:.2f}")
    ax.set_xlabel(f"{x_col} at t-{k}" if k else f"{x_col} at t"); ax.set_ylabel(f"{y_col} at t")
    ax.set_title(title, fontsize=11, wrap=True); ax.grid(alpha=.3); ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout(rect=(0, 0, 1, 0.94)); fig.savefig(path, dpi=170); plt.close(fig)


# =================================================================================== CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="./out"); ap.add_argument("--workdir", default="./gitprobe")
    ap.add_argument("--ddog-csv", default="ddog_calculated_dataset.csv")
    a = ap.parse_args(argv); os.makedirs(a.out_dir, exist_ok=True)

    res = build_quarterly(a.workdir, a.ddog_csv, a.out_dir)
    m, master, qa = res["quarterly"], res["master"], res["qa"]
    print("Quarterly ecosystem rows:", len(m), "| master rows:", len(master))
    print("QA: all 22 quarters present:", qa["all_22_quarters_present"])
    print("QA: reconciliation all match:", qa["net_additions_reconciliation_all_match"])
    print("QA: largest quarterly increase:", qa["largest_quarterly_total_increase"])
    print("QA: bulk commits (>=5 integrations in one commit):", len(qa["bulk_addition_commits_ge5"]))
    print("QA: bulk commits dominating a quarter (>=40% of New_Total):", qa["bulk_commits_dominating_a_quarter_(>=40pct_of_that_quarters_New_Total)"])

    x_cols = ["New_Total_Integrations", "New_Core_Integrations", "New_Extras_Integrations", "Total_YoY_Growth"]
    ll = leadlag_table(master, x_cols)
    ll.to_csv(os.path.join(a.out_dir, "leadlag_table.csv"), index=False)
    print("\n", ll.to_string(index=False))

    best = ll.loc[ll.groupby(["X", "Y"]).pearson.apply(lambda s: s.abs().idxmax())]
    loo_rows = []
    for _, r in best.iterrows():
        lo = leave_one_out(master[r.X], master[r.Y], int(r.k)); lo.update(X=r.X, Y=r.Y, k=int(r.k)); loo_rows.append(lo)
    loo = pd.DataFrame(loo_rows); loo.to_csv(os.path.join(a.out_dir, "leadlag_leaveoneout.csv"), index=False)
    print("\nLeave-one-out on each X-Y pair's best-|r| lag:\n", loo.to_string(index=False))

    chart_timeseries(master, "New_Total_Integrations", "DDOG_Revenue_YoY", os.path.join(a.out_dir, "chart1_new_integrations_vs_ddog_revenue.png"),
                     "New_Total_Integrations (bars) vs DDOG Revenue YoY (line)")
    chart_timeseries(master, "New_Total_Integrations", "Customers_100k_YoY", os.path.join(a.out_dir, "chart2_new_integrations_vs_customers.png"),
                     "New_Total_Integrations (bars) vs $100k+ Customers YoY (line)")
    top = best.reindex(best.pearson.abs().sort_values(ascending=False).index).iloc[0]
    chart_scatter(master, top.X, top.Y, int(top.k), os.path.join(a.out_dir, "chart3_scatter_best_leadlag.png"),
                 f"{top.X}(t-{int(top.k)}) vs {top.Y}(t)\nhighest |Pearson r| among the tested candidates - see robustness before reading anything into it",
                 highlight_years=["2022"])
    return res

if __name__ == "__main__":
    main()
