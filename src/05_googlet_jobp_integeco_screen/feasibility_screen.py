#!/usr/bin/env python3
"""
feasibility_screen.py - rapid feasibility screen of three candidate public signals for Datadog (DDOG), window 2021-01 .. 2026-06.

  A  Google Trends search demand      probe_google_trends()   needs trends.google.com + `pip install pytrends` (unofficial wrapper)
  B  Historical job postings          probe_hn_jobs()         Hacker News "Ask HN: Who is hiring?" via the free Algolia HN API
                                                              (the only free, legal, reproducible keyword-level historical job source identified;
                                                               a broad market source does not exist - see scorecard)
  C  Integration / partner ecosystem  probe_integrations()    git history of DataDog/integrations-core and integrations-extras (blobless clone)

Each probe returns a plain dict. A probe that cannot reach its source reports NOT_TESTABLE_HERE with the reason - it never guesses.
NOTHING here computes correlations or regressions against DDOG.

Usage:
  python feasibility_screen.py --run C                  # fully offline-capable except for github.com (needs git + internet)
  python feasibility_screen.py --run A,B,C --out-dir out   # A and B need internet access to Google / Algolia
"""
from __future__ import annotations
import argparse, collections, datetime as dt, html as htmllib, json, math, os, re, shutil, subprocess, sys, tempfile, time
import numpy as np
import pandas as pd
import requests

UA = "ddog-alt-data-feasibility/1.0"
START, END = "2021-01-01", "2026-06-30"
QUARTERS = [(f"{p.year} Q{p.quarter}", p.end_time.date().isoformat()) for p in pd.period_range("2021Q1", "2026Q2", freq="Q")]   # 22 quarter-ends


# ================================================================================ shared helpers
def reach(url, timeout=20):
    """Classify a host as REACHABLE / BLOCKED_BY_NETWORK_ALLOWLIST / UNREACHABLE without downloading the body."""
    try:
        r = requests.get(url, timeout=timeout, stream=True, headers={"User-Agent": UA}); deny = r.headers.get("x-deny-reason"); code = r.status_code; r.close()
    except requests.RequestException as e:
        return dict(status="UNREACHABLE", detail=type(e).__name__)
    return dict(status="BLOCKED_BY_NETWORK_ALLOWLIST", detail=deny) if deny else dict(status="REACHABLE", http=code)

def is_network_block(exc) -> bool:
    s = str(exc).lower(); return "host_not_allowed" in s or "not in allowlist" in s or "connection" in s and "refused" in s


# ================================================================================ A. Google Trends
TERMS = ["Datadog", "Datadog APM", "Datadog logs", "Datadog monitoring"]

def _pull(tr, kw, timeframe, geo, pause, tries=4):
    """One single-keyword request (each request is normalised to its own 0-100 peak). Own backoff on HTTP 429: pytrends' built-in
    retries=/backoff_factor= options crash on urllib3>=2 (Retry(method_whitelist=...) was removed) - verified when this screen was run."""
    for i in range(tries):
        try:
            tr.build_payload([kw], timeframe=timeframe, geo=geo); time.sleep(pause)
            d = tr.interest_over_time()
            return d[kw].astype(float) if (d is not None and len(d) and kw in d) else pd.Series(dtype=float)
        except Exception as e:
            if "429" in str(e) and i < tries - 1: time.sleep(max(pause, 5) * 2 ** (i + 1)); continue
            raise

def repeat_stats(runs):
    """Sampling noise: Google returns a random sub-sample, so identical requests differ. Measures that spread across repeated pulls."""
    df = pd.concat(runs, axis=1, join="inner"); spread = df.max(axis=1) - df.min(axis=1)
    pc = [df.iloc[:, i].corr(df.iloc[:, j]) for i in range(df.shape[1]) for j in range(i + 1, df.shape[1])]
    idx = pd.Series(df.index); gran = int(idx.diff().dt.days.median()) if len(idx) > 1 else None
    return dict(n_points=int(len(df)), median_days_between_points=gran, zero_share=float((df.mean(axis=1) == 0).mean()),
                max_repeat_spread=float(spread.max()), mean_repeat_spread=float(spread.mean()), min_pairwise_corr=(float(min(pc)) if pc else None))

