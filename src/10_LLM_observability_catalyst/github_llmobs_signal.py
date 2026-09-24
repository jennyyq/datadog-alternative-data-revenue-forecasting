#!/usr/bin/env python3
"""
github_llmobs_signal.py - feasibility snapshot (NOT a historical reconstruction) of a public GitHub activity signal
for adoption of Datadog's LLM/Agent Observability feature, using Datadog-specific fingerprints:
    DD_LLMOBS_ENABLED   (documented env var, datadoghq.com/product/ai/llm-observability)
    LLMObs.enable(      (ddtrace SDK call, Python/Node LLM Observability SDKs)
    llmobs_enabled      (config-flag spelling variant seen in the wild)

This is explicitly an EMERGING-CATALYST tracker: the task does not require 8-12 quarters of history, so this
script reports a current snapshot (repo/commit counts, with whatever dates GitHub's search index returns) rather
than building the rename/flicker-aware historical audit used for the (mature, multi-year) integrations-ecosystem
work earlier in this project. That heavier machinery is not justified for a feature that only went GA in mid-2024.

KNOWN LIMITATIONS (see also the "GitHub external-adoption" feasibility test done earlier in this project, which
found the general case infeasible for a *historical* series - the constraints below are the same underlying API
limits, just less damaging here because the ask is a snapshot, not a quarterly time series):
  - GitHub code search (which would see the fingerprint literally inside a config file) requires an authenticated
    API key; this sandbox has none, so code search returns HTTP 403 here. With a token it becomes usable.
  - Commit search matches commit MESSAGES (and their full body), not diffs - a commit that adds the fingerprint to
    a file without mentioning it in the message is invisible here.
  - Repository search text-matches only name/description/README/topics, not arbitrary file content.
  - The org-exclusion filter matches the literal strings "DataDog"/"datadog"; a Datadog-adjacent org spelled
    differently (e.g. "datadog-labs") is NOT excluded and can appear as a false "third-party" hit - flagged below.
  - No claim is made that these are production deployments; hackathon and tutorial repos are visibly present in
    the sample and are not filtered out (filtering them out would require judgment calls beyond this script's scope).

Usage: python github_llmobs_signal.py [--token YOUR_GITHUB_TOKEN]
"""
from __future__ import annotations
import argparse, json, os, time
import requests

FINGERPRINTS_COMMIT = ["DD_LLMOBS_ENABLED", "LLMObs.enable", "llmobs_enabled"]
EXCLUDE = "-org:DataDog -user:DataDog"          # literal-string exclusion only - see limitations above
DATADOG_ADJACENT_ORGS = ["datadog-labs"]        # known adjacent orgs NOT caught by EXCLUDE; flagged, not filtered


def make_headers(token: str | None) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ddog-llmobs-signal/1.0"}
    if token: h["Authorization"] = f"Bearer {token}"
    return h

def get(session: requests.Session, url: str, **params) -> requests.Response:
    return session.get(url, params=params, timeout=30)

def rate_limit(session: requests.Session) -> dict:
    r = get(session, "https://api.github.com/rate_limit")
    res = r.json().get("resources", {})
    return {k: dict(limit=v["limit"], remaining=v["remaining"]) for k, v in res.items() if k in ("core", "search", "code_search")}

def code_search_probe(session: requests.Session) -> dict:
    r = get(session, "https://api.github.com/search/code", q="DD_LLMOBS_ENABLED")
    ok = r.status_code == 200
    return dict(http=r.status_code, usable=ok, message=(r.json().get("message", "") if not ok else ""))

def commit_snapshot(session: requests.Session, keyword: str, pause: float, sample=5) -> dict:
    time.sleep(pause)
    r = get(session, "https://api.github.com/search/commits", q=f"{keyword} {EXCLUDE}", per_page=sample, sort="committer-date", order="desc")
    j = r.json() if r.status_code == 200 else {}
    items = j.get("items", [])
    adjacent_hits = [it["repository"]["full_name"] for it in items if any(o in it["repository"]["full_name"].lower() for o in DATADOG_ADJACENT_ORGS)]
    return dict(http=r.status_code, total_count=j.get("total_count"), incomplete_results=j.get("incomplete_results"),
               sample=[dict(repo=it["repository"]["full_name"], date=it["commit"]["committer"]["date"][:10],
                            message_first_line=it["commit"]["message"].splitlines()[0][:100]) for it in items],
               datadog_adjacent_org_hits_in_sample=adjacent_hits)

def repo_snapshot(session: requests.Session, query: str, pause: float, sample=8) -> dict:
    time.sleep(pause)
    r = get(session, "https://api.github.com/search/repositories", q=f"{query} {EXCLUDE}", per_page=sample)
    j = r.json() if r.status_code == 200 else {}
    items = j.get("items", [])
    return dict(http=r.status_code, total_count=j.get("total_count"),
               sample=[dict(repo=it["full_name"], created=it["created_at"][:10], pushed=it["pushed_at"][:10],
                            description=(it.get("description") or "")[:90]) for it in items])


def run(token: str | None = None, pause: float = 6.5, session: requests.Session | None = None) -> dict:
    session = session or requests.Session()
    session.headers.update(make_headers(token))
    out = dict(authenticated=bool(token), rate_limit=rate_limit(session), code_search=code_search_probe(session))

    out["commit_search"] = {kw: commit_snapshot(session, kw, pause) for kw in FINGERPRINTS_COMMIT}
    out["repo_search"] = {
        "DD_LLMOBS_ENABLED in:readme": repo_snapshot(session, "DD_LLMOBS_ENABLED in:readme", pause),
        "llmobs in:name,description": repo_snapshot(session, "llmobs in:name,description", pause),
        "\"agent observability\" datadog in:readme": repo_snapshot(session, "\"agent observability\" datadog in:readme", pause),
    }

    # feasibility verdict for THIS narrower, snapshot-only ask (not the historical-series bar used earlier)
    any_signal = any(v["total_count"] for v in out["commit_search"].values() if v.get("total_count")) or \
                any(v["total_count"] for v in out["repo_search"].values() if v.get("total_count"))
    out["verdict"] = dict(
        current_snapshot_signal_feasible="YES" if any_signal else "NO",
        historical_quarterly_series_feasible="NOT ASSESSED - not required for an emerging-catalyst tracker; "
            "see the general GitHub-adoption feasibility test done earlier in this project for why a historical "
            "series specifically would be hard (message-only commit search, no content-level date history without "
            "an authenticated code-search key).",
        recommended_use="A periodic (e.g. monthly) snapshot of repo_search total_counts and commit_search "
            "total_counts, re-run with an authenticated token to also enable code_search. Track the counts "
            "themselves going forward rather than trying to backfill history that the API cannot provide.")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    ap.add_argument("--pause", type=float, default=6.5)
    ap.add_argument("--out", default="github_llmobs_signal_snapshot.json")
    a = ap.parse_args()
    result = run(a.token, a.pause)
    json.dump(result, open(a.out, "w"), indent=2, default=str)
    print(json.dumps(result, indent=2, default=str))
    print("\nVerdict:", result["verdict"]["current_snapshot_signal_feasible"])

if __name__ == "__main__":
    main()
