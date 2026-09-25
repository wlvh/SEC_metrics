"""D04 at a pinned period: the ordinary native going-concern route, for the year asked.

The ordinary route (Issue #28, ``capacity_run.prepare_case`` for D04) does not
decide D04 itself. A model reviews every unit of the complete original source -
visible text, native XBRL facts and supplements, every current-period 10-K/A -
in groups, one request per group; each response passes the frozen per-request
acceptance (``d04_native_assessment.build_acceptance``: complete unit census,
literal source references, the program's own sentence-relation checks); the
accepted findings are assembled into one assessment whose branch says whether
there is going-concern language to excerpt or a defined-scope absence; and
``capacity_text_results`` turns that into Candidate, Evidence, Review and a
TEXT_V1 Result. A Run consumes a *registered* assessment and re-derives
everything that can be re-derived from it.

This module is that route for a pinned period. What changes is only what the
Issue requires to change:

* the source is the pinned period's (``historical_semantic_source``), not the
  latest annual input's;
* the registered assessment is #47's own - keyed by the pinned source and
  recorded under ``issue_47_v1`` - never one registered for #28. A #28
  registration is keyed to that Issue's Requirement and source identity, and
  consuming it here would put another Issue's authorised calls under #47's
  positions (docs/evidence/issue47_history/semantic-route-need/);
* the invocation binding the acceptance reads is derived from the request
  alone (``request_binding``). It carries exactly the fields the frozen
  acceptor reads from a plan - request, source and task-contract identities -
  and it is not a WB-3 invocation plan. #47 has no provider egress: WB-3's
  invocation controller registers requirement generations by id and does not
  know ``issue_47_v1``, and ``tools/check_provider_egress.py`` fixes the exact
  set of transport callers. Both are bound by bytes in the frozen generations,
  so opening a provider socket for #47 is a security-reviewed registration,
  not something this module can do (``historical_model_session``).

Registrations come in two modes. RECORDED_TEST_ONLY records responses a test
supplied; it proves the plumbing from a response to a Run and never a filing's
content, and it is consumed only when the caller asks for it by name. LIVE is
the only mode a batch uses by default, and a LIVE record is consumed only if it
is the creator's own journal record - a data directory cannot enroll its own
responses. There is no way to register LIVE today.

Every consumer re-derives, from the registered assistant outputs and under the
current code, each request's Candidate and Evidence and the assembled
assessment, and requires them equal to what was registered. A registration made
under older code that no longer re-derives is refused by name, not trusted.

B13 inside its approved scope (Ford, Enphase) is not wired here. Its source is
prepared (``historical_semantic_source``), but the ordinary chain's B13 request
contract is still being revised in Issue #28 - the base request's
classification defect is recorded there, and the role/relevance variants are
offline candidates it has not accepted - so a port now would spend model calls
on a contract its owner has not accepted. D03 has no native Run route in the
ordinary chain to port (``normal_run_v3``: registered B13/D04 consumption only).
"""
from pathlib import Path
from types import SimpleNamespace

from git_workspace import first_symlink_in_path

from .canonical import content_hash, sha256_bytes, strict_json_file, strict_json_loads
from .continuous_request_context import FORMAT_VERSION
from .d04_native_assessment import (CURRENT_KINDS, SPEC_PATH as D04_SPEC_PATH,
                                    build_acceptance as accept_d04, native_source)
from .historical_semantic_source import prepare_historical_d04_semantic_source
from .historical_spec_revision import compile_historical_spec_file
from .native_unit_index import evidence_json_bytes, reconstruct_requests
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import raw_blob_record, resolve_repository_file, source_reference_record

REQUIREMENT_ID = "issue_47_v1"
SUPPORTED_METRICS = ("D04",)
MODES = ("LIVE", "RECORDED_TEST_ONLY")
EXPORT_PATHS = {"D04": "config/issue47_historical_going_concern_assessment.json"}
JOURNAL = ".git/issue47-historical-assessments"
SPEC_PATHS = {"D04": D04_SPEC_PATH}
RECORD_TYPE = "ISSUE_47_HISTORICAL_REGISTERED_ASSESSMENT_INPUT"
ASSESSMENT_RECORD_TYPE = "ISSUE_47_HISTORICAL_SOURCE_ASSESSMENT_SET"
BINDING_RECORD_TYPE = "ISSUE_47_HISTORICAL_REQUEST_BINDING"
INPUT_RECORD_TYPE = "ISSUE_47_HISTORICAL_SEMANTIC_INPUT_BINDING"
TEXT_BRANCHES = ("TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW",
                 "DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW")


