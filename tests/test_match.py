"""Unit tests for the match engine (src/match.py).

These cases ARE the project's definition of a GTM leadership-hire signal:
each one is a rule we agreed on, frozen so it can't silently drift. They run
offline - no network, no database - and only exercise the classification rule.

Run with:  python -m pytest tests/ -v
"""
import pytest

from src.match import classify, load_rule

RULE = load_rule()

# (title, department, expected label)
CASES = [
    # --- the core rule -------------------------------------------------------
    ("VP Marketing", "Marketing", "hit"),
    ("Head of Growth", "Growth", "hit"),
    ("Director of Growth", "Growth", "hit"),                 # Growth-only director rule
    ("Director of Marketing", "Marketing", "near_miss"),     # director, non-Growth
    ("CMO", "Marketing", "hit"),                             # abbreviation is senior
    ("VP Sales", "Sales", "hit"),
    ("Director of Sales", "Sales", "near_miss"),
    ("Marketing Manager", "Marketing", "near_miss"),         # right function, below seniority
    ("Account Executive", "Sales", "near_miss"),
    ("Growth Analyst", "Growth", "near_miss"),

    # --- ambiguity and conflict route to review ------------------------------
    ("Director of Growth Engineering", "Engineering", "review"),
    ("Director of Growth Engineering", "Growth", "review"),
    ("Director of Growth Engineering", None, "review"),
    ("Head of Growth Engineering", "Engineering", "review"),
    ("Head of Marketing Operations", "Marketing", "review"),
    ("Director of Marketing Operations", "Marketing", "review"),
    ("VP Marketing", "Engineering", "review"),               # conflict, not missing

    # --- clearly not a signal ------------------------------------------------
    ("VP of Engineering", "Engineering", "not_a_hit"),
    ("Data Scientist", "Engineering", "not_a_hit"),

    # --- a clear title needs no department -----------------------------------
    ("Head of GTM", None, "hit"),

    # --- normalisation / order-independence ----------------------------------
    ("Head of Growth", "Go-To-Market", "hit"),
    ("Head of Growth", "Go To Market", "hit"),
    ("Head of Growth", "go_to_market", "hit"),
    ("VP Marketing", "GTM", "hit"),
    ("VP, Marketing", "Marketing", "hit"),                   # punctuation in title
    ("Director of Growth", "Growth Marketing", "hit"),
    ("Director of Marketing", "Growth Marketing", "near_miss"),
]


@pytest.mark.parametrize("title, department, expected", CASES)
def test_classify(title, department, expected):
    assert classify(title, department, RULE) == expected


def test_department_spelling_is_equivalent():
    """The same department written three ways must classify identically."""
    variants = ["Go-To-Market", "Go To Market", "go_to_market", "GTM"]
    results = {classify("Head of Growth", v, RULE) for v in variants}
    assert results == {"hit"}


def test_department_order_does_not_matter():
    """'Growth Marketing' must not depend on which alias is listed first."""
    assert classify("Director of Growth", "Growth Marketing", RULE) == "hit"
    assert classify("Director of Marketing", "Growth Marketing", RULE) == "near_miss"


def test_short_abbreviation_does_not_fire_inside_a_word():
    """'cro' must not match inside 'Crowd'."""
    assert classify("Crowd Marketing Lead", "Marketing", RULE) != "hit"
