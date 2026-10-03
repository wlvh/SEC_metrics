"""Show that the D04 reference stops where it should (in memory; the source is not edited).

Each injection breaks one guard of ``d04_reference.main`` and must make it stop
with that guard's refusal; the control must write a reference. Zero calls.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/model-egress/dev-dry-run/d04_reference_injections.py <inputs dir>
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import d04_reference as reference  # noqa: E402


def _outcome(inputs):
    with tempfile.TemporaryDirectory() as scratch:
        try:
            reference.main(inputs, Path(scratch) / "out.json")
        except SystemExit as refusal:
            return str(refusal).split(":", 1)[0]
    return "WRITTEN"


def main(inputs):
    rows = []
    original_judgements, original_strings = list(reference.JUDGEMENTS), reference._strings
    original_assessment = reference.ASSESSMENT
    cases = [
        ("CONTROL", lambda: None, "WRITTEN"),
        # A context nobody judged is not counted as harmless.
        ("A_JUDGEMENT_IS_MISSING",
         lambda: setattr(reference, "JUDGEMENTS", original_judgements[:-2] + original_judgements[-1:]),
         "D04_REFERENCE_CUE_NOT_JUDGED_EXACTLY_ONCE"),
        # A walk that skips the blocks finds nothing, which is not the same as
        # the filing saying nothing: the candidate's own block must be reached.
        ("THE_WALK_SKIPS_THE_BLOCKS",
         lambda: setattr(reference, "_strings",
                         lambda value, path: (item for item in original_strings(value, path)
                                              if "blocks" not in item[0])),
         "D04_REFERENCE_SEARCH_MISSED_A_REQUIRED_CANDIDATE"),
        # Assessment wording anywhere in the units stops the reference until read.
        ("ASSESSMENT_WORDING_PRESENT",
         lambda: setattr(reference, "ASSESSMENT", __import__("re").compile(r"(?i)streaming")),
         "D04_REFERENCE_FOUND_ASSESSMENT_WORDING"),
    ]
    for name, break_it, expected in cases:
        reference.JUDGEMENTS, reference._strings = list(original_judgements), original_strings
        reference.ASSESSMENT = original_assessment
        break_it()
        got = _outcome(inputs)
        rows.append({"case": name, "expected": expected, "got": got, "as_expected": got == expected})
    reference.JUDGEMENTS, reference._strings = original_judgements, original_strings
    reference.ASSESSMENT = original_assessment
    result = {"record_type": "ISSUE_47_D04_PRE_CALL_REFERENCE_CHECKS", "results": rows,
              "all_as_expected": all(row["as_expected"] for row in rows), "calls": [0, 0, 0]}
    (HERE / "d04-reference-injections.json").write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result))
    return 0 if result["all_as_expected"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
