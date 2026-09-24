# Developer Adoption data - QA report
_generated 2026-09-23T18:37:03+00:00 UTC, code v1.0_

## 1. What a "download" is, and what the sources cannot tell you

**npm `dd-trace`** - official downloads API (`api.npmjs.org/downloads/range/{start}:{end}/{package}`).
Daily counts, UTC days; data exist from 2015-01-10; a single-package range is limited to 18 months per request (bulk: 365 days),
so the script requests <=365-day windows and *refuses* any response whose start/end differ from the request.
A day's data land after UTC midnight (a map-reduce job over the previous day's logs). Per-version counts exist only for the previous
7 days, so version mix can be snapshotted but not backfilled. Source doc: github.com/npm/registry/blob/main/docs/download-counts.md.
npm's own explanation of *what counts as a download* is in its blog post "Numeric precision matters: how npm download counts work"
(linked from that doc) - **read that before relying on filtering claims; it was not retrievable when this script was written.**
By construction a count is a tarball fetch: CI runs, container builds, mirrors and re-installs each add to it, and the API returns
no user/organisation identifiers, no CI flag and no bot flag.

**PyPI `ddtrace`** - one row in `bigquery-public-data.pypi.file_downloads` per *file* (wheel or sdist) downloaded from PyPI's CDN, streamed by
the Linehaul project. The PyPA Packaging Guide itself states counts are inaccurate: pip's download cache lowers counts; internal/unofficial
mirrors can raise or lower them; unofficial scripts inflate them; known historical data-quality issues lower them; Linehaul under-reported
before 2018-07-26 (outside this window). ClickPy is a free ClickHouse mirror of the same data, updated daily. pypistats.org keeps only 180 days
(and offers a with/without-mirrors split), so it can validate the most recent ~6 months but cannot supply history.
Installer name is available in BigQuery (`details.installer.name`), so mirror-like installers can be measured; the script also uses
`details.ci` if that field exists in the table schema. Neither is available from npm or from ClickPy's per-day table.

## 2. Missing periods

**PyPI ddtrace**: 0 missing days of 2007; 0 gap range(s); 0 zero-count day(s).

**npm dd-trace**: 0 missing days of 2007; 0 gap range(s); 3 zero-count day(s).

Quarters with incomplete coverage (their quarterly value and any YoY that uses them are blank, never partial sums):

_none_

## 3. Abnormal spikes / drops (flagged only - NOTHING is removed)

Rule: ratio to the median of the same weekday over +-5 weeks is >= 2.5x or <= 1/2.5x AND robust z of the log-ratio >= 6.

**PyPI ddtrace** (top 16 by |z|):

| date | value | ratio_vs_same_weekday_median | robust_z | release_within_prior_3d |
|---|---|---|---|---|
| 2026-01-01 | 176,285.000 | 0.166 | -14.640 |  |
| 2025-12-25 | 172,334.000 | 0.168 | -14.524 |  |
| 2024-12-25 | 102,312.000 | 0.223 | -12.250 |  |
| 2025-01-01 | 106,558.000 | 0.232 | -11.918 |  |
| 2025-12-26 | 241,030.000 | 0.255 | -11.136 | 4.1.1 |
| 2025-12-31 | 341,636.000 | 0.312 | -9.496 |  |
| 2022-12-26 | 45,088.000 | 0.314 | -9.441 |  |
| 2025-12-24 | 339,331.000 | 0.329 | -9.061 |  |
| 2022-12-30 | 49,566.000 | 0.340 | -8.804 |  |
| 2024-01-01 | 103,041.000 | 0.343 | -8.730 |  |
| 2021-12-31 | 36,248.000 | 0.350 | -8.556 |  |
| 2023-01-02 | 55,341.000 | 0.385 | -7.768 | 1.5.5, 1.6.4 |
| 2024-12-24 | 184,769.000 | 0.388 | -7.703 |  |
| 2026-01-02 | 369,644.000 | 0.391 | -7.645 |  |
| 2022-12-27 | 65,057.000 | 0.396 | -7.544 |  |
| 2021-09-06 | 36,856.000 | 0.397 | -7.528 |  |

**npm dd-trace** (top 25 by |z|):

