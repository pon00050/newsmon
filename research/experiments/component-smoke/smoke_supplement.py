"""Supplement to smoke.py (2026-11-25). Usage: python smoke_supplement.py <scratch_dir> <out.json>
 (a) known-answer control for conditional GET (a server that should honour it) -> proves the 'Yonhap ignores' result is not an instrument fault
 (b) newspaper4k per-page with errors recorded (smoke.py aborted both pages on the Korean ImportError)
 (c) reader's stored cache validators, read from its SQLite file
 (d) boilerplate leakage in trafilatura's Korean output (reads saved text; no network)"""
import json, sys, sqlite3, re
from pathlib import Path
import feedparser
UA = "news-monitoring-research/0.1 (private research; <contact address>)"
S = Path(sys.argv[1]); out = {}
# (a)
u = "https://pypi.org/rss/project/feedparser/releases.xml"
d1 = feedparser.parse(u, agent=UA)
h = d1.get("headers", {})
d2 = feedparser.parse(u, etag=d1.get("etag"), modified=d1.get("modified"), agent=UA)
out["a_conditional_get_control_pypi"] = {"first_status": d1.get("status"), "got_etag": bool(d1.get("etag")), "got_modified": bool(d1.get("modified")),
                                         "second_status": d2.get("status"), "second_entries": len(d2.entries)}
# yna: repeat feedparser using its own returned validators (not httpx's) for a clean comparison
y = "https://www.yna.co.kr/rss/international.xml"
y1 = feedparser.parse(y, agent=UA)
y2 = feedparser.parse(y, etag=y1.get("etag"), modified=y1.get("modified"), agent=UA)
out["a_conditional_get_yna_feedparser_own_validators"] = {"first_status": y1.get("status"), "etag": y1.get("etag"), "modified": y1.get("modified"),
                                                          "second_status": y2.get("status"), "second_entries": len(y2.entries)}
# (b)
import newspaper
nb = {}
for k, lang in (("bbc", "en"), ("yna", "ko")):
    html = (S / "dl" / f"{k}.html").read_bytes().decode("utf-8", "replace")
    try:
        a = newspaper.article("https://example.invalid/x", input_html=html, language=lang)
        nb[k] = {"chars": len(a.text), "title": a.title, "authors": a.authors[:2], "publish_date": str(a.publish_date), "head": a.text[:100]}
    except Exception as e:
        nb[k] = {"error": f"{type(e).__name__}: {str(e)[:140]}"}
out["b_newspaper4k"] = nb
# (c)
con = sqlite3.connect(S / "reader.sqlite")
cols = [r[1] for r in con.execute("pragma table_info(feeds)")]
row = con.execute("select * from feeds").fetchone()
out["c_reader_db_feed_columns_with_http"] = {c: (str(v)[:40] if v is not None else None) for c, v in zip(cols, row) if "http" in c or "hash" in c or "update" in c}
# (d)
t = (S / "bbc_trafilatura.txt"); k = (S / "yna_trafilatura.txt").read_text(encoding="utf-8")
lines = [l for l in k.splitlines() if l.strip()]
out["d_yna_trafilatura_first_lines"] = lines[:8]
out["d_yna_boilerplate_lines_detected"] = [l for l in lines if re.search(r"전체 내용을 이해하기|구글 검색에서|송고 20", l)]
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
