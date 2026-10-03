"""Can a keyword-level rule remove the excerpts that are outside every C02 reading?

All three meaning options for C02 exclude the same 94 of the 246 excerpts the
route selects. If a deterministic rule removed exactly those without touching
any of the 82 composition facts, that half of the repair would not wait for the
owner's decision. This re-derives the selection for the ten committed positions
under the current code (through the route's own text input and candidate
builder, as tools/read_c02_board_statements.py does), attaches each excerpt's
committed judgement, recomputes which frozen label admitted it, and measures a
set of rules a keyword selector can express. Zero calls.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/c02-board-read/measure_deterministic_narrowing.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))
from read_c02_board_statements import JUDGEMENTS, route_selection  # noqa: E402
from vnext import text_business_candidates as frozen  # noqa: E402

OUT = Path(__file__).with_name("deterministic-narrowing.json")
CATEGORIES = ("COMPOSITION_FACT", "COMPOSITION_POLICY_OR_PROCESS",
              "COMMITTEE_OR_BOARD_FUNCTION", "NOT_BOARD_COMPOSITION")
PAY = r"\b(salary|salaries|bonus|retainer|fees?|award|equity plan|stock option|grant|perquisite|incentive)\b"
BOARD_OF = r"\bboard of directors of [A-Z]"
DIRECTOR_OF = r"\b(?:serves?|served) as (?:a|an) (?:independent )?director of [A-Z]|\bdirector of [A-Z][a-z]"
SINCE_YEAR = r"\((?:since|from) \d{4}"
OTHER_COMPANY = (r"\b(?:board|audit committee|committee) of (?:[A-Z][\w&.,'-]+\s){1,6}"
                 r"(?:Inc|Corp|Corporation|Company|Ltd|LLC|plc|N\.V\.|S\.A\.|Group|Holdings)\b")


def frozen_labels(text):
    """The frozen selector's three labels, recomputed with its own patterns."""
    found = []
    if (frozen._BOARD.search(text) and frozen._BOARD_NUMBER.search(text)
            and frozen._PATTERNS["board_size_statement"].search(text)):
        found.append("SIZE")
    if (frozen._BOARD.search(text) and frozen._INDEPENDENCE.search(text)
            and frozen._PATTERNS["independence_statement"].search(text)):
        found.append("INDEP")
    if frozen._COMMITTEE.search(text) and frozen._PATTERNS["committee_structure"].search(text):
        found.append("COMMITTEE")
    return found


def _sentences(text):
    return re.split(r"(?<=[.;:])\s+", text)


RULES = {
    "dollar_amount": ('"$" in the excerpt', lambda t: "$" in t),
    "short_block_under_80_characters": ("len(text) < 80", lambda t: len(t) < 80),
    "committee_name_and_structure_word_not_in_one_sentence": (
        "the frozen committee label, required within one sentence",
        lambda t: not any(frozen._COMMITTEE.search(s) and frozen._PATTERNS["committee_structure"].search(s)
                          for s in _sentences(t))),
    "pay_terms": (PAY, lambda t: bool(re.search(PAY, t, re.I))),
    "another_company_named_after_board_or_committee_of": (
        OTHER_COMPANY, lambda t: bool(re.search(OTHER_COMPANY, t))),
    # The line above lands on nothing, and a rule that lands on nothing says
    # nothing about biographies. These are the forms the biographies actually
    # use - "serves on the board of directors of Mueller Water Products",
    # "director of the Federal Home Loan Bank", "- Commvault Systems (since
    # 2018) (chair of ...)" - measured so the answer rests on them.
    "board_of_directors_of_a_named_organisation": (
        BOARD_OF, lambda t: bool(re.search(BOARD_OF, t))),
    "director_of_a_named_organisation": (DIRECTOR_OF, lambda t: bool(re.search(DIRECTOR_OF, t))),
    "organisation_listed_with_since_year": (SINCE_YEAR, lambda t: bool(re.search(SINCE_YEAR, t))),
}
COMBINATION = ("dollar_amount", "short_block_under_80_characters", "pay_terms",
               "another_company_named_after_board_or_committee_of",
               "board_of_directors_of_a_named_organisation", "organisation_listed_with_since_year")


