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
import re
from pathlib import Path

from .canonical import content_hash, sha256_file, strict_json_file
# The writer owns where the bundle goes; this reads the same expression
# rather than a second copy of it.
from .historical_projection import ROW_BUNDLE_NAME, row_bundle_path

RECORD_TYPE = "HISTORICAL_RUN_RECEIPT"
ROW_BUNDLE_RECORD_TYPE = "HISTORICAL_PERIOD_ROW_BUNDLE"
_HASHED_FILES = (("records_file_hash", "records.jsonl"),
                 ("review_decisions_file_hash", "review_decisions.jsonl"),
                 ("validation_file_hash", "validation.json"))


class RunReceiptError(ValueError):
    """A run directory does not hold the Run its own manifest describes."""


_ACCESSION = re.compile(r"\d{10}-\d{2}-\d{6}\Z")
# Where an observation's binding names the source references it was read from.
# Each is a list or a single id; the claim lists name verified claims, whose own
# source reference is the filing.
_BINDING_REFERENCE_KEYS = ("source_reference_id",)
_BINDING_REFERENCE_LIST_KEYS = ("source_reference_ids", "ordered_source_reference_ids")
_BINDING_CLAIM_LIST_KEYS = ("matched_verified_claim_ids", "matched_item_4_01_claim_ids")
_BINDING_ACCESSION_KEYS = ("accession", "current_accession", "prior_accession")


def _result_bindings(records):
    """The filings and registrant entities each recorded result was computed from.

    A result's coordinate and value do not say which filing produced it, and an
    acceptance that says "this filing reports this value" has to be able to
    tell whether the result in front of it came from that filing. The Run
    records the answer already: the trace names its input observations, each
    observation's binding names accessions and source references, and each
    source reference names its accession. This follows those links and nothing
    else - no filing is opened.

    Submissions inventories are keyed by a pseudo-accession, not a filing, and
    are left out: they say which filings exist, not which one was read.

    Returns:
        ``{result_id: {"filings": [...], "entities": [...]}}`` with both lists
        sorted and unique. A result without a trace in this Run binds nothing.
    """
    references = {r["source_reference_id"]: r for r in records
                  if r.get("record_type") == "SOURCE_REFERENCE"}
    claims = {r["verified_claim_id"]: r for r in records
              if r.get("record_type") == "DETERMINISTIC_VERIFIED_CLAIM"}
    observations = {r["observation_id"]: r for r in records
                    if r.get("record_type") == "VERIFIED_OBSERVATION"}
    traces = {r["trace_id"]: r for r in records
              if r.get("record_type") == "EXECUTION_TRACE"}
    bound = {}
    for record in records:
        if record.get("record_type") != "METRIC_RESULT":
            continue
        filings, entities = set(), set()
        trace = traces.get(record.get("trace_id"))
        if trace is not None:
            target = trace.get("calculation_target") or {}
            if _ACCESSION.match(str(target.get("accession") or "")):
                filings.add(target["accession"])
            if target.get("entity"):
                entities.add(str(target["entity"]))
            for observation_id in trace.get("input_observation_ids") or ():
                binding = (observations.get(observation_id) or {}).get("source_binding") or {}
                for key in _BINDING_ACCESSION_KEYS:
                    if _ACCESSION.match(str(binding.get(key) or "")):
                        filings.add(binding[key])
                if binding.get("entity"):
                    entities.add(str(binding["entity"]))
                named = [binding[key] for key in _BINDING_REFERENCE_KEYS if binding.get(key)]
                for key in _BINDING_REFERENCE_LIST_KEYS:
                    named.extend(binding.get(key) or ())
                for key in _BINDING_CLAIM_LIST_KEYS:
                    named.extend(claims[claim]["source_reference_id"]
                                 for claim in binding.get(key) or () if claim in claims)
                for reference_id in named:
                    accession = str((references.get(reference_id) or {}).get("accession") or "")
                    if _ACCESSION.match(accession):
                        filings.add(accession)
        bound[record.get("result_id")] = {"filings": sorted(filings),
                                          "entities": sorted(entities)}
    return bound


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
    records = [json.loads(line) for line in
               (run_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
               if line.strip()]
    bindings = _result_bindings(records)
    results = []
    for record in records:
        if record.get("record_type") != "METRIC_RESULT":
            continue
        results.append({**{key: record.get(key) for key in (
            "metric_id", "result_id", "value", "unit", "quality", "publication",
            "reason_code", "applicability", "period_start", "period_end",
            # Two results can share company, metric and period end and still be
            # different measurements. The scope and the value kind are what say
            # so, and a coordinate key does not carry either.
            "scope_key", "value_kind",
            # What the metric means, as the Run recorded it: the compiled Spec's
            # semantics, its dependencies' closures and the declared runtime
            # semantic versions. It does not move with unrelated repository
            # bytes, which is what makes it bindable where the Requirement
            # closure is not.
            "spec_closure_hash")},
            **bindings.get(record.get("result_id"),
                           {"filings": [], "entities": []})})
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
            "public_row": read_row_bundle(run_dir=run_dir, manifest=manifest,
                                          results=results),
            "replayed": False, "business_content_verified": False}
    return {**body, "receipt_id": content_hash(value=body)}


