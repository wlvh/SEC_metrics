"""Faults injected into the C02 reading tool and adjudicator, and the cases that catch them.

Each fault is one edit to the module's source, made in memory: the edited text
is compiled under the module's own path in a fresh interpreter with its own
bytecode cache, so nothing in the checkout changes. Before any fault, the same
harness runs each named case on the unedited source and must see no failure
(a harness that fails on clean code would "catch" everything). An edit that
does not match its target exactly once stops the run before anything runs.

Usage:
    python3 docs/evidence/issue47_history/c02-composition-facts/adjudication_injections.py
"""
import json
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
TOOL = REPO / "tools/read_c02_composition.py"
ADJ = REPO / "docs/evidence/issue47_history/c02-composition-facts/adjudicate.py"
INJECTIONS = [
    ("AN_ADJUDICATED_FACT_IS_NEVER_MISSED", TOOL,
     '        if not any(other in selected for other in cover):\n            problems["missed"].append({"i": index, "why": "adjudicated: " + row["rule"], "redundant_with": cover})',
     '        pass',
     "tests.vnext.test_historical_board_composition_filings.AnAdjudicatedFactIsMissedUnlessSomethingSelectedStatesIt"),
    ("A_COVERING_BLOCK_IS_IGNORED", TOOL,
     '        if not any(other in selected for other in cover):\n            problems["missed"].append({"i": index, "why": "adjudicated: " + row["rule"], "redundant_with": cover})',
     '        problems["missed"].append({"i": index, "why": "adjudicated: " + row["rule"], "redundant_with": cover})',
     "tests.vnext.test_historical_board_composition_filings.AnAdjudicatedFactIsMissedUnlessSomethingSelectedStatesIt"),
    ("A_FACT_DECISION_SKIPS_ITS_TEXT_BINDING", TOOL,
     '        if adjudication(index) is None:\n            continue\n        cover = row.get("redundant_with") or []',
     '        cover = row.get("redundant_with") or []',
     "tests.vnext.test_historical_board_composition_filings.AnAdjudicatedFactIsMissedUnlessSomethingSelectedStatesIt"),
    ("THE_PRESIDING_DUTY_IS_DECIDED_A_FACT", ADJ,
     '"PRESIDING_DUTY": ("NOT",', '"PRESIDING_DUTY": ("FACT",',
     "tests.vnext.test_historical_board_composition_filings.EveryReadPositionAgreesWithTheRoute.test_the_adjudication_is_exactly_what_its_rules_decide_here"),
    ("THE_SAME_SENTENCE_IS_NOT_CHECKED_FOR_A_DEPARTURE", ADJ,
     '                rest = [JOIN.sub(" ", s) for s in sentences(text)]',
     '                rest = [s for s in sentences(text) if not JOIN.search(s)]',
     "tests.vnext.test_historical_board_composition_filings.EveryReadPositionAgreesWithTheRoute.test_the_adjudication_is_exactly_what_its_rules_decide_here"),
    ("A_READER_CITATION_STANDS_OVER_THE_ADJUDICATION", TOOL,
     '        if decided is not None and decided["decision"] == "FACT":\n'
     '            # The adjudication has rejected the reader\'s citation: only the\n'
     '            # blocks it names state this block\'s facts (DATED_ROLE_CHANGE).\n'
     '            cover = decided.get("redundant_with") or []\n',
     '',
     "tests.vnext.test_historical_board_composition_filings.ADatedRoleChangeIsCoveredOnlyByTheSameChange"),
    ("A_YEAR_COVERS_A_DAY", ADJ,
     '    return all(want is None or want == have for want, have in zip(g, o))',
     '    return g[0] == o[0]',
     "tests.vnext.test_historical_board_composition_filings.ADatedRoleChangeIsCoveredOnlyByTheSameChange"),
    ("ANOTHER_PERSONS_CHANGE_COVERS", ADJ,
     '    return (re.search(r"\\b" + re.escape(surname) + r"\\b", text) is not None\n            and re.search(pattern',
     '    return (True\n            and re.search(pattern',
     "tests.vnext.test_historical_board_composition_filings.ADatedRoleChangeIsCoveredOnlyByTheSameChange"),
    ("A_CHANGE_BEFORE_THE_YEAR_IS_DECIDED", ADJ,
     '        if not dates or all(_before(date, start) for date in dates):',
     '        if not dates:',
     "tests.vnext.test_historical_board_composition_filings.ADatedRoleChangeIsCoveredOnlyByTheSameChange"),
    ("A_ROSTER_COVERS_A_JOIN", ADJ,
     '                    recover(index, "JOIN_IN_THE_YEAR", cover, dates=joins)',
     '                    decide(index, "JOIN_IN_THE_YEAR", dates=joins)',
     "tests.vnext.test_historical_board_composition_filings.AJoinInTheYearIsCoveredOnlyByTheSamePersonsJoin"),
    ("A_JOINER_IS_ANY_NAME_BEFORE_THE_PRONOUN", ADJ,
     '    if re.search(r"\\b(?:their|his|her)\\s+$", before, re.I):',
     '    if False:',
     "tests.vnext.test_historical_board_composition_filings.AJoinInTheYearIsCoveredOnlyByTheSamePersonsJoin"),
    ("ANOTHER_PERSONS_JOIN_COVERS", ADJ,
     '    return (re.search(r"\\b" + re.escape(surname) + r"\\b", text) is not None\n            and any(_same_date(date, match.group("date"))',
     '    return (True\n            and any(_same_date(date, match.group("date"))',
     "tests.vnext.test_historical_board_composition_filings.AJoinInTheYearIsCoveredOnlyByTheSamePersonsJoin"),
    ('A_HEADING_COVERS_A_DEPARTURE', ADJ,
     '        if (all(re.search(r"\\b" + re.escape(surname) + r"\\b", sentence) for surname in surnames)',
     '        if (True',
     'tests.vnext.test_historical_board_composition_filings.ATermEndingIsCoveredOnlyByTheSameDeparture'),
    ('ANOTHER_YEARS_DEPARTURE_COVERS', ADJ,
     'and DEPARTURE.search(sentence) is not None and (year is None or not years or year in years)):',
     'and DEPARTURE.search(sentence) is not None):',
     'tests.vnext.test_historical_board_composition_filings.ATermEndingIsCoveredOnlyByTheSameDeparture'),
    ('A_NOMINEES_TERM_IS_A_DEPARTURE', ADJ,
     '        if NOMINEES.search(sentence) and not re.search(r"\\bnot\\b", sentence, re.I):\n            continue',
     '        if False:\n            continue',
     'tests.vnext.test_historical_board_composition_filings.ATermEndingIsCoveredOnlyByTheSameDeparture'),
    ('A_PRONOUN_TERM_IS_ANYONES', ADJ,
     "                if len(people) != 1:\n                    # Not a named director's term: no one, or no one alone, is named.\n                    continue",
     '                if False:\n                    continue',
     'tests.vnext.test_historical_board_composition_filings.ATermEndingIsCoveredOnlyByTheSameDeparture'),
    ('A_POSSESSIVE_NEED_NOT_BE_A_PERSON', ADJ,
     '                if not re.search(r"(?:\\b(?:Mr|Ms|Mrs|Dr)\\s+|\\b(?!(?:The|A|An|Our|Its|This|That|Each|Every|Such)\\s)"\n                                 r"(?-i:[A-Z])[\\w\\-]+\\s+(?:(?-i:[A-Z])\\s+)?)$", sentence[:match.start("owner")]):',
     '                if False:',
     'tests.vnext.test_historical_board_composition_filings.ATermEndingIsCoveredOnlyByTheSameDeparture'),
    ('THE_NOMINEE_FIELD_IS_NOT_DECIDED', ADJ,
     '            decide(index, "NOMINEE_CARD_NO_COMMITTEE")', '            pass',
     'tests.vnext.test_historical_board_composition_filings.ANomineesNoCommitteeFieldIsNotAFact'),
    ('THE_NOMINEE_FIELD_IS_DECIDED_A_FACT', ADJ,
     '"NOMINEE_CARD_NO_COMMITTEE": ("NOT",', '"NOMINEE_CARD_NO_COMMITTEE": ("FACT",',
     'tests.vnext.test_historical_board_composition_filings.ANomineesNoCommitteeFieldIsNotAFact'),
    ('A_SITTING_DIRECTORS_FIELD_IS_A_NOMINEES', ADJ,
     '        if before is not None and NOT_YET.match(texts[before]):',
     '        if before is not None:',
     'tests.vnext.test_historical_board_composition_filings.ANomineesNoCommitteeFieldIsNotAFact'),
    ('THE_RELATIONSHIP_DETERMINATION_IS_NOT_DECIDED', ADJ,
     '        if RELATIONSHIPS.search(text):\n            decide(index, "INDEPENDENCE_RELATIONSHIP_DETERMINATION",',
     '        if False:\n            decide(index, "INDEPENDENCE_RELATIONSHIP_DETERMINATION",',
     'tests.vnext.test_historical_board_composition_filings.ACommitteesRelationshipDeterminationIsAFact'),
    ('THE_RELATIONSHIP_DETERMINATION_IS_DECIDED_NOT', ADJ,
     '"INDEPENDENCE_RELATIONSHIP_DETERMINATION": ("FACT",', '"INDEPENDENCE_RELATIONSHIP_DETERMINATION": ("NOT",',
     'tests.vnext.test_historical_board_composition_filings.ACommitteesRelationshipDeterminationIsAFact'),
    ('THE_SIGNERS_COMMITTEE_IS_NOT_DECIDED', ADJ,
     '        decide(index - 1, "REPORT_SIGNERS_COMMITTEE", redundant_with=cover - set(signers) - {index})',
     '        pass',
     'tests.vnext.test_historical_board_composition_filings.AReportsSigningCommitteeIsAFactAndItsSignOffIsNot'),
    ('THE_SIGN_OFF_IS_DECIDED_A_FACT', ADJ,
     '"REPORT_SIGN_OFF": ("NOT",', '"REPORT_SIGN_OFF": ("FACT",',
     'tests.vnext.test_historical_board_composition_filings.AReportsSigningCommitteeIsAFactAndItsSignOffIsNot'),
    ('A_SIGNATURE_COVERS_ITS_COMMITTEE', ADJ,
     'redundant_with=cover - set(signers) - {index})', 'redundant_with=cover - {index})',
     'tests.vnext.test_historical_board_composition_filings.AReportsSigningCommitteeIsAFactAndItsSignOffIsNot'),
    ('A_SIGN_OFF_NEED_NOT_HEAD_SIGNATURES', ADJ,
     '        if not signers:\n            continue\n        decide(index, "REPORT_SIGN_OFF")',
     '        decide(index, "REPORT_SIGN_OFF")',
     'tests.vnext.test_historical_board_composition_filings.AReportsSigningCommitteeIsAFactAndItsSignOffIsNot'),
    ('THE_COMMITTEE_NEED_NOT_BE_NAMED', ADJ,
     ' or not SUBMITTED_BY.search(texts[index - 1]):', ':',
     'tests.vnext.test_historical_board_composition_filings.AReportsSigningCommitteeIsAFactAndItsSignOffIsNot'),
]
RUNNER = textwrap.dedent('''
    import importlib.util, sys, types, unittest
    sys.path.insert(0, "{repo}/scripts"); sys.path.insert(0, "{repo}")
    target, source, case = sys.argv[1], open(sys.argv[2]).read(), sys.argv[3]
    if target.endswith("read_c02_composition.py"):
        import tools
        module = types.ModuleType("tools.read_c02_composition"); module.__file__ = target
        exec(compile(source, target, "exec"), module.__dict__)
        sys.modules["tools.read_c02_composition"] = module; tools.read_c02_composition = module
    else:
        real = importlib.util.spec_from_file_location
        def patched(name, location, *a, **k):
            spec = real(name, location, *a, **k)
            if str(location) == target:
                loader = spec.loader
                class L(type(loader)):
                    def get_data(self, path):
                        return source.encode() if str(path) == target else super().get_data(path)
                spec.loader = L(loader.name, loader.path)
            return spec
        importlib.util.spec_from_file_location = patched
    result = unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromName(case))
    print("FAILURES", len(result.failures) + len(result.errors), "RAN", result.testsRun)
''').format(repo=REPO)


