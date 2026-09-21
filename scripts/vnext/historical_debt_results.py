"""B06's ordinary six-stage cascade, run against a pinned historical period.

Each stage of the ordinary cascade resolves its own inputs by asking for the
issuer's latest annual filing.  Nothing else inside those stages depends on
which period it is: the debt grammars read the pinned filing's own bytes, and
the registries, policies and Specs they check are repository files.  So the
substitution this module performs is a single one, made at every stage: the
two preparations a stage would perform for itself are performed once here for
the pinned period and handed in.  The rest of each stage's assembly is
reproduced because the frozen entry points accept no period.

The cascade's ORDER is a business rule, not an implementation detail.  The
current-input check precedes the denominator guard, which precedes every debt
grammar, because a ratio already known to be meaningless from nonpositive
equity must not be made to wait on debt evidence.  Wiring one stage would
therefore deliver a confidently wrong answer for every company that reaches a
later one, which is why this module wires all six or none.

The result reason codes are the ordinary ones.  They describe the business
outcome, and renaming them would make a historical result incomparable to the
current one it must agree with.  Only failures that are about this route
itself carry a HISTORICAL_ prefix.
"""
from decimal import Decimal
from pathlib import Path

from .annual_amendment_scope import (POLICY as AMENDMENT_POLICY,
                                     POLICY_PATH as AMENDMENT_POLICY_PATH,
                                     inspect_annual_amendment_scope)
from .b06_current_input import (POLICY as CURRENT_INPUT_POLICY,
                                POLICY_PATH as CURRENT_INPUT_POLICY_PATH,
                                inspect_current_debt_amendment)
from .b06_guarded_result_v3 import (RESOLVER as GUARD_RESOLVER,
                                    SPEC_PATH as GUARD_SPEC_PATH,
                                    _installed_spec, _rebuild_equity, _terminal_records)
from .calculator import withheld_metric_result
from .canonical import (canonical_json_bytes, content_hash, sha256_bytes, sha256_file,
                        strict_json_file, strict_json_loads)
from .constraints import evaluate_expression
from .deterministic_router import parse_accession_xbrl_source
from .historical_annual_input import prepare_historical_annual_input
from .normal_annual_input import _registry_rows
from .normal_companyfacts_results import _SOURCE_ERRORS
from .normal_annual_input_v2 import exact_json_value
from .normal_governance_input import _Sources
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .r5_b06_scope import resolve_financing
from .annual_update import saved_source
from .normal_source_authority import ROOT
from .sources import (companyfacts_structured_facts, raw_blob_record,
                      resolve_repository_file, source_reference_record)
from .specs import compile_spec_file
from .traits import repository_company_traits

from . import normal_bond_debt_results as bond
from . import normal_inclusive_debt_results as inclusive
from . import normal_note_debt_results as note
from . import ordinary_special_debt_scope as special

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sec_urls import accession_document_url, companyfacts_url, submissions_url  # noqa: E402


class HistoricalDebtError(Exception):
    """The pinned period cannot be carried through the ordinary cascade."""


class HistoricalDebtSourceError(HistoricalDebtError):
    """Material the cascade needs is not saved.

    Separated from the base so that an installed policy or authority that no
    longer matches the repository stays loud, while a missing filing becomes a
    withheld Result naming the file - the same distinction C04's route makes.
    """


def _need(condition, reason, source=False):
    if not condition:
        raise (HistoricalDebtSourceError if source
               else HistoricalDebtError)("HISTORICAL_B06_" + reason)


def historical_b06_preparation(*, repo_root: Path, company_id: str, prepared, reader=None):
    """The ordinary B06 source walk, pointed at an already-pinned filing.

    This is `normal_candidates._prepare_b06` with its own call to the latest
    annual input replaced by the caller's pinned one.  The reader, the roles it
    reads under and the ambiguity refusal are the frozen ones.

    `prepared` must be the ORIGINAL pinned input, not the relabelled one: the
    frozen `_prepare_b06` reads `normal_annual_input`, whose fiscal year is
    derived from the report end, while `normal_annual_input_v2` overwrites that
    label with the issuer's own.  The two agree for a calendar-year filer and
    disagree for Salesforce, whose year ending 2026-01-31 the first calls 2025
    and the second calls 2026.  The guard downstream re-derives the period from
    the filing's own bytes and compares, so handing it the relabelled input
    fails on exactly those issuers and on no one else.
    """
    reader = _Sources(repo_root, company_id, prepared["entity"]) if reader is None else reader
    reader.read(submissions_url(cik=int(prepared["entity"])),
                role="submissions", media_type="application/json")
    facts = reader.read(companyfacts_url(cik=int(prepared["entity"])),
                        accession=prepared["filing"]["accessionNumber"],
                        role="companyfacts", media_type="application/json")
    sources = reader.auditor_filing(prepared["filing"])
    xml = [s for s in sources if s["raw_blob"]["media_type"] == "application/xml"]
    primary = [s for s in sources if s["raw_blob"]["media_type"] == "text/html"]
    if len(xml) != 1 or len(primary) != 1:
        raise HistoricalDebtSourceError("B06_NORMAL_ORIGINAL_SOURCE_SET_AMBIGUOUS")
    body = {"record_type": "NORMAL_B06_INPUT_BINDING", "prepared_annual_input": prepared,
            "source_proofs": [r["proof"] for r in reader.proofs.values()],
            "source_sets": reader.file_sets}
    return {"input_binding": {**body, "input_binding_id": content_hash(value=body)},
            "records": list(reader.records.values()), "facts": facts,
            "xml": xml[0], "primary": primary[0]}


