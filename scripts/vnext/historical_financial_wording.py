"""Older annual reports' wording for the financial witnesses (A03, A04, A09, A11, A12).

Purpose: Issue #28's frozen financial inspectors were written against the
financial registrant's newest annual report. Where they decide that a disclosed
number is the measure asked for and covers the whole issuer, they read that
report's sentences and layout. The five-year frame reaches the same
registrant's four earlier annual reports, which disclose the same measures; the
frozen inspectors read the numbers there but stop on six differences of wording
or layout. Every one of the twelve positions they withhold in those years
traces to one of them (docs/evidence/issue47_history/financial-older-wording/):

1. The glossary prints a colon after the abbreviation - "AUM: “Assets under
   management”: Represent ..." where the newest report prints "AUM “Assets under
   management”: ...". (A11, four years.)
2. The segment list reads "There are four major reportable business segments -
   A, B, C and D. In addition, there is a Corporate segment." where the newest
   reads "has three reportable business segments - A, B and C - with the
   remaining activities in Corporate". Both name the reportable segments and
   put the rest of the firm in Corporate. The AUM tables are bound to the
   section of one of them (A11), and the nonaccrual ratio's segment tables are
   told apart from the firmwide one by them (A09, three years).
3. The business the markets-excluded net yield leaves out is named "CIB
   Markets" in the two oldest reports and "Markets" afterwards, and each report
   says what it is ("CIB Markets consists of Fixed Income Markets and Equity
   Markets"; later "Markets consists of CIB's Fixed Income Markets and Equity
   Markets"). The frozen check knows the measure and its introduction only by
   the later name. (A04, two years.)
4. A general note without a marker stands between the selected-financial-data
   table and its lettered footnotes ("Effective January 1, 2020, the Firm
   adopted ..."; in another year a note on an acquisition's effect on the
   results). The frozen footnote reader stops at the first block without a
   marker, so it never reaches the note that says the LCR row is a three-month
   average. In the oldest report that note also names the measure by the
   abbreviation the row label defines ("the percentage represents average LCR
   for ...") where later ones say "average ratios for", and the frozen unit
   check reads only the later words. (A03, two years.)
5. The VaR scope-refinement table is headed "Amount by which reported average
   VaR would have been higher" where the frozen counterfactual header reads
   "Amounts by which reported average VaR would have been lower for the years
   ended:". Either way its "Total VaR" row is an adjustment, not a reported
   total. (A12, one year.)
6. The table of contents lists a section title containing "Firmwide" with a
   page number in the next column, and the nonaccrual census reads the page
   number as a candidate ratio. The A04 census in the same frozen module
   already sets aside a column-less number in a source-named table of
   contents; the A09 census does not. (A09, two years.)

None of these says anything the newest report's form does not, and none moves
a number: each is a reader that cannot read a filing, not a filing that does
not say.

How: a successor here is the frozen function's own source with listed
substitutions, each of which must occur exactly once inside that function,
compiled with its module's whole source. With no substitutions that compile is
the frozen code object itself - checked when the successor is built, so a
frozen file that changed on disk after it was loaded is refused by name - and
the successor runs in its module's own namespace through the release-aware
view. A successor is asked only where the frozen inspector does not resolve,
and its answer is taken only where it resolves; it then carries
``historical_older_wording`` naming the forms and the frozen inspector's own
status. Anywhere else the frozen answer is returned unchanged, so a filing the
frozen inspector reads - every newest-year one measured - keeps its frozen
record byte for byte.

Call relationships: ``historical_financial_results`` takes ``fact`` here in
place of the release-aware view of ``financial_results._fact``. The frozen
modules are not changed; Issue #28's generations record their bytes.
"""
import inspect
import types
from pathlib import Path

from . import financial_balance_scope as _frozen_balance
from . import financial_candidates as _frozen_candidates
from . import financial_duration as _frozen_duration
from . import financial_relationships as _frozen_relationships
from . import financial_results as _frozen_results
from . import financial_structured as _frozen_structured
from .historical_dei import release_aware, release_aware_with

RULE = "HISTORICAL_FINANCIAL_OLDER_WORDING_V1"
RESOLVED = "SINGLE_SOURCE_SEMANTIC_FACT"
PACKAGE = __name__.rpartition(".")[0]


