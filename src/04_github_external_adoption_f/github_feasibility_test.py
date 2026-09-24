#!/usr/bin/env python3
"""
github_feasibility_test.py - SHORT feasibility test: can GitHub's public API give a DEFENSIBLE historical quarterly series of
NEW Datadog adoption in third-party public repositories (2022Q1-2026Q2)?

It performs ~12 search requests, prints a verdict, and writes github_feasibility_report.md / .json.
It does NOT build a collector and does NOT write any adoption series.

Optional: export GITHUB_TOKEN=... (higher limits; makes /search/code usable). Works without a token.

DEFENSIBILITY CRITERIA (all must pass for the preferred "first adoption" metric to be feasible)
  C1  content-level fingerprint search usable AND with a historical (time) dimension
  C2  the commit that INTRODUCED a fingerprint can be identified (needs content/diff search, not message search)
  C3  forks/mirrors of Datadog-owned code can be excluded with API fields
  C4  archived / created / pushed status available without extra per-repository calls
  C5  each quarterly window can be enumerated without hitting the 1,000-results-per-query cap
Documented facts (not tested here): docs.github.com/rest/search/search -> max 1,000 results per search; code search requires
authentication and searches only the current default branch; commit search covers the default branch; commit search matches
commit MESSAGES (and metadata), not diffs; rate limits: unauthenticated 10/min, authenticated 30/min, code search 10/min.
"""
import collections, datetime as dt, json, os, re, sys, time
import requests

TOKEN = os.environ.get("GITHUB_TOKEN")
H = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ddog-alt-data-feasibility"}
if TOKEN: H["Authorization"] = f"Bearer {TOKEN}"
PAUSE = 2.2 if TOKEN else 6.5                                    # stay under the search rate limit
EXCL = "-org:DataDog -user:DataDog"
KW = re.compile(r"ddtrace|dd-trace|datadog", re.I)
LOOKALIKE = re.compile(r"(^|[/_-])(dd-trace|dd-trace-[a-z]+|ddtrace|datadog-agent|dd-agent|integrations-core|datadog-lambda|datadog-api-client)", re.I)
SAMPLE_QUARTERS = {"2021Q1": "2021-01-01..2021-03-31", "2022Q1": "2022-01-01..2022-03-31", "2023Q1": "2023-01-01..2023-03-31",
                   "2024Q1": "2024-01-01..2024-03-31", "2026Q1": "2026-01-01..2026-03-31"}

def get(path, **params):
    r = requests.get("https://api.github.com" + path, headers=H, params=params, timeout=40)
    return r
def search(kind, q, **p):
    time.sleep(PAUSE); return get(f"/search/{kind}", q=q, **p)

