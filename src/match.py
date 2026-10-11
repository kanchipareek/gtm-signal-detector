"""Match engine for Project 2: classify a job posting as a GTM leadership-hire signal.

This module holds the LOGIC. The terms it uses live in config/match_rule.json
(data). Keeping them apart means the rule can be changed without editing code,
and the detector and the labelled test set both read one source of truth.

Text is NORMALISED first (lowercased; any non-alphanumeric run becomes a single
space), so 'VP, Marketing' == 'vp marketing', and a department spelled
'Go-To-Market', 'go_to_market' or 'Go To Market' all resolve to {'gtm'}.
Department resolution is a SET (order-independent), so 'Growth Marketing'
resolves to {'growth', 'marketing'} regardless of list order.

Decision order (precision-first: uncertain cases go to review, never a silent hit):
  1. Department present but maps to NO GTM function, while the title names one
     -> conflict -> review   (a clear title must not silently override a
                              conflicting department field)
  2. Title names a GTM function the department does not contain
     ('gtm' is the umbrella, so it never conflicts) -> review
  3. An ambiguous context word appears in a GTM leadership title -> review
  4. No established GTM function at all:
       - title carries a GTM theme  -> near_miss
       - otherwise                  -> not_a_hit
  5. Function is GTM -> apply the seniority gate:
       - chief / vp / head / cmo / cro        -> hit
       - director, and function is Growth     -> hit
       - director, any other GTM function     -> near_miss
       - below director                       -> near_miss
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


def _department_functions(dept, rule):
    """Return the set of GTM functions a department maps to (order-independent)."""
    dept_n = _norm_text(dept)
    if not dept_n:
        return frozenset()
    found = set()
    for func, aliases in rule["department_functions"].items():
        if any(_has(dept_n, alias) for alias in aliases):
            found.add(func)
    return frozenset(found)


def _title_function(title, rule):
    for term, func in rule["unambiguous_title_department"].items():
        if _has(title, term):
            return func
    return None


def classify(title, department, rule):
    """Return one of: 'hit', 'near_miss', 'review', 'not_a_hit'."""
    title_l = _norm_text(title)
    dept_present = bool(_norm_text(department))

    seniority = _seniority(title_l, rule)
    title_term = _first_title_term(title_l, rule)
    has_ambiguous = any(_has(title_l, w) for w in rule["ambiguous_context_words"])

    dept_funcs = _department_functions(department, rule)
    title_func = _title_function(title_l, rule)

    # 1. Department present but not GTM, while the title names a GTM function -> conflict
    if dept_present and not dept_funcs and title_func is not None:
        return REVIEW

    # 2. Title names a GTM function the department does not contain (gtm is the umbrella)
    if dept_funcs and title_func is not None:
        if "gtm" not in dept_funcs and title_func not in dept_funcs:
            return REVIEW

    # 3. Ambiguous context word in a GTM leadership title -> review
    if has_ambiguous and title_term:
        return REVIEW

    # The role's function: prefer the (more specific) title when conclusive,
    # otherwise fall back to what the department says.
    functions = frozenset({title_func}) if title_func else dept_funcs

    # 4. No established GTM function
    if not functions:
        if title_term:
            return NEAR_MISS
        return NOT_A_HIT

    # 5. Function is GTM -> apply the seniority gate
    if seniority == "senior":
        return HIT
    if seniority == "director":
        allowed = set(rule["seniority"]["director_allowed_functions"])
        return HIT if functions & allowed else NEAR_MISS
    return NEAR_MISS
