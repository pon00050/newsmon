#!/usr/bin/env python3
"""Build the Newsmon GitHub Pages site.

    uv run --with markdown python scripts/build_site.py --out _site

Inputs   site/ (templates, css, js, static, sample-data), docs/**/*.md, research/**/*.md, dashboard JSON (--data)
Output   a self-contained static tree in --out (default _site), plus .nojekyll

Fails loudly (non-zero exit, message on stderr) when a page cannot be generated or when a dashboard JSON file
does not satisfy the "newsmon-public/1" contract. Markdown is rendered with raw HTML disabled and with link
schemes restricted, so no markup or script in a document can reach the output.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import posixpath
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

try:
    import markdown
    from markdown.extensions import Extension
    from markdown.treeprocessors import Treeprocessor
except ImportError:  # pragma: no cover - environment problem, say how to fix it
    sys.stderr.write("build_site.py needs the 'markdown' package: uv run --with markdown python scripts/build_site.py\n")
    raise SystemExit(2)

try:
    from markdown.extensions.toc import slugify_unicode as _slugify
except ImportError:  # older markdown
    _slugify = None

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = REPO_ROOT / "site"
DEFAULT_REPO_URL = "https://github.com/pon00050/newsmon"
DEFAULT_SITE_URL = "https://pon00050.github.io/newsmon/"
OG_IMAGE = ("social/og-queue-1.png", 1200, 630)  # bump the number when the image changes: link previews cache by URL

SCHEMA = "newsmon-public/1"
BANDS = ("flash", "report", "review", "drop")
PUBLIC_LEVELS = ("headline", "metadata")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MAX_ASSET_BYTES = 5 * 1024 * 1024

NAV = [  # key, label, href (relative to site root)
    ("home", "Home", "index.html"),
    ("download", "Download", "download.html"),
    ("docs", "Docs", "docs/index.html"),
    ("research", "Research", "research/index.html"),
    ("dashboard", "Dashboard", "dashboard.html"),
]

# Site chrome per page language. Only the landing page has a Korean version; the other pages are English.
UI = {
    "en": {
        "locale": "en_US", "home": "index.html", "skip": "Skip to content", "nav": NAV,
        "switch": ("한국어", "ko/index.html", "ko"),
        "footer_links": ("Source repository", "Report an issue", "Releases"),
        "footer_notes": (
            "Software: Apache License 2.0. Research documents and synthetic demo data: CC BY 4.0. "
            "News headlines on the live dashboard remain the publishers' and link to them.",
            "This site is static: no cookies, no analytics, no third-party scripts or fonts. Version {version}."),
    },
    "ko": {
        "locale": "ko_KR", "home": "ko/index.html", "skip": "본문으로 건너뛰기",
        "nav": [("home", "홈", "ko/index.html"), ("download", "내려받기", "download.html"),
                ("docs", "문서", "docs/index.html"), ("research", "연구 자료", "research/index.html"),
                ("dashboard", "대시보드", "dashboard.html")],
        "switch": ("English", "index.html", "en"),
        "footer_links": ("소스 저장소", "이슈 등록", "릴리스"),
        "footer_notes": (
            "소프트웨어는 Apache License 2.0, 연구 문서와 합성 데모 데이터는 CC BY 4.0을 따릅니다. "
            "실시간 대시보드의 기사 제목은 각 언론사의 것이며, 제목을 누르면 원문으로 이동합니다.",
            "이 사이트는 정적 페이지로만 이루어져 있습니다. 쿠키, 방문 분석, 외부 스크립트, 외부 웹폰트를 쓰지 않습니다. 버전 {version}."),
    },
}
KO_TITLE = "Newsmon: 외신 모니터링, 뉴스 모니터링 프로그램 (무료 설치형)"
KO_DESCRIPTION = ("외신 모니터링, 뉴스 모니터링을 내 PC 한 대에서. RSS 수집, 통신사 기사 파일, 중복 기사 제거, 규칙 기반 등급 분류, "
                  "한국어 검색, 키워드 알림을 지원하는 무료 설치형 프로그램입니다.")
# The page that exists in both languages: each version lists both (and x-default) as alternates.
ALTERNATES = {"en": "index.html", "ko": "ko/index.html"}
VERIFY_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,100}$")


class BuildError(Exception):
    """A page could not be generated or an input broke its contract."""


# --------------------------------------------------------------------------------------------------------------------
# Data contract
# --------------------------------------------------------------------------------------------------------------------

def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float("inf"), float("-inf"))


def _is_iso(v) -> bool:
    if not isinstance(v, str) or not v:
        return False
    try:
        dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_http_url(v) -> bool:
    if not isinstance(v, str) or not v or any(c.isspace() for c in v):
        return False
    u = urlsplit(v)
    return u.scheme in ("http", "https") and bool(u.netloc)


def validate_dashboard(obj, name: str) -> list[str]:
    """Return a list of contract violations (empty list means the file is valid)."""
    errs: list[str] = []

    def err(path: str, msg: str) -> None:
        errs.append(f"{name}: {path}: {msg}")

    if not isinstance(obj, dict):
        return [f"{name}: top level must be an object"]

    def need(d: dict, key: str, path: str):
        if key not in d:
            err(path, f"missing '{key}'")
            return None
        return d[key]

    if obj.get("schema") != SCHEMA:
        err("schema", f"must be {SCHEMA!r}, got {obj.get('schema')!r}")
    dataset = obj.get("dataset")
    if dataset not in ("synthetic", "live"):
        err("dataset", f"must be 'synthetic' or 'live', got {dataset!r}")
    stem = Path(name).stem
    if stem in ("synthetic", "live") and dataset != stem:
        err("dataset", f"file {name} must declare dataset {stem!r}, got {dataset!r}")
    if not _is_iso(obj.get("generated_utc")):
        err("generated_utc", "must be an ISO-8601 timestamp")
    for key in ("newsmon_version", "notice"):
        if not isinstance(obj.get(key), str):
            err(key, "must be a string")
    prof = obj.get("profile")
    if not isinstance(prof, dict) or not isinstance(prof.get("key"), str) or not isinstance(prof.get("name"), str):
        err("profile", "must be an object with string 'key' and 'name'")

    # sources
    source_keys: dict[str, dict] = {}
    sources = obj.get("sources")
    if not isinstance(sources, list):
        err("sources", "must be a list")
        sources = []
    for i, s in enumerate(sources):
        p = f"sources[{i}]"
        if not isinstance(s, dict):
            err(p, "must be an object")
            continue
        for k in ("key", "name", "basis", "last_status"):
            if not isinstance(s.get(k), str) or not s.get(k):
                err(f"{p}.{k}", "must be a non-empty string")
        if s.get("public_level") not in PUBLIC_LEVELS:
            err(f"{p}.public_level", f"must be one of {PUBLIC_LEVELS}, got {s.get('public_level')!r}")
        bu = need(s, "basis_url", p)
        if bu is not None and not _is_http_url(bu):
            err(f"{p}.basis_url", "must be an http(s) URL or null")
        att = need(s, "attribution", p)
        if att is not None and not isinstance(att, str):
            err(f"{p}.attribution", "must be a string or null")
        if not _is_int(s.get("items")) or s.get("items", -1) < 0:
            err(f"{p}.items", "must be a non-negative integer")
        ls = need(s, "last_success_utc", p)
        if ls is not None and not _is_iso(ls):
            err(f"{p}.last_success_utc", "must be an ISO-8601 timestamp or null")
        key = s.get("key")
        if isinstance(key, str):
            if key in source_keys:
                err(f"{p}.key", f"duplicate source key {key!r}")
            source_keys[key] = s
        if dataset == "live" and s.get("public_level") == "headline" and bu is None:
            err(f"{p}.basis_url", "a live source that publishes headlines must link its redistribution basis")

    # stats
    stats = obj.get("stats")
    if not isinstance(stats, dict):
        err("stats", "must be an object")
        stats = {}
    for k in ("items", "duplicates_collapsed"):
        if not _is_int(stats.get(k)) or stats.get(k, -1) < 0:
            err(f"stats.{k}", "must be a non-negative integer")
    for k in ("by_band", "by_lang", "by_source", "by_topic"):
        m = stats.get(k)
        if not isinstance(m, dict):
            err(f"stats.{k}", "must be an object of integer counts")
            continue
        for mk, mv in m.items():
            if not _is_int(mv) or mv < 0:
                err(f"stats.{k}.{mk}", "count must be a non-negative integer")
        if k == "by_band":
            for mk in m:
                if mk not in BANDS:
                    err("stats.by_band", f"unknown band {mk!r}")
        if k == "by_source":
            for mk in m:
                if mk not in source_keys:
                    err("stats.by_source", f"unknown source key {mk!r}")

    # items
    items = obj.get("items")
    if not isinstance(items, list):
        err("items", "must be a list")
        items = []
    seen_uid: set[str] = set()
    for i, it in enumerate(items):
        p = f"items[{i}]"
        if not isinstance(it, dict):
            err(p, "must be an object")
            continue
        uid = it.get("uid")
        if not isinstance(uid, str) or not uid:
            err(f"{p}.uid", "must be a non-empty string")
        elif uid in seen_uid:
            err(f"{p}.uid", f"duplicate uid {uid!r}")
        else:
            seen_uid.add(uid)
        sk = it.get("source_key")
        if not isinstance(sk, str) or sk not in source_keys:
            err(f"{p}.source_key", f"must name a declared source, got {sk!r}")
        if not isinstance(it.get("source_name"), str) or not it.get("source_name"):
            err(f"{p}.source_name", "must be a non-empty string")
        for k in ("lang", "headline"):
            v = need(it, k, p)
            if v is not None and not isinstance(v, str):
                err(f"{p}.{k}", "must be a string or null")
        pub = need(it, "published_utc", p)
        if pub is not None and not _is_iso(pub):
            err(f"{p}.published_utc", "must be an ISO-8601 timestamp or null")
        if not _is_iso(it.get("first_seen_utc")):
            err(f"{p}.first_seen_utc", "must be an ISO-8601 timestamp")
        link = need(it, "link", p)
        if link is not None and not _is_http_url(link):
            err(f"{p}.link", f"must be an http(s) URL or null, got {link!r}")
        if it.get("band") not in BANDS:
            err(f"{p}.band", f"must be one of {BANDS}, got {it.get('band')!r}")
        if not _is_num(it.get("score")):
            err(f"{p}.score", "must be a finite number")
        for k in ("topics", "entities"):
            v = it.get(k)
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                err(f"{p}.{k}", "must be a list of strings")
        if not _is_int(it.get("duplicates")) or it.get("duplicates", -1) < 0:
            err(f"{p}.duplicates", "must be a non-negative integer")
        if not isinstance(it.get("synthetic"), bool):
            err(f"{p}.synthetic", "must be a boolean")
        elif dataset == "synthetic" and it["synthetic"] is not True:
            err(f"{p}.synthetic", "every item in a synthetic dataset must have synthetic=true")
        elif dataset == "live" and it["synthetic"] is not False:
            err(f"{p}.synthetic", "no item in a live dataset may have synthetic=true")
        if dataset == "live" and isinstance(sk, str) and sk in source_keys:
            if source_keys[sk].get("public_level") == "metadata" and it.get("headline") is not None:
                err(f"{p}.headline", "source has public_level 'metadata': the headline must be null in a live dataset")
    return errs


# --------------------------------------------------------------------------------------------------------------------
# Templating
# --------------------------------------------------------------------------------------------------------------------

_VAR = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def render_template(text: str, values: dict[str, str], where: str) -> str:
    """Single-pass {{name}} substitution. Names ending in _html are inserted raw, all others are escaped."""

    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            raise BuildError(f"{where}: unknown template variable {{{{{key}}}}}")
        val = str(values[key])
        return val if key.endswith("_html") else html.escape(val, quote=True)

    return _VAR.sub(sub, text)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BuildError(f"cannot read {path}: {exc}") from exc


# --------------------------------------------------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------------------------------------------------

_FRONT = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.S)
_H1 = re.compile(r"^#[ \t]+(.+?)[ \t#]*$", re.M)
_LINK = re.compile(r"\[([^\]\n]+)\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


def strip_front_matter(text: str) -> tuple[str, dict[str, str]]:
    m = _FRONT.match(text)
    if not m:
        return text.lstrip("﻿"), {}
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip().strip("'\"")
    return text[m.end():], meta


def plain(s: str) -> str:
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[`*_~]", "", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def short_label(text: str, limit: int = 56) -> str:
    """Sidebar label: cut long titles at the first natural break, else at a word boundary."""
    if len(text) <= limit:
        return text
    for sep in (": ", " — ", " (", " · "):
        head = text.split(sep, 1)[0]
        if 14 <= len(head) <= limit and head != text:
            return head
    cut = text[:limit].rsplit(" ", 1)[0] if " " in text[:limit] else text[:limit]
    return cut.rstrip(" ,;:-") + "…"


def md_out_path(src_rel: str) -> str:
    """docs/a/README.md -> docs/a/index.html ; docs/a/b.md -> docs/a/b.html"""
    d, base = posixpath.split(src_rel)
    stem = base[:-3]
    return posixpath.join(d, "index.html" if stem.lower() == "readme" else stem + ".html")


def rel_url(from_out: str, to_out: str) -> str:
    start = posixpath.dirname(from_out) or "."
    return quote(posixpath.relpath(to_out, start), safe="/#%")


class LinkFixer(Treeprocessor):
    """Rewrite or neutralise every href/src. Runs on the parsed tree, after raw HTML has been disabled."""

    def __init__(self, md, ctx: "PageContext"):
        super().__init__(md)
        self.ctx = ctx

    def run(self, root):
        for el in root.iter():
            if el.tag == "a" and "href" in el.attrib:
                new = self.ctx.fix_url(el.get("href", ""), image=False)
                if new is None:
                    del el.attrib["href"]
                    el.set("title", "link removed: unsupported or unresolved target")
                else:
                    el.set("href", new)
                    if new.startswith(("http://", "https://")):
                        el.set("rel", "noopener noreferrer")
            elif el.tag == "img":
                new = self.ctx.fix_url(el.get("src", ""), image=True)
                if new is None:
                    el.tag = "span"
                    el.attrib.clear()
                    el.text = "[image omitted]"
                else:
                    el.set("src", new)
                    el.set("loading", "lazy")
        return root


class SafeLinks(Extension):
    def __init__(self, ctx: "PageContext"):
        super().__init__()
        self.ctx = ctx

    def extendMarkdown(self, md):
        # Raw HTML is switched off: tags in the source are treated as text and escaped on output.
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")
        md.treeprocessors.register(LinkFixer(md, self.ctx), "newsmon_links", 5)


class PageContext:
    """Everything the link rewriter needs to know about the page being rendered."""

    def __init__(self, src_rel: str, builder: "Site"):
        self.src_rel = src_rel
        self.out_rel = md_out_path(src_rel)
        self.b = builder

    def fix_url(self, url: str, image: bool) -> str | None:
        url = url.strip()
        if not url:
            return None
        u = urlsplit(url)
        if u.scheme:
            if u.scheme in ("http", "https") and u.netloc:
                return url
            if u.scheme == "mailto" and not image:
                return url
            return None
        if u.netloc:
            return None
        if not u.path:  # '#fragment' or '?query'
            return url if not image else None
        frag = ("#" + quote(unquote(u.fragment), safe="-_.~%")) if u.fragment else ""
        src_dir = posixpath.dirname(self.src_rel)
        target = posixpath.normpath(posixpath.join(src_dir, unquote(u.path)))
        if target.startswith("..") or posixpath.isabs(target):
            self.b.warn(f"{self.src_rel}: link leaves the repository: {url}")
            return None
        if target in self.b.md_pages:
            return rel_url(self.out_rel, self.b.md_pages[target]) + frag
        if target in self.b.virtual_pages:
            return rel_url(self.out_rel, self.b.virtual_pages[target]) + frag
        if target in self.b.assets:
            return rel_url(self.out_rel, target)
        full = self.b.repo_root / target
        if full.exists():
            kind = "tree" if full.is_dir() else "blob"
            return f"{self.b.repo_url}/{kind}/main/{quote(target, safe='/')}{frag}"
        self.b.warn(f"{self.src_rel}: unresolved link: {url}")
        if self.b.strict_links:
            self.b.fail(f"{self.src_rel}: unresolved link: {url}")
        return None


def make_markdown(ctx: PageContext) -> "markdown.Markdown":
    cfg = {"toc": {"anchorlink": False, "permalink": False}}
    if _slugify:
        cfg["toc"]["slugify"] = _slugify
    return markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "toc", "footnotes", "def_list", "abbr", SafeLinks(ctx)],
        extension_configs=cfg,
        output_format="html",
    )


def wrap_tables(html_text: str) -> str:
    html_text = html_text.replace("<table>", '<div class="table-wrap"><table>')
    return html_text.replace("</table>", "</table></div>")


# --------------------------------------------------------------------------------------------------------------------
# Site builder
# --------------------------------------------------------------------------------------------------------------------

class Site:
    def __init__(self, args):
        self.out = Path(args.out).resolve()
        self.data_dir = Path(args.data).resolve()
        self.repo_root = Path(args.repo_root).resolve()
        self.site_src = Path(args.site_src).resolve()
        self.repo_url = args.repo_url.rstrip("/")
        self.site_url = args.site_url.rstrip("/") + "/"
        self.verify = {"naver-site-verification": args.naver_verification or "",
                       "google-site-verification": args.google_verification or ""}
        self.version = args.version
        self.strict_links = args.strict_links
        self.warnings: list[str] = []
        self.failures: list[str] = []
        self.md_pages: dict[str, str] = {}    # source rel path -> output rel path
        self.assets: set[str] = set()         # copied image assets (repo-relative == output-relative)
        self.virtual_pages: dict[str, str] = {}  # section README that does not exist -> generated index page
        self.sections: dict[str, list[dict]] = {}
        self.page_list: list[str] = []
        self.base = read_text(self.site_src / "templates" / "base.html")

    # -- bookkeeping --
    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    # -- output --
    def write(self, out_rel: str, text: str) -> None:
        path = self.out / out_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        self.page_list.append(out_rel)

    def nav_html(self, current: str, root: str, lang: str = "en") -> str:
        ui = UI[lang]
        parts = ["<ul>"]
        for key, label, href in ui["nav"]:
            cur = ' aria-current="page"' if key == current else ""
            parts.append(f'<li><a href="{root}{href}"{cur}>{html.escape(label)}</a></li>')
        parts.append(f'<li><a href="{html.escape(self.repo_url, quote=True)}" rel="noopener">GitHub</a></li>')
        label, href, code = ui["switch"]
        parts.append(f'<li><a href="{root}{href}" hreflang="{code}" lang="{code}">{html.escape(label)}</a></li>')
        parts.append("</ul>")
        return "\n      ".join(parts)

    def url(self, out_rel: str) -> str:
        """Absolute URL of a page, in directory form for index pages (one URL per page for canonical and previews)."""
        if out_rel == "index.html" or out_rel.endswith("/index.html"):
            out_rel = out_rel[: -len("index.html")]
        return self.site_url + quote(out_rel, safe="/")

    def head_html(self, out_rel: str, title: str, description: str, lang: str) -> str:
        def e(v: str) -> str:
            return html.escape(v, quote=True)

        img, w, h = OG_IMAGE
        bilingual = out_rel in ALTERNATES.values()
        tags = [f'<link rel="canonical" href="{e(self.url(out_rel))}">']
        if bilingual:
            tags += [f'<link rel="alternate" hreflang="{c}" href="{e(self.url(alt))}">' for c, alt in ALTERNATES.items()]
            tags.append(f'<link rel="alternate" hreflang="x-default" href="{e(self.url(ALTERNATES["en"]))}">')
        tags += [
            '<meta property="og:type" content="website">',
            '<meta property="og:site_name" content="Newsmon">',
            f'<meta property="og:title" content="{e(title)}">',
            f'<meta property="og:description" content="{e(description)}">',
            f'<meta property="og:url" content="{e(self.url(out_rel))}">',
            f'<meta property="og:image" content="{e(self.site_url + img)}">',
            f'<meta property="og:image:width" content="{w}">',
            f'<meta property="og:image:height" content="{h}">',
            f'<meta property="og:locale" content="{UI[lang]["locale"]}">',
        ]
        if bilingual:
            tags += [f'<meta property="og:locale:alternate" content="{UI[c]["locale"]}">' for c in ALTERNATES if c != lang]
        tags.append('<meta name="twitter:card" content="summary_large_image">')
        tags += [f'<meta name="{k}" content="{e(v)}">' for k, v in self.verify.items() if v]
        return "\n".join(tags)

    def footer_html(self, lang: str) -> str:
        ui = UI[lang]
        repo = html.escape(self.repo_url, quote=True)
        items = "".join(f'<li><a href="{repo}{path}" rel="noopener">{html.escape(text)}</a></li>'
                        for text, path in zip(ui["footer_links"], ("", "/issues", "/releases")))
        notes = "".join(f"<p>{html.escape(n.format(version=self.version))}</p>" for n in ui["footer_notes"])
        return f'<footer class="site-footer">\n  <div class="wrap">\n    <ul>{items}</ul>\n    {notes}\n  </div>\n</footer>'

    def page(self, out_rel: str, title: str, description: str, content_html: str, current: str,
             scripts: list[str] | None = None, lang: str = "en") -> None:
        root = "../" * out_rel.count("/")
        scripts_html = "\n".join(f'<script src="{root}{s}" defer></script>' for s in (scripts or []))
        full_title = title if title.startswith("Newsmon") else f"{title} | Newsmon"
        values = {
            "title": full_title, "lang": lang, "skip_label": UI[lang]["skip"], "home_href": UI[lang]["home"],
            "head_html": self.head_html(out_rel, full_title, description, lang), "footer_html": self.footer_html(lang),
            "description": description, "root": root, "version": self.version, "repo_url": self.repo_url,
            "nav_html": self.nav_html(current, root, lang), "content_html": content_html, "scripts_html": scripts_html,
        }
        self.write(out_rel, render_template(self.base, values, out_rel))

    def write_sitemap(self) -> None:
        """sitemap.xml, for submitting the site by hand to Google Search Console or Naver Search Advisor. No lastmod: the
        site is rebuilt every few hours, so a build time would claim changes that did not happen."""
        urls = "".join(f"  <url><loc>{html.escape(self.url(p))}</loc></url>\n"
                       for p in sorted(self.page_list) if p.endswith(".html"))
        (self.out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + urls + "</urlset>\n", encoding="utf-8", newline="\n")

    def body(self, name: str, root: str) -> str:
        text = read_text(self.site_src / "templates" / name)
        return render_template(text, {"root": root, "repo_url": self.repo_url, "version": self.version}, name)

    # -- steps --
    def copy_static(self) -> None:
        for sub in ("css", "js"):
            src = self.site_src / sub
            if not src.is_dir():
                raise BuildError(f"missing {src}")
            shutil.copytree(src, self.out / sub, dirs_exist_ok=True)
        static = self.site_src / "static"
        if static.is_dir():
            shutil.copytree(static, self.out, dirs_exist_ok=True)
        (self.out / ".nojekyll").write_text("", encoding="utf-8")

    def validate_data(self) -> list[Path]:
        files = sorted(self.data_dir.glob("*.json")) if self.data_dir.is_dir() else []
        if not files:
            raise BuildError(f"no dashboard JSON found in {self.data_dir} (expected at least synthetic.json)")
        problems: list[str] = []
        names: list[str] = []
        for f in files:
            try:
                obj = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                problems.append(f"{f.name}: not valid UTF-8 JSON: {exc}")
                continue
            problems.extend(validate_dashboard(obj, f.name))
            names.append(f.name)
        if "synthetic.json" not in names:
            problems.append("synthetic.json is missing from the data folder")
        if problems:
            raise BuildError("dashboard data fails the newsmon-public/1 contract:\n  " + "\n  ".join(problems[:60])
                             + (f"\n  ... and {len(problems) - 60} more" if len(problems) > 60 else ""))
        return files

    def copy_data(self, files: list[Path]) -> list[str]:
        (self.out / "data").mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copyfile(f, self.out / "data" / f.name)
        return [f.name for f in files]

    def scan_section(self, name: str) -> None:
        base = self.repo_root / name
        entries: list[dict] = []
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                rel_parts = p.relative_to(self.repo_root).parts
                if any(part.startswith(".") for part in rel_parts) or not p.is_file():
                    continue
                rel = "/".join(rel_parts)
                if p.suffix.lower() == ".md":
                    out = md_out_path(rel)
                    if out in self.md_pages.values():
                        raise BuildError(f"two sources map to the same page {out}: {rel}")
                    self.md_pages[rel] = out
                    entries.append({"src": rel, "out": out})
                elif p.suffix.lower() in IMAGE_EXTS and p.stat().st_size <= MAX_ASSET_BYTES:
                    self.assets.add(rel)
        self.sections[name] = entries
        if f"{name}/README.md" not in self.md_pages:
            self.virtual_pages[f"{name}/README.md"] = f"{name}/index.html"

    def render_md_page(self, entry: dict, section: str) -> None:
        src = self.repo_root / entry["src"]
        text, meta = strip_front_matter(read_text(src))
        m = _H1.search(text)
        entry["title"] = plain(m.group(1)) if m else (meta.get("title") or Path(entry["src"]).stem.replace("_", " "))
        entry["text"] = text
        entry["meta"] = meta

    def build_markdown_section(self, name: str, label: str, blurb: str) -> None:
        entries = self.sections[name]
        for e in entries:
            self.render_md_page(e, name)
        index_src = f"{name}/README.md"
        have_index = index_src in self.md_pages
        order = self.ordered_entries(name, index_src if have_index else None)
        for e in entries:
            ctx = PageContext(e["src"], self)
            md = make_markdown(ctx)
            try:
                body = wrap_tables(md.convert(e["text"]))
            except Exception as exc:  # noqa: BLE001 - surface any renderer failure as a build failure
                raise BuildError(f"cannot render {e['src']}: {exc}") from exc
            view = f"{self.repo_url}/blob/main/{quote(e['src'], safe='/')}"
            body += f'<p class="src-link"><a href="{html.escape(view, quote=True)}" rel="noopener">View this file on GitHub</a></p>'
            side = self.sidenav(name, label, order, e["out"], have_index)
            content = f'<div class="doc-layout">{side}<article class="prose">{body}</article></div>'
            self.page(e["out"], e["title"], f"{e['title']} ({label.lower()})", content, name, ["js/site.js"])
        if not have_index:
            self.write_generated_index(name, label, blurb, order)
        self.copy_assets(name)

    def ordered_entries(self, name: str, index_src: str | None) -> list[dict]:
        """README link order first (labels from the README), then everything else by path."""
        entries = {e["src"]: e for e in self.sections[name]}
        ordered: list[dict] = []
        seen: set[str] = set()
        if index_src:
            text = entries[index_src]["text"]
            base_dir = posixpath.dirname(index_src)
            for m in _LINK.finditer(text):
                target = urlsplit(m.group(2))
                if target.scheme or target.netloc or not target.path:
                    continue
                key = posixpath.normpath(posixpath.join(base_dir, unquote(target.path)))
                if key in entries and key != index_src and key not in seen:
                    seen.add(key)
                    label = plain(m.group(1))
                    if label.lower().endswith(".md") or "/" in label:  # a bare file path is a poor label
                        label = entries[key]["title"]
                    ordered.append({"src": key, "out": entries[key]["out"], "label": label, "linked": True})
        for src in sorted(entries):
            if src == index_src or src in seen:
                continue
            ordered.append({"src": src, "out": entries[src]["out"], "label": entries[src]["title"], "linked": False})
        return ordered

    def sidenav(self, name: str, label: str, order: list[dict], current_out: str, have_index: bool) -> str:
        here = posixpath.dirname(current_out) or "."

        def link(out: str, text: str) -> str:
            cur = ' aria-current="page"' if out == current_out else ""
            href = quote(posixpath.relpath(out, here), safe="/")
            short = short_label(text)
            tip = f' title="{html.escape(text, quote=True)}"' if short != text else ""
            return f'<li><a href="{href}"{cur}{tip}>{html.escape(short)}</a></li>'

        index_out = f"{name}/index.html"
        parts = [f'<details class="sidenav" open><summary>{html.escape(label)} contents</summary>',
                 f'<nav aria-label="{html.escape(label)}"><ul>', link(index_out, "Overview"), "</ul>"]
        linked = [o for o in order if o["linked"]]
        rest = [o for o in order if not o["linked"]]
        if linked:
            parts.append("<ul>" + "".join(link(o["out"], o["label"]) for o in linked) + "</ul>")
        if rest:
            groups: dict[str, list[dict]] = {}
            for o in rest:
                folder = posixpath.dirname(o["src"])[len(name) + 1:] or "Other documents"
                groups.setdefault(folder, []).append(o)
            for folder in sorted(groups, key=lambda f: (f != "Other documents", f)):
                parts.append(f"<h3>{html.escape(folder)}</h3><ul>"
                             + "".join(link(o["out"], o["label"]) for o in groups[folder]) + "</ul>")
        parts.append("</nav></details>")
        return "".join(parts)

    def write_generated_index(self, name: str, label: str, blurb: str, order: list[dict]) -> None:
        out = f"{name}/index.html"
        if order:
            items = "".join(
                f'<li><a href="{quote(posixpath.relpath(o["out"], name), safe="/")}">{html.escape(o["label"])}</a></li>'
                for o in order)
            body = f"<h1>{html.escape(label)}</h1><p>{html.escape(blurb)}</p><ul>{items}</ul>"
            side = self.sidenav(name, label, order, out, False)
            content = f'<div class="doc-layout">{side}<article class="prose">{body}</article></div>'
        else:
            body = (f"<h1>{html.escape(label)}</h1><p>{html.escape(blurb)}</p>"
                    f'<div class="notice"><p>Nothing is published in this section yet. '
                    f'Follow progress in the <a href="{html.escape(self.repo_url, quote=True)}" rel="noopener">repository</a>.</p></div>')
            content = f'<div class="prose">{body}</div>'
        self.page(out, label, blurb, content, name, ["js/site.js"])

    def copy_assets(self, name: str) -> None:
        for rel in sorted(a for a in self.assets if a.startswith(name + "/")):
            dest = self.out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.repo_root / rel, dest)

    def build(self) -> None:
        data_files = self.validate_data()  # contract check first: a bad data file must not touch the output folder
        if self.out.exists():
            # Only ever clear a directory this script produced.
            if any(self.out.iterdir()) and not (self.out / ".nojekyll").exists():
                raise BuildError(f"{self.out} exists, is not empty and has no .nojekyll: refusing to overwrite it")
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        self.copy_static()
        names = self.copy_data(data_files)

        root = ""
        self.page("index.html", "Newsmon",
                  "Local news monitoring for foreign-news desks: licensed feeds, deduplication, rule-based ranking, a searchable local queue.",
                  self.body("index.body.html", root), "home")
        self.page("ko/index.html", KO_TITLE, KO_DESCRIPTION, self.body("ko.index.body.html", "../"), "home", lang="ko")
        self.page("download.html", "Download", "Download Newsmon: Windows launcher, standalone executable, or install from source.",
                  self.body("download.body.html", root), "download")
        self.page("dashboard.html", "Dashboard",
                  "Public dashboard of Newsmon output: collection statistics, source coverage and a searchable item list.",
                  self.body("dashboard.body.html", root), "dashboard", ["js/dashboard.js"])

        # Scan both sections first so links between docs/ and research/ resolve.
        for name in ("docs", "research"):
            self.scan_section(name)
        self.build_markdown_section("docs", "Documentation", "How to install, configure and operate Newsmon.")
        self.build_markdown_section("research", "Research", "The research and decisions behind Newsmon's design.")

        if self.failures:
            raise BuildError("\n".join(self.failures))
        self.write_sitemap()
        print(f"built {len(self.page_list)} pages into {self.out}")
        for p in sorted(self.page_list):
            print("  " + p)
        print(f"data files: {', '.join(names)}")
        for w in self.warnings:
            print(f"warning: {w}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="_site", help="output directory (default: _site)")
    ap.add_argument("--data", default=str(SITE_SRC / "sample-data"),
                    help="folder with dashboard JSON files (default: site/sample-data)")
    ap.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    ap.add_argument("--version", default=None, help="Newsmon version shown on the site (default: from pyproject.toml)")
    ap.add_argument("--repo-root", default=str(REPO_ROOT), help="folder holding docs/ and research/ (default: this repo)")
    ap.add_argument("--site-src", default=str(SITE_SRC), help="folder holding templates, css, js (default: site/)")
    ap.add_argument("--site-url", default=DEFAULT_SITE_URL,
                    help="public URL of the site, for canonical links, link previews and sitemap.xml (default: %(default)s)")
    ap.add_argument("--naver-verification", default=os.environ.get("NEWSMON_NAVER_VERIFICATION", ""),
                    help="Naver Search Advisor meta-tag token (default: $NEWSMON_NAVER_VERIFICATION)")
    ap.add_argument("--google-verification", default=os.environ.get("NEWSMON_GOOGLE_VERIFICATION", ""),
                    help="Google Search Console meta-tag token (default: $NEWSMON_GOOGLE_VERIFICATION)")
    ap.add_argument("--strict-links", action="store_true", help="fail on unresolved relative links in markdown")
    args = ap.parse_args(argv)
    if not _is_http_url(args.repo_url):
        ap.error("--repo-url must be an http(s) URL")
    if not _is_http_url(args.site_url):
        ap.error("--site-url must be an http(s) URL")
    for name in ("naver_verification", "google_verification"):
        if getattr(args, name) and not VERIFY_TOKEN.match(getattr(args, name)):
            ap.error(f"--{name.replace('_', '-')} must be letters, digits, '-' or '_'")
    if args.version is None:
        pp = Path(args.repo_root) / "pyproject.toml"
        m = re.search(r'^version\s*=\s*"([^"]+)"', pp.read_text(encoding="utf-8"), re.M) if pp.is_file() else None
        args.version = m.group(1) if m else "0.1.0"
    try:
        Site(args).build()
    except BuildError as exc:
        print(f"BUILD FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"BUILD FAILED (unexpected {type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
