"""Pull the publisher's own RSS/terms wording (keyword windows) from pages. Output: terms_snippets.json. Data only, not legal advice (R9 interprets)."""
import httpx, re, sys, json, urllib.robotparser
from urllib.parse import urlparse
from bs4 import BeautifulSoup
UA = "news-monitoring-research/0.1 (private research; <contact address>)"
P = {
 "khan": "https://www.khan.co.kr/help/help_rss.html",
 "yna": "https://www.yna.co.kr/rss/index",
 "sbs": "https://news.sbs.co.kr/news/rss.do",
 "cgtn": "https://www.cgtn.com/subscribe/rss.html",
 "cna_tw": "https://www.cna.com.tw/about/rss.aspx",
 "cna_sg": "https://www.channelnewsasia.com/rss",
 "scmp": "https://www.scmp.com/rss",
 "guardian": "https://www.theguardian.com/help/feeds",
 "sec_rss": "https://www.sec.gov/about/rss-feeds",
 "sec_policy": "https://www.sec.gov/about/webmaster-frequently-asked-questions",
 "fedreg": "https://www.federalregister.gov/reader-aids/developer-resources/rest-api",
 "gdelt": "https://www.gdeltproject.org/about.html",
 "bsky_tos": "https://bsky.social/about/support/tos",
 "mastodon_api": "https://docs.joinmastodon.org/api/guidelines/",
 "yt_api_terms": "https://developers.google.com/youtube/terms/api-services-terms-of-service",
 "aljazeera_tos": "https://www.aljazeera.com/terms-and-conditions",
 "dw_rss": "https://www.dw.com/en/rss/s-9100",
 "france24_tos": "https://www.france24.com/en/rss",
 "koreaherald_tos": "https://www.koreaherald.com/rss",
 "donga": "https://www.donga.com/",
 "hankyung_rss": "https://www.hankyung.com/feed",
 "rfi": "https://www.rfi.fr/cn/rss",
 "bigkinds": "https://www.bigkinds.or.kr/",
 "cc_news": "https://commoncrawl.org/terms-of-use",
 "un_press": "https://press.un.org/en",
}
KW = re.compile(r"(non-?commercial|commercial|redistribut|republish|reproduc|personal use|terms of (use|service)|copyright|licen[sc]e|permission|attribution|rate limit|User-Agent|10 requests|개인|상업|영리|재배포|재전송|무단|허락|허가|저작권|이용약관|금지|商业|商用|转载|轉載|版权|版權|授權|授权|禁止)", re.I)
rp_cache = {}
def allowed(c, url):
    p = urlparse(url); h = f"{p.scheme}://{p.netloc}"
    if h not in rp_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = c.get(h + "/robots.txt", timeout=15)
            if r.status_code == 200: rp.parse(r.text.splitlines())
            elif r.status_code in (401, 403): rp.disallow_all = True
            else: rp.allow_all = True
        except Exception: rp.allow_all = True
        rp_cache[h] = rp
    return rp_cache[h].can_fetch(UA, url)
out = {}
with httpx.Client(headers={"User-Agent": UA}, follow_redirects=True, timeout=25) as c:
    for k, u in P.items():
        rec = {"url": u}
        try:
            if not allowed(c, u): rec["note"] = "robots disallow; not fetched"; out[k] = rec; continue
            r = c.get(u); rec["status"] = r.status_code
            if r.status_code == 200:
                s = BeautifulSoup(r.text, "lxml")
                for t in s(["script", "style", "nav", "header", "footer"]): t.decompose()
                text = re.sub(r"\s+", " ", s.get_text(" ", strip=True))
                rec["text_len"] = len(text)
                sn = []; last = -999
                for m in KW.finditer(text):
                    if m.start() - last < 300: continue
                    last = m.start(); sn.append(text[max(0, m.start() - 150): m.start() + 350])
                    if len(sn) >= 6: break
                rec["snippets"] = sn
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:150]
        out[k] = rec; print(k, rec.get("status"), len(rec.get("snippets", [])), flush=True)
json.dump(out, open("terms_snippets.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
