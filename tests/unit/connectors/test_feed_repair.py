"""The one feed repair: bare ampersands (a live Yonhap feed, 2026-11-27, published `?v=...&feature=...` in an attribute).
Everything else that is malformed stays refused."""
import pytest

from newsmon.connectors.feed import FeedParseError, parse_feed_bytes

RSS = (b'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">'
       b'<channel><title>Synthetic</title><link>http://example.invalid/</link><description>d</description>'
       b'<item><title>Item one</title><link>http://example.invalid/1</link><guid>g1</guid>'
       b'<media:content url="https://video.example.invalid/watch?v=abc&feature=share" medium="video"/></item>'
       b'<item><title>Fish &amp; chips &#38; more</title><link>http://example.invalid/2</link><guid>g2</guid></item>'
       b'</channel></rss>')


def test_bare_ampersand_in_an_attribute_is_repaired_and_marked():
    d = parse_feed_bytes(RSS)
    assert d.get("newsmon_repair") == "bare ampersand escaped"
    assert [e.title for e in d.entries] == ["Item one", "Fish & chips & more"]  # real entities are left alone


def test_a_valid_feed_is_not_marked_repaired():
    d = parse_feed_bytes(RSS.replace(b"&feature", b"&amp;feature"))
    assert d.get("newsmon_repair") is None and len(d.entries) == 2


def test_other_malformed_feeds_stay_refused():
    truncated = RSS[: RSS.index(b"</item>")]  # cut mid-document
    with pytest.raises(FeedParseError, match="malformed XML"):
        parse_feed_bytes(truncated)
    with pytest.raises(FeedParseError, match="malformed XML"):
        parse_feed_bytes(RSS.replace(b"</title><link>http://example.invalid/1", b"</titel><link>http://example.invalid/1"))
    with pytest.raises(FeedParseError, match="entity declaration"):
        parse_feed_bytes(b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x "&amp;">]>' + RSS[38:])


def test_cdata_and_comments_are_left_exactly_as_they_were():
    feed = RSS.replace(b"<title>Item one</title>", b"<title><![CDATA[AT&T & co]]></title><!-- a & b -->")
    d = parse_feed_bytes(feed)
    assert d.get("newsmon_repair") == "bare ampersand escaped"
    assert d.entries[0].title == "AT&T & co"  # not "AT&amp;T"


def test_utf16_documents_are_never_repaired():
    text = RSS.decode("utf-8").replace('encoding="UTF-8"', 'encoding="UTF-16"')
    with pytest.raises(FeedParseError, match="malformed XML"):  # refused, never silently corrupted
        parse_feed_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
