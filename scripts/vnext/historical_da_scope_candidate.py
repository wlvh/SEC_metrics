"""Candidate rule: when B03's depreciation and amortization cannot be shown to be the whole of it.

B03's approved Spec takes depreciation and amortization from the first of three
direct concepts the filing carries (DepreciationDepletionAndAmortization,
DepreciationAmortizationAndAccretionNet, DepreciationAndAmortization), else
composes it from Depreciation and AmortizationOfIntangibleAssets. The frozen
calculator never compares the first direct concept with the others. Salesforce's
FY2026 10-K tags DepreciationDepletionAndAmortization at $1.2 billion on a note
sentence about fixed assets and DepreciationAndAmortization at $3,631 million on
the cash flow statement; the chain took the first, a subtotal the standing rules
forbid taking as the total. That result is withdrawn as a registered defect.

This module is the proposed repair, written as a candidate so it can be tested
before it is adopted. It is not imported by any route and is not a rule file:
adopting it changes which fact an approved Spec selects, which is a revision
through the existing mechanism, and the historical and ordinary B03 routes keep
their meaning until then.

What it says, in the order it is applied:

1. Only facts that could be the definition's quantity are compared: the three
   direct concepts, for exactly the target annual duration, undimensioned, in a
   USD unit. A fact for another period, a segment member or another unit is
   not in conflict with the total, whatever its value.
2. Two values conflict only beyond their reported precision. Each fact states
   its own ``decimals``; ``$1.2 billion`` at -8 and ``$1,234 million`` at -6 are
   the same amount as far as the filing tells us.
3. If every direct candidate agrees, the first in chain order is taken - the
   approved selection, unchanged. Nothing in the filing contradicts it.
4. If they conflict, the filing's own composition is asked: where Depreciation
   and AmortizationOfIntangibleAssets are both tagged for the same period, the
   direct candidate equal to their sum is the one proven to cover what the
   definition's own composition says D&A is, and it is taken - even if it is
   not first in chain order.
5. Otherwise the conflict cannot be resolved from the filing, the selected
   fact cannot be shown to cover the definition, and the result is withheld by
   name, carrying every candidate with its concept, value and precision.

It never adds anything back and never takes the larger number because it is
larger: a statement total can carry impairment the definition excludes
(Salesforce's footnote says its total includes impairment of right-of-use
assets), so "the bigger one" is not a proof of coverage.
"""
import re
from decimal import Decimal, InvalidOperation

from .deterministic_router import (_XbrlContextParser, _XbrlFactParser, _local_name,
                                   _numeric_xbrl_value)

DIRECT = ("DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
          "DepreciationAndAmortization")
COMPOSITION = ("Depreciation", "AmortizationOfIntangibleAssets")
WITHHELD_REASON = "B03_DEPRECIATION_AMORTIZATION_SCOPE_UNPROVEN"
_UNIT = re.compile(r"<(?:\w+:)?unit\b[^>]*\bid=\"([^\"]+)\"[^>]*>(.*?)</(?:\w+:)?unit>",
                   re.S | re.I)
_MEASURE = re.compile(r"<(?:\w+:)?measure\b[^>]*>\s*([^<\s]+)\s*<", re.I)


class _DecimalsFactParser(_XbrlFactParser):
    """The frozen fact parser, keeping each fact's ``decimals`` beside what it already keeps.

    Everything else is the frozen parser's: the same facts, in the same order,
    with the same fields. ``decimals`` is added to the fact the frozen code has
    just opened, so a fact the frozen code would not open is not opened here.
    """

    def handle_starttag(self, tag, attrs):
        before = len(self.active)
        super().handle_starttag(tag, attrs)
        if len(self.active) > before:
            attributes = {name.casefold(): value for name, value in attrs}
            self.active[-1]["decimals"] = attributes.get("decimals")


def _usd_units(text):
    """Unit ids whose single measure is iso4217:USD."""
    usd = set()
    for unit_id, body in _UNIT.findall(text):
        measures = _MEASURE.findall(body)
        if measures == ["iso4217:USD"]:
            usd.add(unit_id)
    return usd


