"""
Release-cadence metadata from the two registries that ARE reachable (pypi.org, registry.npmjs.org).
This is NOT download data. It is used only as context for the data-quality step
(release-driven download spikes, parallel maintained release lines, major-version breaks).
"""
import json, os, re, requests, pandas as pd
from packaging.version import Version, InvalidVersion

def q_label(ts):
    return f"{ts.year} Q{(ts.month-1)//3+1}"

# ---------------- npm: dd-trace ----------------
npm = requests.get("https://registry.npmjs.org/dd-trace", timeout=60).json()
rows = []
for v, t in npm["time"].items():
    if v in ("created", "modified"): continue
    rows.append(dict(version=v, ts=pd.Timestamp(t).tz_convert("UTC"),
                     prerelease=("-" in v), major=int(v.split(".")[0])))
n = pd.DataFrame(rows).sort_values("ts")
n["Quarter"] = n.ts.map(q_label)
print("npm dd-trace: first publish", n.ts.min().date(), "| latest", n.ts.max().date(), "| versions", len(n))
print("npm dist-tags:", json.dumps(npm.get("dist-tags", {})))
print("npm created:", npm["time"]["created"], "| modified:", npm["time"]["modified"])
majors = n.groupby("major").ts.agg(["min", "max", "count"]); majors.columns = ["first_publish", "last_publish", "n_versions"]
print("\nnpm major lines (first/last publish):"); print(majors.to_string())

# ---------------- PyPI: ddtrace ----------------
py = requests.get("https://pypi.org/pypi/ddtrace/json", timeout=120).json()
prow = []
for v, files in py["releases"].items():
    if not files: continue
    ups = [pd.Timestamp(f["upload_time_iso_8601"]) for f in files]
    try: vv = Version(v); pre = vv.is_prerelease or vv.is_devrelease; major = vv.major
    except InvalidVersion: pre = True; major = -1
    prow.append(dict(version=v, ts=min(ups), n_files=len(files), n_yanked=sum(1 for f in files if f.get("yanked")),
                     prerelease=pre, major=major))
p = pd.DataFrame(prow).sort_values("ts"); p["Quarter"] = p.ts.map(q_label)
print("\nPyPI ddtrace: first upload", p.ts.min().date(), "| latest", p.ts.max().date(), "| versions", len(p))
pm = p.groupby("major").ts.agg(["min", "max", "count"]); pm.columns = ["first_upload", "last_upload", "n_versions"]
print("PyPI major lines:"); print(pm.to_string())

# ---------------- per-quarter cadence table 2021Q1..2026Q2 ----------------
qs = [f"{y} Q{q}" for y in range(2021, 2027) for q in range(1, 5)][:22]
def cad(df, pref):
    g = df.groupby("Quarter")
    out = pd.DataFrame({f"{pref}_releases_all": g.size(),
                        f"{pref}_releases_stable": df[~df.prerelease].groupby("Quarter").size()})
    return out
cn, cp = cad(n, "npm_dd-trace"), cad(p, "pypi_ddtrace")
cp["pypi_ddtrace_files_uploaded"] = p.groupby("Quarter").n_files.sum()
cadence = pd.DataFrame(index=qs).join(cn).join(cp).fillna(0).astype(int)
cadence.index.name = "Quarter"
print("\nRelease cadence per calendar quarter:"); print(cadence.to_string())
OUT = os.environ.get("OUT_DIR", "outputs"); os.makedirs(OUT, exist_ok=True)
cadence.to_csv(os.path.join(OUT, "registry_release_cadence_context.csv"))

# npm: how many distinct release lines were published in the same quarter (parallel maintained lines)
par = n[~n.prerelease].groupby("Quarter").major.nunique().reindex(qs).fillna(0).astype(int)
print("\nnpm: distinct MAJOR lines receiving stable releases per quarter:"); print(par.to_string())
yk = p.n_yanked.sum(); print("\nPyPI yanked files total:", int(yk))
