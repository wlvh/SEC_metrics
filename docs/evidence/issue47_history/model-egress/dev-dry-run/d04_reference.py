"""A reference for the 16 approved D04 requests, written before any paid answer.

The paid answers will be read in both directions, and the reference has to
exist before they do - a reference written after reading an answer agrees with
it too easily. This reads the exact messages the calls send (the dry-run
rendering on the run package, ``dump_requests.py <dir> D04``; each file is
checked against ``d04-inputs-index.json``), walks every string the request
supplies as filing content (its units and the shared source dictionaries the
units point into), and searches them twice:

* for the wording a going-concern assessment is written in (``ASSESSMENT``);
* for wider cues a careless answer could turn into one - doubt, the ability to
  continue, bankruptcy, the next twelve months (``CUES``).

Every cue hit must match exactly one recorded judgement (``JUDGEMENTS``), or
this stops: a context nobody judged is not silently counted as harmless. Each
required candidate gets the categories a correct answer may give it. What the
census cannot see is said in the output: a filing that states doubt in other
words would escape both patterns, and no block was read in full except those
the hits point at.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/model-egress/dev-dry-run/d04_reference.py <inputs dir> <output.json>

Zero calls.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from dump_requests import render_input  # noqa: E402

ASSESSMENT = re.compile(r"(?i)going[ -]concern|substantial doubt|continue as a going")
CUES = re.compile(r"(?i)\bdoubt|ability to continue|cease operations|bankrupt|chapter 11|"
                  r"next (?:twelve|12) months")
# (name, pattern over the hit's context, judgement, categories a correct answer
# may give it if it lists it at all). Listing none of them is the expected answer.
JUDGEMENTS = [
    ("OTHER_PARTIES_BANKRUPTCY_AS_A_BUSINESS_RISK",
     r"(?i)bankruptcy of a hotel owner|(?:owners|hotel owners) could declare bankruptcy|"
     r"foreclosures or bankruptcies",
     "A risk factor about hotel owners' or franchisees' bankruptcy ending Marriott's agreements; "
     "not an assessment of Marriott's own ability to continue as a going concern.",
     ["OTHER_ENTITY", "CONDITIONAL_OR_BOILERPLATE"]),
    ("CONTRACTUAL_AMOUNTS_DUE_WITHIN_TWELVE_MONTHS",
     r"(?i)payable within the next 12 months|not expected to be funded within the next 12 months",
     "Contractual obligations (debt, transition tax, guarantees) falling due within a year; a "
     "maturity disclosure, not a going-concern assessment, and not an express statement that "
     "doubt is absent.",
     []),
    ("TAX_POSITIONS_WITHIN_TWELVE_MONTHS",
     r"(?i)resolution of income tax examinations|reserve for uncertain tax positions will "
     r"significantly change",
     "An accounting estimate about tax examinations; no going-concern meaning.",
     []),
    ("PREPAYMENTS_EXPENSED_WITHIN_TWELVE_MONTHS",
     r"(?i)expected to be expensed over the next 12 months",
     "A balance-sheet classification of programming prepayments; no going-concern meaning.",
     []),
    ("DOUBTFUL_ACCOUNTS",
     r"(?i)doubtful accounts|ProvisionForDoubtful",
     "Credit-loss accounting for receivables (the word 'doubtful'); no going-concern meaning.",
     []),
    ("ABILITY_TO_CONTINUE_TO_ATTRACT_USERS",
     r"(?i)ability to continue to attract, engage and retain streaming subscribers",
     "A streaming risk factor: the ability to continue to attract subscribers, the words in "
     "another meaning. Paramount request 1 requires an assessment of this block.",
     ["VALUATION_OR_OTHER_MEANING", "CONDITIONAL_OR_BOILERPLATE"]),
]
WRONG_FOR_THE_TARGET = ["DOUBT_DISCLOSED", "DOUBT_ALLEVIATED", "NO_DOUBT_DECLARATION"]


def _strings(value, path):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from _strings(value[key], path + [key])
    elif isinstance(value, list):
        for position, item in enumerate(value):
            yield from _strings(item, path + [position])


def _context(text, start, end, width=160):
    return re.sub(r"\s+", " ", text[max(0, start - width):end + width])


def main(inputs, output):
    inputs = Path(inputs)
    requests = json.loads((HERE / "d04-requests-index.json").read_text(encoding="utf-8"))
    digests = {row["file"]: row["sha256"]
               for row in json.loads((HERE / "d04-inputs-index.json").read_text(encoding="utf-8"))["files"]}
    rows, judged = [], {name: 0 for name, *_ in JUDGEMENTS}
    for request in requests:
        name = request["file"]
        messages = json.loads((inputs / (name + ".messages.json")).read_text(encoding="utf-8"))
        rendered = render_input(messages).encode("utf-8")
        if hashlib.sha256(rendered).hexdigest() != digests[name + ".txt"]:
            raise SystemExit("D04_REFERENCE_INPUT_IS_NOT_THE_INDEXED_ONE: " + name)
        user = json.loads(messages[1]["content"])
        supplied = {"units": user["units"],
                    "shared_source_dictionaries": user.get("shared_source_dictionaries", {})}
        assessment, cues, searched = [], [], 0
        for path, text in _strings(supplied, []):
            searched += len(text)
            for match in ASSESSMENT.finditer(text):
                assessment.append({"path": path, "context": _context(text, *match.span())})
            for match in CUES.finditer(text):
                context = _context(text, *match.span())
                hit = [name_ for name_, pattern, *_ in JUDGEMENTS if re.search(pattern, context)]
                if len(hit) != 1:
                    raise SystemExit("D04_REFERENCE_CUE_NOT_JUDGED_EXACTLY_ONCE: " + name + " "
                                     + json.dumps(path) + " " + context)
                judged[hit[0]] += 1
                cues.append({"path": path, "matched": match.group(0), "judgement": hit[0]})
        candidates = []
        for candidate in user["required_candidate_assessments"]:
            unit = next(u for u in user["units"] if u["unit_id"] == candidate["unit_id"])
            row = unit["payload"]["blocks"][str(candidate["source_index"])]
            text = row[unit["payload"]["row_layout"]["columns"].index("text")]
            matched = [j for j in JUDGEMENTS if re.search(j[1], text)]
            if len(matched) != 1:
                raise SystemExit("D04_REFERENCE_CANDIDATE_NOT_JUDGED: " + name)
            # A positive control on the search itself: the block a candidate names
            # must be among this request's cue hits, or the walk did not reach it.
            if not any(hit["path"][:5] == ["units", user["units"].index(unit), "payload", "blocks",
                                           str(candidate["source_index"])] for hit in cues):
                raise SystemExit("D04_REFERENCE_SEARCH_MISSED_A_REQUIRED_CANDIDATE: " + name)
            candidates.append({**candidate, "text": text, "judgement": matched[0][0],
                               "acceptable_categories": matched[0][3]})
        rows.append({"file": name, "company_id": request["company_id"],
                     "report_end": request["report_end"], "ledger_digest": request["ledger_digest"],
                     "input_sha256": digests[name + ".txt"], "units": len(user["units"]),
                     "characters_searched": searched,
                     "assessment_wording_hits": assessment, "cue_hits": cues,
                     "required_candidates": candidates})
    if any(row["assessment_wording_hits"] for row in rows):
        raise SystemExit("D04_REFERENCE_FOUND_ASSESSMENT_WORDING: read those blocks before calling")
    positions = sorted({(row["company_id"], row["report_end"]) for row in rows})
    value = {
        "record_type": "ISSUE_47_D04_PRE_CALL_REFERENCE",
        "written_before_any_paid_answer": True,
        "made_by": "the executor, one reader; not an independent human acceptance",
        "inputs": "the exact messages of the 16 approved D04 requests (dump_requests.py on the run "
                  "package), each checked against d04-inputs-index.json",
        "assessment_pattern": ASSESSMENT.pattern, "cue_pattern": CUES.pattern,
        "judgements": [{"name": name, "pattern": pattern, "judgement": what,
                        "categories_a_correct_answer_may_give_if_it_lists_it": categories,
                        "hits": judged[name]} for name, pattern, what, categories in JUDGEMENTS],
        "expected": {
            "per_position": [{"company_id": c, "report_end": e,
                              "outcome": "NO_GOING_CONCERN_DOUBT_DISCLOSED_IN_THE_SUPPLIED_UNITS"}
                             for c, e in positions],
            "an_answer_is_wrong_if": [
                "it gives any of " + ", ".join(WRONG_FOR_THE_TARGET) + " about the target "
                "registrant: no supplied unit carries going-concern assessment wording, and the "
                "definitions say no ordinary risk, maturity table or clean opinion may stand in "
                "for one",
                "it classifies a required candidate outside its acceptable categories, or leaves "
                "it UNRESOLVED (the block itself settles its meaning)",
                "it omits a required candidate (the contract's own check refuses that)"],
            "not_wrong": "listing a judged cue under one of its acceptable categories; the "
                         "definitions discourage it, and it does not move the outcome"},
        "what_this_cannot_see": [
            "doubt stated in words neither pattern matches; no unit was read in full except the "
            "contexts the hits point at",
            "whether DeepSeek reads every unit: a long request answered with no findings is "
            "indistinguishable here from one that skipped units, which the contract's coverage "
            "check (every required unit answered) only partly addresses"],
        "requests": rows, "calls": [0, 0, 0]}
    Path(output).write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"requests": len(rows), "positions": len(positions),
                      "cue_hits": {k: v for k, v in judged.items()},
                      "required_candidates": sum(len(r["required_candidates"]) for r in rows)}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