def quarterly_yoy(s: pd.Series):
    """Quarterly mean of the index (complete quarters only) and YoY on that mean. YoY is undefined where the base quarter mean is 0."""
    q = s.groupby(s.index.to_period("Q")).agg(["mean", "count"]); q = q[q["count"] >= 3]["mean"]
    yoy = (q / q.shift(4) - 1) * 100; yoy[(q.shift(4) <= 0)] = np.nan
    return q, yoy

def stitch_check(tr, kw, geo, pause):
    """Weekly data only exist for spans up to ~5.25 years, so 2021-01..2026-06 (5.5y) needs two overlapping windows, each rescaled to its own 0-100 peak.
    This measures how stable the implied rescaling factor is across the overlap (a proxy for stitching artefacts)."""
    a = _pull(tr, kw, f"{START} 2025-12-31", geo, pause); b = _pull(tr, kw, f"2022-01-01 {END}", geo, pause)
    ov = a.index.intersection(b.index); ov = ov[(a.reindex(ov) >= 10) & (b.reindex(ov) >= 10)]
    if len(ov) < 20: return dict(n_overlap=int(len(ov)), note="overlap too thin/low-volume to stitch reliably")
    r = (a[ov] / b[ov]); h = len(r) // 2
    return dict(n_overlap=int(len(ov)), scale_median=float(r.median()), ratio_cv=float(r.std() / r.mean()), half_split_drift=float(r.iloc[:h].median() / r.iloc[h:].median()))

def probe_google_trends(geo="", repeats=3, pause=20, weekly_check=True, tr=None):
    out = dict(candidate="A", geo=geo or "worldwide")
    if tr is None:
        try:
            from pytrends.request import TrendReq
            tr = TrendReq(hl="en-US", tz=0)          # do NOT pass retries=/backoff_factor= (see _pull)
        except ImportError:
            return dict(out, status="NOT_RUN", reason="pip install pytrends (unofficial wrapper; not maintained by Google)")
    try:
        sug = tr.suggestions("Datadog")
    except Exception as e:
        blocked = is_network_block(e) or reach("https://trends.google.com/trends/api/explore").get("status") == "BLOCKED_BY_NETWORK_ALLOWLIST"
        return dict(out, status="NOT_TESTABLE_HERE" if blocked else "ERROR", reason=(str(e)[:200] + (" [host blocked by network allowlist]" if blocked else "")))
    out["topic_candidates"] = sug
    titles = [s for s in sug if str(s.get("title", "")).lower() == "datadog"]
    topic = titles[0]["mid"] if len(titles) == 1 else None
    out["topic_mid_unambiguous"] = topic                                   # if None a human must pick from topic_candidates - never guessed
    tf = f"{START} {END}"; res = {}
    for label, kw in [("topic:Datadog", topic)] + [(t, t) for t in TERMS]:
        if kw is None: res[label] = dict(note="no unambiguous Datadog topic returned"); continue
        runs = [_pull(tr, kw, tf, geo, pause) for _ in range(repeats)]
        st = repeat_stats(runs); q, yoy = quarterly_yoy(pd.concat(runs, axis=1).mean(axis=1))
        st.update(quarters_complete=int(len(q)), yoy_defined_2022Q1_2026Q2=int(yoy.loc["2022Q1":"2026Q2"].notna().sum())); res[label] = st
    out["single_request_full_range"] = res
    if weekly_check: out["weekly_stitching_test_term_Datadog"] = stitch_check(tr, "Datadog", geo, pause)
    return dict(out, status="TESTED")


# ================================================================================ B. HN "Who is hiring?" job postings
ALGOLIA = "https://hn.algolia.com/api/v1"
RX_DD = re.compile(r"\bdatadog\b", re.I)
RX_APM = re.compile(r"\bdatadog\b.{0,40}\bapm\b|\bapm\b.{0,40}\bdatadog\b", re.I | re.S)
RX_OBS = re.compile(r"\bobservability\b", re.I)
RX_OWN = re.compile(r"^\W*datadog\b", re.I)                                # the post's FIRST line begins with Datadog => Datadog advertising its own jobs

def _get(url, params=None, retries=4):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=60, headers={"User-Agent": UA})
            if r.status_code == 200: return r.json()
            if r.status_code in (429, 500, 502, 503): time.sleep(2 ** (i + 1)); continue
            raise RuntimeError(f"GET {url} -> HTTP {r.status_code}: {r.text[:200]}")
        except requests.RequestException:
            time.sleep(2 ** (i + 1))
    raise RuntimeError(f"giving up on {url}")

