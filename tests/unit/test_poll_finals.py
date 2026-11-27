"""poll_finals: one entry per poll, however many retried attempts it wrote (status-page streak and feed incidents)."""
from newsmon.repo.sources import poll_finals


def rows(*attempts):
    """fetch_run-like rows, newest first, given each row's attempt number."""
    return [{"attempt": a, "i": i} for i, a in enumerate(attempts)]


def test_single_attempt_polls_are_each_a_poll():
    assert [r["i"] for r in poll_finals(rows(1, 1, 1))] == [0, 1, 2]


def test_a_retried_poll_counts_once():
    # newest first: poll B (attempts 3, 2, 1), poll A (attempts 3, 2, 1)
    assert [r["i"] for r in poll_finals(rows(3, 2, 1, 3, 2, 1))] == [0, 3]


def test_mixed_polls():
    # newest first: a single-attempt poll, a two-attempt poll, a three-attempt poll
    assert [r["i"] for r in poll_finals(rows(1, 2, 1, 3, 2, 1))] == [0, 1, 3]


def test_empty():
    assert poll_finals([]) == []