class HistoricalSemanticError(ValueError):
    """A pinned semantic case could not be assembled; ``category`` says why."""

    def __init__(self, reason, category="IMPLEMENTATION_GAP"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="IMPLEMENTATION_GAP"):
    if not condition:
        raise HistoricalSemanticError(reason, category)


def pinned_native_source(*, repo_root: Path, company_id: str, metric_id: str, period_selection):
    """The complete native source the ordinary D04 route builds, for the pinned period.

    The request configuration is the ordinary route's current one: measured
    request grouping (``continuous_request_context``) and the complete-response
    contract, under which a response must answer every unit by id and order.
    """
    _need(metric_id in SUPPORTED_METRICS, "HISTORICAL_SEMANTIC_METRIC_NOT_WIRED:" + metric_id)
    return native_source(
        prepare_historical_d04_semantic_source(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection),
        request_context_format=FORMAT_VERSION, complete_response_contract=True)


def pinned_requests(source):
    """Every request the source partitions into, in order - the base contract only."""
    return reconstruct_requests(source)


def request_binding(request):
    """The invocation identity the frozen acceptor reads, derived from the request.

    ``build_acceptance`` reads four fields from its plan: the request identity
    (``selected_representation_hash``), the source identity
    (``source_identity_hash``), the task contract - metric and system prompt -
    and a plan id it folds into the Candidate's attempt id. The first three are
    computed here exactly as the ordinary plan builder computes them; the id is
    this binding's own content hash, and the record type says it is a #47
    request binding rather than a WB-3 plan.
    """
    body = {"record_type": BINDING_RECORD_TYPE, "requirement_id": REQUIREMENT_ID,
            "request_id": request["request_id"],
            "selected_representation_hash": request["request_id"],
            "source_identity_hash": request["source_id"],
            "task_contract_hash": content_hash(value={"metric": request["metric_id"],
                                                      "prompt": request["system_prompt"]}),
            "output_schema_hash": content_hash(value=request["response_protocol"])}
    return {**body, "ai_invocation_plan_id": content_hash(value=body)}


def accept_output(*, source, request, output):
    """One response through the frozen per-request acceptance."""
    _need(type(output) is bytes, "HISTORICAL_ASSESSMENT_OUTPUT_BYTES_REQUIRED")
    prepared = SimpleNamespace(source_bytes=evidence_json_bytes(source),
                               request_bytes=evidence_json_bytes(request))
    return accept_d04(prepared=prepared, plan=request_binding(request), response_body=output)


def assemble_assessment(*, source, requests, rows, mode):
    """The assessment set over every request, with the ordinary route's branch rule.

    The branch rule is ``capacity_native_assessment.collect_native_assessments``'
    for D04, restated without the ledger it reads rows from: a missing request
    is an incomplete assessment, never nondisclosure; more than one current
    going-concern kind needs cross-request reconciliation; any current
    target-registrant going-concern kind is text to excerpt; otherwise the
    defined scope holds no such statement. ``capacity_text_results`` re-derives
    the two text branches from the same findings and refuses a mismatch.
    """
    completed = {row["request_id"]: row for row in rows}
    _need(len(completed) == len(rows), "HISTORICAL_ASSESSMENT_DUPLICATE_REQUEST")
    missing = [r["request_id"] for r in requests if r["request_id"] not in completed]
    ordered = [completed[r["request_id"]] for r in requests if r["request_id"] in completed]
    _need(len(ordered) == len(rows), "HISTORICAL_ASSESSMENT_REQUEST_NOT_IN_SOURCE")
    findings = [f for row in ordered
                for f in row["candidate"]["selected"]["source_assessment"]["findings"]]
    current = [f for f in findings
               if f["subject"] == "TARGET_REGISTRANT" and f["timing"] == "CURRENT_REPORT"]
    kinds = {f["kind"] for f in current}
    relevant = [f for f in current if f["kind"] in CURRENT_KINDS]
    if missing:
        branch = "INCOMPLETE_ASSESSMENT_NOT_NONDISCLOSURE"
    elif len(kinds & CURRENT_KINDS) > 1:
        branch = "CROSS_REQUEST_GOING_CONCERN_RECONCILIATION_REQUIRED"
    elif relevant:
        branch = "TEXT_QUAL_PROPOSAL_REQUIRES_NATIVE_REVIEW"
    else:
        branch = "DEFINED_SCOPE_ABSENCE_PROPOSAL_REQUIRES_NATIVE_REVIEW"
    body = {"record_type": ASSESSMENT_RECORD_TYPE, "metric_id": source["metric_id"],
            "requirement_id": REQUIREMENT_ID, "source_id": source["semantic_source_id"],
            "company_id": source["company_id"],
            "required_request_ids": [r["request_id"] for r in requests], "completed": ordered,
            "missing_request_ids": missing, "failed_requests": [],
            "all_source_requests_accepted": not missing, "proposed_branch": branch,
            "source_findings": findings, "mode": mode, "metric_result_created": False,
            "review_complete": False, "production_authorized": False}
    return {**body, "assessment_set_id": content_hash(value=body)}


