"""Prove B06's nonpositive denominator before attempting a debt relationship.

Only installed saved sources and the installed successor Spec can enter this
ordinary API. A terminal result binds the equity observation alone; it makes
no assertion about debt completeness and creates no Run or publication.
"""
from decimal import Decimal
from pathlib import Path
import re

from .calculator import _result_and_trace
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, sha256_file, strict_json_loads
from .constraints import parse_numeric_claim
from .deterministic_router import parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex, _fact_cells
from .governance_signals import _FactAttributes, _source_value
from .normal_annual_input import annual_period, _registry_rows
from .normal_candidates import _prepare_b06
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .observations import scope_key, structured_observation
from .r5_b06_scope import precision_choice
from .sources import companyfacts_structured_facts, resolve_repository_file
from .specs import compile_spec_file


SPEC_PATH = "catalog/r5/B06_guarded_v3.md"
RESOLVER = "debt_equity_nonpositive_guard_v3"
EQUITY_CONCEPT = "us-gaap:StockholdersEquity"
_TRAIT_FILES = ("config/company_registry.csv", "config/metric_applicability.yaml",
                "catalog/company_traits.yaml")


class B06GuardError(ValueError):
    """A guard/source failure, never an inferred debt amount."""


def _need(condition, reason):
    if not condition:
        raise B06GuardError(reason)


def _installed_spec(repo_root):
    local = resolve_repository_file(repo_root=repo_root, repo_relative_path=SPEC_PATH)
    _need(sha256_file(path=local) == sha256_file(path=ROOT / SPEC_PATH),
          "B06_GUARD_INSTALLED_SPEC_REQUIRED")
    spec = compile_spec_file(path=local, dependency_specs={})
    _need(spec == compile_spec_file(path=ROOT / SPEC_PATH, dependency_specs={}),
          "B06_GUARD_INSTALLED_SPEC_REQUIRED")
    semantic = spec["compiled"]
    _need(semantic["metric_id"] == "B06" and semantic["kind"] == "derived_numeric"
          and semantic["source_mode"] == "structured"
          and semantic["formula"] == {"op": "divide", "args": ["debt", "equity"]}
          and "denominator_positive" in semantic["top_level_guards"]
          and semantic["quality_rule"]["resolver"] == RESOLVER
          and semantic["quality_rule"]["early_terminal_guard"] == {
              "role": "equity", "condition": "nonpositive",
              "required_sources": ["primary_inline", "accession_xml", "same_filing_companyfacts"],
              "debt_completeness": "NOT_EVALUATED",
              "terminal_reason": "DENOMINATOR_NONPOSITIVE"},
          "B06_GUARD_SPEC_SEMANTICS_CHANGED")
    hashes = {}
    for relative in _TRAIT_FILES:
        expected = sha256_file(path=ROOT / relative)
        _need(sha256_file(path=resolve_repository_file(repo_root=repo_root,
              repo_relative_path=relative)) == expected, "B06_GUARD_TRAIT_AUTHORITY_CHANGED")
        hashes[relative] = expected
    return spec, hashes