class HistoricalFinancialWordingError(ValueError):
    """A successor that would not be the frozen function with only its listed substitutions."""


def _need(condition, reason):
    if not condition:
        raise HistoricalFinancialWordingError(reason)


def _function_codes(code, name, first_line):
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            if constant.co_name == name and constant.co_firstlineno == first_line:
                yield constant
            yield from _function_codes(constant, name, first_line)


def _compiled(function, source):
    module = compile(source, function.__code__.co_filename, "exec", dont_inherit=True)
    found = list(_function_codes(module, function.__name__, function.__code__.co_firstlineno))
    _need(len(found) == 1, "HISTORICAL_SUCCESSOR_FUNCTION_NOT_FOUND:" + function.__qualname__)
    return found[0]


def successor(function, substitutions):
    """``function``'s own source with ``substitutions``, compiled as its module compiles it.

    Args:
        function: A plain top-level function of this package (no closure).
        substitutions: (old, new) pairs; each ``old`` must occur exactly once
            inside the function's own source lines.

    Returns:
        A function on the frozen module's own namespace whose code is the
        compiled substituted source. Its ``historical_substitutions`` lists the
        pairs.

    Raises:
        HistoricalFinancialWordingError: when the function is not such a
            function, when the module's source on disk does not compile to the
            loaded code, or when an ``old`` occurs other than exactly once.
    """
    _need(isinstance(function, types.FunctionType) and function.__closure__ is None
          and isinstance(function.__module__, str) and function.__module__.startswith(PACKAGE + ".")
          and function.__qualname__ == function.__name__,
          "HISTORICAL_SUCCESSOR_TARGET_NOT_A_TOP_LEVEL_PACKAGE_FUNCTION:" + repr(function)[:120])
    path = Path(function.__code__.co_filename)
    source = path.read_text(encoding="utf-8")
    _need(_compiled(function, source) == function.__code__,
          "HISTORICAL_SUCCESSOR_SOURCE_IS_NOT_THE_LOADED_CODE:" + function.__qualname__)
    lines, first = inspect.getsourcelines(function)
    module_lines = source.splitlines(keepends=True)
    before = "".join(module_lines[:first - 1])
    body = "".join(module_lines[first - 1:first - 1 + len(lines)])
    after = "".join(module_lines[first - 1 + len(lines):])
    _need(body == "".join(lines), "HISTORICAL_SUCCESSOR_SOURCE_SPAN_DIFFERS:" + function.__qualname__)
    _need(bool(substitutions), "HISTORICAL_SUCCESSOR_WITHOUT_SUBSTITUTIONS:" + function.__qualname__)
    for old, new in substitutions:
        _need(body.count(old) == 1,
              "HISTORICAL_SUCCESSOR_SUBSTITUTION_NOT_FOUND_ONCE:" + function.__qualname__ + ":"
              + old[:80])
        body = body.replace(old, new)
    made = types.FunctionType(_compiled(function, before + body + after), function.__globals__,
                              function.__name__, function.__defaults__, function.__closure__)
    made.__kwdefaults__ = function.__kwdefaults__
    made.__qualname__ = function.__qualname__
    made.historical_substitutions = tuple(substitutions)
    return made


# 1. The glossary's colon after the abbreviation.
GLOSSARY_COLON = (
    ("""match = re.fullmatch(r'AUM [“"]Assets under management[”"]: Represent""",
     """match = re.fullmatch(r'AUM:? [“"]Assets under management[”"]: Represent"""),)

# 2. The segment list's older sentence, asked when the newest form is absent.
SEGMENT_LIST = (
    ("""r"(.+?)\\s*[–—-]\\s*with the remaining activities in", block["visible_text"], re.I)""",
     """r"(.+?)\\s*[–—-]\\s*with the remaining activities in", block["visible_text"], re.I) or re.search(
            r"There are (?:[0-9]+|two|three|four|five|six) major reportable business segments\\s*[–—-]\\s*"
            r"(.+?)\\.\\s*In addition, there is a Corporate segment\\b", block["visible_text"], re.I)"""),)