def _accepted_rows(*, source, requests, outputs):
    rows = []
    for request in requests:
        output = outputs[request["request_id"]]
        acceptance = accept_output(source=source, request=request, output=output)
        rows.append({"request_id": request["request_id"],
                     "binding_id": request_binding(request)["ai_invocation_plan_id"],
                     "assistant_output_sha256": sha256_bytes(content=output),
                     "candidate": acceptance["candidate_record"],
                     "evidence": acceptance["evidence_record"]})
    return rows


def registered_record(*, source, period_selection, outputs, mode):
    """A complete registration: every request answered and accepted.

    ``outputs`` maps each request id to the assistant output bytes. A set that
    does not answer every request of the source, or answers one it does not
    have, is not registered - an incomplete assessment is never an input.

    The record names the Requirement it is for, not the closure it was made
    under: every consumer re-derives the acceptance under its own code, so the
    rules that decide are always the current ones, and a registration they no
    longer re-derive is refused rather than trusted.
    """
    _need(mode in MODES, "HISTORICAL_ASSESSMENT_MODE_INVALID")
    requests = pinned_requests(source)
    _need(set(outputs) == {r["request_id"] for r in requests},
          "HISTORICAL_ASSESSMENT_OUTPUT_SET_DIFFERS_FROM_REQUEST_SET")
    rows = _accepted_rows(source=source, requests=requests, outputs=outputs)
    assessment = assemble_assessment(source=source, requests=requests, rows=rows, mode=mode)
    body = {"record_type": RECORD_TYPE, "schema_version": 1, "metric_id": source["metric_id"],
            "company_id": source["company_id"],
            "period_selection_id": period_selection["selection_id"],
            "source_id": source["semantic_source_id"], "requirement_id": REQUIREMENT_ID,
            "mode": mode, "request_context_format": source.get("request_context_format"),
            "response_contract_version": source.get("response_contract_version"),
            "assessment": assessment,
            "native_requests": [{"request_id": r["request_id"], "binding": request_binding(r),
                                 "assistant_output": outputs[r["request_id"]].decode("utf-8")}
                                for r in requests],
            "new_call_authority": False, "production_authorized": False}
    return {**body, "input_record_id": content_hash(value=body)}


def journal_directory(*, mode, metric_id, source_id):
    """Where the creator's own registrations for one pinned source live.

    Inside the checkout's ``.git``, so no data directory - and no Run - can
    write one. It is the counterpart of ``capacity_assessment_input``'s private
    journal, with #47's own name.
    """
    _need(mode in MODES and metric_id in SUPPORTED_METRICS, "HISTORICAL_ASSESSMENT_KEY_INVALID")
    git = ROOT / ".git"
    _need(git.is_dir() and not git.is_symlink(), "HISTORICAL_ASSESSMENT_JOURNAL_REQUIRED")
    path = ROOT / JOURNAL / mode / metric_id / source_id[len("sha256:"):]
    _need(first_symlink_in_path(path=path) is None, "HISTORICAL_ASSESSMENT_JOURNAL_ALIAS")
    return path