def _source_equity(*, raw, kind, target, period, filing):
    """Rebuild all eligible reports, with native identity and visible cells."""
    _need(annual_period(raw=raw, cik=target["entity"], filing=filing) == period,
          "B06_GUARD_ANNUAL_SOURCE_IDENTITY_CONFLICT")
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    metadata = _FactAttributes()
    metadata.feed(raw.decode("utf-8"))
    metadata.close()
    _need(metadata.ordinal == len(parsed.facts), "B06_GUARD_FACT_STREAM_DIFFERS")
    reports, census = [], []
    for fact in parsed.facts:
        item = metadata.facts[fact["ordinal"]]
        namespace, name = item["concept"]
        if name.casefold() != "stockholdersequity":
            continue
        _need(re.fullmatch(r"https?://fasb\.org/us-gaap/[0-9]{4}", namespace) is not None,
              "B06_GUARD_EQUITY_NAMESPACE_CONFLICT")
        context = parsed.contexts[fact["context_ref"]]
        scope = {**dict(context), "dimensions": dict(context["dimensions"])}
        row = {"ordinal": fact["ordinal"], "context": scope}
        if context["period_start"] != context["period_end"] or context["period_end"] != target["period_end"]:
            row["disposition"] = "OTHER_SOURCE_PERIOD"
        elif context["dimensions"] or context["typed_dimension_count"]:
            row["disposition"] = "DIMENSIONED_EQUITY_NOT_CONSOLIDATED_DENOMINATOR"
        else:
            _need(str(int(context["entity_identifier"])) == target["entity"],
                  "B06_GUARD_EQUITY_SUBJECT_CONFLICT")
            unit = metadata.units.get(fact["unit_ref"])
            _need(unit == {"measures": [("http://www.xbrl.org/2003/iso4217", "USD")], "divided": False},
                  "B06_GUARD_EQUITY_UNIT_CONFLICT")
            _need(item["attrs"]["contextref"] == fact["context_ref"], "B06_GUARD_CONTEXT_BINDING_CHANGED")
            value = _source_value(fact, item)
            report = {"value": value, "decimals": item["attrs"].get("decimals"),
                      "ordinal": fact["ordinal"], "context_ref": fact["context_ref"]}
            reports.append(report)
            row.update(disposition="CONSOLIDATED_CURRENT_EQUITY", value=value,
                       decimals=report["decimals"], native_unit_definition=unit)
        census.append(row)
    _need(bool(reports), "B06_GUARD_CURRENT_EQUITY_MISSING:" + kind)
    selected = precision_choice(reports)
    if kind == "primary_inline":
        index = _InlineTableIndex(raw)
        index.feed(raw.decode("utf-8"))
        index.close()
        cells = _fact_cells(index, parsed, {r["ordinal"] for r in reports})
        for report in reports:
            _need(report["ordinal"] in cells, "B06_GUARD_EQUITY_VISIBLE_CELL_REQUIRED")
            table, cell = cells[report["ordinal"]]
            fact = parsed.facts[report["ordinal"] - 1]
            visible = parse_numeric_claim(raw_value=cell["text"], reported_unit="USD")
            visible *= Decimal(10) ** int(fact["scale"] or "0")
            _need(visible == Decimal(report["value"]), "B06_GUARD_VISIBLE_SIGN_OR_SCALE_CONFLICT")
            report["visible_cell"] = {"table_id": table["table_id"], "grid_sha256": table["grid_sha256"],
                **{k: cell[k] for k in ("row_index", "column_index", "origin_row_index", "origin_column_index",
                                       "rowspan", "colspan", "raw_text", "text")}}
            report["raw_start_byte"] = index.fact_positions[report["ordinal"]]
    return {"source_sha256": sha256_bytes(content=raw), "kind": kind,
            "reports": reports, "chosen": selected, "equity_census": census}


def _rebuild_equity(*, primary, xml, facts_raw, facts_source, target, period, filing):
    primary_evidence = _source_equity(raw=primary, kind="primary_inline", target=target, period=period, filing=filing)
    xml_evidence = _source_equity(raw=xml, kind="accession_xml", target=target, period=period, filing=filing)
    chosen = precision_choice(primary_evidence["reports"] + xml_evidence["reports"])
    facts = companyfacts_structured_facts(raw_bytes=facts_raw, source_reference=facts_source,
        approved_concepts=[EQUITY_CONCEPT], allowed_ciks=[target["entity"]], include_instant=True)
    current = [f for f in facts if f["accession"] == target["accession"]
               and f["entity"] == target["entity"]
               and f["period_start"] == f["period_end"] == target["period_end"]]
    _need(bool(current), "B06_GUARD_SAME_FILING_COMPANYFACTS_MISSING")
    _need(all(f["unit"] == "USD" and f["value"] == chosen["value"] for f in current),
          "B06_GUARD_COMPANYFACTS_CONFLICT")
    # Bind the observation to an actual report at the selected precision.
    # A compatible coarser XML value must not become the locator for a finer
    # inline value that it did not itself report.
    located = [(kind, report) for kind, evidence in (("xml", xml_evidence), ("primary", primary_evidence))
               for report in evidence["reports"]
               if report["value"] == chosen["value"] and report["decimals"] == chosen["decimals"]]
    source_kind, observation_report = located[0]
    return {"record_type": "B06_DENOMINATOR_SOURCE_PROOF", "value": chosen["value"], "unit": "USD",
            "target": target, "filing_period": period, "primary": primary_evidence, "xml": xml_evidence,
            "observation_source_kind": source_kind, "observation_report": observation_report,
            "same_filing_companyfacts": current, "debt_completeness": "NOT_EVALUATED"}


