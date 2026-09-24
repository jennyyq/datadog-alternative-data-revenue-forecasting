"""
Tests for feasibility_screen.py.  ALL DATA HERE IS SYNTHETIC (mocks / a toy git repo in a temp dir). Not Datadog / Google / HN data.
Run: python test_feasibility_screen.py
"""
import os, subprocess, tempfile
import numpy as np, pandas as pd
import feasibility_screen as F

# ---------------------------------------------------------------- A: mock Google Trends (mimics: monthly when span > 5.25y, else weekly; each request rescaled to its own peak=100; random sampling noise)
class FakeTR:
    def __init__(self, seed=0, ambiguous=False): self.rng = np.random.default_rng(seed); self.ambiguous = ambiguous
    def suggestions(self, kw):
        s = [{"mid": "/g/xyz", "title": "Datadog", "type": "Software"}]
        return s + ([{"mid": "/m/abc", "title": "Datadog", "type": "Company"}] if self.ambiguous else [])
    def build_payload(self, kw_list, cat=0, timeframe="", geo="", gprop=""): self.kw, self.tf = kw_list[0], timeframe
    def interest_over_time(self):
        a, b = [pd.Timestamp(x) for x in self.tf.split()]
        idx = pd.date_range(a, b, freq="MS") if (b - a).days / 365.25 > 5.25 else pd.date_range(a, b, freq="W-SUN")
        days = (idx - pd.Timestamp("2021-01-01")).days.values
        base = 40 + 25 * days / 2000 + 5 * np.sin(days / 90)
        noisy = base * (1 + 0.03 * self.rng.standard_normal(len(idx)))
        return pd.DataFrame({self.kw: np.round(100 * noisy / noisy.max()), "isPartial": False}, index=idx)

def test_trends_probe_full_range_single_request_and_stitching():
    r = F.probe_google_trends(tr=FakeTR(), repeats=3, pause=0)
    assert r["status"] == "TESTED" and r["topic_mid_unambiguous"] == "/g/xyz"
    t = r["single_request_full_range"]["topic:Datadog"]
    assert t["n_points"] == 66 and 28 <= t["median_days_between_points"] <= 31           # monthly, 2021-01..2026-06 in ONE request
    assert t["quarters_complete"] == 22 and t["yoy_defined_2022Q1_2026Q2"] == 18
    assert t["max_repeat_spread"] > 0 and t["min_pairwise_corr"] > 0.9                    # sampling noise is measured, and small here
    s = r["weekly_stitching_test_term_Datadog"]; assert s["n_overlap"] > 100 and s["ratio_cv"] < 0.2

def test_trends_ambiguous_topic_is_never_guessed():
    r = F.probe_google_trends(tr=FakeTR(ambiguous=True), repeats=2, pause=0, weekly_check=False)
    assert r["topic_mid_unambiguous"] is None and "no unambiguous" in r["single_request_full_range"]["topic:Datadog"]["note"]

def test_trends_blocked_network_is_reported_not_hidden():
    class Blocked:
        def suggestions(self, kw): raise RuntimeError("HTTP 403: Host not in allowlist: trends.google.com")
    r = F.probe_google_trends(tr=Blocked()); assert r["status"] == "NOT_TESTABLE_HERE"

# ---------------------------------------------------------------- B: mock HN / Algolia
def fake_get(url, params=None):
    if url.endswith("/search_by_date"):
        return {"nbPages": 1, "hits": [{"objectID": "1", "created_at": "2021-01-04T15:00:00Z", "title": "Ask HN: Who is hiring? (January 2021)"},
                                       {"objectID": "2", "created_at": "2021-01-04T15:01:00Z", "title": "Ask HN: Who wants to be hired? (January 2021)"}]}
    if url.endswith("/items/1"):
        return {"children": [
            {"text": "Acme | Backend | Remote<p>Stack: Python, Datadog APM, k8s. We care about observability."},
            {"text": "Datadog | Senior Engineer | NYC<p>Join us building monitoring"},                # Datadog's own post -> excluded
            {"text": "Foo | Dev<p>We use Sentry"},
            {"text": None},                                                                        # deleted
            {"text": "Bar | SRE<p>Datadog and Grafana on-call"}]}
    raise AssertionError(url)

def test_hn_thread_counts_and_employer_exclusion():
    r = F.probe_hn_jobs(get=fake_get)
    assert r["status"] == "TESTED" and r["threads_found"] == 1 and r["threads_expected"] == 66            # 'Who wants to be hired' correctly ignored
    row = r["thread_sample"][0]
    assert (row["n_posts"], row["n_deleted"], row["dd_own_posts_excluded"], row["dd_mentions_third_party"], row["dd_apm"], row["dd_and_observability"]) == (4, 1, 1, 2, 1, 1)
    assert abs(row["dd_share_of_posts"] - 0.5) < 1e-9

# ---------------------------------------------------------------- C: real git logic on a toy repo with controlled dates
def mk_repo(tmp):
    src = os.path.join(tmp, "src"); os.makedirs(src)
    def run(*a, date=None):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        if date: env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(["git", *a], cwd=src, env=env, check=True, capture_output=True)
    def put(path, txt):
        os.makedirs(os.path.dirname(os.path.join(src, path)), exist_ok=True); open(os.path.join(src, path), "w").write(txt)
    run("init", "-b", "main")
    put("a/manifest.json", '{"manifest_version":"1.0.0","categories":["cloud"]}'); run("add", "-A"); run("commit", "-m", "add a", date="2021-02-10T12:00:00+0000")
    put("b/manifest.json", '{"manifest_version":"2.0.0","tile":{"classifier_tags":["Category::Cloud"]}}'); put("c/d/manifest.json", "{}")   # nested one must NOT count
    run("add", "-A"); run("commit", "-m", "add b and nested", date="2021-04-15T12:00:00+0000")
    run("rm", "a/manifest.json"); run("commit", "-m", "remove a", date="2021-08-01T12:00:00+0000")
    return src

def test_git_quarter_end_counts_removals_nested_exclusion_and_schema():
    tmp = tempfile.mkdtemp(); src = mk_repo(tmp)
    qs = [("pre", "2020-12-31"), ("2021 Q1", "2021-03-31"), ("2021 Q2", "2021-06-30"), ("2021 Q3", "2021-09-30")]
    r = F.probe_integrations(os.path.join(tmp, "w"), repos={"toy": src}, blobless=False, quarters=qs)
    assert r["status"] == "TESTED"; qc = r["repos"]["toy"]["quarter_counts"].set_index("quarter").n_integrations
    assert pd.isna(qc["pre"]) and qc["2021 Q1"] == 1 and qc["2021 Q2"] == 2 and qc["2021 Q3"] == 1          # removal reduces the point-in-time count; nested manifest ignored
    s = r["repos"]["toy"]["history_stats"]; assert s == dict(total_additions=2, total_removals=1, largest_single_commit_addition=1)
    repo = os.path.join(tmp, "w", "toy.git"); sh = F.schema_share(repo, F.commit_before(repo, "2021-06-30"))
    assert sh == dict(sampled=2, legacy_categories=1, classifier_tags=1)                                       # schema break is detected

def test_scorecard_totals():
    t = F.scorecard().set_index("candidate").total_of_30
    assert t["A Google Trends"] == 22 and t["B Job postings (HN-only variant)"] == 21 and t["C Integration ecosystem (public repos)"] == 24

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed (synthetic data only).")