def validate_registered_record(*, record, source, mode):
    """Re-derive a registration from its outputs under the current code.

    Returns:
        The record, unchanged, if every request's Candidate and Evidence and the
        assembled assessment re-derive exactly.
    """
    _need(type(record) is dict and record.get("record_type") == RECORD_TYPE
          and record.get("schema_version") == 1
          and record.get("input_record_id") == content_hash(value={
              k: v for k, v in record.items() if k != "input_record_id"}),
          "HISTORICAL_REGISTERED_ASSESSMENT_CHANGED")
    _need(record["requirement_id"] == REQUIREMENT_ID,
          "HISTORICAL_ASSESSMENT_REGISTERED_FOR_ANOTHER_REQUIREMENT")
    _need(record["mode"] == mode and record["assessment"]["mode"] == mode,
          "HISTORICAL_ASSESSMENT_MODE_CONFLICT")
    _need(record["metric_id"] == source["metric_id"] and record["company_id"] == source["company_id"]
          and record["source_id"] == source["semantic_source_id"]
          and record["request_context_format"] == source.get("request_context_format")
          and record["response_contract_version"] == source.get("response_contract_version"),
          "HISTORICAL_ASSESSMENT_SOURCE_CHANGED")
    _need(record["new_call_authority"] is False and record["production_authorized"] is False,
          "HISTORICAL_ASSESSMENT_AUTHORITY_CLAIMED")
    requests = pinned_requests(source)
    native = record["native_requests"]
    _need([row["request_id"] for row in native] == [r["request_id"] for r in requests]
          and all(row["binding"] == request_binding(r) for row, r in zip(native, requests)),
          "HISTORICAL_ASSESSMENT_REQUEST_SET_CHANGED")
    outputs = {row["request_id"]: row["assistant_output"].encode("utf-8") for row in native}
    rows = _accepted_rows(source=source, requests=requests, outputs=outputs)
    _need(rows == record["assessment"]["completed"],
          "HISTORICAL_ASSESSMENT_ACCEPTANCE_DOES_NOT_RE_DERIVE")
    _need(assemble_assessment(source=source, requests=requests, rows=rows, mode=mode)
          == record["assessment"], "HISTORICAL_ASSESSMENT_SET_DOES_NOT_RE_DERIVE")
    return record


def load_historical_assessment(*, data_root: Path, source, mode=None):
    """The registered assessment a Run may consume for this pinned source.

    From an installed data root the installed copy is read, and its mode is the
    Run's; from the checkout that registered it, the creator journal is read.
    Where both exist they must be the same record. A LIVE copy must be in the
    creator journal; a RECORDED_TEST_ONLY one carries no credit and may be
    replayed portably, but only ever when the caller or the installed copy names
    that mode - the default is LIVE, so a test registration is never picked up
    by a batch.
    """
    metric_id = source["metric_id"]
    _need(metric_id in SUPPORTED_METRICS, "HISTORICAL_SEMANTIC_METRIC_NOT_WIRED:" + metric_id)
    export = Path(data_root) / EXPORT_PATHS[metric_id]
    installed = (strict_json_file(path=resolve_repository_file(
        repo_root=data_root, repo_relative_path=EXPORT_PATHS[metric_id]))
        if export.exists() else None)
    if mode is None:
        mode = installed["mode"] if installed is not None else "LIVE"
    _need(mode in MODES, "HISTORICAL_ASSESSMENT_MODE_INVALID")
    _need(installed is None or installed.get("mode") == mode, "HISTORICAL_ASSESSMENT_MODE_CONFLICT")
    has_journal = (ROOT / ".git").is_dir()
    directory = (journal_directory(mode=mode, metric_id=metric_id,
                                   source_id=source["semantic_source_id"])
                 if has_journal else None)
    if installed is None:
        choices = sorted(directory.glob("*.json")) if directory is not None and directory.is_dir() else []
        _need(bool(choices), "HISTORICAL_SEMANTIC_ASSESSMENT_NOT_REGISTERED:" + mode,
              "MODEL_REVIEW_NOT_EXECUTED")
        _need(len(choices) == 1, "HISTORICAL_SEMANTIC_ASSESSMENT_AMBIGUOUS:" + mode)
        record = strict_json_file(path=choices[0])
    else:
        record = installed
        path = (directory / (str(record.get("input_record_id", ""))[len("sha256:"):] + ".json")
                if directory is not None else None)
        if path is not None and path.is_file():
            _need(strict_json_file(path=path) == record, "HISTORICAL_ASSESSMENT_INSTALLED_COPY_CHANGED")
        else:
            _need(mode == "RECORDED_TEST_ONLY", "HISTORICAL_LIVE_ASSESSMENT_NOT_IN_CREATOR_JOURNAL")
    return validate_registered_record(record=record, source=source, mode=mode)