def hn_threads(get, start=START, end=END):
    """All monthly 'Ask HN: Who is hiring?' stories by user whoishiring inside [start, end]."""
    t0 = int(pd.Timestamp(start).timestamp()); t1 = int(pd.Timestamp(end).timestamp()) + 86399; out, page = [], 0
    while True:
        j = get(f"{ALGOLIA}/search_by_date", dict(tags="story,author_whoishiring", numericFilters=f"created_at_i>={t0},created_at_i<={t1}", hitsPerPage=100, page=page))
        out += [(h["objectID"], h["created_at"][:10], h["title"]) for h in j["hits"] if re.match(r"\s*Ask HN: Who is hiring\?", h["title"], re.I)]
        page += 1
        if page >= j.get("nbPages", 1): break
    return sorted(set(out), key=lambda x: x[1])

def count_thread(item):
    """Top-level comments only = one job post each. Deleted/dead comments (text None) are counted separately, never as posts."""
    posts = [c for c in item.get("children", []) if c.get("text")]; dele = sum(1 for c in item.get("children", []) if not c.get("text"))
    own = third = apm = obs = 0
    for c in posts:
        txt = htmllib.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<p>", "\n", c["text"])))
        first = next((l for l in txt.splitlines() if l.strip()), "")
        if not RX_DD.search(txt): continue
        if RX_OWN.match(first): own += 1; continue
        third += 1; apm += bool(RX_APM.search(txt)); obs += bool(RX_OBS.search(txt))
    return dict(n_posts=len(posts), n_deleted=dele, dd_own_posts_excluded=own, dd_mentions_third_party=third, dd_apm=apm, dd_and_observability=obs)

def probe_hn_jobs(sample_months=None, get=None):
    out = dict(candidate="B_HN_variant")
    get = get or _get
    try:
        threads = hn_threads(get)
    except Exception as e:
        return dict(out, status="NOT_TESTABLE_HERE" if is_network_block(e) else "ERROR", reason=str(e)[:300])
    out["threads_found"] = len(threads); expected = len(pd.period_range("2021-01", "2026-06", freq="M")); out["threads_expected"] = expected
    pick = [t for t in threads if (sample_months is None or t[1][:7] in sample_months)]
    rows = []
    for tid, d, title in pick:
        item = get(f"{ALGOLIA}/items/{tid}")                                          # one request returns the whole comment tree
        r = count_thread(item); r.update(thread_id=tid, thread_date=d, dd_share_of_posts=(r["dd_mentions_third_party"] / r["n_posts"]) if r["n_posts"] else None)
        r["poisson_rel_se_of_count"] = (1 / math.sqrt(r["dd_mentions_third_party"])) if r["dd_mentions_third_party"] else None; rows.append(r)
    out["thread_sample"] = rows; out["status"] = "TESTED"
    return out


# ================================================================================ C. Integration ecosystem from git history
REPOS = {"core": "https://github.com/DataDog/integrations-core.git", "extras": "https://github.com/DataDog/integrations-extras.git"}
RX_TOP_MANIFEST = re.compile(r"^[^/]+/manifest\.json$")                          # depth-2 only: excludes templates nested inside tooling dirs

def git(*a, cwd=None, inp=None, check=True):
    r = subprocess.run(["git", *a], cwd=cwd, input=inp, capture_output=True, timeout=600)
    if check and r.returncode: raise RuntimeError(f"git {' '.join(a)} -> {r.stderr.decode()[:300]}")
    return r.stdout

def ensure_clone(url, dest, blobless=True):
    """Bare clone. Blobless keeps every commit and tree (all we need for counts) but no file contents: seconds, ~tens of MB."""
    if not os.path.isdir(dest): git("clone", "--bare", "--no-tags", *(["--filter=blob:none"] if blobless else []), url, dest)
    return dest

def commit_before(repo, day):
    """Last first-parent commit on/before the end of `day` (UTC). First-parent = mainline history, so dates are monotonic."""
    return git("rev-list", "-1", "--first-parent", f"--before={day} 23:59:59 +0000", "HEAD", cwd=repo).decode().strip() or None

