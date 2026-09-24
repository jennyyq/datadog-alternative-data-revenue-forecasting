#!/usr/bin/env python3
"""
Developer Adoption Index - data collection, transformation and QA for
    PyPI package  ddtrace   and   npm package  dd-trace
Target window: 2021-01-01 .. 2026-06-30 (daily), aggregated to calendar quarters 2021 Q1 .. 2026 Q2.

DESIGN RULES (from the task brief)
  * No estimation, no interpolation, no back-filling. A day that is absent from the source stays NaN.
  * A calendar quarter is summed ONLY if every day of that quarter is present; otherwise the quarter is NaN.
  * YoY is computed only where the quarter four periods earlier is available (2021 quarters have no t-4 -> blank).
  * Outliers are FLAGGED in the QA report, never removed.
  * No revenue analysis, no regressions, no combination of the two signals.

SOURCES
  npm    : official downloads API      https://api.npmjs.org/downloads/range/{start}:{end}/dd-trace   (daily, UTC)
  PyPI   : (a) ClickPy / ClickHouse public SQL (open mirror of the PyPI BigQuery data, updated daily)  [default, no credentials]
           (b) Google BigQuery public dataset  bigquery-public-data.pypi.file_downloads              [needs GCP credentials; billed]
           (c) pypistats.org API - ONLY last 180 days -> used solely as a cross-check of (a)/(b)
  Registries (release timestamps, used only to annotate the QA): registry.npmjs.org, pypi.org

USAGE
  python collect_developer_adoption.py --out-dir ./out                              # ClickPy for PyPI
  python collect_developer_adoption.py --out-dir ./out --pypi-source bigquery --bq-project MY_GCP_PROJECT --max-gb 1500
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, os, re, sys, time
import numpy as np
import pandas as pd
import requests

NPM_PKG, PYPI_PKG = "dd-trace", "ddtrace"
NPM_API = "https://api.npmjs.org"
NPM_MAX_DAYS = 365                     # documented cap: 18 months (single package) / 365 days (bulk). 365 is safe for both.
CLICKHOUSE_URL = "https://sql-clickhouse.clickhouse.com:443/"
CLICKHOUSE_USER = "demo"               # per ClickPy public SQL docs (verify at clickpy.clickhouse.com if this changes)
PYPISTATS_API = "https://pypistats.org/api"
UA = "developer-adoption-index/1.0 (academic research; set-your-contact-here)"
CODE_VERSION = "1.0"

FIRST_Q, LAST_Q = "2021Q1", "2026Q2"
MIRROR_LIKE_INSTALLERS = {"bandersnatch", "z3c.pypimirror", "artifactory", "devpi", "nexus"}   # lower-case; informational only


# =============================================================================================== HTTP
class Http:
    """Thin requests wrapper with retry/backoff. Raises loudly on anything other than HTTP 200."""
    def __init__(self, retries=6, backoff=2.0, timeout=90):
        self.retries, self.backoff, self.timeout = retries, backoff, timeout
        self.s = requests.Session(); self.s.headers["User-Agent"] = UA
        self.log = []                                    # request log -> sources.json

    def request(self, method, url, **kw):
        last = None
        for i in range(self.retries):
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kw)
            except requests.RequestException as e:
                last = repr(e); time.sleep(self.backoff ** (i + 1)); continue
            if r.status_code == 200:
                self.log.append(dict(method=method, url=r.url, status=200, bytes=len(r.content),
                                     sha256=hashlib.sha256(r.content).hexdigest(),
                                     retrieved_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")))
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                wait = float(r.headers.get("Retry-After", self.backoff ** (i + 1)))
                last = f"HTTP {r.status_code}"; time.sleep(min(wait, 120)); continue
            raise RuntimeError(f"{method} {url} -> HTTP {r.status_code}: {r.text[:300]}")
        raise RuntimeError(f"giving up on {url}: {last}")


# =============================================================================================== npm
def date_windows(start: dt.date, end: dt.date, max_days: int):
    """Contiguous, non-overlapping windows covering [start, end] inclusive, each <= max_days long."""
    cur = start
    while cur <= end:
        w_end = min(cur + dt.timedelta(days=max_days - 1), end)
        yield cur, w_end
        cur = w_end + dt.timedelta(days=1)

def fetch_npm_daily(http, pkg, start, end, verify_point=True):
    """Daily downloads from the official npm API. Refuses (raises) if npm trims/alters a window or returns a partial window."""
    parts, checks = [], []
    for a, b in date_windows(start, end, NPM_MAX_DAYS):
        body = http.request("GET", f"{NPM_API}/downloads/range/{a}:{b}/{pkg}").json()
        if body.get("start") != str(a) or body.get("end") != str(b):
            raise RuntimeError(f"npm returned a different window than requested: asked {a}:{b}, got {body.get('start')}:{body.get('end')}")
        d = pd.DataFrame(body["downloads"])
        d["date"] = pd.to_datetime(d["day"])
        expected = (b - a).days + 1
        if len(d) != expected or d["date"].duplicated().any():
            raise RuntimeError(f"npm window {a}:{b}: expected {expected} unique days, got {len(d)}")
        if (d["downloads"] < 0).any():
            raise RuntimeError("negative download count from npm API")
        parts.append(d[["date", "downloads"]])
        if verify_point:                                    # integrity: point endpoint total must equal the sum of the daily rows
            pt = http.request("GET", f"{NPM_API}/downloads/point/{a}:{b}/{pkg}").json()["downloads"]
            checks.append(dict(window=f"{a}:{b}", daily_sum=int(d.downloads.sum()), point_total=int(pt), match=int(d.downloads.sum()) == int(pt)))
    s = pd.concat(parts).set_index("date")["downloads"].astype("float64").sort_index()
    return s, checks

def fetch_npm_version_snapshot(http, pkg):
    """Per-version counts exist only for the previous 7 days (documented limit): a snapshot, not history."""
    body = http.request("GET", f"{NPM_API}/versions/{pkg}/last-week").json()
    return pd.Series(body["downloads"]).rename("downloads_last_week")


# =============================================================================================== PyPI
def _safe_name(name):
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", name): raise ValueError("unsafe project name")
    return name

def ch_query(http, sql, user=CLICKHOUSE_USER, url=CLICKHOUSE_URL):
    return http.request("POST", url, params={"user": user, "default_format": "JSONCompact"}, data=sql.encode()).json()

def fetch_pypi_clickhouse(http, project, start, end):
    """Daily downloads from the ClickPy ClickHouse mirror of the PyPI BigQuery data. Schema is verified before use."""
    project = _safe_name(project)
    cols = ch_query(http, "SELECT name FROM system.columns WHERE database='pypi' AND table='pypi_downloads_per_day'")
    names = {r[0] for r in cols["data"]}
    if not {"date", "project", "count"} <= names:
        raise RuntimeError(f"ClickPy schema differs from what this script expects (found columns: {sorted(names)}). "
                           "Check https://clickpy.clickhouse.com and adjust the query.")
    sql = (f"SELECT date, sum(count) AS downloads FROM pypi.pypi_downloads_per_day "
           f"WHERE project = '{project}' AND date >= '{start}' AND date <= '{end}' GROUP BY date ORDER BY date")
    rows = ch_query(http, sql)["data"]
    s = pd.Series({pd.Timestamp(r[0]): float(r[1]) for r in rows}, dtype="float64").sort_index()
    return s                                                # days absent from the source stay absent (-> NaN after reindex)

def fetch_pypi_bigquery(project_id, pkg, start, end, max_bytes, breakdown=True):
    """Daily downloads (and optional installer / CI breakdown) from bigquery-public-data.pypi.file_downloads.
    Column names follow the PyPA Packaging Guide: file.project, details.installer.name, timestamp (partition column)."""
    from google.cloud import bigquery                        # imported lazily: only needed for this backend
    pkg = _safe_name(pkg)
    client = bigquery.Client(project=project_id)
    tbl = "`bigquery-public-data.pypi.file_downloads`"
    fields = {r.field_path for r in client.query(
        "SELECT field_path FROM `bigquery-public-data.pypi.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS` WHERE table_name='file_downloads'").result()}
    has_ci = "details.ci" in fields
    def run(sql, params):
        cfg = bigquery.QueryJobConfig(query_parameters=params, use_query_cache=False, dry_run=True)
        est = client.query(sql, job_config=cfg).total_bytes_processed
        if est > max_bytes:
            raise RuntimeError(f"dry run says {est/1e9:.0f} GB would be scanned > --max-gb guard ({max_bytes/1e9:.0f} GB). Aborting before any billing.")
        cfg = bigquery.QueryJobConfig(query_parameters=params, use_query_cache=False, maximum_bytes_billed=max_bytes)
        return client.query(sql, job_config=cfg).result().to_dataframe(), est
    daily, brk, scanned = [], [], 0
    for a, b in date_windows(start, end, 366):              # ~1 year per query keeps each scan bounded
        params = [bigquery.ScalarQueryParameter("pkg", "STRING", pkg),
                  bigquery.ScalarQueryParameter("t0", "TIMESTAMP", dt.datetime(a.year, a.month, a.day, tzinfo=dt.timezone.utc)),
                  bigquery.ScalarQueryParameter("t1", "TIMESTAMP", dt.datetime(b.year, b.month, b.day, tzinfo=dt.timezone.utc) + dt.timedelta(days=1))]
        sql = f"SELECT DATE(timestamp) AS date, COUNT(*) AS downloads FROM {tbl} WHERE file.project = @pkg AND timestamp >= @t0 AND timestamp < @t1 GROUP BY date ORDER BY date"
        df, est = run(sql, params); scanned += est; daily.append(df)
        if breakdown:
            ci_col = ", details.ci AS ci" if has_ci else ""
            sql2 = (f"SELECT DATE(timestamp) AS date, details.installer.name AS installer{ci_col}, COUNT(*) AS downloads FROM {tbl} "
                    f"WHERE file.project = @pkg AND timestamp >= @t0 AND timestamp < @t1 GROUP BY date, installer{', ci' if has_ci else ''}")
            d2, est2 = run(sql2, params); scanned += est2; brk.append(d2)
    d = pd.concat(daily); d["date"] = pd.to_datetime(d["date"])
    s = d.set_index("date")["downloads"].astype("float64").sort_index()
    b = pd.concat(brk) if brk else None
    if b is not None: b["date"] = pd.to_datetime(b["date"])
    return s, b, dict(bytes_scanned_estimate=int(scanned), has_ci_column=has_ci)

def fetch_pypistats_recent(http, pkg):
    """pypistats.org retains only the last 180 days: cross-check material only, never a substitute for the history."""
    body = http.request("GET", f"{PYPISTATS_API}/packages/{_safe_name(pkg)}/overall").json()
    d = pd.DataFrame(body["data"]); d["date"] = pd.to_datetime(d["date"])
    return d.pivot_table(index="date", columns="category", values="downloads", aggfunc="sum").sort_index()


# =============================================================================================== registries (context only)
def fetch_registry_metadata(http):
    npm = http.request("GET", f"https://registry.npmjs.org/{NPM_PKG}").json()
    rows = [dict(version=v, ts=pd.Timestamp(t).tz_convert("UTC"), prerelease=("-" in v), major=int(v.split(".")[0]))
            for v, t in npm.get("time", {}).items() if v not in ("created", "modified")]
    ne = pd.DataFrame(rows).sort_values("ts") if rows else pd.DataFrame(columns=["version", "ts", "prerelease", "major"])
    py = http.request("GET", f"https://pypi.org/pypi/{PYPI_PKG}/json").json()
    from packaging.version import Version, InvalidVersion
    prow = []
    for v, files in py.get("releases", {}).items():
        if not files: continue
        ts = min(pd.Timestamp(f["upload_time_iso_8601"]) for f in files)
        try: vv = Version(v); pre, major = (vv.is_prerelease or vv.is_devrelease), vv.major
        except InvalidVersion: pre, major = True, -1
        prow.append(dict(version=v, ts=ts, prerelease=pre, major=major, n_files=len(files)))
    pe = pd.DataFrame(prow).sort_values("ts") if prow else pd.DataFrame(columns=["version", "ts", "prerelease", "major", "n_files"])
    return dict(npm_events=ne, npm_dist_tags=npm.get("dist-tags", {}), pypi_events=pe)


# =============================================================================================== transformation
def q_label(p: pd.Period) -> str:
    return f"{p.year} Q{p.quarter}"

def to_full_daily(s: pd.Series, start, end) -> pd.Series:
    """Reindex to every calendar day in [start, end]. Absent days become NaN - nothing is filled."""
    return s.reindex(pd.date_range(start, end, freq="D"))

def quarterly(daily: pd.Series, first_q=FIRST_Q, last_q=LAST_Q) -> pd.DataFrame:
    """Sum per calendar quarter, ONLY when every day of the quarter is present; else NaN (never partial sums)."""
    rows = []
    for p in pd.period_range(first_q, last_q, freq="Q"):
        a, b = p.start_time.normalize(), p.end_time.normalize()
        expected = (b - a).days + 1
        seg = daily.reindex(pd.date_range(a, b, freq="D"))
        present = int(seg.notna().sum())
        rows.append(dict(Quarter=q_label(p), days_expected=expected, days_present=present,
                         downloads=float(seg.sum()) if present == expected else np.nan))
    return pd.DataFrame(rows)

def add_yoy(q: pd.DataFrame) -> pd.DataFrame:
    """YoY (%) = Downloads_t / Downloads_(t-4) - 1, only when both are available and the base is > 0."""
    q = q.copy(); base = q["downloads"].shift(4)
    yoy = (q["downloads"] / base - 1.0) * 100.0
    yoy[(base <= 0) | base.isna() | q["downloads"].isna()] = np.nan
    q["yoy_pct"] = yoy
    return q


# =============================================================================================== QA
def gap_ranges(s: pd.Series):
    miss = s.index[s.isna()]
    out, i = [], 0
    while i < len(miss):
        j = i
        while j + 1 < len(miss) and (miss[j + 1] - miss[j]).days == 1: j += 1
        out.append((miss[i].date(), miss[j].date(), j - i + 1)); i = j + 1
    return out

def weekday_baseline_ratio(s: pd.Series, half=5, min_neighbors=6) -> pd.Series:
    """value / median(same weekday, +-half weeks, excluding the day itself). Robust to weekday seasonality."""
    out = pd.Series(np.nan, index=s.index)
    for wd in range(7):
        sub = s[s.index.weekday == wd]; v = sub.values
        for i in range(len(v)):
            nb = np.concatenate([v[max(0, i - half):i], v[i + 1:i + 1 + half]]); nb = nb[~np.isnan(nb)]
            if len(nb) >= min_neighbors and not np.isnan(v[i]):
                med = np.median(nb)
                if med > 0: out.loc[sub.index[i]] = v[i] / med
    return out

def spike_table(s: pd.Series, events: pd.DataFrame | None, ratio_cut=2.5, z_cut=6.0, top=25):
    r = weekday_baseline_ratio(s); lr = np.log(r.replace(0, np.nan)).dropna()
    if lr.empty: return pd.DataFrame(), r
    med = lr.median(); mad = max((lr - med).abs().median() * 1.4826, 0.02)     # floor: avoids absurd z on near-noise-free data
    z = (lr - med) / mad
    flag = z[(z.abs() >= z_cut) & ((r[z.index] >= ratio_cut) | (r[z.index] <= 1 / ratio_cut))]
    t = pd.DataFrame({"date": flag.index.date, "value": s[flag.index].values, "ratio_vs_same_weekday_median": r[flag.index].values, "robust_z": flag.values})
    if events is not None and len(events):
        ev = events.copy(); ev["d"] = pd.to_datetime(ev["ts"]).dt.tz_localize(None).dt.normalize()
        def near(d):
            hit = ev[(ev.d >= pd.Timestamp(d) - pd.Timedelta(days=3)) & (ev.d <= pd.Timestamp(d))]
            return ", ".join(hit.version.head(3)) if len(hit) else ""
        t["release_within_prior_3d"] = [near(d) for d in t["date"]]
    return t.reindex(t.robust_z.abs().sort_values(ascending=False).index).head(top).reset_index(drop=True), r

def level_shift_table(s: pd.Series, min_ratio=1.4, top=15):
    """Weekly (Mon-Sun, complete weeks only) totals; compare median of next 4 weeks to median of previous 4 weeks."""
    wk = s.groupby(pd.Grouper(freq="W-SUN")).agg(lambda x: x.sum() if x.notna().all() and len(x) == 7 else np.nan)
    v = wk.values; rows = []
    for i in range(4, len(v) - 4):
        prev, nxt = v[i - 4:i], v[i:i + 4]
        if np.isnan(prev).any() or np.isnan(nxt).any() or np.median(prev) <= 0: continue
        rr = np.median(nxt) / np.median(prev)
        if rr >= min_ratio or rr <= 1 / min_ratio: rows.append((wk.index[i].date(), rr))
    out, last = [], None                                    # merge adjacent flags, keep the strongest week of each cluster
    for d, rr in rows:
        if last is not None and (pd.Timestamp(d) - pd.Timestamp(last[0])).days <= 14:
            if abs(math.log(rr)) > abs(math.log(last[1])): last = (d, rr); out[-1] = last
        else: last = (d, rr); out.append(last)
    t = pd.DataFrame(out, columns=["week_ending_start_of_next4", "ratio_next4wk_median_vs_prev4wk_median"])
    return t.reindex(t.iloc[:, 1].apply(lambda x: -abs(math.log(x))).sort_values().index).head(top).reset_index(drop=True) if len(t) else t

def weekend_ratio_by_year(s: pd.Series) -> pd.DataFrame:
    d = s.dropna().to_frame("v"); d["yr"] = d.index.year; d["we"] = d.index.weekday >= 5
    g = d.groupby(["yr", "we"]).v.mean().unstack()
    return pd.DataFrame({"mean_weekday": g[False], "mean_weekend_day": g[True], "weekend_over_weekday": g[True] / g[False]})

def release_response(ratio: pd.Series, events: pd.DataFrame | None, days=(0, 1, 2, 3)):
    if events is None or events.empty: return None
    st = events[~events.prerelease]; vals = []
    for ts in st.ts:
        d0 = pd.Timestamp(ts).tz_localize(None).normalize() if pd.Timestamp(ts).tzinfo is None else pd.Timestamp(ts).tz_convert("UTC").tz_localize(None).normalize()
        w = ratio.reindex([d0 + pd.Timedelta(days=k) for k in days]).dropna()
        if len(w): vals.append(w.mean())
    if not vals: return None
    a = np.array(vals)
    return dict(n_stable_releases_with_data=len(a), mean_ratio_day0_to_3=float(a.mean()), median_ratio=float(np.median(a)), share_of_releases_with_ratio_gt_1_25=float((a > 1.25).mean()))

def md_table(df: pd.DataFrame, fmt="{:,.3f}") -> str:
    if df is None or len(df) == 0: return "_none_\n"
    df = df.reset_index() if df.index.name else df
    cols = list(df.columns); lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    df = df.astype(object)                                   # stops pandas upcasting ints (e.g. years) to floats row-wise
    for _, r in df.iterrows():
        cells = []
        for x in r:
            if isinstance(x, (float, np.floating)): cells.append("" if pd.isna(x) else fmt.format(x))
            else: cells.append(str(x))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


DEFINITIONS_MD = """
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
"""

def build_qa_report(raw, qtbl, py_daily, npm_daily, registry, extra, out_dir):
    L = ["# Developer Adoption data - QA report", f"_generated {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} UTC, code v{CODE_VERSION}_", DEFINITIONS_MD]
    L.append("## 2. Missing periods\n")
    for name, s in (("PyPI ddtrace", py_daily), ("npm dd-trace", npm_daily)):
        g = gap_ranges(s); z = int((s == 0).sum())
        L.append(f"**{name}**: {int(s.isna().sum())} missing days of {len(s)}; {len(g)} gap range(s); {z} zero-count day(s).\n")
        if g: L.append(md_table(pd.DataFrame(g, columns=["first_missing", "last_missing", "days"])))
    L.append("Quarters with incomplete coverage (their quarterly value and any YoY that uses them are blank, never partial sums):\n")
    inc = qtbl[(qtbl.days_present_pypi < qtbl.days_expected) | (qtbl.days_present_npm < qtbl.days_expected)]
    L.append(md_table(inc[["Quarter", "days_expected", "days_present_pypi", "days_present_npm"]]))
    ev = {"PyPI ddtrace": registry["pypi_events"] if registry else None, "npm dd-trace": registry["npm_events"] if registry else None}
    ratios = {}
    L.append("## 3. Abnormal spikes / drops (flagged only - NOTHING is removed)\n")
    L.append("Rule: ratio to the median of the same weekday over +-5 weeks is >= 2.5x or <= 1/2.5x AND robust z of the log-ratio >= 6.\n")
    for name, s in (("PyPI ddtrace", py_daily), ("npm dd-trace", npm_daily)):
        t, r = spike_table(s, ev[name]); ratios[name] = r
        L.append(f"**{name}** (top {len(t)} by |z|):\n"); L.append(md_table(t))
    L.append("## 4. Candidate level shifts / structural breaks\n")
    L.append("Weekly totals: median of the next 4 weeks vs median of the previous 4 weeks, ratio >= 1.4x or <= 1/1.4x (clusters merged).\n")
    for name, s in (("PyPI ddtrace", py_daily), ("npm dd-trace", npm_daily)):
        L.append(f"**{name}**:\n"); L.append(md_table(level_shift_table(s)))
    if registry:
        L.append("### Package identity / release-line structure (from the registries)\n")
        for name, key in (("npm dd-trace", "npm_events"), ("PyPI ddtrace", "pypi_events")):
            e = registry[key]
            if len(e):
                m = e.groupby("major").ts.agg(first="min", last="max", n_versions="count"); m["first"] = m["first"].dt.date; m["last"] = m["last"].dt.date
                L.append(f"**{name}** major lines:\n"); L.append(md_table(m))
        L.append(f"npm dist-tags (parallel maintained lines, e.g. per Node.js version): `{json.dumps(registry['npm_dist_tags'])}`\n")
        L.append("Downloads of an older major line and of the newest one are summed in one series: users pinned to legacy lines are still counted, "
                 "so a major-version transition can move counts without any change in the adopter base.\n")
    L.append("## 5. Evidence that CI/CD or automated installs could inflate activity\n")
    for name, s in (("PyPI ddtrace", py_daily), ("npm dd-trace", npm_daily)):
        L.append(f"**{name}** - weekend / weekday download intensity by year (a flat profile, i.e. ratio near 1, points to automated rather than human-driven installs; "
                 "a strong weekday pattern points to work-day activity, including work-day CI):\n"); L.append(md_table(weekend_ratio_by_year(s)))
        rr = release_response(ratios[name], ev[name]) if registry else None
        L.append(f"Release response (days 0-3 after each stable release vs same-weekday baseline): `{json.dumps(rr)}`\n")
    for k, v in extra.items():
        L.append(f"### {k}\n"); L.append(v if isinstance(v, str) else md_table(v))
    L.append("""## 6. Adoption vs repeated deployment - what these data can and cannot support
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
""")
    open(os.path.join(out_dir, "developer_adoption_qa_report.md"), "w").write("\n".join(L))


# =============================================================================================== pipeline
def run(args, http=None, bq_fetch=None):
    http = http or Http()
    start, end = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end)
    os.makedirs(args.out_dir, exist_ok=True)
    meta = dict(code_version=CODE_VERSION, start=args.start, end=args.end, packages=dict(pypi=PYPI_PKG, npm=NPM_PKG), notes=[])
    extra = {}

    # ---- npm
    npm_raw, npm_checks = fetch_npm_daily(http, NPM_PKG, start, end, verify_point=not args.no_point_check)
    npm_daily = to_full_daily(npm_raw, start, end)
    meta["npm"] = dict(endpoint=f"{NPM_API}/downloads/range/{{start}}:{{end}}/{NPM_PKG}", windows=len(npm_checks), point_checks=npm_checks)
    if not all(c["match"] for c in npm_checks): meta["notes"].append("npm point-vs-range total mismatch in >=1 window - see meta.npm.point_checks")

    # ---- PyPI
    breakdown = None
    if args.pypi_source == "clickhouse":
        py_raw = fetch_pypi_clickhouse(http, PYPI_PKG, start, end)
        meta["pypi"] = dict(source="ClickPy/ClickHouse pypi.pypi_downloads_per_day", endpoint=CLICKHOUSE_URL, user=CLICKHOUSE_USER)
    else:
        py_raw, breakdown, info = (bq_fetch or (lambda: fetch_pypi_bigquery(args.bq_project, PYPI_PKG, start, end, int(args.max_gb * 1e9))))()
        meta["pypi"] = dict(source="BigQuery bigquery-public-data.pypi.file_downloads", **info)
    py_daily = to_full_daily(py_raw, start, end)

    # ---- cross-check against pypistats (last 180 days only)
    if not args.no_crosscheck:
        try:
            ps = fetch_pypistats_recent(http, PYPI_PKG); key = "with_mirrors" if "with_mirrors" in ps else ps.columns[0]
            j = pd.concat([ps[key].rename("pypistats"), py_daily.rename("primary")], axis=1, join="inner").dropna()
            if len(j):
                extra["Cross-check: primary PyPI series vs pypistats.org (overlap only; pypistats keeps 180 days)"] = \
                    f"{len(j)} overlapping days; median(primary / pypistats) = {float((j.primary / j.pypistats).median()):.4f}; "\
                    f"max abs daily deviation = {float(((j.primary / j.pypistats) - 1).abs().max()):.4%}\n"
        except Exception as e:                                       # cross-check is optional; never blocks the pipeline
            meta["notes"].append(f"pypistats cross-check skipped: {e}")

    # ---- registry context (release timestamps) - optional, reachable without special access
    registry = None
    if not args.no_registry:
        try: registry = fetch_registry_metadata(http)
        except Exception as e: meta["notes"].append(f"registry metadata skipped: {e}")
    if args.npm_version_snapshot:
        try:
            vs = fetch_npm_version_snapshot(http, NPM_PKG); mj = vs.groupby(lambda v: v.split(".")[0]).sum().to_frame("downloads_last_7_days")
            mj["share"] = mj.downloads_last_7_days / mj.downloads_last_7_days.sum()
            extra[f"npm per-major download share, snapshot of the previous 7 days as of {dt.date.today()} (API cannot backfill)"] = mj
        except Exception as e: meta["notes"].append(f"npm version snapshot skipped: {e}")

    # ---- PyPI installer / CI breakdown (BigQuery only)
    if breakdown is not None and len(breakdown):
        b = breakdown.copy(); b["Quarter"] = b.date.dt.to_period("Q").map(q_label)
        b["installer_l"] = b.installer.fillna("(none)").str.lower(); tot = b.groupby("Quarter").downloads.sum()
        tab = pd.DataFrame({"share_mirror_like_installers": b[b.installer_l.isin(MIRROR_LIKE_INSTALLERS)].groupby("Quarter").downloads.sum() / tot,
                            "share_pip": b[b.installer_l == "pip"].groupby("Quarter").downloads.sum() / tot})
        if "ci" in b.columns: tab["share_ci_true"] = b[b.ci.fillna(False).astype(bool)].groupby("Quarter").downloads.sum() / tot
        extra["PyPI installer / CI composition by quarter (BigQuery)"] = tab.fillna(0.0)
        breakdown.to_csv(os.path.join(args.out_dir, "pypi_breakdown_daily.csv"), index=False)

    # ---- STEP 1 output: raw daily
    raw = pd.DataFrame({"Date": py_daily.index.date, "ddtrace_Python_Downloads": py_daily.values, "dd-trace_NPM_Downloads": npm_daily.values})
    for c in ("ddtrace_Python_Downloads", "dd-trace_NPM_Downloads"): raw[c] = raw[c].astype("Int64")     # missing stays blank, never 0
    raw.to_csv(os.path.join(args.out_dir, "developer_adoption_raw.csv"), index=False)

    # ---- STEP 2/3 output: quarterly + YoY
    qp, qn = add_yoy(quarterly(py_daily)), add_yoy(quarterly(npm_daily))
    out = pd.DataFrame({"Quarter": qp.Quarter, "PyPI_ddtrace_Downloads": qp.downloads, "PyPI_Download_YoY": qp.yoy_pct,
                        "NPM_ddtrace_Downloads": qn.downloads, "NPM_Download_YoY": qn.yoy_pct})
    out["PyPI_ddtrace_Downloads"] = out["PyPI_ddtrace_Downloads"].astype("Int64"); out["NPM_ddtrace_Downloads"] = out["NPM_ddtrace_Downloads"].astype("Int64")
    out["PyPI_Download_YoY"] = out["PyPI_Download_YoY"].round(2); out["NPM_Download_YoY"] = out["NPM_Download_YoY"].round(2)
    out.to_csv(os.path.join(args.out_dir, "developer_adoption_quarterly.csv"), index=False)
    qa = pd.DataFrame({"Quarter": qp.Quarter, "days_expected": qp.days_expected, "days_present_pypi": qp.days_present, "days_present_npm": qn.days_present})
    qa.to_csv(os.path.join(args.out_dir, "developer_adoption_quarterly_coverage.csv"), index=False)

    # ---- STEP 4: QA report + source documentation
    build_qa_report(raw, qa, py_daily, npm_daily, registry, extra, args.out_dir)
    meta["http_log"] = http.log
    json.dump(meta, open(os.path.join(args.out_dir, "developer_adoption_sources.json"), "w"), indent=2, default=str)
    return out, raw, qa

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2021-01-01"); ap.add_argument("--end", default="2026-06-30"); ap.add_argument("--out-dir", default="./out")
    ap.add_argument("--pypi-source", choices=["clickhouse", "bigquery"], default="clickhouse")
    ap.add_argument("--bq-project", help="GCP project id used (and billed) for BigQuery"); ap.add_argument("--max-gb", type=float, default=2000, help="abort if a dry run says more than this many GB would be scanned")
    ap.add_argument("--no-point-check", action="store_true"); ap.add_argument("--no-crosscheck", action="store_true"); ap.add_argument("--no-registry", action="store_true")
    ap.add_argument("--npm-version-snapshot", action="store_true")
    a = ap.parse_args(argv)
    if a.pypi_source == "bigquery" and not a.bq_project: ap.error("--bq-project is required with --pypi-source bigquery")
    return a

if __name__ == "__main__":
    out, raw, qa = run(parse_args())
    print(out.to_string(index=False)); print("\nrows in raw file:", len(raw))