def prepare_historical_semantic_case(*, repo_root: Path, company_id: str, metric_id: str,
                                     period_selection, assessment_mode=None):
    """One pinned period's D04 text case, from its registered assessment.

    Returns:
        The case's records, sources, Spec, coordinate and ``text_arguments``
        (which hold the filing's bytes and so never enter a binding), plus the
        registered record for installation and a content-addressed component.
    """
    source = pinned_native_source(repo_root=repo_root, company_id=company_id,
                                  metric_id=metric_id, period_selection=period_selection)
    registered = load_historical_assessment(data_root=repo_root, source=source,
                                            mode=assessment_mode)
    assessment = registered["assessment"]
    _need(assessment["proposed_branch"] in TEXT_BRANCHES,
          metric_id + "_NATIVE_BRANCH_REQUIRES_IMPLEMENTATION:" + assessment["proposed_branch"])
    spec_path = SPEC_PATHS[metric_id]
    spec = compile_historical_spec_file(repo_root=repo_root, repo_relative_path=spec_path,
                                        dependency_specs={})
    annual = source["prepared_annual_input"]
    period = annual["table_input"]["target_period"]
    scope = spec["compiled"]["required_claims"]
    target = {"company_id": company_id, "entity": annual["entity"],
              "accession": annual["filing"]["accessionNumber"],
              "period_start": period["period_start"], "period_end": period["period_end"],
              "scope": scope, "scope_key": content_hash(value=scope)}
    records, references, raw, represented = [], [], {}, set()
    for document in source["documents"]:
        reference, blob = document["source_reference"], document["raw_blob"]
        records.extend([blob, reference])
        references.append(reference)
        raw[blob["raw_asset_id"]] = resolve_repository_file(
            repo_root=repo_root, repo_relative_path=blob["storage_uri"]).read_bytes()
        represented.add((reference["source_url"], blob["raw_asset_id"]))
    for proof in source["source_proofs"]:
        key = (proof["source_url"], "sha256:" + proof["content_sha256"])
        if key in represented:
            continue
        blob = raw_blob_record(repo_root=repo_root,
                               repo_relative_path=proof["request_repo_relative_path"],
                               media_type="application/json"
                               if proof["document_name"].endswith(".json") else "text/plain")
        reference = source_reference_record(
            raw_blob=blob, company_id=company_id, source_url=proof["source_url"],
            accession=proof["accession"] or "SUBMISSIONS-" + annual["entity"],
            document_name=proof["document_name"], source_role="supporting_input",
            request_attempt_id=proof["request_attempt_id"])
        records.extend([blob, reference])
        references.append(reference)
        represented.add(key)
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=source["source_proofs"])
    records = list({content_hash(value=record): record for record in records}.values())
    component = {"record_type": INPUT_RECORD_TYPE, "metric_id": metric_id,
                 "company_id": company_id, "period_selection_id": period_selection["selection_id"],
                 "source_id": source["semantic_source_id"],
                 "assessment_input_id": registered["input_record_id"],
                 "assessment_set_id": assessment["assessment_set_id"],
                 "proposed_branch": assessment["proposed_branch"], "mode": registered["mode"],
                 "export_path": EXPORT_PATHS[metric_id], "production_authorized": False}
    component = {**component, "input_binding_id": content_hash(value=component)}
    return {"source": source, "registered": registered, "spec_path": spec_path,
            "compiled_spec": spec, "records": records, "source_references": references,
            "source_proofs": source["source_proofs"], "admission": admission,
            "target_period": {"fiscal_year": period["fiscal_year"],
                              "period_start": period["period_start"],
                              "period_end": period["period_end"]},
            "component": component,
            "text_arguments": {"target": target, "source": source, "assessment": assessment,
                               "source_references": [d["source_reference"]
                                                     for d in source["documents"]],
                               "raw_bytes_by_id": raw}}


def registered_export_bytes(record):
    """The installed copy's bytes: the evidence serialiser the loader reads back."""
    return evidence_json_bytes(record)


def decode_registered_export(raw):
    return strict_json_loads(text=raw.decode("utf-8"))