def historical_amendment_scopes(*, repo_root: Path, company_id: str, prepared):
    """`annual_amendment_scope.prepare_saved_amendment_scopes` for a pinned period.

    The amendments compared here are the pinned period's own, which the pinned
    input already resolved; the classification itself is the frozen inspector.
    """
    # Frozen `prepare_saved_amendment_scopes` reads `normal_annual_input`, so
    # this takes the original pinned input for the same reason the source walk
    # above does.
    policy_path = resolve_repository_file(repo_root=repo_root,
                                          repo_relative_path=AMENDMENT_POLICY_PATH)
    _need(policy_path.read_bytes() == (ROOT / AMENDMENT_POLICY_PATH).read_bytes()
          and strict_json_file(path=policy_path) == AMENDMENT_POLICY,
          "AMENDMENT_INSTALLED_POLICY_CHANGED")
    proofs = list(prepared["source_proofs"])
    sources, records = [], []
    for filing in [prepared["filing"], *prepared["amendments"]]:
        url = accession_document_url(cik=int(prepared["entity"]),
                                     accession=filing["accessionNumber"],
                                     document_name=filing["primaryDocument"])
        saved = saved_source(repo_root=repo_root, url=url, accession=filing["accessionNumber"])
        _need(saved is not None, "AMENDMENT_SOURCE_NOT_SAVED:" + url, source=True)
        proof = saved["proof"]
        proofs.append(proof)
        blob = raw_blob_record(repo_root=repo_root,
                               repo_relative_path=proof["request_repo_relative_path"],
                               media_type="text/html")
        reference = source_reference_record(
            raw_blob=blob, company_id=company_id, source_url=url,
            accession=filing["accessionNumber"], document_name=filing["primaryDocument"],
            source_role="annual_source_identity", request_attempt_id=proof["request_attempt_id"])
        records.extend([blob, reference])
        sources.append({"raw": saved["raw"], "blob": blob, "reference": reference, "filing": filing})
    proofs = list({content_hash(value=p): p for p in proofs}.values())
    scopes = [inspect_annual_amendment_scope(original=sources[0], amendment=s,
                                             company_id=company_id, cik=prepared["entity"])
              for s in sources[1:]]
    return {"prepared_input": prepared, "source_proofs": proofs,
            "source_admission": verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs),
            "scopes": scopes, "source_records": records,
            "policy_sha256": sha256_file(path=policy_path),
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}


def prepare_historical_current_debt_input(*, repo_root: Path, company_id: str, packet):
    """`b06_current_input.prepare_current_debt_input` over a pinned packet.

    The amendment effect check itself is the frozen one, so a pinned period
    whose amendment changed debt or equity is refused for the same reason and
    with the same evidence as the current period would be.
    """
    path = resolve_repository_file(repo_root=repo_root,
                                   repo_relative_path=CURRENT_INPUT_POLICY_PATH)
    _need(path.read_bytes() == (ROOT / CURRENT_INPUT_POLICY_PATH).read_bytes()
          and strict_json_file(path=path) == CURRENT_INPUT_POLICY,
          "CURRENT_INPUT_INSTALLED_POLICY_CHANGED")
    blobs = {r["raw_asset_id"]: r for r in packet["source_records"]
             if r["record_type"] == "RAW_BLOB"}
    checks = []
    for scope in packet["scopes"]:
        args = {}
        for role in ["original", "amendment"]:
            source = scope[role]
            blob = blobs[source["source_reference"]["raw_asset_id"]]
            args[role] = {
                "raw": resolve_repository_file(
                    repo_root=repo_root,
                    repo_relative_path=blob["storage_uri"]).read_bytes(),
                "blob": blob, "reference": source["source_reference"],
                "filing": source["filing"]}
        checks.append(inspect_current_debt_amendment(
            **args, company_id=company_id, cik=packet["prepared_input"]["entity"]))
    body = exact_json_value({
        **packet, "record_type": "B06_CURRENT_INPUT",
        "input_class": CURRENT_INPUT_POLICY["input_class"], "metric_ids": ["B06"],
        "checks": checks,
        "decision": "INPUT_PROPERTY_PROVEN" if all(
            c["decision"] == "INPUT_PROPERTY_PROVEN" for c in checks) else "WITHHELD",
        "current_primary_only": True, "per_metric_statement_scope_required": True,
        "annual_continuity_proven": False, "debt_completeness_proven": False,
        "policy_sha256": sha256_file(path=path)})
    return {**body, "current_input_id": content_hash(value=body)}


def withheld_historical_current_debt_case(*, repo_root: Path, company_id: str,
                                          prepared, preparation, packet):
    """`b06_current_input.withheld_current_debt_case` for a pinned period."""
    end = prepared["filing"]["reportDate"]
    scope = {"entity_scope": "consolidated"}
    target = {"company_id": company_id, "entity": prepared["entity"],
              "accession": prepared["filing"]["accessionNumber"],
              "period_start": end, "period_end": end,
              "scope": scope, "scope_key": content_hash(value=scope)}
    path = "catalog/r5/B06_new_source_v2.md"
    spec = compile_spec_file(path=repo_root / path, dependency_specs={})
    simple_target = {k: target[k] for k in
                     ["company_id", "period_start", "period_end", "scope", "scope_key"]}
    result, trace = withheld_metric_result(compiled_spec=spec, target=simple_target,
                                           reason_code="B06_CURRENT_INPUT_UNRESOLVED")
    records = list({content_hash(value=r): r for r in
                    [*preparation["records"], *packet["source_records"]]}.values())
    proofs = list({content_hash(value=p): p for p in
                   [*preparation["input_binding"]["source_proofs"],
                    *prepared["source_proofs"], *packet["source_proofs"]]}.values())
    selection = {"classification": "CURRENT_INPUT_SCOPE_UNRESOLVED",
                 "reason": "B06_CURRENT_INPUT_UNRESOLVED",
                 "amendment_checks": packet["checks"],
                 "equity_guard_evaluated": False, "debt_evaluated": False}
    return {"kind": "STRUCTURED", "primary_metric_id": "B06",
            "input_binding": {"original_source_input": preparation["input_binding"],
                              "annual_label_input": prepared, "current_debt_input": packet},
            "source_records": records,
            "references": [r for r in records if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": proofs,
            "admission": verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs),
            "spec_paths": {"B06": path}, "compiled_specs": {"B06": spec},
            "target_period": {"fiscal_year": prepared["table_input"]["target_period"]["fiscal_year"],
                              "period_start": end, "period_end": end},
            "expected_records": [*records, trace, result],
            "results": {"B06": result}, "traces": {"B06": trace},
            "observations": [], "selection": selection}


