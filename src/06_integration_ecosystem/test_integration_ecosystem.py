"""
Tests for build_integration_ecosystem.py.  ALL DATA IS SYNTHETIC: a real (tiny) git repo built in a temp dir with
controlled commit dates. Not Datadog data.  Run: python test_integration_ecosystem.py
"""
import os, subprocess, tempfile
import numpy as np, pandas as pd
import build_integration_ecosystem as B


# ---------------------------------------------------------------- toy repo builder
# IMPORTANT: commits are created in STRICT CHRONOLOGICAL ORDER (matching how every real git history behaves - a
# child's committer-date is never earlier than an ancestor's). `commit_before()` walks the first-parent chain by
# date and its correctness depends on that being true, exactly as it would for the live DataDog repos.
def mk_repo(tmp):
    src = os.path.join(tmp, "src"); os.makedirs(src)
    def run(*a, date=None):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        if date: env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(["git", *a], cwd=src, env=env, check=True, capture_output=True)
    def put(path, txt):
        os.makedirs(os.path.dirname(os.path.join(src, path)), exist_ok=True); open(os.path.join(src, path), "w").write(txt)
    def rm(path): os.remove(os.path.join(src, path))
    run("init", "-b", "master")

    # 2021-02-01: "alpha" added - lives forever
    put("alpha/manifest.json", '{"v":1}'); run("add", "-A"); run("commit", "-m", "add alpha", date="2021-02-01T00:00:00+0000")
    # 2021-05-01: "beta" added - removed much later (2023), genuinely, no re-add
    put("beta/manifest.json", '{"v":1,"pad":"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}')
    run("add", "-A"); run("commit", "-m", "add beta", date="2021-05-01T00:00:00+0000")
    # 2021-06-01: a NESTED manifest.json (depth 3) that must be EXCLUDED everywhere
    put("tooling/tests/fixtures/manifest.json", "{}"); run("add", "-A"); run("commit", "-m", "nested fixture", date="2021-06-01T00:00:00+0000")
    # 2021-08-01 / 08-10 / 08-15: "gamma" added, deleted by mistake, re-added 5 days later -> FLICKER (one identity)
    put("gamma/manifest.json", '{"v":1,"pad":"yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"}')
    run("add", "-A"); run("commit", "-m", "add gamma", date="2021-08-01T00:00:00+0000")
    rm("gamma/manifest.json"); run("add", "-A"); run("commit", "-m", "oops remove gamma", date="2021-08-10T00:00:00+0000")
    put("gamma/manifest.json", '{"v":1,"pad":"yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"}')
    run("add", "-A"); run("commit", "-m", "re-add gamma (fix)", date="2021-08-15T00:00:00+0000")
    # 2021-11-01 / 11-05: "delta" added then removed (genuinely, not re-added until 2022-05, well past the flicker window)
    put("delta/manifest.json", '{"v":1,"pad":"zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"}')
    run("add", "-A"); run("commit", "-m", "add delta", date="2021-11-01T00:00:00+0000")
    rm("delta/manifest.json"); run("add", "-A"); run("commit", "-m", "remove delta", date="2021-11-05T00:00:00+0000")
    # 2022-01-01: content-only modify of alpha - must NOT affect its identity
    put("alpha/manifest.json", '{"v":2}'); run("add", "-A"); run("commit", "-m", "modify alpha", date="2022-01-01T00:00:00+0000")
    # 2022-02-01 / 03-01: "epsilon" added then RENAMED to "epsilon2" - must be ONE identity, original add date kept
    put("epsilon/manifest.json", '{"v":1,"pad":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}')
    run("add", "-A"); run("commit", "-m", "add epsilon", date="2022-02-01T00:00:00+0000")
    os.makedirs(os.path.join(src, "epsilon2"), exist_ok=True)
    os.rename(os.path.join(src, "epsilon/manifest.json"), os.path.join(src, "epsilon2/manifest.json")); os.rmdir(os.path.join(src, "epsilon"))
    run("add", "-A"); run("commit", "-m", "rename epsilon->epsilon2", date="2022-03-01T00:00:00+0000")
    # 2022-05-25: "delta" genuinely re-introduced (200+ days after its 2021-11-05 removal) -> a FRESH identity
    put("delta/manifest.json", '{"v":9,"pad":"wwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwwww"}')
    run("add", "-A"); run("commit", "-m", "re-introduce delta, much later", date="2022-05-25T00:00:00+0000")
    # 2023-02-01: "beta" genuinely removed for good
    rm("beta/manifest.json"); run("add", "-A"); run("commit", "-m", "remove beta", date="2023-02-01T00:00:00+0000")
    # 2023-08-15: bulk import of 6 integrations in ONE commit (bulk-addition QA check)
    for n in range(6):
        put(f"bulk{n}/manifest.json", f'{{"v":1,"n":{n}}}')
    run("add", "-A"); run("commit", "-m", "bulk import 6 integrations", date="2023-08-15T00:00:00+0000")
    return src