| date | value | ratio_vs_same_weekday_median | robust_z | release_within_prior_3d |
|---|---|---|---|---|
| 2025-01-01 | 87,215.000 | 0.144 | -28.807 |  |
| 2026-01-01 | 140,445.000 | 0.159 | -27.320 |  |
| 2025-12-25 | 150,650.000 | 0.173 | -26.061 |  |
| 2024-12-25 | 108,630.000 | 0.179 | -25.554 |  |
| 2024-01-01 | 67,681.000 | 0.181 | -25.399 |  |
| 2021-12-31 | 38,281.000 | 0.193 | -24.428 | 2.0.0-appsec-beta.4 |
| 2023-12-25 | 74,121.000 | 0.200 | -23.882 | 5.0.0-pre-03f1a68 |
| 2022-12-26 | 76,407.000 | 0.236 | -21.436 |  |
| 2021-12-24 | 48,673.000 | 0.245 | -20.869 |  |
| 2025-12-26 | 190,895.000 | 0.264 | -19.792 |  |
| 2023-11-02 | 120,291.000 | 0.280 | -18.934 |  |
| 2024-12-26 | 178,440.000 | 0.290 | -18.402 |  |
| 2023-12-26 | 123,171.000 | 0.299 | -17.918 |  |
| 2024-12-31 | 186,725.000 | 0.309 | -17.435 |  |
| 2023-01-02 | 103,697.000 | 0.320 | -16.911 |  |
| 2025-12-31 | 298,402.000 | 0.333 | -16.363 |  |
| 2021-12-30 | 77,179.000 | 0.343 | -15.921 | 2.0.0-appsec-beta.4 |
| 2022-12-30 | 104,726.000 | 0.343 | -15.885 |  |
| 2024-12-24 | 207,432.000 | 0.344 | -15.877 |  |
| 2021-12-25 | 13,352.000 | 0.350 | -15.614 |  |
| 2025-12-24 | 315,043.000 | 0.351 | -15.559 |  |
| 2024-12-27 | 190,928.000 | 0.360 | -15.200 |  |
| 2022-12-27 | 135,225.000 | 0.371 | -14.752 |  |
| 2021-12-27 | 79,286.000 | 0.379 | -14.440 |  |
| 2022-01-01 | 14,543.000 | 0.381 | -14.348 | 2.0.0-appsec-beta.4 |

## 4. Candidate level shifts / structural breaks

Weekly totals: median of the next 4 weeks vs median of the previous 4 weeks, ratio >= 1.4x or <= 1/1.4x (clusters merged).

**PyPI ddtrace**:

| week_ending_start_of_next4 | ratio_next4wk_median_vs_prev4wk_median |
|---|---|
| 2026-01-25 | 1.679 |
| 2024-10-27 | 0.597 |
| 2024-09-22 | 1.555 |
| 2021-07-11 | 0.654 |
| 2023-01-22 | 1.491 |
| 2025-12-14 | 0.679 |
| 2022-04-10 | 1.452 |
| 2022-05-08 | 0.692 |

**npm dd-trace**:

| week_ending_start_of_next4 | ratio_next4wk_median_vs_prev4wk_median |
|---|---|
| 2026-01-25 | 1.657 |
| 2025-01-26 | 1.637 |
| 2021-12-19 | 0.617 |
| 2022-01-23 | 1.606 |
| 2021-07-25 | 1.561 |
| 2024-12-22 | 0.671 |

### Package identity / release-line structure (from the registries)

**npm dd-trace** major lines:

| major | first | last | n_versions |
|---|---|---|---|
| 0 | 2018-02-28 | 2022-06-02 | 240 |
| 1 | 2021-06-29 | 2022-02-25 | 18 |
| 2 | 2021-10-01 | 2023-08-15 | 77 |
| 3 | 2022-08-02 | 2024-05-14 | 77 |
| 4 | 2023-02-03 | 2025-01-08 | 89 |
| 5 | 2023-05-23 | 2026-09-11 | 174 |
| 6 | 2024-01-16 | 2026-09-11 | 59 |

**PyPI ddtrace** major lines:

| major | first | last | n_versions |
|---|---|---|---|
| 0 | 2017-01-23 | 2023-01-17 | 192 |
| 1 | 2022-03-01 | 2024-05-20 | 193 |
| 2 | 2023-09-22 | 2025-10-24 | 200 |
| 3 | 2025-02-04 | 2026-07-13 | 117 |
| 4 | 2025-11-13 | 2026-09-23 | 149 |