def _terminal_records(*, spec, target, proof, source, filed, form):
    """Private record materializer; ordinary callers must use source replay."""
    _need(type(proof["value"]) is str and Decimal(proof["value"]) <= 0
          and proof["target"] == target and proof["debt_completeness"] == "NOT_EVALUATED",
          "B06_GUARD_NONPOSITIVE_PROOF_REQUIRED")
    report = proof["observation_report"]
    kind = proof["observation_source_kind"]
    _need(report["value"] == proof["value"] and report in proof[kind]["reports"]
          and source["raw_asset_id"] == "sha256:" + proof[kind]["source_sha256"],
          "B06_GUARD_OBSERVATION_SOURCE_VALUE_CHANGED")
    binding = {"raw_asset_id": source["raw_asset_id"], "source_reference_id": source["source_reference_id"],
        "source_role": source["source_role"], "document_name": source["document_name"], "accession": target["accession"],
        "entity": target["entity"], "concept": EQUITY_CONCEPT, "form": form, "filed": filed,
        "xbrl_context_ref": report["context_ref"], "xbrl_fact_ordinal": report["ordinal"],
        "reported_decimals": report["decimals"], "denominator_proof_hash": content_hash(value=proof)}
    observation = structured_observation(metric_id="B06", semantic_role="equity", company_id=target["company_id"],
        period_start=target["period_start"], period_end=target["period_end"], scope=target["scope"],
        value=proof["value"], unit="USD", quality="EXACT", source_binding=binding)
    result, trace = _result_and_trace(compiled_spec=spec, target=target, applicability="APPLICABLE",
        quality="NOT_MEANINGFUL", publication="PUBLISHED", reason_code="DENOMINATOR_NONPOSITIVE",
        value=None, result_unit=None,
        trace_steps=[{"event": "DENOMINATOR_GUARD", "resolver": RESOLVER, "role": "equity",
            "condition": "nonpositive", "value": proof["value"], "source_proof_hash": content_hash(value=proof),
            "debt_completeness": "NOT_EVALUATED", "numerator_evaluated": False}],
        input_ids=[observation["observation_id"]])
    return result, trace, [observation]


def prepare_guarded_b06_result(*, repo_root: Path, company_id: str):
    """Return NOT_MEANINGFUL native records, or CONTINUE_DEBT_PATH; never a Run."""
    spec, trait_hashes = _installed_spec(repo_root)
    preparation = _prepare_b06(repo_root=repo_root, company_id=company_id)
    prepared = preparation["input_binding"]["prepared_annual_input"]
    proofs = list(preparation["input_binding"]["source_proofs"]) + list(prepared["source_proofs"])
    admission = verify_saved_source_proofs(data_root=repo_root, proofs=proofs)
    period = prepared["table_input"]["target_period"]
    scope = {"entity_scope": "consolidated"}
    target = {"company_id": company_id, "entity": prepared["entity"], "accession": prepared["filing"]["accessionNumber"],
              "period_start": period["period_end"], "period_end": period["period_end"],
              "scope": scope, "scope_key": scope_key(scope=scope)}
    for key in ("primary", "xml", "facts"):
        item = preparation[key]
        _need(item["source_reference"]["raw_asset_id"] == "sha256:" + sha256_bytes(content=item["raw_bytes"]),
              "B06_GUARD_SOURCE_CHANGED_AFTER_ADMISSION")
    proof = _rebuild_equity(primary=preparation["primary"]["raw_bytes"], xml=preparation["xml"]["raw_bytes"],
        facts_raw=preparation["facts"]["raw_bytes"], facts_source=preparation["facts"]["source_reference"],
        target=target, period=period, filing=prepared["filing"])
    company = next(c for c in _registry_rows(repo_root=repo_root) if c["company_id"] == company_id)
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
        result, trace, observations = _terminal_records(spec=spec, target=target, proof=proof,
            source=preparation[proof["observation_source_kind"]]["source_reference"],
            filed=prepared["filing"]["filingDate"], form=prepared["filing"]["form"])
    body = {"record_type": "B06_GUARDED_RESULT_COMPONENT", "resolver": RESOLVER, "company_id": company_id,
        "status": status, "reason_code": reason, "spec_path": SPEC_PATH, "spec_closure_hash": spec["spec_closure_hash"],
        "input_binding": preparation["input_binding"], "source_admission": admission, "trait_file_hashes": trait_hashes,
        "target": target, "filing_period": period, "equity_proof": proof, "debt_completeness": "NOT_EVALUATED",
        "source_records": preparation["records"],
        "source_references": [r for r in preparation["records"] if r["record_type"] == "SOURCE_REFERENCE"],
        "observations": observations, "trace": trace, "result": result, "native_run_status": "NOT_CREATED",
        "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}
    # QName measures originate as Python tuples. The public component contract
    # is JSON, so return the same list shapes that a cold reader receives.
    body = strict_json_loads(text=canonical_json_bytes(value=body).decode("utf-8"))
    return {**body, "component_id": content_hash(value=body)}


def verify_guarded_b06_result(*, candidate, repo_root: Path, company_id: str):
    """Rebuild original sources and exact native records, not just a checksum."""
    rebuilt = prepare_guarded_b06_result(repo_root=repo_root, company_id=company_id)
    _need(candidate == rebuilt, "B06_GUARDED_RESULT_REPLAY_CHANGED")
    return rebuilt
