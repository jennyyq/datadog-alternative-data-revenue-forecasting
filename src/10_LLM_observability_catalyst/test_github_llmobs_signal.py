"""
Tests for github_llmobs_signal.py. Uses a mocked requests.Session - no real network calls in the tests themselves.
Run: python test_github_llmobs_signal.py
"""
import json
import github_llmobs_signal as G

class FakeResp:
    def __init__(self, status, body): self.status_code = status; self._b = body
    def json(self): return self._b

class FakeSession:
    def __init__(self, code_search_ok=False, adjacent_org_in_sample=False):
        self.code_search_ok = code_search_ok; self.adjacent = adjacent_org_in_sample; self.calls = []; self.headers = {}
    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if url.endswith("/rate_limit"):
            return FakeResp(200, {"resources": {"core": {"limit": 60, "remaining": 12}, "search": {"limit": 10, "remaining": 9},
                                                "code_search": {"limit": 10, "remaining": 0 if not self.code_search_ok else 10}}})
        if url.endswith("/search/code"):
            return (FakeResp(200, {"total_count": 3, "items": []}) if self.code_search_ok
                    else FakeResp(403, {"message": "API rate limit exceeded"}))
        if url.endswith("/search/commits"):
            repo = "datadog-labs/adjacent-repo" if self.adjacent else "acme/widgets"
            items = [{"repository": {"full_name": repo}, "commit": {"committer": {"date": "2026-03-01T00:00:00Z"},
                     "message": "add DD_LLMOBS_ENABLED to service config\n\nmore body text"}}]
            return FakeResp(200, {"total_count": 42, "incomplete_results": False, "items": items})
        if url.endswith("/search/repositories"):
            items = [{"full_name": "acme/llmobs-demo", "created_at": "2025-06-01T00:00:00Z", "pushed_at": "2026-01-01T00:00:00Z", "description": "demo"}]
            return FakeResp(200, {"total_count": 7, "items": items})
        raise AssertionError("unexpected URL: " + url)

def test_rate_limit_parses_expected_keys():
    r = G.rate_limit(FakeSession())
    assert set(r.keys()) == {"core", "search", "code_search"} and r["search"]["remaining"] == 9

def test_code_search_probe_reports_unusable_when_403():
    p = G.code_search_probe(FakeSession(code_search_ok=False))
    assert p["usable"] is False and p["http"] == 403 and "rate limit" in p["message"].lower()

def test_code_search_probe_reports_usable_when_200():
    p = G.code_search_probe(FakeSession(code_search_ok=True))
    assert p["usable"] is True and p["http"] == 200

def test_commit_snapshot_extracts_total_and_sample():
    s = G.commit_snapshot(FakeSession(), "DD_LLMOBS_ENABLED", pause=0)
    assert s["total_count"] == 42 and len(s["sample"]) == 1
    assert s["sample"][0]["repo"] == "acme/widgets" and s["sample"][0]["date"] == "2026-03-01"

def test_commit_snapshot_flags_datadog_adjacent_org_not_caught_by_exclusion():
    s = G.commit_snapshot(FakeSession(adjacent_org_in_sample=True), "DD_LLMOBS_ENABLED", pause=0)
    assert s["datadog_adjacent_org_hits_in_sample"] == ["datadog-labs/adjacent-repo"]

def test_repo_snapshot_extracts_total_and_sample():
    s = G.repo_snapshot(FakeSession(), "llmobs in:name,description", pause=0)
    assert s["total_count"] == 7 and s["sample"][0]["repo"] == "acme/llmobs-demo"

def test_exclusion_string_is_appended_to_every_query():
    sess = FakeSession()
    G.commit_snapshot(sess, "DD_LLMOBS_ENABLED", pause=0)
    G.repo_snapshot(sess, "llmobs in:name,description", pause=0)
    for url, params in sess.calls:
        if "q" in (params or {}):
            assert G.EXCLUDE in params["q"]

def test_run_end_to_end_verdict_yes_when_signal_present():
    out = G.run(token=None, pause=0, session=FakeSession())
    assert out["authenticated"] is False
    assert out["code_search"]["usable"] is False              # unauthenticated FakeSession -> 403
    assert out["verdict"]["current_snapshot_signal_feasible"] == "YES"   # commit/repo counts are nonzero in the fake
    assert set(out["commit_search"].keys()) == set(G.FINGERPRINTS_COMMIT)

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests: t(); print("PASS", t.__name__)
    print(f"\n{len(tests)}/{len(tests)} tests passed (mocked GitHub responses, no live calls in tests).")
