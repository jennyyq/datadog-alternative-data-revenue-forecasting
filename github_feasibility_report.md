# GitHub feasibility test - report
_run 2026-09-24T08:52:53+00:00 UTC; authenticated=False_

**Preferred first-adoption quarterly series feasible: NO**

| criterion | passed | evidence |
|---|---|---|
| C1 | False | code search returned HTTP 401 |
| C2 | False | commit search matches commit MESSAGES only; a commit that adds ddtrace/DD_* to a file under an unrelated message is invisible, and no endpoint searches historical diffs |
| C3 | False | 5 non-fork repos in a 100-commit sample look like re-uploads/mirrors of Datadog tracer code (fork flag False) |
| C4 | False | commit-search results omit archived/created_at/pushed_at; each needs a separate core-API call per repository (core limit 60/h unauthenticated, 5,000/h with a token) |
| C5 | False | quarters exceeding the 1,000-result cap for ONE keyword: ['2021Q1']; enumerating unique repos then needs sub-quarter slicing and is still keyword-by-keyword |

## Observations
```
{
  "rate_limit": {
    "code_search": {
      "limit": 60,
      "remaining": 60
    },
    "core": {
      "limit": 60,
      "remaining": 60
    },
    "search": {
      "limit": 10,
      "remaining": 10
    }
  },
  "authenticated": false,
  "code_search": {
    "http": 401,
    "message": "Requires authentication",
    "has_date_qualifier_documented": false,
    "scope": "current default-branch snapshot only"
  },
  "commit_sample_2023Q1": {
    "http": 200,
    "total_count": 961,
    "sampled": 100,
    "unique_repos_in_sample": 35,
    "top_repos": [
      [
        "jadielmiranda87-cell/BesttDelivery",
        8
      ],
      [
        "yoloakit/rbynetwork",
        8
      ],
      [
        "devsbranch/ofn",
        8
      ]
    ],
    "message_contains_keyword": 100,
    "bot_authored": 44,
    "fork_flag_true": 0,
    "datadog_lookalike_repo_names": 5,
    "lookalike_commits": 9,
    "lookalike_with_fork_flag_false": 9,
    "lookalike_examples": [
      "Flibiaautcla/dd-trace-py",
      "VidyaBipin/dd-trace-rb-ruby-c-roff",
      "aha-app/dd-trace-rb",
      "ritika994/dd-trace-go",
      "saaslabsco/dd-trace-php"
    ],
    "repository_object_has_archived": false,
    "repository_object_has_created_at": false
  },
  "stability_same_query_twice": [
    961,
    961
  ],
  "ddtrace_commit_message_totals_third_party": {
    "2021Q1": {
      "total_count": 1291,
      "incomplete": false
    },
    "2022Q1": {
      "total_count": 721,
      "incomplete": false
    },
    "2023Q1": {
      "total_count": 961,
      "incomplete": false
    },
    "2024Q1": {
      "total_count": 938,
      "incomplete": false
    },
    "2026Q1": {
      "total_count": 365,
      "incomplete": false
    }
  },
  "repo_search_readme_created_2023Q1": {
    "http": 200,
    "total_count": 9
  },
  "A_preferred_first_adoption_series_feasible": "NO",
  "fingerprints_testable_via_public_api": {
    "ddtrace/dd-trace": "commit-message keyword only (no history of file content)",
    "DD_* env vars / datadog.yaml / datadog-agent": "code search only: authenticated, current snapshot, no time dimension"
  }
}
```