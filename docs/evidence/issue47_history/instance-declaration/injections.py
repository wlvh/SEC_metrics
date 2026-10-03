"""Undo each part of the XBRL instance declaration and require the case written for it to fail.

Usage: python3 injections.py <out.json> [NAME ...]

Same harness as ../c03-first-ecd-release/injections.py: each injection edits a
file in place (exactly one match, must compile), runs the module holding its
case with a fresh bytecode prefix, and restores the bytes. The control run
must pass first. It edits the tree it lives in, so nothing else may read that
tree while it runs. Zero calls.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ecd_injections", HERE.parent / "c03-first-ecd-release/injections.py")
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)

SOURCE = "scripts/vnext/historical_instance_sources.py"
FRAME = "scripts/vnext/historical_source_acquisition.py"
RESUME = "scripts/vnext/historical_sec_resume.py"
CASES = "tests.vnext.test_historical_instance_sources"
harness.SOURCE, harness.NOTE, harness.MODULES, harness.CASES = SOURCE, FRAME, (CASES,), CASES
harness.INJECTIONS = {
    "THE_PRIMARY_IS_DECLARED_AS_AN_INSTANCE": (
        SOURCE,
        "        if role == ROLE:\n",
        "        if role in (ROLE, \"target_primary\"):\n",
        "test_the_declaration_alone_names_nothing_but_the_instances"),
    "A_MISSING_INDEX_DECLARES_NOTHING_SILENTLY": (
        SOURCE,
        "            limitations.append({\"accession\": accession, \"reason\": \"ACCESSION_INDEX_NOT_SAVED\",\n",
        "            (lambda **_: None)(**{\"accession\": accession, \"reason\": \"ACCESSION_INDEX_NOT_SAVED\",\n",
        "test_an_index_not_saved_is_a_limitation_not_an_empty_set"),
    "THE_FRAME_DOES_NOT_TAKE_THE_INSTANCES": (
        FRAME,
        "    requirements = _union(planned=requirements, added=instances[\"requirements\"])\n",
        "\n",
        "test_every_saved_index_names_exactly_what_the_reader_reads"),
    "THE_CLASS_IS_NOT_TERMINAL": (
        RESUME,
        "TERMINAL_CLASSES = (\"ACCESSION_XBRL_INSTANCE\", \"FISCAL_EVENT_FILING\",\n",
        "TERMINAL_CLASSES = (\"FISCAL_EVENT_FILING\",\n",
        "test_capturing_an_instance_declares_nothing_new"),
}
if __name__ == "__main__":
    sys.exit(harness.main(sys.argv[1], sys.argv[2:]))
