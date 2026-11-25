"""GDELT follow-up probe: language controls (known-answer EN/KO/ZH + nonsense) with 15 s spacing (GDELT asks for
one request per 5 s; the first pass got 429 at 5.5-12 s spacing). Output: gdelt_results.json.
Usage: python probe_gdelt.py [out_dir]"""
import json, sys, time, datetime as dt
from urllib.parse import quote
import httpx

UA = "news-monitoring-research/0.1 (private research; <contact address>)"
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
B = "https://api.gdeltproject.org/api/v2"
def doc(q, span, n=10): return f"{B}/doc/doc?query={quote(q)}&mode=artlist&format=json&timespan={span}&maxrecords={n}"
Q = [
 ("en_known", doc("Korea sourcelang:english", "1h")),
 ("zh_known_sourcelang_chinese", doc("习近平 sourcelang:chinese", "1d")),
 ("ko_known_sourcelang_korean", doc("대통령 sourcelang:korean", "1d")),
 ("ko_known_no_sourcelang", doc("대통령", "1d")),
 ("ko_known_sourcelang_kor", doc("대통령 sourcelang:kor", "1d")),
 ("nonsense_2tokens", doc("zzqxjvkw9137 qplmzkxq", "1d")),
 ("tv_timeline_24h", f"{B}/tv/tv?query=Korea&mode=timelinevol&format=json&timespan=24h"),
 ("geo_plain", f"{B}/geo/geo?query=Korea"),
]
res = []
with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as c:
    for name, url in Q:
        rec = {"name": name, "url": url, "at": dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            t0 = time.time(); r = c.get(url)
            rec.update(status=r.status_code, latency_s=round(time.time() - t0, 2), bytes=len(r.content), ctype=r.headers.get("content-type"))
            try:
                j = r.json()
                arts = j.get("articles") if isinstance(j, dict) else None
                rec["n_articles"] = len(arts) if arts is not None else None
                if arts:
                    rec["sample"] = [{"title": a.get("title"), "domain": a.get("domain"), "language": a.get("language"), "seendate": a.get("seendate")} for a in arts[:3]]
                    rec["languages"] = sorted({a.get("language") for a in arts})
                rec["json_keys"] = list(j.keys()) if isinstance(j, dict) else f"list[{len(j)}]"
            except Exception:
                rec["body_head"] = r.text[:200]
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
        res.append(rec); print(name, rec.get("status"), rec.get("n_articles"), rec.get("latency_s"), rec.get("error", ""), flush=True)
        time.sleep(15)
json.dump(res, open(f"{OUT}/gdelt_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