def prepare_historical_guarded_b06_result(*, repo_root: Path, company_id: str, preparation):
    """`ordinary_debt_guard.prepare_current_guarded_b06_result` for a pinned period.

    Returns NOT_MEANINGFUL native records or CONTINUE_DEBT_PATH; never a Run.
    """
    spec, trait_hashes = _installed_spec(repo_root)
    prepared = preparation["input_binding"]["prepared_annual_input"]
    proofs = list(preparation["input_binding"]["source_proofs"]) + list(prepared["source_proofs"])
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    period = prepared["table_input"]["target_period"]
    scope = {"entity_scope": "consolidated"}
    target = {"company_id": company_id, "entity": prepared["entity"],
              "accession": prepared["filing"]["accessionNumber"],
              "period_start": period["period_end"], "period_end": period["period_end"],
              "scope": scope, "scope_key": scope_key(scope=scope)}
    for key in ("primary", "xml", "facts"):
        item = preparation[key]
        _need(item["source_reference"]["raw_asset_id"]
              == "sha256:" + sha256_bytes(content=item["raw_bytes"]),
              "GUARD_SOURCE_CHANGED_AFTER_ADMISSION")
    proof = _rebuild_equity(primary=preparation["primary"]["raw_bytes"],
                            xml=preparation["xml"]["raw_bytes"],
                            facts_raw=preparation["facts"]["raw_bytes"],
                            facts_source=preparation["facts"]["source_reference"],
                            target=target, period=period, filing=prepared["filing"])
    company = next(c for c in _registry_rows(repo_root=repo_root)
                   if c["company_id"] == company_id)
    parsed = parse_accession_xbrl_source(raw_bytes=preparation["xml"]["raw_bytes"])
    industrial = set(spec["compiled"]["quality_rule"]["scope_review_dimension_members"])
    restricted = company["industry_profile"] == "financial_institution" or any(
        any(str(member).split(":")[-1] in industrial for member in c["dimensions"].values())
        for c in parsed.contexts.values() if c["period_end"] == target["period_end"]
        and str(int(c["entity_identifier"])) == target["entity"])
    nonpositive = Decimal(proof["value"]) <= 0
    terminal = nonpositive and not restricted
    observations, result, trace = [], None, None
    status = "NOT_MEANINGFUL" if terminal else "CONTINUE_DEBT_PATH"
    reason = "DENOMINATOR_NONPOSITIVE" if terminal else (
        "EXISTING_SPECIAL_SCOPE_REQUIRED" if restricted else "DENOMINATOR_POSITIVE")
    if terminal:
        result, trace, observations = _terminal_records(
            spec=spec, target=target, proof=proof,
            source=preparation[proof["observation_source_kind"]]["source_reference"],
            filed=prepared["filing"]["filingDate"], form=prepared["filing"]["form"])
    body = {"record_type": "B06_GUARDED_RESULT_COMPONENT", "resolver": GUARD_RESOLVER,
            "company_id": company_id, "status": status, "reason_code": reason,
            "spec_path": GUARD_SPEC_PATH, "spec_closure_hash": spec["spec_closure_hash"],
            "input_binding": preparation["input_binding"], "source_admission": admission,
            "trait_file_hashes": trait_hashes, "target": target, "filing_period": period,
            "equity_proof": proof, "debt_completeness": "NOT_EVALUATED",
            "source_records": preparation["records"],
            "source_references": [r for r in preparation["records"]
                                  if r["record_type"] == "SOURCE_REFERENCE"],
            "observations": observations, "trace": trace, "result": result,
            "native_run_status": "NOT_CREATED",
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}
    body = strict_json_loads(text=canonical_json_bytes(value=body).decode("utf-8"))
    return {**body, "component_id": content_hash(value=body)}


