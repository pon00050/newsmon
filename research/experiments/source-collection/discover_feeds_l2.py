"""Feed discovery: fetch each publisher's own page (homepage or RSS-index page) and extract
<link rel=alternate type=rss/atom> plus anchors that look like feed links. One request per page,
robots.txt checked first. Output: discovery_results.json. Feed URLs are NEVER guessed."""
import json, sys, time, urllib.robotparser, re
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
UA = "news-monitoring-research/0.1 (private research; <contact address>)"
import json as _j
PAGES = _j.load(open(sys.argv[2], encoding="utf-8"))
FEEDTYPE = re.compile(r"(rss|atom)\+?xml|application/xml|text/xml", re.I)
FEEDHREF = re.compile(r"(rss|atom|feed|\.xml)", re.I)
out = {}
rp_cache = {}
def robots(url):
    host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if host not in rp_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = httpx.get(host + "/robots.txt", headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            rp_cache[host] = (rp, r.status_code)
        except Exception as e:
            rp_cache[host] = (None, f"ERR {type(e).__name__}")
    return rp_cache[host]
with httpx.Client(headers={"User-Agent": UA}, timeout=20, follow_redirects=True) as c:
    for sid, url in PAGES.items():
        rec = {"page": url}
        rp, st = robots(url)
        rec["robots_status"] = st
        allowed = True if rp is None else rp.can_fetch(UA, url)
        rec["robots_allows"] = allowed
        if not allowed:
            rec["note"] = "disallowed by robots; not fetched"; out[sid] = rec; print(sid, "ROBOTS-DENY"); continue
        try:
            r = c.get(url)
            rec["status"] = r.status_code; rec["final_url"] = str(r.url)
            feeds = []
            if r.status_code == 200 and "html" in r.headers.get("content-type", "").lower() or "xml" in r.headers.get("content-type",""):
                soup = BeautifulSoup(r.text, "lxml")
                for l in soup.find_all("link", rel=lambda v: v and "alternate" in v):
                    if FEEDTYPE.search(l.get("type", "") or ""):
                        feeds.append({"via": "link-alternate", "href": urljoin(str(r.url), l.get("href", "")), "title": l.get("title")})
                for a in soup.find_all("a", href=True):
                    h = a["href"]
                    if FEEDHREF.search(h) and not h.startswith(("javascript", "#")):
                        feeds.append({"via": "anchor", "href": urljoin(str(r.url), h), "text": a.get_text(strip=True)[:60]})
            seen = set(); uniq = []
            for f in feeds:
                if f["href"] not in seen: seen.add(f["href"]); uniq.append(f)
            rec["candidates"] = uniq[:60]; rec["n_candidates"] = len(uniq)
            print(sid, r.status_code, len(uniq))
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:200]; print(sid, "ERR", rec["error"])
        out[sid] = rec
        time.sleep(0.5)
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "discovery_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
