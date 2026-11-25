"""TS-ROB-01 (T-12): RFC 9309 matching table, including the '?' case urllib.robotparser gets wrong (control)."""
import urllib.robotparser

import pytest

from newsmon.fetcher.robots import is_allowed, parse_robots, rules_for

pytestmark = pytest.mark.unit
UA = "newsmon/0.1 (test)"

ROBOTS = """
User-agent: *
Disallow: /r?
Disallow: /private/
Allow: /private/ok
Disallow: /*.pdf$
Disallow: /tmp

User-agent: newsmon
Disallow: /only-us
"""


@pytest.mark.req("NFR-03")
@pytest.mark.parametrize("path,agent,expected", [
    ("/r?id=1", "other", False),          # '?' is literal: robotparser mishandles this rule
    ("/r", "other", True),
    ("/rss.xml", "other", True),
    ("/private/x", "other", False),
    ("/private/ok", "other", True),      # longer Allow wins
    ("/doc.pdf", "other", False),
    ("/doc.pdf?x=1", "other", True),     # '$' anchors the end
    ("/tmp/x", "other", False),
    ("/only-us", UA, False),             # our own group wins over '*'
    ("/r?id=1", UA, True),               # ...and replaces it entirely
])
def test_matching_table(path, agent, expected):
    groups = parse_robots(ROBOTS)
    assert is_allowed(rules_for(groups, agent), path) is expected


def test_tie_goes_to_allow():
    groups = parse_robots("User-agent: *\nDisallow: /a\nAllow: /a\n")
    assert is_allowed(rules_for(groups, "x"), "/a/b") is True


def test_robotparser_control_disagrees():
    """Known-answer control (R5, ACQUISITION_METHODS): the stdlib strips the trailing '?' from `Disallow: /r?` and so
    wrongly blocks /rss; RFC 9309 allows it."""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(ROBOTS.splitlines())
    stdlib_says = rp.can_fetch("other", "https://example.com/rss")
    ours = is_allowed(rules_for(parse_robots(ROBOTS), "other"), "/rss")
    assert ours is True
    if stdlib_says is True:  # Python 3.14 fixed the stdlib parser; the control no longer has a wrong answer to show
        pytest.skip("this Python's urllib.robotparser no longer has the '/r?' bug the control demonstrates")
    assert stdlib_says is False