def main():
    judgements = json.loads((ROOT / JUDGEMENTS).read_text(encoding="utf-8"))["positions"]
    rows = []
    for key, judged in sorted(judgements.items()):
        company_id, report_end = key.split(":")
        selected = route_selection(repo_root=ROOT, company_id=company_id, report_end=report_end)
        if [j["block_index"] for j in judged] != [s["block_index"] for s in selected]:
            raise SystemExit("JUDGEMENTS_DO_NOT_DESCRIBE_THE_SELECTION:" + key)
        rows.extend({"position": key, "block": j["block_index"], "category": j["category"],
                     "text": s["text"], "labels": frozen_labels(s["text"])}
                    for j, s in zip(judged, selected))

    def removes(rule):
        return {c: sum(1 for r in rows if r["category"] == c and rule(r["text"])) for c in CATEGORIES}

    combination = lambda t: any(RULES[name][1](t) for name in COMBINATION)  # noqa: E731
    labels = Counter((r["category"], "+".join(r["labels"])) for r in rows)
    body = {
        "record_type": "ISSUE_47_C02_DETERMINISTIC_NARROWING_MEASUREMENT",
        "question": "All three meaning options exclude the same 94 excerpts. Can a deterministic "
                    "rule remove them without removing any of the 82 composition facts, so that "
                    "part of the repair need not wait for the decision?",
        "answer": "Not with the rules measured. The best combination removes {} of the 94 and "
                  "also removes {} composition facts; the rest share the frozen labels' surface "
                  "features with composition facts.".format(
                      removes(combination)["NOT_BOARD_COMPOSITION"],
                      removes(combination)["COMPOSITION_FACT"]),
        "data": "the 246 excerpts the route selects for the ten committed positions, re-derived "
                "under the current code, each with its committed judgement",
        "category_totals": {c: sum(r["category"] == c for r in rows) for c in CATEGORIES},
        "frozen_label_by_category": {c + " | " + l: n for (c, l), n in sorted(labels.items())},
        "rules": {name: {"rule": desc, "removes": removes(rule)}
                  for name, (desc, rule) in RULES.items()},
        "best_combination": {
            "rules": list(COMBINATION), "removes": removes(combination),
            "composition_facts_lost": [{"position": r["position"], "block": r["block"],
                                        "text": r["text"]} for r in rows
                                       if r["category"] == "COMPOSITION_FACT"
                                       and combination(r["text"])]},
        "why_the_rest_do_not_separate": [
            "a nominee biography naming another company's audit committee has the same words "
            "as a statement of who sits on this board's audit committee",
            "an equity plan's definition of 'the Committee' and the compensation discussion's "
            "process text name the committee and a structure word",
            "the only surface feature short labels share is length, and two of the shortest "
            "excerpts are the independence counts"],
        "what_this_means_for_the_repair": {
            "option_1_composition_facts_only":
                "a successor that selects composition facts directly (board size and "
                "independence count statements, committee membership and chair designations) "
                "rather than narrowing the keyword selection; the 82 judged facts are its "
                "positive set and the 164 others its negative set",
            "options_2_and_3":
                "a narrower keyword selection still carries excerpts outside every reading; a "
                "per-excerpt semantic review would be a new call type needing a model-call "
                "allowance",
            "either_way":
                "not decision-independent after all: the rule that removes the 94 without "
                "losing facts is not a keyword rule, so what replaces the selector depends on "
                "which reading the owner picks"},
        "not_claimed": "that no rule exists; only that the ones a keyword selector can express "
                       "were measured and none separates the sets",
        "calls": {"provider": 0, "paid": 0, "sec": 0}}
    OUT.write_text(json.dumps(body, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps(body["best_combination"]["removes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