def manifests_at(repo, commit):
    return [l.split("\t")[1] for l in git("ls-tree", "-r", commit, cwd=repo).decode().splitlines() if RX_TOP_MANIFEST.match(l.split("\t")[1])]

def quarter_counts(repo, quarters=QUARTERS):
    rows = []
    for label, qe in quarters:
        c = commit_before(repo, qe)
        rows.append(dict(quarter=label, quarter_end=qe, commit=(c or "")[:9], n_integrations=(len(manifests_at(repo, c)) if c else None)))
    return pd.DataFrame(rows)

def add_remove_stats(repo):
    """Additions/removals of top-level manifests over the whole history + the largest single-commit addition (bulk-import check)."""
    txt = git("log", "--first-parent", "--no-renames", "--format=C\t%h\t%cs", "--name-status", "--", ":(glob)*/manifest.json", cwd=repo).decode()
    adds, rem, cur = collections.Counter(), 0, None
    for l in txt.splitlines():
        if l.startswith("C\t"): cur = l.split("\t")[1]
        elif l[:1] == "A" and RX_TOP_MANIFEST.match(l.split("\t")[1]): adds[cur] += 1
        elif l[:1] == "D" and RX_TOP_MANIFEST.match(l.split("\t")[1]): rem += 1
    return dict(total_additions=sum(adds.values()), total_removals=rem, largest_single_commit_addition=(max(adds.values()) if adds else 0))

def schema_share(repo, commit, limit=40):
    """Share of sampled manifests using the legacy v1 'categories' field vs v2 'classifier_tags' (a definitional break in the category vocabulary)."""
    ls = [l for l in git("ls-tree", "-r", commit, cwd=repo).decode().splitlines() if RX_TOP_MANIFEST.match(l.split("\t")[1])][:limit]
    shas = [l.split()[2] for l in ls]; raw = git("cat-file", "--batch", cwd=repo, inp=("\n".join(shas) + "\n").encode()); pos, v1, v2, n = 0, 0, 0, 0
    for _ in shas:
        nl = raw.index(b"\n", pos); size = int(raw[pos:nl].split()[2]); body = raw[nl + 1:nl + 1 + size]; pos = nl + 1 + size + 1
        try: j = json.loads(body)
        except ValueError: continue
        n += 1; v1 += bool(j.get("categories")); v2 += bool((j.get("tile") or {}).get("classifier_tags") or j.get("classifier_tags"))
    return dict(sampled=n, legacy_categories=v1, classifier_tags=v2)

def probe_integrations(workdir, repos=REPOS, blobless=True, quarters=QUARTERS):
    out = dict(candidate="C"); os.makedirs(workdir, exist_ok=True)
    try:
        res = {}
        for name, url in repos.items():
            repo = ensure_clone(url, os.path.join(workdir, f"{name}.git"), blobless)
            qc = quarter_counts(repo, quarters); s = add_remove_stats(repo)
            sch = {q: schema_share(repo, commit_before(repo, d)) for q, d in [("2021 Q1", "2021-03-31"), ("2026 Q2", "2026-06-30")] if commit_before(repo, d)}
            res[name] = dict(quarter_counts=qc, history_stats=s, schema_share=sch, complete_quarters=int(qc.n_integrations.notna().sum()))
        out["repos"] = res; out["status"] = "TESTED"
        out["marketplace_repo"] = "private (git demands credentials) -> marketplace integrations NOT reconstructible from public history"
    except Exception as e:
        out.update(status="NOT_TESTABLE_HERE" if is_network_block(e) or "Could not resolve" in str(e) else "ERROR", reason=str(e)[:300])
    return out