def annual_facts(*, raw_bytes, period_start, period_end, concepts):
    """Every undimensioned USD fact of ``concepts`` for exactly this annual duration."""
    text = raw_bytes.decode("utf-8")
    contexts = _XbrlContextParser()
    contexts.feed(text)
    contexts.close()
    contexts = contexts.contexts()
    parser = _DecimalsFactParser()
    parser.feed(text)
    parser.close()
    usd = _usd_units(text)
    found = []
    for fact in parser.facts():
        local = _local_name(qualified_name=str(fact["qualified_name"]))
        if local not in concepts or not fact["text"] or not fact["unit_ref"]:
            continue
        context = contexts.get(fact["context_ref"])
        if (context is None or context["dimensions"] or context["typed_dimension_count"]
                or context["period_start"] != period_start
                or context["period_end"] != period_end
                or fact["unit_ref"] not in usd):
            continue
        found.append({"concept": local, "fact_ordinal": fact["ordinal"],
                      "context_ref": fact["context_ref"], "unit_ref": fact["unit_ref"],
                      "value": _numeric_xbrl_value(text=fact["text"], scale=str(fact["scale"]),
                                                   sign=str(fact["sign"])),
                      "decimals": fact["decimals"]})
    return found


def _tolerance(decimals):
    if decimals is None or str(decimals).upper() == "INF":
        return Decimal(0)
    try:
        return Decimal("0.5") * (Decimal(10) ** (-int(decimals)))
    except (InvalidOperation, ValueError):
        return None


def agree(first, second):
    """Whether two facts can be the same amount at the precision each reports."""
    tolerances = (_tolerance(first["decimals"]), _tolerance(second["decimals"]))
    if None in tolerances:
        return False
    return abs(Decimal(first["value"]) - Decimal(second["value"])) <= sum(tolerances)


def _one_value(facts):
    """A concept's facts collapse to one amount only if they agree with each other."""
    for fact in facts[1:]:
        if not agree(facts[0], fact):
            return None
    return facts[0]


def da_scope_answer(*, facts):
    """Take, compose or withhold - never add back, never prefer the larger number."""
    by_concept = {}
    for fact in facts:
        by_concept.setdefault(fact["concept"], []).append(fact)
    direct = []
    for concept in DIRECT:
        if concept not in by_concept:
            continue
        chosen = _one_value(by_concept[concept])
        if chosen is None:
            return {"status": "WITHHOLD", "reason_code": WITHHELD_REASON,
                    "why": "ONE_CONCEPT_CARRIES_TWO_AMOUNTS:" + concept,
                    "candidates": by_concept[concept]}
        direct.append(chosen)
    if not direct:
        return {"status": "NO_DIRECT_CANDIDATE", "why": "THE_APPROVED_COMPOSITION_APPLIES",
                "candidates": []}
    if all(agree(direct[0], other) for other in direct[1:]):
        return {"status": "TAKE", "selected": direct[0], "candidates": direct,
                "why": "EVERY_DIRECT_CANDIDATE_AGREES"}
    parts = [_one_value(by_concept[concept]) if concept in by_concept else None
             for concept in COMPOSITION]
    if None not in parts:
        total = {"concept": "+".join(COMPOSITION),
                 "value": str(sum(Decimal(part["value"]) for part in parts)),
                 # Adding two rounded amounts adds their rounding: the sum is
                 # only as precise as the coarser of the two, twice over.
                 "decimals": None}
        tolerance = sum(_tolerance(part["decimals"]) or Decimal(0) for part in parts)
        covering = [candidate for candidate in direct
                    if abs(Decimal(candidate["value"]) - Decimal(total["value"]))
                    <= tolerance + (_tolerance(candidate["decimals"]) or Decimal(0))]
        if len(covering) == 1:
            return {"status": "TAKE", "selected": covering[0], "candidates": direct,
                    "why": "EQUALS_THE_FILING_S_OWN_COMPOSITION", "composition": parts}
    return {"status": "WITHHOLD", "reason_code": WITHHELD_REASON,
            "why": "DIRECT_CANDIDATES_CONFLICT_AND_NOTHING_IN_THE_FILING_RESOLVES_IT",
            "candidates": direct, "composition": [part for part in parts if part]}