def build(tmp):
    src = mk_repo(tmp); branch = B.default_branch(src)
    return src, branch


# ---------------------------------------------------------------- tests
def test_default_branch_and_snapshot_excludes_nested():
    tmp = tempfile.mkdtemp(); src, branch = build(tmp)
    assert branch == "master"
    qs = ["2021 Q1", "2021 Q2", "2021 Q3", "2021 Q4", "2022 Q1", "2022 Q2", "2023 Q2", "2023 Q3"]
    dates = {q: d for q, d in zip(qs, ["2021-03-31", "2021-06-30", "2021-09-30", "2021-12-31", "2022-03-31", "2022-06-30", "2023-06-30", "2023-09-30"])}
    B.QEND_DATES.update(dates)
    snap = B.quarter_end_snapshot(src, branch, qs)
    s = snap.set_index("quarter").n_integrations
    assert s["2021 Q1"] == 1                     # alpha only
    assert s["2021 Q2"] == 2                     # alpha, beta (nested fixture excluded despite existing)
    assert s["2021 Q3"] == 3                     # alpha, beta, gamma (flicker resolved by quarter end)
    assert s["2021 Q4"] == 3                     # delta added then removed within the same quarter -> net zero at quarter-end
    assert s["2022 Q1"] == 4                     # alpha, beta, gamma, epsilon2 (renamed, still 1 integration; delta still removed)
    assert s["2022 Q2"] == 5                     # + delta re-introduced 2022-05-25
    assert s["2023 Q2"] == 4                     # beta removed 2023-02-01 -> alpha, gamma, epsilon2, delta
    assert s["2023 Q3"] == 10                    # + 6 bulk-imported

def test_rename_is_not_a_removal_plus_addition():
    tmp = tempfile.mkdtemp(); src, branch = build(tmp)
    audit = B.reconstruct_audit(src, branch, "toy")
    eps = audit[audit.integration_name.isin(["epsilon", "epsilon2"])]
    assert len(eps) == 1 and eps.iloc[0].integration_name == "epsilon2"           # current name, single identity
    assert eps.iloc[0].first_added_date == "2022-02-01"                            # ORIGINAL add date preserved, not the rename date
    assert eps.iloc[0].was_renamed and eps.iloc[0].rename_events == 1
    assert not eps.iloc[0].removed_later                                           # a rename must never show as a removal

def test_flicker_merge_collapses_correction_into_one_identity():
    tmp = tempfile.mkdtemp(); src, branch = build(tmp)
    audit = B.reconstruct_audit(src, branch, "toy")
    g = audit[audit.integration_name == "gamma"]
    assert len(g) == 1                                                            # ONE identity, not two
    assert g.iloc[0].first_added_date == "2021-08-01"                             # original date, not the 08-15 re-add
    assert not g.iloc[0].removed_later and g.iloc[0].flicker_merges_applied == 1

def test_genuine_removal_and_later_reintroduction_are_two_identities():
    tmp = tempfile.mkdtemp(); src, branch = build(tmp)
    audit = B.reconstruct_audit(src, branch, "toy")
    d = audit[audit.integration_name == "delta"].sort_values("first_added_date")
    assert len(d) == 2                                                            # beyond the flicker window -> NOT merged
    assert d.iloc[0].first_added_date == "2021-11-01" and d.iloc[0].removed_later and d.iloc[0].removal_date == "2021-11-05"
    assert d.iloc[1].first_added_date == "2022-05-25" and not d.iloc[1].removed_later

def test_nested_manifest_never_enters_the_audit():
    tmp = tempfile.mkdtemp(); src, branch = build(tmp)
    audit = B.reconstruct_audit(src, branch, "toy")
    assert not audit.integration_name.isin(["fixtures", "tests", "tooling"]).any()
    assert "manifest.json" not in "".join(audit.integration_name)                  # never picked up a nested path

def test_genuine_permanent_removal_recorded_correctly():
    tmp = tempfile.mkdtemp(); src, branch = build(tmp)
    audit = B.reconstruct_audit(src, branch, "toy")
    b = audit[audit.integration_name == "beta"]
    assert len(b) == 1 and b.iloc[0].removed_later and b.iloc[0].removal_date == "2023-02-01" and b.iloc[0].removal_quarter == "2023 Q1"

def test_bulk_commit_detected_by_qa():
    tmp = tempfile.mkdtemp(); src, branch = build(tmp)
    audit = B.reconstruct_audit(src, branch, "toy")
    bulk_commit_rows = audit.groupby("first_added_commit").size()
    assert (bulk_commit_rows >= 6).any()                                          # the 6-integration bulk-import commit is visible


