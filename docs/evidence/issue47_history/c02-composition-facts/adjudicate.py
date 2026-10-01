"""Write the executor's C02 adjudications where independent readers split.

Each class of block that some readers judged one way and others the other way
is decided by one rule, applied to every block of the class in every reading -
the ten latest years' and the 27 older years' - whether or not the route takes
the block. A class is defined by what its text says, never by what the route
does with it; the route's selection is not read here at all. A decision is
written only where the reading does not already say what the rule says, so
each row is one place a reader is overruled (or, for a block outside the
reader's pool, a place no reader looked), with the reader's own verdict and
reason kept beside it. A FACT decision names the blocks of the same document
that state the same fact (``redundant_with``); a comparison counts the block
missed only when none of them is selected.

The owner's meaning (2026-09-27): board size, independence, committee setup,
members, chairs, and the related independence and qualification
determinations. The rules below place each split class inside or outside it.

CARD_TENURE_FIELD (NOT)
    A director card's "Director since: 2017" / "Joined the Board: 2025" field.
    How long a sitting director has served is none of the owner's facts.

CARD_SUBJECT_NAME (FACT)
    The name a director card or a table row prints before a field the reading
    judges a composition fact ("NCG (Chair)", "Committees: N/A", a summary
    compensation table's "Chairman and Chief Executive Officer"). A field says
    nothing without whose it is. Decided where the same reading's reason for
    the field names the person; the name is covered wherever the field's own
    restatements are.

CHAIR_CEO_STRUCTURE (FACT)
    A statement that the board's chair and the chief executive are two people
    or one: "the Board has chosen to separate the roles of Chairman of the
    Board and CEO". It says who can hold the board's chair, the kind of fact
    every reading takes when the holder is named. Older readers took it in 31
    blocks across five companies; the latest Lumen and Marriott readers left
    out the same sentences. A sentence about a policy or a proposal, or one
    naming both choices, states no structure and is outside the class.

CLASSIFIED_SLATE_COUNT (NOT)
    On a board divided into classes, the number of nominees standing in one
    class's election. It is neither the board's size nor a change in who sits
    on it. On a board that is not classified the whole board stands and the
    same count is its size (outside this class).

DIRECTOR_GROUP_HEADING (NOT)
    A heading over a group of directors that states their class, their
    standing for election or their continuing in office, and the term
    ("Continuing Class I Directors (Until 2025 Annual Meeting)", "Nominees for
    Election as Directors:", "Continuing Directors:"), over a table or over
    director cards alike. Class and term are tenure-like; the directors' own
    names and fields carry who they are.

DIRECTOR_TABLE_NAME (FACT)
    A director's name in a board table whose columns mark independence (an
    "IND Independent" legend): each listed director carries the table's
    determination, marked or not.

DIRECTOR_COUNT_ON_A_DATE (FACT)
    A count of the board's directors, or of its non-employee directors, on a
    date, wherever it is printed ("there were ... 11 non-employee directors",
    "of the twelve then current members of the Board, twelve attended").

COMPENSATION_COMMITTEE_INTERLOCKS (FACT)
    That no member of the compensation committee is or was an officer or an
    employee: a determination about the committee's members.

MEMBERSHIP_CRITERIA_DETERMINATION (FACT)
    The board's determination that its directors meet the criteria for board
    membership or comply with the governance principles' requirements for
    serving: a qualification determination.

PRESIDING_DUTY (NOT)
    That an office presides over or leads the independent directors' sessions
    ("led by our Chairman", "the independent Chair of the Nominating and
    Governance Committee presides at meetings of the independent directors",
    "The independent Lead Director presides"). It is a duty given to an
    office; who holds the office is the composition fact, stated where the
    filing names the holder, as a list of a lead director's duties is not.
    Fourteen readings saw such sentences: nine left them out, five took them.
    A block that also names a holder is left to the reading.

BOARD_TASK_FORCE (FACT)
    A body of the board made up of named directors ("The Digital Innovation
    Task Force is made up of three directors, ..."), and its title: committee
    setup and membership.

NOMINEES_ARE_SITTING_DIRECTORS (FACT)
    "Each nominee is currently a member of the Board": the slate is the
    sitting board.

COMMITTEES_NAMED_AS_A_SET (FACT)
    A sentence naming the board's committees together ("the charter of each
    of the Audit, ..., and ... Committees"): committee setup. Covered by the
    other blocks the reading judges to name the same committees.

JOIN_BEFORE_THE_YEAR (NOT) / JOIN_IN_THE_YEAR (FACT)
    A sentence giving when a director joined the board ("has served as a
    member of our Board since March 2011", "was appointed a member of the
    Board in September 2017", "joined our Board on February 25, 2021"). A join
    dated in the target year or after it is a change in who sits on the board
    in the period the filing reports; a join dated earlier is tenure in other
    words, as CARD_TENURE_FIELD is. A block whose other sentences state
    another composition fact (a chair, a committee, a departure) is left to
    the reading.

Older years' filings are read from a root restored from the acquisition's
export by this checkout (``--source-root``). Building a document takes the
route's input preparation; ``--documents`` names a cache directory (outside
the checkout) shared with ``c02-selector-repairs/measure.py``.

With ``--effect-output`` the tool also holds today's selection to every
reading under the adjudication committed at ``--before`` and under the one it
just wrote, and records each position's problems both ways.

Usage:
    python3 docs/evidence/issue47_history/c02-composition-facts/adjudicate.py \
        --source-root <root> --documents <cache dir> [--effect-output <json> [--before <git ref>]]
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from tools import read_c02_composition as reading  # noqa: E402
from vnext.historical_board_composition_v2 import (  # noqa: E402
    board_composition_facts, clean, person_name, sentences, _strip_name)

HERE = Path(__file__).resolve().parent
RULES = {
    "CARD_TENURE_FIELD": ("NOT", "Tenure of a sitting director is not in the owner's meaning (size, independence, "
                                 "committee setup, members, chairs, related determinations)."),
    "CARD_SUBJECT_NAME": ("FACT", "A field states nothing without whose it is; the same reading's reason for the "
                                  "field names this person."),
    "CHAIR_CEO_STRUCTURE": ("FACT", "Whether the board's chair and the CEO are two people or one says who can hold "
                                    "the board's chair, the kind of fact every reading takes when the holder is "
                                    "named."),
    "CLASSIFIED_SLATE_COUNT": ("NOT", "On a classified board the nominees of one class are neither the board's size "
                                      "nor a change in who sits on it."),
    "DIRECTOR_GROUP_HEADING": ("NOT", "Class, election standing and term are tenure-like; the names and fields under "
                                      "the heading carry who the directors are."),
    "DIRECTOR_TABLE_NAME": ("FACT", "A director listed in a table whose columns mark independence carries the "
                                    "table's determination, marked or not."),
    "DIRECTOR_COUNT_ON_A_DATE": ("FACT", "A count of the board's directors, or of its non-employee directors, on a "
                                         "date is a composition fact wherever it is printed."),
    "COMPENSATION_COMMITTEE_INTERLOCKS": ("FACT", "That no compensation committee member is or was an officer or "
                                                  "employee is a determination about the committee's members."),
    "MEMBERSHIP_CRITERIA_DETERMINATION": ("FACT", "The board's determination that its directors meet the criteria "
                                                  "for membership is a qualification determination."),
    "PRESIDING_DUTY": ("NOT", "Presiding over the independent directors' sessions is a duty of an office; who holds "
                              "the office is the composition fact, stated where the holder is named."),
    "BOARD_TASK_FORCE": ("FACT", "A body of the board made up of named directors is committee setup and "
                                 "membership."),
    "NOMINEES_ARE_SITTING_DIRECTORS": ("FACT", "The statement that each nominee is a current member says the slate "
                                               "is the sitting board."),
    "COMMITTEES_NAMED_AS_A_SET": ("FACT", "A sentence naming the board's committees together states committee "
                                          "setup."),
    "JOIN_BEFORE_THE_YEAR": ("NOT", "A join dated before the target year is tenure in other words."),
    "JOIN_IN_THE_YEAR": ("FACT", "A join dated in the target year or after it is a change in who sits on the board "
                                 "in the period the filing reports."),
}

TENURE = re.compile(r"^\s*(?:director since|joined the board)\s*:?", re.I)
_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_NUM = r"(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen)"
_DATE = r"(?P<date>(?:(?:" + _MONTHS + r")\s+(?:\d{1,2},\s+)?)?(?:19|20)\d\d)"

_ROLE = r"(?:roles?|positions?|functions?|offices?|structure)"
_CHAIR = r"(?:board\s+)?chair(?:man|person|woman)?(?:\s+of\s+the\s+board(?:\s+of\s+directors)?)?"
_CEO = r"(?:ceo|chief executive officer)(?:\s+\(\W*ceo\W*\))?"
_PAIR = r"(?:" + _CHAIR + r"\s+(?:and|&)\s+(?:the\s+)?" + _CEO + r"|" + _CEO + r"\s+(?:and|&)\s+(?:the\s+)?" + _CHAIR + ")"
STRUCTURE = re.compile(
    r"\b(?:separat\w*|split|combin\w*)\b[^.;]{0,40}?\b(?:" + _ROLE + r"\s+of\s+(?:the\s+)?)?" + _PAIR
    + r"|\b" + _PAIR + r"\s+" + _ROLE + r"\b[^.;]{0,80}?\b(?:separat\w*|combin\w*|single individual|one person"
    r"|same person|different (?:individuals|people|persons))", re.I)
TWO_WAYS = re.compile(r"\bseparat\w*\b.*\bcombin\w*|\bcombin\w*\b.*\bseparat\w*", re.I)
NOT_A_STRUCTURE = re.compile(r"\bpolic(?:y|ies)\b|\bmandat\w*|\bimpos\w*|\brequir\w*|\bproposal\b|\bshould\b"
                             r"|\bmay\b", re.I)

CLASSES = re.compile(r"\bclass\s+(?:i{1,3}|[123])\s+(?:directors?|nominees?)\b|\bclassified board\b"
                     r"|\bdivided into three classes\b", re.I)
SLATE = re.compile(r"\b(?:to elect|election of|has nominated|have nominated|nominated)\b[^.;]{0,40}?\b" + _NUM
                   + r"\s+(?:(?:of\s+)?(?:our|its|the)\s+)?(?:\w+\s+){0,2}(?:nominees|directors)\b", re.I)
BOARD_SIZE = re.compile(r"\bboard\b[^.;]{0,40}?\b(?:consists of|currently (?:has|consists of)|has|is (?:composed|comprised"
                        r"|made up) of)\s+(?:a total of\s+)?" + _NUM + r"\s+(?:directors|members)\b|\bsize of the board\b",
                        re.I)

GROUP_HEADING = re.compile(
    r"^(?:continuing\s+)?class\s+(?:i{1,3}|iv|v|[1-5])\s+(?:director\s+)?(?:nominees|directors)\b"
    r"|^(?:director\s+)?nominees\s+for\s+election\b|^continuing\s+directors\b|^directors\s+continuing\s+in\s+office\b",
    re.I)
TABLE_HEADER = re.compile(r"director\s*since.*committee", re.I)
TABLE_LEGEND = re.compile(r"\bIND\b\s*Independent\b")

DIRECTOR_COUNT = (
    re.compile(r"\b(?:had|has|have|there (?:were|are)|including|of (?:our|the|its))\b[^.;]{0,60}?\b" + _NUM
               + r"\s+(?:non-employee|non-management|outside)\s+directors\b", re.I),
    re.compile(r"\bof the " + _NUM + r"\s+then[- ]current members of the board\b", re.I),
)
INTERLOCKS = re.compile(
    r"\b(?:none of the|no) (?:members?|directors?)\b[^.;]{0,30}?\b(?:of|on|serving on|who served on)\s+(?:the|our)\s+"
    r"(?:[\w,&]+\s+){0,4}(?:compensation|human resources|talent|people)\b[\w,&\s]{0,40}?\bcommittee\b[^.;]{0,120}?"
    r"\b(?:is|was|were|has|have)\b[^.;]{0,40}?\b(?:officers?|employees?)\b"
    r"|\bcommittee consisted of\b[^.]{0,200}\bnone of whom\b[^.;]{0,60}\b(?:officers?|employees?)\b"
    r"|\bserved on the compensation committee\b[^.]{0,200}\bnone of\b[^.;]{0,80}\b(?:officers?|employees?)\b",
    re.I)
CRITERIA = re.compile(r"\bdetermined that (?:the criteria for board membership have been satisfied"
                      r"|all directors are in compliance with)", re.I)
PRESIDING = re.compile(
    r"\b(?:independent|non-management|non-employee) directors\b[^.;]{0,60}?\bexecutive sessions?\b[^.;]{0,60}?"
    r"\b(?:led|chaired|presided over) by (?:our|the)\b"
    r"|\b(?:chair|chairman|chairperson|lead director|lead independent director)\b[^.;]{0,80}?\bpresides? (?:at|over)"
    r"\b[^.;]{0,40}?\b(?:meetings|sessions) of the (?:independent|non-management|non-employee) directors\b", re.I)
TASK_FORCE_LINE = re.compile(r"\btask force is (?:made up|composed|comprised) of\b[^.;]{0,30}?\b" + _NUM
                             + r"\s+directors\b", re.I)
TASK_FORCE_TITLE = re.compile(r"^[A-Z][\w ]{0,60}\bTask Force$")
SITTING = re.compile(r"\b(?:each|every|all) (?:of the )?nominees? (?:is|are) currently (?:a )?(?:members? of the "
                     r"board|directors?)\b", re.I)
CHARTER_SET = re.compile(r"\bcharters? (?:of|for) (?:each of )?(?:the|our)\b(?P<list>[^.;]{10,300})", re.I)
# The first word of each capitalised committee name in a list: "Audit Committee",
# "Compensation, Talent and Culture Committee" -> Audit, Compensation.
COMMITTEE_NAME = re.compile(r"(?<![\w])(?!Committee)([A-Z][a-z]+)(?:(?:,\s*|\s+and\s+|\s+)(?!Committee)[A-Z][\w’']*){0,4}"
                            r"\s+Committees?\b")
HOLDER = re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.\s+[A-Z]|\bhas an? (?:independent )?(?:lead|presiding) (?:independent )?director\b",
                    re.I)
JOIN = re.compile(
    r"\b(?:has served as (?:[^.;]{0,60}?\b)?(?:a |an )?(?:independent |non-employee |non-executive )?"
    r"(?:member of (?:the|our) board(?: of directors)?|director)(?: of (?:the|our) company)?\s+since"
    r"|joined (?:the|our) board(?: of directors)?(?: as [^.;]{0,40}?)?\s+(?:on|in|effective)"
    r"|(?:appointed|elected|named)\b[^.;]{0,80}?\b(?:a member of|to) (?:the|our) board(?: of directors)?\s+"
    r"(?:on|in|effective|at the)"
    r"|first elected to (?:the|our) board at the"
    r"|since joining (?:the|our) board(?: of directors)? in)\s+(?:the\s+)?" + _DATE, re.I)
OTHER_COMPOSITION = re.compile(r"\b(?:chair(?:man|person|woman)?|vice[- ]chair\w*|committee|independen\w*|lead "
                               r"(?:independent )?director|presiding|retir\w*|resign\w*|step(?:ped|s)? down"
                               r"|not stand|not be standing|cease\w*|depart\w*)\b", re.I)


def _fy_start(report_end):
    return dt.date.fromisoformat(report_end) - dt.timedelta(days=364)


def _when(date_text):
    """(year, month) of a date written as 'March 2011', 'February 25, 2021' or '2021'."""
    year = int(re.search(r"(?:19|20)\d\d", date_text).group(0))
    month = re.match(r"(" + _MONTHS + r")", date_text, re.I)
    return year, (_MONTHS.split("|").index(month.group(1).lower()) + 1) if month else None


def _before(date_text, start):
    year, month = _when(date_text)
    return (year, month or 12) < (start.year, start.month)


def _structure(text):
    return any(STRUCTURE.search(s) and not TWO_WAYS.search(s) and not NOT_A_STRUCTURE.search(s)
               for s in sentences(text))


def _name_at(blocks, index):
    """The blocks of the name that ends at ``index`` and its surname, or None.

    A name is one block of two or more tokens ("David Ellison (1)"), or a
    surname alone whose block follows the rest of the name ("James D." /
    "Farley, Jr.", "Laura" / "Alber"). A letter's closing ("Sincerely,") is
    not a name.
    """
    def name_block(i):
        raw = clean(blocks[i]["text"])
        return i >= 0 and not raw.endswith(",") and person_name(raw)
    if not name_block(index):
        return None
    tokens = _strip_name(blocks[index]["text"]).replace(",", " ").split()
    if len(tokens) >= 2:
        return [index], tokens[-1]
    before = _strip_name(blocks[index - 1]["text"]) if index > 0 else ""
    if name_block(index - 1) and (len(before.split()) == 1 or re.search(r"\b[A-Z]\.$", before)):
        return [index - 1, index], tokens[0]
    return None


def _judged(record):
    return {row["i"]: row for row in [*record["selected"], *record["pool_facts"],
                                      *record.get("outside_pool_facts", []), *record.get("supplementary", [])]}


def decisions_for(position, document, record):
    """Every decision the rules write for one reading."""
    blocks = document["blocks"]
    verdict = _judged(record)
    pool = {row["i"] for row in record.get("pool", [])}
    start = _fy_start(position.rsplit(":", 1)[1])
    facts = {i for i, row in verdict.items() if row["verdict"] in ("FACT", "MIXED")}
    out = {}

    def said(index):
        row = verdict.get(index)
        return row["verdict"] if row else ("LEFT_OUT_OF_POOL_FACTS" if index in pool else "NOT_READ")

    def decide(index, rule, redundant_with=(), **extra):
        decision = RULES[rule][0]
        reader = said(index)
        if (decision == "FACT") == (reader in ("FACT", "MIXED")) or index in out:
            return
        row = {"position": position, "i": index, "text_sha256": reading.text_sha256(blocks[index]["text"]),
               "rule": rule, "decision": decision, "reader_verdict": reader,
               "reader_why": (verdict.get(index) or {}).get("why", "")[:200], **extra}
        if decision == "FACT":
            row["redundant_with"] = sorted(set(redundant_with) - {index})
        out[index] = row

    def usable(index):
        return not blocks[index]["linked"] and len(blocks[index]["text"]) <= 3000

    texts = [clean(block["text"]) for block in blocks]
    # CARD_TENURE_FIELD: a NOT decision is only ever needed where a reader took the field.
    for index in sorted(facts):
        if TENURE.match(blocks[index]["text"]):
            decide(index, "CARD_TENURE_FIELD")
    # CARD_SUBJECT_NAME: the nearest name before a field whose reason names it.
    for index in sorted(facts):
        if len(texts[index]) > 160:
            continue
        why = verdict[index].get("why", "")
        for before in range(index - 1, max(index - 13, -1), -1):
            found = _name_at(blocks, before)
            if found is None:
                continue
            name, surname = found
            # A field that names the person itself ("Mr. Webb is not standing
            # for reelection") needs no name before it.
            if len(surname) >= 3 and re.search(r"\b" + re.escape(surname) + r"\b", why) \
                    and not re.search(r"\b" + re.escape(surname) + r"\b", texts[index]):
                cover = [i for i in verdict[index].get("redundant_with") or [] if i not in name]
                for part in name:
                    decide(part, "CARD_SUBJECT_NAME", redundant_with=cover, surname=surname, field=index)
                break
    structure = [i for i in range(len(blocks)) if usable(i) and _structure(texts[i])]
    for index in structure:
        decide(index, "CHAIR_CEO_STRUCTURE", redundant_with=structure)
    if CLASSES.search(" ".join(texts)):
        for index in sorted(facts):
            if usable(index) and any(SLATE.search(s) for s in sentences(texts[index])) \
                    and not BOARD_SIZE.search(texts[index]):
                decide(index, "CLASSIFIED_SLATE_COUNT")
    for index in sorted(facts):
        if len(texts[index]) <= 200 and GROUP_HEADING.match(texts[index]):
            decide(index, "DIRECTOR_GROUP_HEADING")
    for header in [i for i in range(len(blocks)) if len(texts[i]) < 300 and TABLE_HEADER.search(texts[i])]:
        legend = next((j for j in range(header + 1, min(header + 80, len(blocks))) if TABLE_LEGEND.search(texts[j])),
                      None)
        if legend is not None:
            for index in range(header + 1, legend):
                if person_name(blocks[index]["text"]) and not GROUP_HEADING.match(texts[index]):
                    decide(index, "DIRECTOR_TABLE_NAME")
    for index in range(len(blocks)):
        if not usable(index):
            continue
        text = texts[index]
        if any(pattern.search(text) for pattern in DIRECTOR_COUNT):
            decide(index, "DIRECTOR_COUNT_ON_A_DATE")
        if INTERLOCKS.search(text):
            decide(index, "COMPENSATION_COMMITTEE_INTERLOCKS")
        if CRITERIA.search(text):
            decide(index, "MEMBERSHIP_CRITERIA_DETERMINATION")
        if index in facts and PRESIDING.search(text) and not HOLDER.search(text):
            decide(index, "PRESIDING_DUTY")
        if TASK_FORCE_LINE.search(text):
            decide(index, "BOARD_TASK_FORCE")
            title = next((j for j in range(index - 1, max(index - 4, -1), -1)
                          if TASK_FORCE_TITLE.match(texts[j])), None)
            if title is not None:
                decide(title, "BOARD_TASK_FORCE", redundant_with=[index])
        if SITTING.search(text):
            decide(index, "NOMINEES_ARE_SITTING_DIRECTORS")
        named = CHARTER_SET.search(text)
        committees = {m.group(1) for m in COMMITTEE_NAME.finditer(named.group("list"))} if named else set()
        if len(committees) >= 3:
            # Covered by a block the reading judges a fact that names every one of them.
            cover = [i for i in facts if i != index and all(re.search(r"\b" + name + r"\b", texts[i])
                                                            for name in committees)]
            cover += [j for i in cover for j in verdict[i].get("redundant_with") or []]
            decide(index, "COMMITTEES_NAMED_AS_A_SET", redundant_with=cover, committees=sorted(committees))
        joins = [m.group("date") for s in sentences(text) for m in JOIN.finditer(s)]
        if joins:
            if any(not _before(d, start) for d in joins):
                decide(index, "JOIN_IN_THE_YEAR", dates=joins)
            elif index in facts:
                rest = [JOIN.sub(" ", s) for s in sentences(text)]
                if not any(OTHER_COMPOSITION.search(s) for s in rest):
                    decide(index, "JOIN_BEFORE_THE_YEAR", dates=joins)
    return [out[i] for i in sorted(out)]


def _measure():
    path = HERE.parent / "c02-selector-repairs" / "measure.py"
    spec = importlib.util.spec_from_file_location("c02_selector_measure", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "adjudication.json")
    parser.add_argument("--effect-output", type=Path)
    parser.add_argument("--before", default="HEAD")
    args = parser.parse_args(argv)
    decisions, latest, held = [], set(), []
    for dumped in _measure().documents(cache=args.documents, source_root=args.source_root.resolve()):
        record = json.loads((REPO / dumped["reading"]).read_text(encoding="utf-8"))
        if (REPO / dumped["reading"]).parent == reading.READING_DIR:
            latest.add(record["position"])
        decisions.extend(decisions_for(record["position"], dumped["document"], record))
        held.append((record, dumped["document"]))
    out = {"record_type": "C02_COMPOSITION_ADJUDICATION",
           "decided_by": "executor, applying each rule to every block of its class in every reading",
           "readings": [str(reading.READING_DIR.relative_to(REPO)), str(reading.OLDER_READING_DIR.relative_to(REPO))],
           "rules": {name: {"decision": decision, "reason": reason} for name, (decision, reason) in RULES.items()},
           "decisions": decisions}
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    counts = {}
    for row in decisions:
        key = row["rule"] + ("@latest" if row["position"] in latest else "@older")
        counts[key] = counts.get(key, 0) + 1
    print(json.dumps(counts, sort_keys=True, indent=1))
    if args.effect_output:
        _effect(held=held, latest=latest, before_ref=args.before, after_path=args.output, output=args.effect_output)


def _effect(*, held, latest, before_ref, after_path, output):
    """Each position's problems under the committed and the new adjudication."""
    committed = subprocess.run(["git", "-C", str(REPO), "show",
                                before_ref + ":" + str((HERE / "adjudication.json").relative_to(REPO))],
                               check=True, capture_output=True).stdout
    with tempfile.NamedTemporaryFile(suffix=".json") as handle:
        handle.write(committed)
        handle.flush()
        tables = {"before": reading.load_adjudications(handle.name), "after": reading.load_adjudications(after_path)}
    positions, totals = {}, {side: {"wrongly_taken": 0, "missed": 0, "agree": 0} for side in tables}
    for record, document in held:
        chosen = sorted(c["block_index"] for c in board_composition_facts(document=document)["candidates"])
        entry = {"years": "latest" if record["position"] in latest else "older"}
        for side, table in tables.items():
            answer = reading.read_position(document=document, chosen=chosen, reading=record, adjudications=table)
            problems = {kind: sorted(item["i"] if isinstance(item, dict) else item for item in items)
                        for kind, items in answer["problems"].items() if items}
            entry[side] = {"verdict": answer["verdict"], "problems": problems}
            totals[side]["wrongly_taken"] += len(problems.get("wrongly_taken", []))
            totals[side]["missed"] += len(problems.get("missed", []))
            totals[side]["agree"] += answer["verdict"] == "READING_AGREES"
        positions[record["position"]] = entry
    output.write_text(json.dumps({
        "record_type": "C02_ADJUDICATION_EFFECT",
        "selection": "today's scripts/vnext/historical_board_composition_v2.py on each judged position's document",
        "before": before_ref + ":" + str((HERE / "adjudication.json").relative_to(REPO)),
        "after": "the adjudication this tool wrote",
        "totals": totals, "positions": positions}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
