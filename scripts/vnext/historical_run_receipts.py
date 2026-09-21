"""Read what a frozen historical Run recorded, without replaying it.

The coverage matrix used to answer "did this position produce a value" by
building a second candidate, a second Evidence check, a second system review
decision and a second Result - none of which was the Run's. A statistic
computed by a second implementation is not a statistic about the system, and
the two disagreed in both directions: the matrix reported ``native_run_wired``
as a hard-coded ``False`` while 114 frozen Runs existed, and it reported B01 and
B03 as EXACT while the public renderer still refused them.

This reads instead. No filing is parsed, no candidate is built, no review
decision is made. What it does check is the three file hashes the manifest
already carries, because a directory that has been edited is not the Run it
claims to be - and that check costs a file read, not a parse.

A receipt is evidence of what a Run recorded. It is not evidence that the
recorded content is right: a Run can be FROZEN, PASSED and EXACT and still hold
another item's text. Those are separate states and the report keeps them apart.
"""
import json
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file

RECORD_TYPE = "HISTORICAL_RUN_RECEIPT"
ROW_BUNDLE_NAME = "row_receipt.json"
ROW_BUNDLE_RECORD_TYPE = "HISTORICAL_PERIOD_ROW_BUNDLE"
_HASHED_FILES = (("records_file_hash", "records.jsonl"),
                 ("review_decisions_file_hash", "review_decisions.jsonl"),
                 ("validation_file_hash", "validation.json"))


class RunReceiptError(ValueError):
    """A run directory does not hold the Run its own manifest describes."""


def _need(condition, reason):
    if not condition:
        raise RunReceiptError(reason)


def classify_result(result):
    """The position status a recorded Result implies, by the Result's own fields."""
    if result["applicability"] != "APPLICABLE":
        return "N_A_STRUCTURAL"
    if result["publication"] == "WITHHELD":
        return "WITHHELD_SOURCE_OR_ROUTE"
    if result["value"] is None:
        return "NO_VALUE_PUBLISHED"
    return "VALUE_" + result["quality"]