npm dist-tags (parallel maintained lines, e.g. per Node.js version): `{"legacy": "0.13.3", "profiler": "1.1.0-profiler.0", "appsec-alpha": "2.0.0-appsec-alpha.1", "appsec-beta": "2.0.0-appsec-beta.5", "legacy-v1": "1.7.1", "latest-node8": "0.36.6", "latest-node10": "0.36.6", "latest-node12": "2.46.0", "latest-node14": "3.58.0", "latest-node16": "4.55.0", "dev": "6.0.0-pre-0bb1f17", "latest": "6.16.0", "latest-node18": "5.127.0"}`

Downloads of an older major line and of the newest one are summed in one series: users pinned to legacy lines are still counted, so a major-version transition can move counts without any change in the adopter base.

## 5. Evidence that CI/CD or automated installs could inflate activity

**PyPI ddtrace** - weekend / weekday download intensity by year (a flat profile, i.e. ratio near 1, points to automated rather than human-driven installs; a strong weekday pattern points to work-day activity, including work-day CI):

| yr | mean_weekday | mean_weekend_day | weekend_over_weekday |
|---|---|---|---|
| 2021 | 109,931.739 | 28,734.885 | 0.261 |
| 2022 | 151,490.219 | 36,345.533 | 0.240 |
| 2023 | 231,212.127 | 65,700.714 | 0.284 |
| 2024 | 445,204.126 | 130,422.337 | 0.293 |
| 2025 | 693,493.000 | 194,176.798 | 0.280 |
| 2026 | 1,442,723.419 | 431,676.288 | 0.299 |

Release response (days 0-3 after each stable release vs same-weekday baseline): `{"n_stable_releases_with_data": 505, "mean_ratio_day0_to_3": 1.0332185585196219, "median_ratio": 1.0212822058435835, "share_of_releases_with_ratio_gt_1_25": 0.05148514851485148}`

**npm dd-trace** - weekend / weekday download intensity by year (a flat profile, i.e. ratio near 1, points to automated rather than human-driven installs; a strong weekday pattern points to work-day activity, including work-day CI):

| yr | mean_weekday | mean_weekend_day | weekend_over_weekday |
|---|---|---|---|
| 2021 | 171,857.356 | 25,210.192 | 0.147 |
| 2022 | 272,120.523 | 40,922.648 | 0.150 |
| 2023 | 398,206.112 | 57,963.686 | 0.146 |
| 2024 | 465,661.813 | 68,394.769 | 0.147 |
| 2025 | 679,957.123 | 110,146.567 | 0.162 |
| 2026 | 1,154,046.690 | 220,350.942 | 0.191 |

Release response (days 0-3 after each stable release vs same-weekday baseline): `{"n_stable_releases_with_data": 373, "mean_ratio_day0_to_3": 1.0027851522865836, "median_ratio": 1.0146522189272082, "share_of_releases_with_ratio_gt_1_25": 0.00804289544235925}`

### Cross-check: primary PyPI series vs pypistats.org (overlap only; pypistats keeps 180 days)

97 overlapping days; median(primary / pypistats) = 1.0000; max abs daily deviation = 2.7130%

## 6. Adoption vs repeated deployment - what these data can and cannot support
* A download is a package-fetch **event**. It is not a unique developer, host, service or Datadog customer, and neither API exposes any such identifier.
* Every CI job, image build, cold container start that installs the package, dependency-resolver retry, mirror sync and auto-upgrade after a release adds counts;
  installs served from a local cache add none. Counts therefore blend (i) new adoption, (ii) upgrades of existing users and (iii) repeated builds/deployments.
* Growth in downloads can come from more services instrumented, but equally from more frequent builds per service, more release lines, or more CI.
  This dataset cannot separate them; the diagnostics above can only indicate how much automation-like behaviour is present.
* Treat the series as a proxy for **deployment/build activity involving the tracer**, not as a clean measure of developer adoption, unless the
  BigQuery CI/installer breakdown (PyPI only) shows the automated share is small and stable.
## 7. Limitations
* Two different sources with different (partly undocumented) filtering: series are not like-for-like, and YoY on each is only comparable to itself.
* Source methodology can change without notice (installer behaviour, CDN/logging changes, bot filtering). The break detector flags candidates; it cannot attribute cause.
* No outlier has been removed or adjusted. Any decision to winsorise or drop a spike must be made later, explicitly, with the evidence above.
