"""Experiment 4: volume spike detection on a GDELT DOC 2.0 timelinevol series (query 'Ukraine', timespan 30d, daily).
Methods: rolling z-score (trailing window 7 points, flag z >= 2.5 and >= 2.0) and one-sided CUSUM (k = 0.5 sd, h = 4 sd,
baseline = trailing median/MAD-based sd). Also reports calendar gaps in the series.
Usage: python -I -X utf8 spike_detect.py <series.json> <out.json>"""
import json, sys, datetime as dt, statistics as st
d = json.load(open(sys.argv[1], encoding="utf-8"))["timeline"][0]["data"]
dates = [dt.datetime.strptime(x["date"], "%Y%m%dT%H%M%SZ").date() for x in d]; v = [x["value"] for x in d]
gaps = [(str(a), str(b), (b - a).days - 1) for a, b in zip(dates, dates[1:]) if (b - a).days > 1]
out = {"points": len(v), "first": str(dates[0]), "last": str(dates[-1]), "calendar_gaps": gaps,
       "max": [str(dates[v.index(max(v))]), max(v)], "series": list(zip(map(str, dates), v)), "z": {}, "cusum": []}
W = 7
for thr in (2.0, 2.5):
    flags = []
    for i in range(W, len(v)):
        win = v[i - W:i]; m, s = st.mean(win), st.pstdev(win) or 1e-9
        z = (v[i] - m) / s
        if z >= thr: flags.append([str(dates[i]), v[i], round(z, 2)])
    out["z"][thr] = flags
# CUSUM against a robust trailing baseline
S = 0.0
for i in range(W, len(v)):
    win = v[i - W:i]; med = st.median(win); mad = st.median([abs(x - med) for x in win]) * 1.4826 or 1e-9
    S = max(0.0, S + (v[i] - med) / mad - 0.5)
    if S >= 4:
        out["cusum"].append([str(dates[i]), v[i], round(S, 2)]); S = 0.0
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), indent=1)
print(json.dumps({k: out[k] for k in ("points", "first", "last", "calendar_gaps", "max", "z", "cusum")}, indent=1))
print("series:", " ".join(f"{a[5:]}:{b:.2f}" for a, b in out["series"]))