_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")
# What the renderer writes and what a reader may therefore require. Listed so
# that a bundle missing any of them is refused rather than read partially.
_ROW_BUNDLE_FIELDS = ("status", "run_id", "run_status", "requirement_id", "result_id",
                      "primary_metric_id", "period_selection_id", "row_hash",
                      "evidence_hash", "evidence_count", "source_validation",
                      # What produced the row, not just what it was produced
                      # from. The renderer writes both and they were sitting
                      # unread; two rows for one result that came out of
                      # different renderer or policy bytes are not two views
                      # of one row.
                      "presentation_policy_sha256", "renderer_sha256",
                      "production_authorized", "receipt_id")
# The renderer's two states. A preview is rendered from a mechanical replay of
# an open Run and is evidence of something; it is not evidence that a frozen
# Run reached a public row, so the reader keeps them apart instead of calling
# both "a row exists".
ROW_BUNDLE_STATES = {"FROZEN_CANDIDATE": "FROZEN", "VERIFIED_OPEN_PREVIEW": "OPEN"}


def read_row_bundle(*, run_dir: Path, manifest, results):
    """What the public renderer wrote beside this Run, if it wrote anything.

    A Run that froze and validated is not the same as a position that reached
    a public row: the renderer has its own refusals - an unwired route kind, a
    unit the presentation policy disagrees with, an evidence set that does not
    cover the published items. Without this the report could only say "a Run
    exists" and leave the reader to assume the rest.

    The bundle is checked rather than trusted, and the first version of this
    check was not enough. It verified the receipt's summary of its own row and
    evidence and stopped there, so a bundle whose row and evidence were
    untouched but whose receipt named another Run, another Requirement and
    ``NOT_REPLAYED`` was still read - and the position still counted as having
    reached a public row. Verifying that a document agrees with itself is not
    verifying that it describes the Run it is lying beside.

    So three things are checked now. The receipt's own identity is recomputed,
    which is what the stale ``receipt_id`` in that probe failed. The Run
    identity it claims - run, status, Requirement - has to be this Run's. And
    the result it claims has to be one this Run actually recorded, under the
    metric the receipt names.

    What this does not claim: that a Run itself could not be forged. This is a
    reader refusing evidence that does not match what it sits beside, not a
    proof about Run construction.

    A refused bundle is reported, not raised. The manifest's three file hashes
    are the Run's integrity envelope and they are checked separately; this file
    is not inside it, so a side-car that has been edited cannot forge the
    records and refusing it should not erase them. Raising here took the whole
    matrix down over one directory and threw away every other Run's
    independently verified evidence with it - the same shape of mistake as
    picking one run to read every layer off.
    """
    path = row_bundle_path(run_dir=run_dir)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        checked = _check_row_bundle(path=path, manifest=manifest, results=results)
    except RunReceiptError as refusal:
        return {"accepted": False, "refusal": str(refusal),
                **{key: None for key in _ROW_BUNDLE_FIELDS}}
    except ValueError as unreadable:
        # A bundle that is not readable JSON, or not the shape strict_json_file
        # accepts. Named as unreadable rather than reported as absent, because
        # "there is no row" and "the row cannot be read" are different facts.
        return {"accepted": False, "refusal": "ROW_BUNDLE_UNREADABLE:" + str(unreadable),
                **{key: None for key in _ROW_BUNDLE_FIELDS}}
    return {"accepted": True, "refusal": None, **checked}


