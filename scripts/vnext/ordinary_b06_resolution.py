"""Existing original-source borrowing resolver, without native Run management."""
from .canonical import content_hash
from .specs import compile_spec_file
from .traits import repository_company_traits


def _b06_resolution(*, data_root, preparation):
    from . import b06_disclosure_v2 as disclosure
    from .calculator import withheld_metric_result
    from .normal_annual_input import _registry_rows
    from .r5_b06_scope import resolve_financing
    from .sources import companyfacts_structured_facts
    from .canonical import strict_json_file
    prepared = preparation["input_binding"]["prepared_annual_input"]
    path = disclosure.SPEC_PATH
    spec = compile_spec_file(path=data_root / path, dependency_specs={})
    scope = {"entity_scope": "consolidated"}
    end = prepared["table_input"]["target_period"]["period_end"]
    target = {"company_id": prepared["company_id"], "entity": prepared["entity"],
              "accession": prepared["filing"]["accessionNumber"], "period_start": end,
              "period_end": end, "scope": scope, "scope_key": content_hash(value=scope)}
    company = next(c for c in _registry_rows(repo_root=data_root) if c["company_id"] == prepared["company_id"])
    try:
        if company["industry_profile"] == "financial_institution":
            raise ValueError("B06_BANK_SCOPE_NOT_IMPLEMENTED_IN_THIS_RESOLVER")
        parsed = disclosure.prior.parse_accession_xbrl_source(raw_bytes=preparation["xml"]["raw_bytes"])
        members = set(spec["compiled"]["quality_rule"]["scope_review_dimension_members"])
        if any(any(str(member).split(":")[-1] in members for member in c["dimensions"].values())
               for c in parsed.contexts.values() if c["period_end"] == end
               and str(int(c["entity_identifier"])) == prepared["entity"]):
            raise ValueError("B06_INDUSTRIAL_SCOPE_REQUIRES_SEPARATE_PROOF")
        proposal = disclosure.propose(raw=preparation["xml"]["raw_bytes"],
            primary=preparation["primary"]["raw_bytes"], target=target)
        measurement = disclosure.verify(raw=preparation["xml"]["raw_bytes"],
            primary=preparation["primary"]["raw_bytes"], source=preparation["xml"]["source_reference"],
            spec=spec, target=target, filed=prepared["filing"]["filingDate"], data_root=data_root, proposal=proposal)
        registry = strict_json_file(path=data_root / spec["compiled"]["quality_rule"]["debt_set_registry"])
        concepts = {spec["compiled"]["quality_rule"]["equity_concept"]}
        for model in registry["debt_set_models"].values():
            concepts.update(model["inputs"].values())
            for check in model.get("checks", []): concepts.update(check["inputs"].values())
        facts = companyfacts_structured_facts(raw_bytes=preparation["facts"]["raw_bytes"],
            source_reference=preparation["facts"]["source_reference"], approved_concepts=sorted(concepts),
            allowed_ciks=[prepared["entity"]], include_instant=True)
        result, trace, observations, audit = resolve_financing(spec=spec, target=target,
            traits=repository_company_traits(repo_root=data_root, company_id=prepared["company_id"]),
            facts=facts, measurement=measurement)
        return path, {"result": result, "trace": trace, "observations": observations,
                      "selection": {"measurement": measurement, "audit": audit}}
    except ValueError as error:
        reason = str(error)
        category = ("RELATIONSHIP_AMBIGUOUS" if reason.startswith("UNRESOLVED_FINANCING_ITEM")
                    else "SOURCE_CONFLICT" if reason.startswith("B06_V2_PRIMARY_XML_AMOUNT_CONFLICT")
                    else "IMPLEMENTATION_GAP")
        simple_target = {k: target[k] for k in ("company_id", "period_start", "period_end", "scope", "scope_key")}
        result, trace = withheld_metric_result(compiled_spec=spec, target=simple_target,
                                             reason_code="B06_SOURCE_RELATIONSHIP_UNRESOLVED")
        return path, {"result": result, "trace": trace, "observations": [],
                      "selection": {"reason": reason, "classification": category}}
