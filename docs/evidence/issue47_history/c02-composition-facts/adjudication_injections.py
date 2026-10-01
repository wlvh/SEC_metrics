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