# ---------------------------------------------------------------- end-to-end pipeline test (real toy repos, fake ddog csv)
def full_pipeline_setup(tmp):
    core_src = mk_repo(os.path.join(tmp, "core_build")); extras_src = mk_repo(os.path.join(tmp, "extras_build"))
    workdir = os.path.join(tmp, "gitprobe"); os.makedirs(workdir, exist_ok=True)
    import shutil
    for name, src in (("core", core_src), ("extras", extras_src)):
        subprocess.run(["git", "clone", "--bare", src, os.path.join(workdir, f"{name}.git")], check=True, capture_output=True)
    quarters22 = B.QUARTERS
    ddog = pd.DataFrame({"Quarter": [q for q in quarters22 if q >= "2022 Q1"],
                         "Revenue_YoY": np.linspace(20, 35, 18), "Customers_100k_YoY": np.linspace(10, 25, 18)})
    ddog_csv = os.path.join(tmp, "ddog.csv"); ddog.to_csv(ddog_csv, index=False)
    return workdir, ddog_csv

def test_end_to_end_pipeline_schema_and_qa():
    tmp = tempfile.mkdtemp(); workdir, ddog_csv = full_pipeline_setup(tmp); out_dir = os.path.join(tmp, "out")
    res = B.build_quarterly(workdir, ddog_csv, out_dir)
    m, master, qa = res["quarterly"], res["master"], res["qa"]
    assert list(m.quarter) == B.QUARTERS and len(m) == 22
    assert qa["all_22_quarters_present"] is True
    assert qa["net_additions_reconciliation_all_match"] is True, qa["net_additions_reconciliation_mismatches"]
    assert list(master.columns) == ["Quarter", "DDOG_Revenue_YoY", "Customers_100k_YoY", "Core_Integrations", "Extras_Integrations",
                                    "Total_Integrations", "Core_YoY_Growth", "Extras_YoY_Growth", "Total_YoY_Growth",
                                    "New_Core_Integrations", "New_Extras_Integrations", "New_Total_Integrations"]
    assert len(master) == 18 and master.Quarter.iloc[0] == "2022 Q1" and master.Quarter.iloc[-1] == "2026 Q2"
    for f in ("integration_additions_audit.csv", "integration_ecosystem_quarterly.csv", "qa_reconciliation.csv", "qa_report.json", "ddog_integration_master.csv"):
        assert os.path.exists(os.path.join(out_dir, f)), f
    aud = pd.read_csv(os.path.join(out_dir, "integration_additions_audit.csv"))
    assert list(aud.columns) == ["integration_name", "repository", "first_added_date", "first_added_quarter", "removed_later",
                                 "removal_date", "removal_quarter", "was_renamed", "rename_events", "flicker_merges_applied",
                                 "first_added_commit", "removal_commit"]
    assert (aud.repository.isin(["core", "extras"])).all()


# ---------------------------------------------------------------- lead-lag arithmetic tests
def test_leadlag_lag_convention_and_arithmetic_against_brute_force():
    q = B.QUARTERS
    # a NON-monotonic (oscillating) series: unlike a straight trend, shifting it changes the phase, so the fit at
    # the wrong lag is genuinely worse rather than "still perfect because everything is linear in everything".
    x = pd.Series(np.sin(np.arange(len(q)) * 1.3) + 0.05 * np.arange(len(q)), index=q)
    y = pd.Series(index=q, dtype=float)
    for i, qq in enumerate(q):
        y[qq] = 2 * x.iloc[i - 1] + 1 if i >= 1 else np.nan            # y(t) is an EXACT linear function of x(t-1)
    r0 = B.ll_row(x, y, 0); r1 = B.ll_row(x, y, 1); r2 = B.ll_row(x, y, 2)
    assert r1["pearson"] > 0.999 and r1["spearman"] > 0.999          # exact linear relation at the correct lag
    assert r1["n"] == 21                                              # one NaN dropped (first quarter has no y)
    assert abs(r0["pearson"]) < 0.99 and abs(r2["pearson"]) < 0.99    # markedly worse fit at the wrong lags
    # brute-force cross-check of r1 by hand
    xs = x.shift(1).dropna(); ys = y.reindex(xs.index)
    import numpy as _np
    expected = _np.corrcoef(xs.values, ys.values)[0, 1]
    assert abs(expected - r1["pearson"]) < 1e-9

def test_leave_one_out_reports_full_r_and_bounds():
    q = B.QUARTERS[:10]
    x = pd.Series(np.random.default_rng(1).normal(size=10), index=q)
    y = pd.Series(np.random.default_rng(2).normal(size=10), index=q)
    r = B.leave_one_out(x, y, 0)
    assert set(r.keys()) == {"full_r", "loo_min_r", "loo_min_dropped", "loo_max_r", "loo_max_dropped", "max_abs_shift"}
    assert r["loo_min_r"] <= r["full_r"] <= r["loo_max_r"] + 1e-9 or r["loo_min_r"] - 1e-9 <= r["full_r"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed (synthetic toy repos / synthetic data only).")
