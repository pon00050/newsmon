"""Probe news/information source endpoints.
One GET per endpoint (+1 conditional GET to test 304 where the server sent ETag/Last-Modified), robots.txt check per
host (robots-disallowed endpoints are NOT fetched), polite UA. Endpoint list: endpoints.py (same folder).
Controls: ctl_known_* must work, ctl_nonsense_* must fail/return nothing.
Writes probe_results.json and probe_summary.csv into OUT.
Usage: python probe_sources.py [out_dir]   (deps: requirements.txt)"""
import csv, json, re, sys, time, datetime as dt
from pathlib import Path
from urllib.parse import urlparse
import httpx, feedparser

sys.path.insert(0, str(Path(__file__).parent))
from endpoints import E

UA = "news-monitoring-research/0.1 (private research; <contact address>)"
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
ONLY = set(sys.argv[2:])  # optional: re-probe only these source_ids and merge into existing probe_results.json
rp_cache = {}


def _parse_robots(text):
    """Return {agent_token: [(allow_bool, pattern)]} per RFC 9309 (no urlunparse normalisation)."""
    groups, cur_agents, in_rules = {}, [], False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if in_rules:
                cur_agents, in_rules = [], False
            cur_agents.append(v.lower())
            groups.setdefault(v.lower(), [])
        elif k in ("allow", "disallow"):
            in_rules = True
            for a in cur_agents:
                groups[a].append((k == "allow", v))
    return groups


def _match(pattern, path):
    if pattern == "":
        return -1
    rx = re.escape(pattern).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return len(pattern) if re.match(rx, path) else -1


def robots(c, url):
    p = urlparse(url)
    host = f"{p.scheme}://{p.netloc}"
    if host not in rp_cache:
        groups, st = None, None
        try:
            r = c.get(host + "/robots.txt", timeout=15)
            st = r.status_code
            if st == 200:
                groups = _parse_robots(r.text)
            elif 500 <= st < 600:
                groups = "disallow-all"   # RFC 9309: server error = assume disallow
            else:
                groups = {}               # 4xx (incl. 401/403 WAF pages) = no robots rules found; recorded in robots_status
        except Exception as e:
            st = f"ERR {type(e).__name__}"
        rp_cache[host] = (groups, st)
    groups, st = rp_cache[host]
    if groups is None:
        return None, st
    if groups == "disallow-all":
        return False, st
    rules = groups.get("news-monitoring-research") or groups.get("*") or []
    path = p.path or "/"
    if p.query:
        path += "?" + p.query
    best, allow = -1, True
    for a, pat in rules:
        n = _match(pat, path)
        if n > best or (n == best and a):
            best, allow = n, a
    return (allow if best >= 0 else True), st


def age_hours(parsed):
    ts = []
    for e in parsed.entries[:50]:
        t = e.get("published_parsed") or e.get("updated_parsed")
        if t:
            ts.append(dt.datetime(*t[:6], tzinfo=dt.timezone.utc))
    if not ts:
        return None, None, None
    now = dt.datetime.now(dt.timezone.utc)
    return round((now - max(ts)).total_seconds() / 3600, 2), max(ts).isoformat(), min(ts).isoformat()