# 3. The excluded business's earlier name, in the measure's label and its introduction.
MARKETS_NAME = (
    ("""elif _clean(label["text"]) == "net yield on average interest-earning assets excluding markets":""",
     """elif re.fullmatch(r"net yield on average interest-earning assets excluding (?:cib )?markets",
                                      _clean(label["text"])):"""),
    ("""and "excluding Markets, as shown below" in text""",
     """and re.search(r"excluding (?:CIB )?Markets, as shown below", text)"""),
)

# 4. One general note, a full sentence without a marker, before the lettered notes.
GENERAL_NOTE = (
    ("""    notes = {}
""", """    notes, general = {}, []
"""),
    ("""        if match is None:
            break
""", """        if match is None:
            if notes or general or not _text(block["visible_text"]).endswith("."):
                break
            general.append(block)
            continue
"""),
)

# 4b. The note binding the row to a percent names the measure by the
# abbreviation the row's own label defines ("average LCR for") where the newest
# report says "average ratios for".
MEASURE_ABBREVIATION = (
    (r'''        r"\bpercentage\s+represents\s+(?:average\s+)?ratios?\s+for\b",''',
     r'''        r"\bpercentage\s+represents\s+(?:average\s+)?(?:ratios?" + "".join(
            "|" + re.escape(name) for name in
            (re.findall(r"\(\s*[“\"]([A-Za-z]{2,10})[”\"]\s*\)", label["text"]) if label else []))
        + r")\s+for\b",'''),)

# 5. The counterfactual header's other direction.
COUNTERFACTUAL_HEADER = (
    ("""and _clean(c["text"]) == "amounts by which reported average var would have been lower for the years ended:\"""",
     """and _clean(c["text"]) in ("amounts by which reported average var would have been lower for the years ended:",
                                    "amount by which reported average var would have been higher")"""),
    ("""item.update(disposition="COUNTERFACTUAL_REDUCTION_AMOUNT_NOT_REPORTED_TOTAL",""",
     """item.update(disposition="COUNTERFACTUAL_" + ("INCREASE" if _clean(counterfactual[0]["text"]).endswith("higher")
                                                              else "REDUCTION") + "_AMOUNT_NOT_REPORTED_TOTAL","""),
)

# 6. A column-less number in a source-named table of contents, as the A04 census reads it.
TABLE_OF_CONTENTS = (
    ("""                    elif re.search(r"\\bcriticized\\b.*\\bretained\\b|\\bsecured by real estate\\b", label["text"], re.I):""",
     """                    elif (column is None and (contents := _nearest_table_introduction(structure, table))
                          and re.search(r"\\bTable of Contents$", contents["visible_text"], re.I)):
                        item.update(disposition="SOURCE_NAMED_TABLE_OF_CONTENTS", navigation_heading=contents)
                    elif re.search(r"\\bcriticized\\b.*\\bretained\\b|\\bsecured by real estate\\b", label["text"], re.I):"""),
)

# The A09 ambiguity fallback imports the HTML inspector inside its body, where
# no view can bind it; the successor reads it from its namespace instead.
FALLBACK_BY_NAME = (
    ("""    from .financial_relationships import inspect_nonaccrual_loan_ratio
""", ""),)

FORMS = {"GLOSSARY_COLON": GLOSSARY_COLON, "SEGMENT_LIST": SEGMENT_LIST,
         "MARKETS_NAME": MARKETS_NAME, "GENERAL_NOTE": GENERAL_NOTE,
         "MEASURE_ABBREVIATION": MEASURE_ABBREVIATION,
         "COUNTERFACTUAL_HEADER": COUNTERFACTUAL_HEADER, "TABLE_OF_CONTENTS": TABLE_OF_CONTENTS,
         "FALLBACK_BY_NAME": FALLBACK_BY_NAME}

_SEGMENTS = successor(_frozen_relationships._reported_segment_sections, SEGMENT_LIST)

_AUM_DEFINITIONS = successor(_frozen_balance._aum_definitions, GLOSSARY_COLON)
_AUM_SCOPE = release_aware_with(_frozen_balance._aum_reported_scope,
                                _aum_definitions=_AUM_DEFINITIONS, _reported_segment_sections=_SEGMENTS)
