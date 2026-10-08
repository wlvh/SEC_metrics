"""In-process fault injections for the D01 reader's three JPMorgan steps.

Each injection replaces one name in the imported reader module and runs the
two test classes that read real filings; no file is edited. The control run
must pass and every injection must fail at least one test.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/d01-risk-headings/full-frame/inject.py
"""
import io, json, re, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from tools import read_d01_headings as reader
from tests.vnext import test_d01_byte_reading as t

def run(name, patch):
    saved = {k: getattr(reader, k) for k in patch}
    for k, v in patch.items():
        setattr(reader, k, v)
    try:
        suite = unittest.TestSuite()
        for cls in (t.JPMorgansLayoutTest, t.TheReaderReproducesThePublishedValueTest):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
        out = io.StringIO()
        result = unittest.TextTestRunner(stream=out, verbosity=0).run(suite)
        failed = sorted({test.id().split(".")[-1] for test, _ in result.failures + result.errors})
        return {"injection": name, "caught": bool(failed), "failing_tests": failed}
    finally:
        for k, v in saved.items():
            setattr(reader, k, v)

old_furniture = re.compile(r"^(?:table of contents|\d+|[ivx]+-\d+|.*form 10-k.*)$", re.I)
single_part = re.compile(r"^(?:table of contents|\d+|[ivx]+-\d+|.*form 10-k.*|part\s+[ivx]+)$", re.I)
results = [
    run("ITEM_TITLE_MUST_BE_BOLD", {"ITEM_1A_TITLE": re.compile(r"(?!)")}),
    run("NO_PART_LABEL_FURNITURE", {"FURNITURE": old_furniture}),
    run("ONLY_A_SINGLE_PART_LABEL_IS_FURNITURE", {"FURNITURE": single_part}),
    run("NO_TAGGED_COVER_DATE", {"_tagged_texts": lambda document, name: []}),
    run("TAGGED_TEXT_STOPS_AT_THE_FIRST_CLOSE", {"_tagged_texts": lambda document, name: [
        m.group(1).strip() for m in re.finditer(
            r'name="' + re.escape(name) + r'"[^>]*>(?:<[^>]+>)*([^<]+)<', document)]}),
]
control = run("CONTROL", {})
print(json.dumps({"control": control, "injections": results}, indent=1))