results = []
with httpx.Client(headers={"User-Agent": UA, "Accept": "*/*"}, follow_redirects=True, timeout=30) as c:
    last_gdelt = 0.0
    for (sid, name, lang, cat, url, kind, basis) in E:
        if ONLY and sid not in ONLY:
            continue
        rec = dict(source_id=sid, name=name, language=lang, category=cat, endpoint=url, kind=kind,
                   discovery_basis=basis, probed_at=dt.datetime.now(dt.timezone.utc).isoformat())
        allows, rst = robots(c, url)
        rec["robots_status"] = rst
        rec["robots_allows"] = allows
        if allows is False:
            rec["result"] = "not-fetched-robots-disallow"
            results.append(rec)
            print(sid, "ROBOTS-DENY", flush=True)
            continue
        if "gdeltproject.org/api" in url:  # GDELT asks for <= 1 request per 5 s
            w = 12 - (time.time() - last_gdelt)
            if w > 0:
                time.sleep(w)
        try:
            t0 = time.time()
            r = c.head(url) if kind == "head" else c.get(url)
            rec["latency_s"] = round(time.time() - t0, 3)
            if "gdeltproject.org/api" in url:
                last_gdelt = time.time()
            rec["status"] = r.status_code
            rec["final_url"] = str(r.url)
            h = r.headers
            for k in ("content-type", "etag", "last-modified", "cache-control", "content-length", "retry-after",
                      "x-ratelimit-remaining", "x-ratelimit-limit", "server"):
                if k in h:
                    rec["h_" + k] = h[k]
            rec["bytes"] = len(r.content)
            body = r.text if kind != "head" else ""
            if kind == "feed" and r.status_code == 200:
                p = feedparser.parse(r.content)
                rec["feed_format"] = p.version
                rec["bozo"] = bool(p.bozo)
                rec["n_entries"] = len(p.entries)
                if p.entries:
                    e0 = p.entries[0]
                    rec["entry_fields"] = sorted(e0.keys())
                    rec["first_title"] = (e0.get("title") or "")[:90]
                    rec["first_summary_chars"] = len(e0.get("summary") or "")
                    cont = e0.get("content")
                    rec["has_content_encoded"] = bool(cont)
                    rec["first_content_chars"] = len(cont[0].get("value", "")) if cont else 0
                    rec["has_guid"] = bool(e0.get("id"))
                    rec["has_published"] = bool(e0.get("published") or e0.get("updated"))
                    rec["has_media"] = bool(e0.get("media_content") or e0.get("enclosures") or e0.get("media_thumbnail"))
                rec["newest_age_h"], rec["newest"], rec["oldest_in_feed"] = age_hours(p)
                rec["feed_title"] = (p.feed.get("title") or "")[:80]
            elif kind == "json" and r.status_code in (200, 400, 401, 403, 429):
                try:
                    j = r.json()
                    rec["json_top_keys"] = list(j.keys())[:12] if isinstance(j, dict) else f"list[{len(j)}]"
                    if isinstance(j, dict):
                        for k in ("articles", "features", "statuses", "feed", "posts", "documents", "results", "timeline", "response"):
                            if isinstance(j.get(k), list):
                                rec["n_items"] = len(j[k])
                                rec["json_item_keys"] = list(j[k][0].keys())[:20] if j[k] and isinstance(j[k][0], dict) else None
                                break
                    elif isinstance(j, list):
                        rec["n_items"] = len(j)
                        rec["json_item_keys"] = list(j[0].keys())[:20] if j and isinstance(j[0], dict) else None
                    if r.status_code != 200:
                        rec["error_body_head"] = body[:200]
                except Exception:
                    rec["json_error"] = True
                    rec["body_head"] = body[:200]
            elif kind == "text" and r.status_code == 200:
                rec["body_head"] = body[:600]
            elif kind == "html":
                m = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
                rec["title"] = m.group(1).strip()[:100] if m else None
                rec["alt_feed_links"] = re.findall(r'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]*>', body, re.I)[:5]
            if r.status_code >= 400 and kind not in ("json",):
                rec["error_body_head"] = body[:150]
            hh = {k.lower(): v for k, v in h.items()}
            if kind in ("feed", "text") and r.status_code == 200:
                if hh.get("etag") or hh.get("last-modified"):
                    ch = {}
                    if hh.get("etag"):
                        ch["If-None-Match"] = hh["etag"]
                    if hh.get("last-modified"):
                        ch["If-Modified-Since"] = hh["last-modified"]
                    time.sleep(1)
                    t0 = time.time()
                    r2 = c.get(url, headers=ch)
                    rec["cond_status"] = r2.status_code
                    rec["cond_latency_s"] = round(time.time() - t0, 3)
                    rec["cond_bytes"] = len(r2.content)
                    if r2.status_code == 304:
                        rec["conditional_get"] = "etag+last-modified" if hh.get("etag") and hh.get("last-modified") else ("etag" if hh.get("etag") else "last-modified")
                    else:
                        rec["conditional_get"] = "header-sent-but-no-304"
                else:
                    rec["conditional_get"] = "none"
            rec["result"] = "ok" if r.status_code == 200 else f"http-{r.status_code}"
        except Exception as e:
            rec["result"] = "error"
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
        results.append(rec)
        print(sid, rec.get("status"), rec.get("n_entries", rec.get("n_items", "")), rec.get("latency_s"), rec.get("cond_status", ""), flush=True)
        time.sleep(1.0)

if ONLY:
    old = json.load(open(f"{OUT}/probe_results.json", encoding="utf-8"))
    new_by = {r["source_id"]: r for r in results}
    order = [e[0] for e in E]
    merged = {r["source_id"]: r for r in old}
    merged.update(new_by)
    results = [merged[i] for i in order if i in merged]
json.dump(results, open(f"{OUT}/probe_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
cols = ["source_id", "language", "category", "endpoint", "robots_allows", "status", "result", "latency_s", "feed_format",
        "n_entries", "has_content_encoded", "first_summary_chars", "has_media", "newest_age_h", "h_etag",
        "h_last-modified", "cond_status", "conditional_get", "json_top_keys", "n_items", "discovery_basis"]
with open(f"{OUT}/probe_summary.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in results:
        r = dict(r)
        r["json_top_keys"] = json.dumps(r.get("json_top_keys"), ensure_ascii=False) if r.get("json_top_keys") else ""
        w.writerow(r)
print("DONE", len(results), flush=True)