_OLDER = {
    "A11": release_aware_with(_frozen_balance.inspect_aum_balance,
                              _aum_definitions=_AUM_DEFINITIONS, _aum_reported_scope=_AUM_SCOPE),
    "A04": release_aware(successor(_frozen_relationships.inspect_nim_relationships, MARKETS_NAME)),
    "A12": release_aware(successor(_frozen_balance.inspect_total_var, COUNTERFACTUAL_HEADER)),
    "A03": release_aware_with(
        _frozen_candidates.inspect_lcr_disclosed_fact,
        inspect_financial_candidates=release_aware_with(
            _frozen_candidates.inspect_financial_candidates,
            inspect_financial_duration=release_aware_with(
                successor(_frozen_duration.inspect_financial_duration, MEASURE_ABBREVIATION),
                _linked_notes=successor(_frozen_duration._linked_notes, GENERAL_NOTE)))),
    "A09": release_aware_with(
        successor(_frozen_structured.inspect_ordinary_a09_source_fact, FALLBACK_BY_NAME),
        inspect_nonaccrual_loan_ratio=release_aware_with(
            successor(_frozen_relationships.inspect_nonaccrual_loan_ratio, TABLE_OF_CONTENTS),
            _reported_segment_sections=_SEGMENTS)),
}
_METRIC_FORMS = {"A03": ("GENERAL_NOTE", "MEASURE_ABBREVIATION"), "A04": ("MARKETS_NAME",),
                 "A09": ("SEGMENT_LIST", "TABLE_OF_CONTENTS", "FALLBACK_BY_NAME"),
                 "A11": ("GLOSSARY_COLON", "SEGMENT_LIST"), "A12": ("COUNTERFACTUAL_HEADER",)}
_FROZEN = {"A03": release_aware(_frozen_candidates.inspect_lcr_disclosed_fact),
           "A04": release_aware(_frozen_relationships.inspect_nim_relationships),
           "A09": release_aware(_frozen_structured.inspect_ordinary_a09_source_fact),
           "A11": release_aware(_frozen_balance.inspect_aum_balance),
           "A12": release_aware(_frozen_balance.inspect_total_var)}


def _resolved(metric_id, fact):
    """What ``financial_results._fact`` takes as a pass for the metric."""
    if metric_id == "A03":
        return fact["status"] == RESOLVED
    if metric_id == "A09":
        return fact["outcome"] in {"STRUCTURED_PRIMARY_RESOLVED", "HTML_FALLBACK_SOURCE_SEMANTIC_FACT"}
    return fact["semantic_status"] == RESOLVED


def _frozen_status(fact):
    return {key: fact[key] for key in ("status", "semantic_status", "outcome",
                                       "whole_issuer_scope_status") if key in fact}


def _older(metric_id, arguments):
    frozen = _FROZEN[metric_id](**arguments)
    if _resolved(metric_id, frozen):
        return frozen
    older = _OLDER[metric_id](**arguments)
    if not _resolved(metric_id, older):
        return frozen
    return {**older, "historical_older_wording": {
        "rule": RULE, "forms": list(_METRIC_FORMS[metric_id]),
        "frozen_inspector_status": _frozen_status(frozen),
        "taken_because": "FROZEN_INSPECTOR_UNRESOLVED_AND_OLDER_WORDING_RESOLVED"}}


def inspect_lcr_disclosed_fact(**arguments):
    """The frozen LCR inspector; the general-note form only where it does not resolve."""
    return _older("A03", arguments)


def inspect_nim_relationships(**arguments):
    """The frozen NIM inspector; the excluded business's earlier name only where it does not resolve."""
    return _older("A04", arguments)


def inspect_ordinary_a09_source_fact(**arguments):
    """The frozen A09 route; the older segment list and contents rule only where it does not resolve."""
    return _older("A09", arguments)


def inspect_aum_balance(**arguments):
    """The frozen AUM inspector; the glossary colon and older segment list only where it does not resolve."""
    return _older("A11", arguments)


def inspect_total_var(**arguments):
    """The frozen total-VaR inspector; the other counterfactual header only where it does not resolve."""
    return _older("A12", arguments)


fact = release_aware_with(
    _frozen_results._fact, inspect_lcr_disclosed_fact=inspect_lcr_disclosed_fact,
    inspect_nim_relationships=inspect_nim_relationships,
    inspect_ordinary_a09_source_fact=inspect_ordinary_a09_source_fact,
    inspect_aum_balance=inspect_aum_balance, inspect_total_var=inspect_total_var)