def main():
    rep, crit = {}, {}
    # ---- rate limits
    rl = get("/rate_limit").json()["resources"]
    rep["rate_limit"] = {k: dict(limit=v["limit"], remaining=v["remaining"]) for k, v in rl.items() if k in ("core", "search", "code_search")}
    rep["authenticated"] = bool(TOKEN)

    # ---- T1 code search availability (needed for content fingerprints such as DD_TRACE_ENABLED, datadog.yaml)
    r = search("code", "DD_TRACE_ENABLED")
    rep["code_search"] = dict(http=r.status_code, message=(r.json().get("message") if r.headers.get("content-type", "").startswith("application/json") else "")[:160],
                              has_date_qualifier_documented=False, scope="current default-branch snapshot only")
    code_ok = r.status_code == 200
    crit["C1"] = dict(passed=False, why=("code search returned HTTP %d" % r.status_code if not code_ok else "code search works but is a current-snapshot search with no date dimension"))

    # ---- T2 commit search: sample quality (2023Q1, 'ddtrace', third-party only)
    r = search("commits", f"ddtrace committer-date:2023-01-01..2023-03-31 {EXCL}", per_page=100)
    j = r.json(); items = j.get("items", [])
    repos = collections.Counter(i["repository"]["full_name"] for i in items)
    bots = sum(1 for i in items if ((i.get("author") or {}).get("type") == "Bot") or "bot" in ((i.get("author") or {}).get("login") or "").lower()
               or "bot" in (i["commit"]["author"].get("name") or "").lower())
    lookalike = [i for i in items if LOOKALIKE.search(i["repository"]["name"]) or LOOKALIKE.search(i["repository"]["full_name"])]
    forkflag = sum(1 for i in items if i["repository"].get("fork"))
    lookalike_nonfork = [i for i in lookalike if not i["repository"].get("fork")]
    repo_keys = set(items[0]["repository"].keys()) if items else set()
    rep["commit_sample_2023Q1"] = dict(http=r.status_code, total_count=j.get("total_count"), sampled=len(items), unique_repos_in_sample=len(repos),
        top_repos=repos.most_common(3), message_contains_keyword=sum(1 for i in items if KW.search(i["commit"]["message"])),
        bot_authored=bots, fork_flag_true=forkflag, datadog_lookalike_repo_names=len({i['repository']['full_name'] for i in lookalike}),
        lookalike_commits=len(lookalike), lookalike_with_fork_flag_false=len(lookalike_nonfork),
        lookalike_examples=sorted({i["repository"]["full_name"] for i in lookalike_nonfork})[:8],
        repository_object_has_archived=("archived" in repo_keys), repository_object_has_created_at=("created_at" in repo_keys))
    crit["C2"] = dict(passed=False, why="commit search matches commit MESSAGES only; a commit that adds ddtrace/DD_* to a file under an unrelated message is invisible, "
                                        "and no endpoint searches historical diffs")
    crit["C3"] = dict(passed=(len(lookalike_nonfork) == 0), why=f"{len({i['repository']['full_name'] for i in lookalike_nonfork})} non-fork repos in a 100-commit sample look like re-uploads/mirrors of Datadog tracer code (fork flag False)")
    crit["C4"] = dict(passed=("archived" in repo_keys and "created_at" in repo_keys), why="commit-search results omit archived/created_at/pushed_at; each needs a separate core-API call per repository (core limit 60/h unauthenticated, 5,000/h with a token)")

    # ---- T3 stability + quarterly totals (also tests the 1,000-result cap)
    a = search("commits", f"ddtrace committer-date:2023-01-01..2023-03-31 {EXCL}", per_page=1).json().get("total_count")
    b = search("commits", f"ddtrace committer-date:2023-01-01..2023-03-31 {EXCL}", per_page=1).json().get("total_count")
    rep["stability_same_query_twice"] = [a, b]
    tot = {}
    for lab, rng in SAMPLE_QUARTERS.items():
        jj = search("commits", f"ddtrace committer-date:{rng} {EXCL}", per_page=1).json()
        tot[lab] = dict(total_count=jj.get("total_count"), incomplete=jj.get("incomplete_results"))
    rep["ddtrace_commit_message_totals_third_party"] = tot
    over = [k for k, v in tot.items() if (v["total_count"] or 0) > 1000]
    crit["C5"] = dict(passed=(not over), why=f"quarters exceeding the 1,000-result cap for ONE keyword: {over or 'none in sample'}; enumerating unique repos then needs sub-quarter slicing and is still keyword-by-keyword")

    # ---- T4 repository-search proxy (creation date is available here, but it is not an adoption date)
    r = search("repositories", f"ddtrace in:readme created:2023-01-01..2023-03-31 fork:false {EXCL}", per_page=1)
    rep["repo_search_readme_created_2023Q1"] = dict(http=r.status_code, total_count=r.json().get("total_count"))

    # ---- verdict
    feasible = all(c["passed"] for c in crit.values())
    rep["criteria"] = crit
    rep["A_preferred_first_adoption_series_feasible"] = "YES" if feasible else "NO"
    rep["fingerprints_testable_via_public_api"] = {"ddtrace/dd-trace": "commit-message keyword only (no history of file content)", "DD_* env vars / datadog.yaml / datadog-agent": "code search only: authenticated, current snapshot, no time dimension"}
    json.dump(rep, open("github_feasibility_report.json", "w"), indent=2, default=str)

    L = ["# GitHub feasibility test - report", f"_run {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} UTC; authenticated={bool(TOKEN)}_", "",
         f"**Preferred first-adoption quarterly series feasible: {rep['A_preferred_first_adoption_series_feasible']}**", "",
         "| criterion | passed | evidence |", "|---|---|---|"] + [f"| {k} | {v['passed']} | {v['why']} |" for k, v in crit.items()] + [
         "", "## Observations", "```", json.dumps({k: v for k, v in rep.items() if k != "criteria"}, indent=2, default=str), "```"]
    open("github_feasibility_report.md", "w").write("\n".join(L))
    print(json.dumps({k: rep[k] for k in ("rate_limit", "code_search", "commit_sample_2023Q1", "stability_same_query_twice", "ddtrace_commit_message_totals_third_party", "repo_search_readme_created_2023Q1")}, indent=2, default=str))
    print("\nCRITERIA:"); [print(f"  {k}: {'PASS' if v['passed'] else 'FAIL'} - {v['why']}") for k, v in crit.items()]
    print("\nA. Preferred first-adoption series feasible:", rep["A_preferred_first_adoption_series_feasible"])

if __name__ == "__main__":
    main()