def prepare_historical_special_debt_case(*, repo_root: Path, company_id: str, preparation):
    """`ordinary_special_debt_scope.prepare_special_debt_case` for a pinned period.

    None means this is not a bank/industrial-dimension filing, so the cascade
    continues into the debt grammars.
    """
    rules = strict_json_file(path=repo_root / special.POLICY_PATH)
    _need(rules == strict_json_file(path=ROOT / special.POLICY_PATH)
          and rules["full_ratio_enabled"] is False, "SPECIAL_SCOPE_INSTALLED_RULES_CHANGED")
    annual = preparation["input_binding"]["prepared_annual_input"]
    company = next(c for c in _registry_rows(repo_root=repo_root) if c["company_id"] == company_id)
    inspected = special.inspect_special_scope(
        primary=preparation["primary"], xml=preparation["xml"], annual=annual,
        financial_institution=company["industry_profile"] == "financial_institution", rules=rules)
    if inspected is None:
        return None
    proofs = [*preparation["input_binding"]["source_proofs"], *annual["source_proofs"]]
    admission = verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs)
    spec_path = rules["spec_path"]
    spec = compile_spec_file(path=repo_root / spec_path, dependency_specs={})
    _need(spec == compile_spec_file(path=ROOT / spec_path, dependency_specs={}),
          "SPECIAL_SCOPE_SPEC_CHANGED")
    end = inspected["period_end"]
    scope = {"entity_scope": "consolidated"}
    target = {"company_id": company_id, "period_start": end, "period_end": end,
              "scope": scope, "scope_key": content_hash(value=scope)}
    result, trace = withheld_metric_result(compiled_spec=spec, target=target,
                                           reason_code="B06_SOURCE_RELATIONSHIP_UNRESOLVED")
    records = preparation["records"]
    selection = {"classification": "SOURCE_REBUILT_SPECIAL_SCOPE_LIMITATION",
                 "scope_class": inspected["scope_class"], "reasons": inspected["limitations"],
                 "scope_source": inspected, "reported_subtotal": inspected["reported_subtotal"],
                 "ratio": None}
    return {"kind": "STRUCTURED", "primary_metric_id": "B06",
            "input_binding": {"original_source_input": preparation["input_binding"],
                              "scope_source": inspected, "source_proofs": proofs,
                              "policy_sha256": sha256_file(path=repo_root / special.POLICY_PATH)},
            "source_records": records,
            "references": [r for r in records if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": proofs, "admission": admission, "spec_paths": {"B06": spec_path},
            "compiled_specs": {"B06": spec},
            "target_period": {"fiscal_year": annual["table_input"]["target_period"]["fiscal_year"],
                              "period_start": end, "period_end": end},
            "expected_records": [*records, trace, result],
            "results": {"B06": result}, "traces": {"B06": trace},
            "observations": [], "selection": selection}


def _grammar_frame(*, repo_root, company_id, preparation, prepared, spec):
    """The identical opening every debt grammar performs once its Spec is loaded."""
    original = preparation["input_binding"]["prepared_annual_input"]
    end = original["filing"]["reportDate"]
    proofs = list({content_hash(value=p): p for p in
                   [*preparation["input_binding"]["source_proofs"],
                    *original["source_proofs"], *prepared["source_proofs"]]}.values())
    scope = {"entity_scope": "consolidated"}
    target = {"company_id": company_id, "entity": original["entity"],
              "accession": original["filing"]["accessionNumber"],
              "period_start": end, "period_end": end,
              "scope": scope, "scope_key": content_hash(value=scope)}
    return {"original": original, "end": end, "proofs": proofs, "target": target,
            "admission": verify_ordinary_source_proofs(data_root=repo_root, proofs=proofs),
            "traits": repository_company_traits(repo_root=repo_root, company_id=company_id),
            "spec": spec}


def _grammar_case(*, repo_root, company_id, preparation, prepared, frame, spec_path,
                  policy_path, record_type, result, trace, observations, selection,
                  source_proof):
    """The identical closing every debt grammar performs once it has a result."""
    records = preparation["records"]
    binding = exact_json_value({
        "record_type": record_type,
        "original_source_input": preparation["input_binding"],
        "annual_label_input": prepared, "source_proofs": frame["proofs"],
        "source_proof": source_proof, "selection": selection,
        "policy_sha256": sha256_file(path=repo_root / policy_path),
        "production_authorized": False})
    return {"kind": "STRUCTURED", "primary_metric_id": "B06", "input_binding": binding,
            "source_records": records,
            "references": [r for r in records if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": frame["proofs"], "admission": frame["admission"],
            "spec_paths": {"B06": spec_path}, "compiled_specs": {"B06": frame["spec"]},
            "target_period": {"fiscal_year": prepared["table_input"]["target_period"]["fiscal_year"],
                              "period_start": frame["end"], "period_end": frame["end"]},
            "expected_records": [*records, *observations, trace, result],
            "results": {"B06": result}, "traces": {"B06": trace},
            "observations": observations, "selection": selection}


def _withheld_grammar(*, frame, error):
    simple = {k: frame["target"][k] for k in
              ["company_id", "period_start", "period_end", "scope", "scope_key"]}
    result, trace = withheld_metric_result(compiled_spec=frame["spec"], target=simple,
                                           reason_code="B06_SOURCE_RELATIONSHIP_UNRESOLVED")
    return result, trace, [], {"classification": "SOURCE_OR_RELATIONSHIP_UNRESOLVED",
                               "reason": str(error)}


def prepare_historical_note_debt_case(*, repo_root: Path, company_id: str,
                                      preparation, prepared):
    """`normal_note_debt_results.prepare_note_debt_case` for a pinned period.

    None means a different grammar; a matched but failed grammar stays withheld.
    """
    original = preparation["input_binding"]["prepared_annual_input"]
    end = original["filing"]["reportDate"]
    if not note.matches_source_grammar(preparation["xml"]["raw_bytes"], end):
        return None
    spec = note._spec(repo_root)
    frame = _grammar_frame(repo_root=repo_root, company_id=company_id,
                           preparation=preparation, prepared=prepared, spec=spec)
    target = frame["target"]
    source_proof = None
    try:
        company = next(c for c in _registry_rows(repo_root=repo_root)
                       if c["company_id"] == company_id)
        if company["industry_profile"] == "financial_institution":
            raise note.NoteCarryingError("NOTE_CARRYING_SEPARATE_BANK_SCOPE_REQUIRED")
        parsed = parse_accession_xbrl_source(raw_bytes=preparation["xml"]["raw_bytes"])
        restricted = set(spec["compiled"]["quality_rule"]["scope_review_dimension_members"])
        if any(any(str(m).split(":")[-1] in restricted for m in c["dimensions"].values())
               for c in parsed.contexts.values() if c["period_end"] == end):
            raise note.NoteCarryingError("NOTE_CARRYING_SEPARATE_INDUSTRIAL_SCOPE_REQUIRED")
        source_proof = note.inspect_note_carrying(primary=preparation["primary"],
                                                  xml=preparation["xml"], prepared=original)
        rule = spec["compiled"]["quality_rule"]
        path = repo_root / rule["debt_set_registry"]
        _need(sha256_file(path=path) == rule["debt_set_registry_sha256"],
              "NOTE_DEBT_REGISTRY_CHANGED")
        registry = strict_json_file(path=path)
        model = registry["debt_set_models"][note.POLICY["model_id"]]
        note.validate_partition(model, registry["required_liability_classes"]["consolidated_nonbank"],
                                absent=["finance_leases"])
        from .b06_disclosure import _facts
        get = _facts(preparation["xml"]["raw_bytes"], preparation["xml"]["source_reference"],
                     target, original["filing"]["filingDate"])
        selected, precision = {}, []
        for role, concept in {**model["inputs"], "equity": rule["equity_concept"]}.items():
            fact, evidence = get(concept)
            _need(fact["value"] == source_proof["reports"][role]["chosen"]["value"],
                  "NOTE_DEBT_LOCATOR_AMOUNT_CHANGED")
            selected[role] = fact
            precision.append(evidence)
        total = source_proof["composition"]["balances"]["total"]
        measurement = {"model_id": note.POLICY["model_id"], "model": model,
                       "scope_class": "consolidated_nonbank", "complete": True, "unresolved": [],
                       "established_absent_classes": ["finance_leases"],
                       "source_credit": "SEPARATE_ORDINARY_BASELINE_ADMISSION",
                       "calculation_facts": list(selected.values()),
                       "equity_fact": selected["equity"],
                       "components": {k: v for k, v in selected.items() if k != "equity"},
                       "carrying_amount": total, "precision": precision,
                       "debt_scope_definition": registry["debt_scope_definition"],
                       "source_proof": source_proof,
                       "reconciliations": source_proof["composition"]}
        source = preparation["facts"]
        facts = companyfacts_structured_facts(
            raw_bytes=source["raw_bytes"], source_reference=source["source_reference"],
            approved_concepts=["us-gaap:" + name for name in note.POLICY["monetary_concepts"].values()],
            allowed_ciks=[original["entity"]], include_instant=True)
        for role, name in note.POLICY["monetary_concepts"].items():
            current = [f for f in facts if f["concept"] == "us-gaap:" + name
                       and f["accession"] == target["accession"]
                       and f["period_start"] == f["period_end"] == end
                       and f["entity"] == target["entity"]]
            _need(current and all(f["unit"] == "USD"
                                  and f["value"] == source_proof["reports"][role]["chosen"]["value"]
                                  for f in current),
                  "NOTE_DEBT_COMPANYFACTS_CONFLICT_OR_MISSING:" + role)
        result, trace, observations, audit = resolve_financing(
            spec=spec, target=target, traits=frame["traits"], facts=facts, measurement=measurement)
        selection = {"classification": "SOURCE_RECONCILED_NOTE_CARRYING", "audit": audit}
    except note.NoteCarryingError as error:
        result, trace, observations, selection = _withheld_grammar(frame=frame, error=error)
    return _grammar_case(repo_root=repo_root, company_id=company_id, preparation=preparation,
                         prepared=prepared, frame=frame, spec_path=note.SPEC_PATH,
                         policy_path=note.POLICY_PATH, record_type="ORDINARY_NOTE_DEBT_INPUT",
                         result=result, trace=trace, observations=observations,
                         selection=selection, source_proof=source_proof)


# The bond and inclusive grammars are the same algorithm.  Normalising six
# names (the module, its policy, error, inspector, model id and the phrase in
# the classification) makes their frozen bodies differ only in how the policy
# lists its concepts and in the message the scope refusal carries.  One
# implementation therefore serves both, and a regression asserts that the two
# frozen bodies still reduce to each other - if they ever stopped, this shared
# implementation would no longer be faithful to both of them.
_RECONCILED_GRAMMARS = {
    "bond": {"module": bond, "error": None, "concepts": lambda p: list(p["note_concepts"].values()),
             "scope_reason": "BOND_LEASE_SEPARATE_BANK_OR_INDUSTRIAL_SCOPE_REQUIRED",
             "record_type": "ORDINARY_BOND_DEBT_INPUT",
             "classification": "SOURCE_RECONCILED_BONDS_AND_SEPARATE_FINANCE_LEASES",
             "prefix": "BOND_DEBT"},
    "inclusive": {"module": inclusive, "error": None,
                  "concepts": lambda p: list(p["note_concepts"]) + list(p["extension_note_concepts"]),
                  "scope_reason": "INCLUSIVE_DEBT_SEPARATE_BANK_OR_INDUSTRIAL_SCOPE_REQUIRED",
                  "record_type": "ORDINARY_INCLUSIVE_DEBT_INPUT",
                  "classification": "SOURCE_RECONCILED_TOTAL_WITH_FINANCE_LEASE_INCLUDED",
                  "prefix": "INCLUSIVE_DEBT"},
}
_RECONCILED_GRAMMARS["bond"]["error"] = bond.BondLeaseError
_RECONCILED_GRAMMARS["bond"]["inspect"] = bond.inspect_bond_debt_scope
_RECONCILED_GRAMMARS["inclusive"]["error"] = inclusive.InclusiveDebtError
_RECONCILED_GRAMMARS["inclusive"]["inspect"] = inclusive.inspect_inclusive_debt_scope


def prepare_historical_reconciled_debt_case(*, repo_root: Path, company_id: str,
                                            preparation, prepared, grammar: str):
    """The bond and inclusive grammars for a pinned period.

    None means a different grammar; a matched but failed grammar stays withheld.
    """
    rules = _RECONCILED_GRAMMARS[grammar]
    module = rules["module"]
    original = preparation["input_binding"]["prepared_annual_input"]
    end = original["filing"]["reportDate"]
    parsed = parse_accession_xbrl_source(raw_bytes=preparation["xml"]["raw_bytes"])
    available = {f["qualified_name"].split(":")[-1].casefold() for f in parsed.facts
                 if parsed.contexts[f["context_ref"]]["period_end"] == end}
    if not all(local.casefold() in available for local in rules["concepts"](module.POLICY)):
        return None
    spec = module._spec(repo_root)
    rule = spec["compiled"]["quality_rule"]
    frame = _grammar_frame(repo_root=repo_root, company_id=company_id,
                           preparation=preparation, prepared=prepared, spec=spec)
    target = frame["target"]
    source_proof = None
    try:
        company = next(c for c in _registry_rows(repo_root=repo_root)
                       if c["company_id"] == company_id)
        restricted = set(rule["scope_review_dimension_members"])
        if company["industry_profile"] == "financial_institution" or any(
                any(str(m).split(":")[-1] in restricted for m in c["dimensions"].values())
                for c in parsed.contexts.values() if c["period_end"] == end):
            raise rules["error"](rules["scope_reason"])
        source_proof = rules["inspect"](primary=preparation["primary"],
                                        xml=preparation["xml"], prepared=original)
        path = repo_root / rule["debt_set_registry"]
        _need(sha256_file(path=path) == rule["debt_set_registry_sha256"],
              rules["prefix"] + "_REGISTRY_CHANGED")
        registry = strict_json_file(path=path)
        model = registry["debt_set_models"][module.MODEL_ID]
        module.validate_partition(model,
                                  registry["required_liability_classes"]["consolidated_nonbank"])
        from .b06_disclosure import _facts
        get = _facts(preparation["xml"]["raw_bytes"], preparation["xml"]["source_reference"],
                     target, original["filing"]["filingDate"])
        selected, precision = {}, []
        for role, concept in {**model["inputs"], "equity": rule["equity_concept"]}.items():
            fact, evidence = get(concept)
            selected[role] = fact
            precision.append(evidence)
        checks = []
        for check in model["checks"]:
            values = {k: Decimal(v["value"]) for k, v in selected.items()}
            extra = []
            for role, concept in check["inputs"].items():
                f, p = get(concept)
                values[role] = Decimal(f["value"])
                extra.append(f)
                precision.append(p)
            left = evaluate_expression(expression=check["left"], values=values)
            right = evaluate_expression(expression=check["right"], values=values)
            _need(left == right, rules["prefix"] + "_DECLARED_RECONCILIATION_FAILED")
            checks.append({"rule": check, "left_value": str(left), "right_value": str(right),
                           "facts": extra})
        amount = evaluate_expression(expression=model["expression"],
                                     values={k: Decimal(f["value"]) for k, f in selected.items()})
        _need(amount == Decimal(source_proof["proven_composition_amount"]),
              rules["prefix"] + "_PROVED_AMOUNT_CHANGED")
        measurement = {"model_id": module.MODEL_ID, "model": model,
                       "scope_class": "consolidated_nonbank", "complete": True, "unresolved": [],
                       "calculation_facts": list(selected.values()),
                       "equity_fact": selected["equity"],
                       "components": {k: v for k, v in selected.items() if k != "equity"},
                       "carrying_amount": str(amount), "precision": precision,
                       "reconciliations": checks,
                       "debt_scope_definition": registry["debt_scope_definition"],
                       "source_proof": source_proof}
        concepts = sorted({p["concept"] for p in precision})
        source = preparation["facts"]
        facts = companyfacts_structured_facts(
            raw_bytes=source["raw_bytes"], source_reference=source["source_reference"],
            approved_concepts=concepts, allowed_ciks=[original["entity"]], include_instant=True)
        for p in precision:
            if not p["concept"].startswith("us-gaap:"):
                continue
            current = [f for f in facts if f["concept"] == p["concept"]
                       and f["accession"] == target["accession"]
                       and f["period_start"] == f["period_end"] == end
                       and f["entity"] == target["entity"]]
            _need(current and all(f["unit"] == "USD"
                                  and f["value"] in {v["value"] for v in p["all_reports"]}
                                  for f in current),
                  rules["prefix"] + "_COMPANYFACTS_CONFLICT_OR_MISSING:" + p["concept"])
        result, trace, observations, audit = resolve_financing(
            spec=spec, target=target, traits=frame["traits"], facts=facts, measurement=measurement)
        selection = {"classification": rules["classification"], "audit": audit}
    except rules["error"] as error:
        result, trace, observations, selection = _withheld_grammar(frame=frame, error=error)
    return _grammar_case(repo_root=repo_root, company_id=company_id, preparation=preparation,
                         prepared=prepared, frame=frame, spec_path=module.SPEC_PATH,
                         policy_path=module.POLICY_PATH, record_type=rules["record_type"],
                         result=result, trace=trace, observations=observations,
                         selection=selection, source_proof=source_proof)


def _guarded_case(*, repo_root: Path, prepared, guarded):
    """`ordinary_remaining_cases`' nonpositive-denominator case, pinned.

    The guard component already holds the Result, its observations and the
    source set they came from; this is the shape the ordinary chain gives them.
    """
    original = guarded["input_binding"]
    annual = guarded["filing_period"]
    return {"kind": "STRUCTURED", "input_binding": {"guarded_result": guarded},
            "records": guarded["source_records"], "references": guarded["source_references"],
            "source_proofs": [*original["source_proofs"],
                              *original["prepared_annual_input"]["source_proofs"]],
            "admission": guarded["source_admission"], "spec_path": guarded["spec_path"],
            "result": guarded["result"], "trace": guarded["trace"],
            "observations": guarded["observations"], "derived_assets": [],
            "selection": {"reason_code": guarded["reason_code"],
                          "debt_completeness": "NOT_EVALUATED",
                          "equity_proof": guarded["equity_proof"]},
            "target_period": {"fiscal_year": annual["fiscal_year"],
                              "period_start": guarded["target"]["period_start"],
                              "period_end": guarded["target"]["period_end"]}}


def _fallback_case(*, repo_root: Path, company_id: str, preparation, guarded):
    """`normal_candidates._b06_resolution` behind the ordinary remaining-cases shape.

    This is the last stage, not the only one.  Reaching it means the pinned
    filing matched no debt grammar and its denominator is positive, so the v2
    disclosure resolver answers - with a value when it can read the relationship
    and a withheld Result naming what it could not when it cannot.
    """
    from .normal_candidates import _b06_resolution
    path, resolution = _b06_resolution(data_root=repo_root, preparation=preparation)
    result = resolution["result"]
    annual = preparation["input_binding"]["prepared_annual_input"]["table_input"]["target_period"]
    observations = resolution.get("observations",
                                  [resolution["observation"]] if resolution.get("observation") else [])
    binding = preparation["input_binding"]
    case = {"kind": "STRUCTURED", "input_binding": binding, "records": preparation["records"],
            "references": [r for r in preparation["records"]
                           if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": [*binding["source_proofs"],
                              *binding["prepared_annual_input"]["source_proofs"]],
            "admission": verify_ordinary_source_proofs(
                data_root=repo_root,
                proofs=[*binding["source_proofs"],
                        *binding["prepared_annual_input"]["source_proofs"]]),
            "spec_path": path, "result": result, "trace": resolution["trace"],
            "observations": observations, "derived_assets": resolution.get("derived_assets", []),
            "selection": resolution["selection"],
            "target_period": {"fiscal_year": annual["fiscal_year"],
                              "period_start": result["period_start"],
                              "period_end": result["period_end"]}}
    case["input_binding"] = {"denominator_guard": guarded, "debt_input": case["input_binding"]}
    return case


def _integrated_case(*, repo_root: Path, company_id: str, prepared, old):
    """The ordinary integrated run's wrapper around a remaining-cases component.

    The fiscal-year label comes from the pinned annual input rather than from
    the issuer's latest one, which is the whole substitution; the replay guard
    it protects is reproduced because a resolved period whose label moved is
    exactly the case it exists for.
    """
    from .normal_run_v2 import _policy
    policy = _policy(repo_root)
    spec = compile_spec_file(
        path=resolve_repository_file(repo_root=repo_root, repo_relative_path=old["spec_path"]),
        dependency_specs={})
    _need(spec == compile_spec_file(path=ROOT / old["spec_path"], dependency_specs={}),
          "REMAINING_SPEC_DIFFERS_FROM_INSTALLED")
    year = prepared["table_input"]["target_period"]["fiscal_year"]
    if year != old["target_period"]["fiscal_year"]:
        # The frozen wrapper guards the second of these only for a structured
        # case. B06 has no text route, so it is structured on every stage and
        # the condition is always true here; it is left unconditional rather
        # than reproduced as a branch that cannot be false.
        _need(spec["compiled"]["quality_rule"].get("resolver") != "reported_compensation_table_v2",
              "SOURCE_YEAR_REPLAY_REQUIRED")
        _need("fiscal_year" not in old["trace"]["calculation_target"]["scope"],
              "SOURCE_SCOPE_YEAR_REPLAY_REQUIRED")
    period = {**old["target_period"], "fiscal_year": year}
    source_records = [r for r in old["records"]
                      if r["record_type"] in {"RAW_BLOB", "SOURCE_REFERENCE"}]
    case = {"kind": "STRUCTURED", "primary_metric_id": "B06",
            "input_binding": {"original_source_route": old["input_binding"],
                              "annual_label_input": prepared},
            "source_records": source_records, "references": old["references"],
            "source_proofs": old["source_proofs"], "admission": old["admission"],
            "spec_paths": {"B06": old["spec_path"]}, "compiled_specs": {"B06": spec},
            "target_period": period, "selection": old.get("selection"),
            "results": {"B06": old["result"]}, "traces": {"B06": old["trace"]},
            "observations": old["observations"],
            "expected_records": [*old["records"], *old.get("derived_assets", []),
                                 *old["observations"], old["trace"], old["result"]]}
    _need(old["spec_path"] in policy["metric_spec_paths"]["B06"],
          "SPEC_ROUTE_NOT_ENABLED:" + old["spec_path"])
    return case


RECORD_TYPE = "HISTORICAL_DEBT_COMPONENT"
SUPPORTED_METRICS = ("B06",)
# The Spec a withheld Result is filed under when no stage was reached. It is
# the route's own B06 Spec - the one the last stage and the first stage's
# refusal both use - because a period whose material is missing has not chosen
# a grammar and must not be filed under one.
UNREACHED_SPEC_PATH = "catalog/r5/B06_new_source_v2.md"


def _withheld_source_case(*, repo_root, company_id, prepared, reader, error):
    """A pinned period whose material is not saved, said in a Result.

    The cascade reads the filing's own directory index before it can choose a
    stage, so a period missing that file cannot reach one. Raising here would
    lose the position entirely; what belongs in the record is a withheld Result
    naming the file, exactly as the governance route does.
    """
    period = prepared["table_input"]["target_period"]
    end = period["period_end"]
    scope = {"entity_scope": "consolidated"}
    target = {"company_id": company_id, "period_start": end, "period_end": end,
              "scope": scope, "scope_key": content_hash(value=scope)}
    spec = compile_spec_file(path=repo_root / UNREACHED_SPEC_PATH, dependency_specs={})
    result, trace = withheld_metric_result(
        compiled_spec=spec, target=target,
        reason_code="HISTORICAL_B06_SOURCE_ROUTE_UNRESOLVED")
    proofs_by_id = {}
    for proof in [*prepared["source_proofs"],
                  *(value["proof"] for value in reader.proofs.values())]:
        proofs_by_id[proof["request_attempt_id"]] = proof
    proofs = list(proofs_by_id.values())
    source_records = list(reader.records.values())
    references = [r for r in source_records if r["record_type"] == "SOURCE_REFERENCE"]
    return {"record_type": RECORD_TYPE, "schema_version": 1, "company_id": company_id,
            "metric_id": "B06", "cascade_stage": "NO_STAGE_REACHED",
            "spec_path": UNREACHED_SPEC_PATH, "compiled_spec": spec,
            "selection": {"classification": "SOURCE_ROUTE_UNRESOLVED",
                          "reason": str(error), "error_type": type(error).__name__,
                          "category": getattr(error, "category",
                                              "SOURCE_OR_IMPLEMENTATION_UNRESOLVED")},
            "records": [*source_records, trace, result],
            "source_records": source_records, "source_references": references,
            "source_proofs": proofs,
            "source_admission": verify_ordinary_source_proofs(data_root=repo_root,
                                                              proofs=proofs),
            "result": result, "trace": trace, "observations": [],
            "target_period": {"fiscal_year": period["fiscal_year"],
                              "period_start": end, "period_end": end},
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}


def _component(*, company_id, metric_id, case, stage):
    """The historical Run factory's component shape around an ordinary case."""
    return {"record_type": RECORD_TYPE, "schema_version": 1, "company_id": company_id,
            "metric_id": metric_id, "cascade_stage": stage,
            "spec_path": case["spec_paths"][metric_id],
            "compiled_spec": case["compiled_specs"][metric_id],
            "selection": case.get("selection"),
            "records": case["expected_records"], "source_records": case["source_records"],
            "source_references": case["references"], "source_proofs": case["source_proofs"],
            "source_admission": case["admission"], "result": case["results"][metric_id],
            "trace": case["traces"][metric_id], "observations": case["observations"],
            "target_period": case["target_period"],
            "calls": {"provider": 0, "paid": 0, "sec": 0},
            "native_run_created": False, "production_authorized": False}


def resolve_historical_debt_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                   period_selection):
    """B06 for a pinned period, through the ordinary cascade in its own order.

    Args:
        repo_root: Installed data root holding the pinned period's sources.
        company_id: Configured company.
        metric_id: Currently B06 only.
        period_selection: The pinned period this Run is for.

    Returns:
        The component shape the historical Run factory consumes, plus the name
        of the cascade stage that answered.  The cascade never falls through:
        the ordinary chain has no other branch for B06, so the last stage
        answers whatever the earlier ones declined.

    Raises:
        HistoricalDebtError: When the metric is not wired here, when the pinned
            subject is not a continuous primary registrant, or when a stage's
            installed authority no longer matches the repository's.
    """
    _need(metric_id in SUPPORTED_METRICS, "METRIC_NOT_WIRED:" + metric_id)
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection)
    _need(prepared["subject_policy"]["mode"] == "CONTINUOUS_PRIMARY",
          "SUCCESSOR_SCOPE_NOT_IMPLEMENTED")
    # Two ordinary anchors, not one. The source walk and the amendment scopes
    # read the original input; the fiscal-year label the Run is filed under
    # comes from the relabelled one. Substituting a single pinned input for
    # both is what a copy of this cascade gets wrong.
    original = prepared["original_input"]
    # The reader is created here rather than inside the walk so that a period
    # whose material is missing still carries whatever was read before the gap.
    reader = _Sources(repo_root, company_id, original["entity"])
    try:
        preparation = historical_b06_preparation(repo_root=repo_root, company_id=company_id,
                                                 prepared=original, reader=reader)
        packet = prepare_historical_current_debt_input(
            repo_root=repo_root, company_id=company_id,
            packet=historical_amendment_scopes(repo_root=repo_root, company_id=company_id,
                                               prepared=original))
    except (*_SOURCE_ERRORS, HistoricalDebtSourceError) as error:
        return _withheld_source_case(repo_root=repo_root, company_id=company_id,
                                     prepared=prepared, reader=reader, error=error)
    if packet["decision"] != "INPUT_PROPERTY_PROVEN":
        case = withheld_historical_current_debt_case(
            repo_root=repo_root, company_id=company_id, prepared=prepared,
            preparation=preparation, packet=packet)
        return _component(company_id=company_id, metric_id=metric_id, case=case,
                          stage="CURRENT_INPUT_UNRESOLVED")
    # The established denominator guard precedes every debt grammar.  A source
    # layout extension must not require debt evidence to establish a ratio
    # already known to be meaningless from nonpositive equity.
    guarded = prepare_historical_guarded_b06_result(
        repo_root=repo_root, company_id=company_id, preparation=preparation)
    case, stage = None, None
    if guarded["status"] != "NOT_MEANINGFUL":
        if guarded["reason_code"] == "EXISTING_SPECIAL_SCOPE_REQUIRED":
            case = prepare_historical_special_debt_case(
                repo_root=repo_root, company_id=company_id, preparation=preparation)
            stage = "SPECIAL_SCOPE" if case is not None else None
        if case is None:
            case = prepare_historical_note_debt_case(
                repo_root=repo_root, company_id=company_id,
                preparation=preparation, prepared=prepared)
            stage = "NOTE_CARRYING" if case is not None else None
        for grammar in ("bond", "inclusive"):
            if case is not None:
                break
            case = prepare_historical_reconciled_debt_case(
                repo_root=repo_root, company_id=company_id, preparation=preparation,
                prepared=prepared, grammar=grammar)
            stage = grammar.upper() if case is not None else None
    if case is None:
        old = (_guarded_case(repo_root=repo_root, prepared=prepared, guarded=guarded)
               if guarded["status"] == "NOT_MEANINGFUL"
               else _fallback_case(repo_root=repo_root, company_id=company_id,
                                   preparation=preparation, guarded=guarded))
        stage = ("DENOMINATOR_GUARD" if guarded["status"] == "NOT_MEANINGFUL"
                 else "FALLBACK_RESOLVER")
        case = _integrated_case(repo_root=repo_root, company_id=company_id,
                                prepared=prepared, old=old)
    # Every B06 case carries its current-input packet, whichever stage built
    # it: the packet's sources are part of the Run's graph and the binder is
    # where the result's registrant scope is proved against them.
    from .b06_current_input import bind_current_debt_input
    case = bind_current_debt_input(case=case, packet=packet, repo_root=repo_root)
    return _component(company_id=company_id, metric_id=metric_id, case=case, stage=stage)