def _check_row_bundle(*, path: Path, manifest, results):
    """The checks themselves, raising so that each names its own failure."""
    bundle = strict_json_file(path=path)
    _need(bundle.get("record_type") == ROW_BUNDLE_RECORD_TYPE,
          "ROW_BUNDLE_TYPE_INVALID")
    receipt, row, evidence = bundle["receipt"], bundle["row"], bundle["evidence"]
    _need(set(_ROW_BUNDLE_FIELDS) <= set(receipt), "ROW_BUNDLE_RECEIPT_FIELDS_MISSING")
    _need(receipt["row_hash"] == content_hash(value=row),
          "ROW_BUNDLE_ROW_CHANGED")
    _need(receipt["evidence_hash"] == content_hash(value=evidence),
          "ROW_BUNDLE_EVIDENCE_CHANGED")
    _need(receipt["evidence_count"] == len(evidence),
          "ROW_BUNDLE_EVIDENCE_COUNT_CHANGED")
    # The renderer builds receipt_id over the receipt without it, so the same
    # computation reproduces it here or the receipt has been edited since.
    identity = {key: value for key, value in receipt.items() if key != "receipt_id"}
    _need(receipt["receipt_id"] == content_hash(value=identity),
          "ROW_BUNDLE_RECEIPT_IDENTITY_CHANGED")
    _need(receipt["run_id"] == manifest.get("run_id")
          and receipt["run_status"] == manifest.get("status")
          and receipt["requirement_id"] == manifest.get("requirement_id"),
          "ROW_BUNDLE_IS_FOR_ANOTHER_RUN")
    _need(receipt["status"] in ROW_BUNDLE_STATES
          and ROW_BUNDLE_STATES[receipt["status"]] == manifest.get("status"),
          "ROW_BUNDLE_STATE_DISAGREES_WITH_RUN")
    named = [result for result in results
             if result["result_id"] == receipt["result_id"]
             and result["metric_id"] == receipt["primary_metric_id"]]
    _need(len(named) == 1, "ROW_BUNDLE_RESULT_IS_NOT_THIS_RUNS")
    _need(isinstance(receipt["period_selection_id"], str)
          and bool(_SHA.match(receipt["period_selection_id"])),
          "ROW_BUNDLE_PERIOD_SELECTION_INVALID")
    _need(receipt["source_validation"] == "FULL_NATIVE_HISTORICAL_RUN_REPLAY",
          "ROW_BUNDLE_SOURCE_VALIDATION_CHANGED:" + str(receipt["source_validation"]))
    return {key: receipt[key] for key in _ROW_BUNDLE_FIELDS}


def collect_run_receipts(*, runs_root: Path):
    """Every readable Run receipt under one directory of run directories.

    A directory without a manifest is skipped rather than reported as a broken
    Run: the driver writes its own artifacts beside the run directories.

    A directory that holds a manifest its own files do not match is reported
    rather than raised. Reading one Run and refusing it is right - the
    directory is not the Run it claims. Reading many and refusing all of them
    over one is not: a runs root read while a batch is still writing always
    holds a run mid-write, and raising there produced no report at all rather
    than a report with one line missing. Measured on a live batch: three of 87
    directories were OPEN with a manifest seconds old, and the whole matrix was
    unbuildable because of them.

    The two cases are not the same and the record says which. An OPEN run whose
    files do not match its manifest is being written. A FROZEN one is a
    directory that is not the Run it claims, and that is the loud case.
    """
    runs_root = Path(runs_root)
    _need(runs_root.is_dir() and not runs_root.is_symlink(),
          "RUN_RECEIPT_ROOT_INVALID:" + str(runs_root))
    receipts, unreadable = [], []
    directories = 0
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir() or child.is_symlink():
            continue
        directories += 1
        try:
            receipt = read_run_receipt(run_dir=child)
        except RunReceiptError as refusal:
            # The manifest itself parsed - the hash it carries is what failed -
            # so the status it claims can be reported, as a claim.
            claimed = None
            try:
                claimed = strict_json_file(path=child / "manifest.json").get("status")
            except ValueError:
                claimed = None
            unreadable.append({"run_directory_name": child.name, "reason": str(refusal),
                               "claimed_run_status": claimed,
                               "reading": ("RUN_IS_BEING_WRITTEN" if claimed == "OPEN"
                                           else "DIRECTORY_IS_NOT_THE_RUN_IT_CLAIMS")})
            continue
        if receipt is not None:
            receipts.append(receipt)
    # A root full of directories and no Run is reported, not returned empty.
    # Measured: a batch writes `<root>/<period>/run-<period>-<metric>`, the scan
    # is one level, and pointing the report at that root found nothing - so
    # every position read as "has a route and was never run" when 372 Runs
    # existed one level down. An absence has to be established before it is
    # reported as a fact, and "I looked in the wrong place" is not an absence.
    _need(not directories or receipts or unreadable,
          "RUN_RECEIPT_ROOT_HOLDS_NO_RUNS:" + str(directories)
          + " directories, none carrying a manifest: " + str(runs_root))
    return {"receipts": receipts, "unreadable": unreadable}


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
            "unit": result.get("unit"),
            "spec_closure_hash": result.get("spec_closure_hash"),
            "filings": list(result.get("filings") or ()),
            "entities": list(result.get("entities") or ()),
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
