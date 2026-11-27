"""The website build: Korean landing page, one canonical URL per page, hreflang pair, link previews and sitemap."""
import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytest.importorskip("markdown")

ROOT = Path(__file__).resolve().parents[2]
SITE = "https://example.org/newsmon/"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path_factory.mktemp("site") / "_site"
    assert mod.main(["--out", str(out), "--site-url", SITE, "--naver-verification", "abc_123"]) == 0
    return out


def head(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text[: text.index("</head>")]


def test_korean_landing_page_is_korean_and_canonical_to_itself(site):
    h = head(site / "ko" / "index.html")
    assert '<html lang="ko">' in h
    assert f'<link rel="canonical" href="{SITE}ko/">' in h
    assert f'<meta property="og:url" content="{SITE}ko/">' in h
    assert '<meta property="og:locale" content="ko_KR">' in h
    assert re.search(r"<title>[^<]*[가-힣][^<]*</title>", h)


def test_both_landing_pages_list_the_same_alternates(site):
    want = [f'hreflang="en" href="{SITE}"', f'hreflang="ko" href="{SITE}ko/"', f'hreflang="x-default" href="{SITE}"']
    for page in ("index.html", "ko/index.html"):
        h = head(site / page)
        assert all(w in h for w in want), page


def test_english_pages_stay_english_and_only_landing_pages_have_alternates(site):
    h = head(site / "download.html")
    assert '<html lang="en">' in h and 'hreflang=' not in h
    assert f'<link rel="canonical" href="{SITE}download.html">' in h
    assert f'<link rel="canonical" href="{SITE}docs/">' in head(site / "docs" / "index.html")


def test_link_preview_image_exists_and_verification_tag_is_optional(site):
    h = head(site / "index.html")
    m = re.search(r'<meta property="og:image" content="([^"]+)">', h)
    assert m and m.group(1).startswith(SITE)
    assert (site / m.group(1)[len(SITE):]).is_file()
    assert '<meta name="naver-site-verification" content="abc_123">' in h
    assert "google-site-verification" not in h  # not configured, so not emitted


def test_korean_page_assets_resolve(site):
    page = site / "ko" / "index.html"
    for src in re.findall(r'(?:src|href)="(\.\./[^"#]+)"', page.read_text(encoding="utf-8")):
        assert (page.parent / src).resolve().is_file(), src


def test_sitemap_lists_every_page_once_in_directory_form(site):
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in ET.parse(site / "sitemap.xml").getroot().findall("s:url/s:loc", ns)]
    assert len(locs) == len(set(locs))
    assert SITE in locs and f"{SITE}ko/" in locs
    assert not [u for u in locs if u.endswith("/index.html")]
    assert ET.parse(site / "sitemap.xml").getroot().find("s:url/s:lastmod", ns) is None