def run(path, source, case, label):
    with tempfile.TemporaryDirectory() as scratch:
        edited = Path(scratch) / "edited.py"
        edited.write_text(source)
        proc = subprocess.run([sys.executable, "-c", RUNNER, str(path), str(edited), case], cwd=REPO,
                              capture_output=True, text=True, timeout=1800,
                              env={"PYTHONPYCACHEPREFIX": str(Path(scratch) / "pycache"), "PATH": "/usr/bin:/bin"})
    line = [row for row in proc.stdout.splitlines() if row.startswith("FAILURES ")]
    if not line:
        raise SystemExit(label + ": the harness did not report (" + (proc.stdout + proc.stderr)[-400:] + ")")
    failures, ran = int(line[-1].split()[1]), int(line[-1].split()[3])
    return {"failures": failures, "ran": ran}


for name, path, old, new, case in INJECTIONS:
    if path.read_text().count(old) != 1:
        raise SystemExit("INJECTION_TARGET_NOT_UNIQUE:" + name)
controls = {}
for path, case in sorted({(str(p), c) for _n, p, _o, _new, c in INJECTIONS}):
    controls[case] = run(Path(path), Path(path).read_text(), case, "control")
    if controls[case]["failures"] or not controls[case]["ran"]:
        raise SystemExit("CONTROL_FAILED:" + case)
out = []
for name, path, old, new, case in INJECTIONS:
    result = run(path, path.read_text().replace(old, new), case, name)
    out.append({"injection": name, "module": str(path.relative_to(REPO)), "case": case,
                "caught": result["failures"] > 0, **result})
    print(name, result, flush=True)
(HERE / "adjudication-injections.json").write_text(json.dumps(
    {"record_type": "C02_ADJUDICATION_FAULT_INJECTIONS", "controls": controls, "injections": out,
     "all_caught": all(row["caught"] for row in out)}, indent=1) + "\n")