# ================================================================================ scorecard (judgements, stored as data with reasons)
SCORES = {   # 1-5, 5 = best. cleaning: 5 = easy. bias: 5 = low risk. Documentation/testing basis noted per candidate.
    "A Google Trends": dict(hist=5, repro=3, freq=4, econ=3, clean=4, bias=3,
        why=dict(hist="monthly since 2004; 2021-2026 covered in ONE request", repro="random sub-sample per pull + per-window 0-100 rescale; needs averaged repeat pulls; official API gated/alpha; unofficial wrappers can break or be rate-limited",
                 freq="monthly in one consistent request; weekly needs a 2-window stitch (5.5y > ~5.25y weekly cap)", econ="brand awareness/evaluation/login intent, but also investors, students, job-seekers",
                 clean="single request; zero-inflated for 'Datadog APM/logs/monitoring'", bias="search-behaviour drift (AI assistants), integer quantisation at low volume"),
        basis="documentation + peer-reviewed literature; NOT live-tested (host blocked in the build sandbox)"),
    "B Job postings (HN-only variant)": dict(hist=5, repro=5, freq=3, econ=3, clean=3, bias=2,
        why=dict(hist="threads exist monthly since 2011", repro="public API, free with attribution, 10,000 req/h/IP; threads are near-immutable", freq="monthly, ~3 threads/quarter; counts per quarter are small",
                 econ="hiring demand for Datadog skills = adoption breadth, but only among HN-audience employers", clean="exclude Datadog's own posts; same company reposts monthly; dedupe/normalise by thread size",
                 bias="startup/US/remote skew, small-count Poisson noise, thread-size drift"),
        basis="API docs + design; NOT live-tested (hosts blocked in the build sandbox). Broad job-market source: FAIL (no free keyword-level history; Indeed Hiring Lab data are aggregate indices only)"),
    "C Integration ecosystem (public repos)": dict(hist=5, repro=5, freq=5, econ=2, clean=4, bias=3,
        why=dict(hist="git history since 2015; 22 quarter-ends 2021Q1-2026Q2 reconstructed", repro="deterministic: quarter-end commit -> count top-level manifest.json; no manual step", freq="any frequency (commit timestamps)",
                 econ="supply-side product breadth; cumulative and controlled by Datadog; weak link to customer expansion", clean="v1->v2 manifest schema break (category split needs a mapping); non-integration dirs excluded by path rule",
                 bias="marketplace not public; cloud-provider integrations not in repos; product-mix shifts (e.g. security log integrations 2024+)"),
        basis="LIVE-TESTED end-to-end"),
}
def scorecard():
    rows = []
    for name, s in SCORES.items():
        tot = sum(s[k] for k in ("hist", "repro", "freq", "econ", "clean", "bias"))
        rows.append(dict(candidate=name, historical_coverage=s["hist"], reproducibility=s["repro"], frequency=s["freq"], economic_connection=s["econ"],
                         cleaning_ease=s["clean"], low_bias_risk=s["bias"], total_of_30=tot, evidence_basis=s["basis"]))
    return pd.DataFrame(rows)


# ================================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="C"); ap.add_argument("--out-dir", default="./out"); ap.add_argument("--workdir", default="./gitprobe")
    ap.add_argument("--geo", default=""); ap.add_argument("--repeats", type=int, default=3); ap.add_argument("--pause", type=float, default=20)
    ap.add_argument("--hn-months", default="2021-01,2022-01,2023-01,2024-01,2025-01,2026-01", help="comma list, or 'all'")
    a = ap.parse_args(argv); os.makedirs(a.out_dir, exist_ok=True); rep = {}
    for c in [x.strip().upper() for x in a.run.split(",")]:
        if c == "A": rep["A"] = probe_google_trends(a.geo, a.repeats, a.pause)
        if c == "B": rep["B"] = probe_hn_jobs(None if a.hn_months == "all" else set(a.hn_months.split(",")))
        if c == "C":
            r = probe_integrations(a.workdir); rep["C"] = r
            if r.get("status") == "TESTED":
                allq = pd.concat([v["quarter_counts"].assign(repo=k) for k, v in r["repos"].items()])
                allq.to_csv(os.path.join(a.out_dir, "feasibility_probe_C_quarter_end_counts.csv"), index=False)
    sc = scorecard(); sc.to_csv(os.path.join(a.out_dir, "feasibility_scorecard.csv"), index=False)
    def clean(o):
        if isinstance(o, pd.DataFrame): return o.to_dict("records")
        if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list): return [clean(v) for v in o]
        return o
    json.dump(clean(rep), open(os.path.join(a.out_dir, "feasibility_probe_results.json"), "w"), indent=2, default=str)
    print(sc.to_string(index=False))
    for k, v in rep.items(): print(f"\n[{k}] status={v.get('status')} {v.get('reason', '')}")
    return rep

if __name__ == "__main__":
    main()