def read_run_receipt(*, run_dir: Path):
    """One Run's own identity and outcome, verified against its own manifest.

    Args:
        run_dir: A frozen run directory holding ``manifest.json``.

    Returns:
        The receipt, or ``None`` when the directory holds no manifest at all.

    Raises:
        RunReceiptError: When the directory holds a manifest whose own hashes
            do not describe the files beside it.
    """
    run_dir = Path(run_dir)
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = strict_json_file(path=manifest_path)
    # A field that is not there cannot be checked, and "found no conflict"
    # because nothing was supplied is not verification. A FROZEN manifest
    # carries all three, so an absent one there is a refusal; anywhere else the
    # receipt records which were checked and which were not, and the caller
    # decides what an unverified receipt is worth.
    frozen = manifest.get("status") == "FROZEN"
    verified, unverified = [], []
    for key, name in _HASHED_FILES:
        recorded = manifest.get(key)
        if recorded is None:
            _need(not frozen, "RUN_RECEIPT_HASH_ABSENT:" + key)
            unverified.append(name)
            continue
        path = run_dir / name
        _need(path.is_file() and not path.is_symlink(),
              "RUN_RECEIPT_FILE_MISSING:" + name)
        _need(sha256_file(path=path) == recorded,
              "RUN_RECEIPT_FILE_CHANGED:" + name)
        verified.append(name)
    results = []
    for line in (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("record_type") != "METRIC_RESULT":
            continue
        results.append({key: record.get(key) for key in (
            "metric_id", "result_id", "value", "unit", "quality", "publication",
            "reason_code", "applicability", "period_start", "period_end",
            # Two results can share company, metric and period end and still be
            # different measurements. The scope and the value kind are what say
            # so, and a coordinate key does not carry either.
            "scope_key", "value_kind")})
    validation = None
    if (run_dir / "validation.json").is_file():
        validation = strict_json_file(path=run_dir / "validation.json").get("status")
    body = {"record_type": RECORD_TYPE, "schema_version": 1,
            "run_directory_name": run_dir.name,
            "run_id": manifest.get("run_id"), "run_status": manifest.get("status"),
            "requirement_id": manifest.get("requirement_id"),
            "requirement_closure_hash": manifest.get("requirement_closure_hash"),
            "company_id": manifest.get("company_id"),
            "target_period": manifest.get("target_period"),
            "validation_status": validation,
            "results": sorted(results, key=lambda r: str(r["metric_id"])),
            "manifest_file_hashes_verified": not unverified,
            "verified_files": verified, "unverified_files": unverified,
            "public_row": read_row_bundle(run_dir=run_dir),
            "replayed": False, "business_content_verified": False}
    return {**body, "receipt_id": content_hash(value=body)}


def read_row_bundle(*, run_dir: Path):
    """What the public renderer wrote beside this Run, if it wrote anything.

    A Run that froze and validated is not the same as a position that reached
    a public row: the renderer has its own refusals - an unwired route kind, a
    unit the presentation policy disagrees with, an evidence set that does not
    cover the published items. Without this the report could only say "a Run
    exists" and leave the reader to assume the rest.

    The bundle is checked rather than trusted. Its receipt carries the hashes
    of the row and the evidence it was written with, so an edited bundle is
    refused the same way an edited records file is.
    """
    path = Path(run_dir) / ROW_BUNDLE_NAME
    if not path.is_file() or path.is_symlink():
        return None
    bundle = strict_json_file(path=path)
    _need(bundle.get("record_type") == ROW_BUNDLE_RECORD_TYPE,
          "ROW_BUNDLE_TYPE_INVALID")
    receipt, row, evidence = bundle["receipt"], bundle["row"], bundle["evidence"]
    _need(receipt["row_hash"] == content_hash(value=row),
          "ROW_BUNDLE_ROW_CHANGED")
    _need(receipt["evidence_hash"] == content_hash(value=evidence),
          "ROW_BUNDLE_EVIDENCE_CHANGED")
    _need(receipt["evidence_count"] == len(evidence),
          "ROW_BUNDLE_EVIDENCE_COUNT_CHANGED")
    return {key: receipt[key] for key in (
        "status", "run_id", "run_status", "requirement_id", "result_id",
        "primary_metric_id", "period_selection_id", "row_hash", "evidence_hash",
        "evidence_count", "source_validation", "production_authorized", "receipt_id")}


def collect_run_receipts(*, runs_root: Path):
    """Every readable Run receipt under one directory of run directories.

    A directory without a manifest is skipped rather than reported as a broken
    Run: the driver writes its own artifacts beside the run directories.
    """
    runs_root = Path(runs_root)
    _need(runs_root.is_dir() and not runs_root.is_symlink(),
          "RUN_RECEIPT_ROOT_INVALID:" + str(runs_root))
    receipts = []
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir() or child.is_symlink():
            continue
        receipt = read_run_receipt(run_dir=child)
        if receipt is not None:
            receipts.append(receipt)
    return receipts


def result_identity(*, receipt, result):
    """What a coordinate key does not distinguish, kept beside it.

    The key is company, metric and period end. That is the coordinate the
    coverage frame enumerates, and it is deliberately coarser than a
    measurement: the pinned fiscal coordinate, the window actually measured,
    the scope and the filing the Run selected are all separate facts, and two
    results can agree on the key and disagree on any of them.

    They are not folded into the key, because the frame's rows are coordinates
    and a report that keyed on the measurement would stop having a row per
    coordinate. They are carried so that a merge can be checked instead of
    assumed - result_id already differs whenever any of them does, so the
    selector's equality test is exact, and this is what makes an inequality
    readable when it happens.
    """
    period = receipt["target_period"] or {}
    return {"pinned_fiscal_year": period.get("fiscal_year"),
            "pinned_period_end": period.get("period_end"),
            "measured_period_start": result.get("period_start"),
            "measured_period_end": result.get("period_end"),
            "scope_key": result.get("scope_key"),
            "value_kind": result.get("value_kind"),
            "requirement_closure_hash": receipt["requirement_closure_hash"],
            "run_id": receipt["run_id"]}


def index_receipts(*, receipts):
    """Receipts keyed by the coordinate a coverage position carries.

    A coordinate is company, metric and period end. Two receipts for the same
    coordinate are kept, not collapsed: the same position run under two
    Requirement closures is exactly the case the report has to show rather than
    silently pick a winner for.
    """
    index = {}
    for receipt in receipts:
        period = receipt["target_period"] or {}
        for result in receipt["results"]:
            key = (receipt["company_id"], result["metric_id"],
                   result.get("period_end") or period.get("period_end"))
            index.setdefault(key, []).append(
                {"receipt": receipt, "result": result,
                 "identity": result_identity(receipt=receipt, result=result)})
    return index
