"""Match engine for Project 2: classify a job posting as a GTM leadership-hire signal.

This module holds the LOGIC. The terms it uses live in config/match_rule.json
(data). Text is normalised first, and term matching uses word boundaries.

Decision order (precision-first: uncertain cases go to review, never a silent hit):
  1. Department present but maps to NO GTM function, while the title names one
     -> conflict -> review
  2. Title and department name different GTM functions -> conflict -> review
  3. An ambiguous context word appears in a GTM leadership title -> review
  4. HIT requires the TITLE ITSELF to name a GTM function:
       - senior title + a GTM function in the title        -> hit
       - director + growth                                 -> hit
     The department can flag a conflict, but it can NOT create a hit on its own.
  5. Otherwise: a GTM function anywhere -> near_miss, else not_a_hit.
"""
import json
import re
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "match_rule.json"

HIT, NEAR_MISS, REVIEW, NOT_A_HIT = "hit", "near_miss", "review", "not_a_hit"


def load_rule(path=DEFAULT_CONFIG):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _norm_text(text):
    """Lowercase and reduce any non-alphanumeric run to a single space."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _has(text, phrase):
    """Whole-word/phrase match on already-normalised text."""
    return re.search(r"\b" + re.escape(phrase) + r"\b", text) is not None


def _seniority(title, rule):
    if any(_has(title, w) for w in rule["seniority"]["senior"]):
        return "senior"
    if any(_has(title, w) for w in rule["seniority"]["director"]):
        return "director"
    return "below"


def _first_title_term(title, rule):
    for term in rule["title_terms"]:
        if _has(title, term):
            return term
    return None


def _title_functions(title, rule):
    """Every GTM function the TITLE implies (function words + curated terms)."""
    funcs = set()
    for word, func in rule["gtm_function_words"].items():
        if _has(title, word):
            funcs.add(func)
    for term, func in rule["unambiguous_title_department"].items():
        if _has(title, term):
            funcs.add(func)
    return funcs


def _department_functions(dept, rule):
    """The set of GTM functions a department maps to (order-independent)."""
    dept_n = _norm_text(dept)
    if not dept_n:
        return frozenset()
    found = set()
    for func, aliases in rule["department_functions"].items():
        if any(_has(dept_n, alias) for alias in aliases):
            found.add(func)
    return frozenset(found)


def classify(title, department, rule):
    """Return one of: 'hit', 'near_miss', 'review', 'not_a_hit'."""
    title_l = _norm_text(title)
    dept_present = bool(_norm_text(department))

    seniority = _seniority(title_l, rule)
    title_term = _first_title_term(title_l, rule)
    title_funcs = _title_functions(title_l, rule)
    names_gtm = bool(title_term) or bool(title_funcs)
    has_ambiguous = any(_has(title_l, w) for w in rule["ambiguous_context_words"])

    dept_funcs = _department_functions(department, rule)

    # 1. Department present but not GTM, while the title names a GTM function -> conflict
    if dept_present and not dept_funcs and names_gtm:
        return REVIEW

    # 2. Title and department name different GTM functions -> conflict
    if dept_funcs and title_funcs and not (dept_funcs & title_funcs) and "gtm" not in dept_funcs:
        return REVIEW

    # 3. Ambiguous context word in a GTM leadership title -> review
    if has_ambiguous and names_gtm:
        return REVIEW

    # 4. A hit needs the TITLE to name a GTM function - the department can't create one
    if seniority == "senior" and names_gtm:
        return HIT
    if seniority == "director" and "growth" in title_funcs:
        return HIT

    # 5. Near-miss if a GTM function shows up anywhere, otherwise not a hit
    if title_funcs or dept_funcs:
        return NEAR_MISS
    return NOT_A_HIT
