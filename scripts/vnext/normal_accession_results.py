"""Ordinary A01/A02/B12 native facts with explicit units and instant grain.

The frozen catalog still owns the concept/dimension scope. A separate ordinary
policy converts declared unit definitions and corrects the new result grain;
no historical catalog, engine, Result, or Run is rewritten.
"""
import copy
from pathlib import Path
import re

from sec_urls import companyfacts_url, submissions_url
from .calculator import metric_is_applicable, withheld_metric_result, calculate_observation_metric
from .canonical import canonical_json_bytes, content_hash, sha256_file, sha256_bytes, strict_json_file, strict_json_loads
from .deterministic_router import parse_accession_xbrl_source, verified_claim
from .governance_signals import _source_value, _qname
from .normal_annual_input_v2 import prepare_saved_annual_input, exact_json_value, POLICY_PATH as FISCAL_LABEL_POLICY_PATH
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .observations import scope_key, structured_observation
from .sources import resolve_repository_file
from .text_results_v2 import _ReportedFactMetadata, _verified_context
from .traits import repository_company_traits
from .zero_ai_r2 import (_load_deterministic_catalog, _compiled_deterministic_spec,
    _manual_result_trace, _exact_filing_source_set)


POLICY_PATH = "config/normal_accession_metrics_v1.json"
_AUTHORITY = (POLICY_PATH,FISCAL_LABEL_POLICY_PATH,"catalog/deterministic_metrics.json","config/company_registry.csv",
              "catalog/company_traits.yaml","config/metric_applicability.yaml")


class NormalAccessionError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise NormalAccessionError(reason)


class _Metadata(_ReportedFactMetadata):
    def __init__(self):
        super().__init__()
        self.root_namespaces = None

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if self.root_namespaces is None and len(self.stack) == 1:
            self.root_namespaces = dict(self.stack[0][1])


def _expanded_scope(component, namespaces, policy):
    result, extensions = {}, set()
    for axis, member in component["required_dimensions"].items():
        resolved = []
        for value in (axis, member):
            prefix = value.partition(":")[0]
            uri, local = _qname(value, namespaces)
            _need(uri and local,"NORMAL_ACCESSION_CATALOG_NAMESPACE_UNBOUND")
            patterns = {"us-gaap":"us_gaap_namespace_pattern","srt":"srt_namespace_pattern","dei":"dei_namespace_pattern"}
            if prefix in patterns:
                _need(re.fullmatch(policy[patterns[prefix]],uri),"NORMAL_ACCESSION_STANDARD_NAMESPACE_CHANGED")
            else:
                # The existing catalog names this member in the filing's
                # declared extension. A locally rebound prefix cannot replace
                # the root declaration used to expand this required scope.
                extensions.add(uri)
            resolved.append((uri,local))
        result[resolved[0]] = resolved[1]
    return result, extensions


def inspect_ordinary_accession_facts(*, raw_bytes, source_reference, source_set_manifest,
                                    expected_cik, period_end, route, metric_id, policy):
    """Inspect supplied source bytes; source acquisition is not granted here."""
    _need(source_reference["raw_asset_id"] == "sha256:"+sha256_bytes(content=raw_bytes),
          "NORMAL_ACCESSION_SOURCE_BYTES_CHANGED")
    parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
    metadata = _Metadata();metadata.feed(raw_bytes.decode("utf-8-sig"));metadata.close()
    _need(metadata.ordinal == len(parsed.facts),"NORMAL_ACCESSION_FACT_STREAM_CHANGED")
    _need(len(route["branches"]) == 1 and len(route["branches"][0]["components"]) == 1,
          "NORMAL_ACCESSION_DIRECT_SCOPE_REQUIRED")
    component = route["branches"][0]["components"][0]
    required_dimensions, extension_namespaces = _expanded_scope(component, metadata.root_namespaces or {}, policy)
    names = {n.casefold() for n in component["approved_concepts"]}
    metric = policy["metrics"][metric_id]
    rows, selected, conflicts = [], [], []
    for fact in parsed.facts:
        meta = metadata.facts[fact["ordinal"]]
        uri, local = meta["concept"]
        if local.casefold() not in names:
            continue
        native = parsed.contexts[fact["context_ref"]]
        context = {**native,"dimensions":dict(native["dimensions"])}
        row = {"ordinal":fact["ordinal"],"qualified_name":fact["qualified_name"],"concept_qname":[uri,local],
               "context":context,"unit_ref":fact["unit_ref"],"source_text":fact["text"],"reason":None}
        if context["period_start"] != period_end or context["period_end"] != period_end:
            row["reason"] = "OTHER_SOURCE_PERIOD"
        elif str(context["entity_identifier"]).isdigit() and int(context["entity_identifier"]) != int(expected_cik):
            row["reason"] = "OTHER_SOURCE_ENTITY"
        else:
            try:
                proof = _verified_context(native=context,metadata=metadata)
                dimensions = {tuple(d["dimension_qname"]):tuple(d["member_qname"]) for d in proof["dimensions"]}
                if dimensions != required_dimensions:
                    row["reason"] = "OTHER_DISCLOSED_DIMENSION_SCOPE"
                else:
                    valid_namespace = (re.fullmatch(policy["us_gaap_namespace_pattern"],uri) is not None
                        if metric["concept_namespace"] == "US_GAAP" else len(extension_namespaces) == 1 and uri in extension_namespaces)
                    _need(valid_namespace,"NORMAL_ACCESSION_CONCEPT_NAMESPACE_NOT_APPROVED")
                    unit = metadata.units.get(fact["unit_ref"])
                    _need(unit == {"measures":[tuple(metric["unit_measure"])],"divided":False},
                          "NORMAL_ACCESSION_DECLARED_UNIT_NOT_APPROVED")
                    tag_uri, tag_local = _qname(meta["tag"],meta["namespaces"])
                    _need((tag_uri in policy["numeric_inline_namespaces"] and tag_local == "nonfraction")
                          or (tag_uri,tag_local) == meta["concept"],"NORMAL_ACCESSION_NUMERIC_TAG_NOT_PROVEN")
                    value = _source_value(fact,meta)
                    transform = meta["attrs"].get("format","")
                    if _qname(transform,meta["namespaces"])[1] not in {"fixed-zero","numdash"}:
                        pattern = policy["dot_decimal_pattern"] if transform else policy["unformatted_decimal_pattern"]
                        _need(re.fullmatch(pattern,str(fact["text"]).strip()),"NORMAL_ACCESSION_NUMERIC_LEXICAL_FORM_NOT_SUPPORTED")
                    claim = verified_claim(claim_kind="ACCESSION_XBRL_NUMERIC_FACT",source_reference=source_reference,
                        source_set_manifest=source_set_manifest,locator={"qualified_name":fact["qualified_name"],
                            "context_ref":fact["context_ref"],"ordinal":fact["ordinal"]},
                        value=value,unit=metric["canonical_unit"],attributes={"adapter_id":"ACCESSION_XBRL",
                            "canonical_name":local,"context":context,"lexical_value":fact["text"],
                            "verified_context":proof,"concept_qname":[uri,local],"source_unit_definition":unit,
                            "raw_unit_ref":fact["unit_ref"],"ordinary_policy_hash":content_hash(value=policy)})
                    selected.append(claim);row.update(value=value,unit=metric["canonical_unit"],reason="EXACT_SOURCE_SCOPE")
            except ValueError as error:
                row["reason"] = str(error);conflicts.append({"ordinal":fact["ordinal"],"reason":str(error)})
        rows.append(row)
    values = {(c["value"],c["unit"]) for c in selected}
    if len(values)>1:
        conflicts.append({"reason":"CONFLICTING_SAME_SCOPE_SOURCE_FACTS"})
    return {"metric_id":metric_id,"source_reference_id":source_reference["source_reference_id"],
        "facts":rows,"selected_claims":selected,"conflicts":conflicts,
        "status":"SOURCE_SCOPE_PROVEN" if selected and not conflicts else "UNRESOLVED",
        "source_acquisition_credit":False}


def resolve_ordinary_accession_metrics(*, repo_root: Path, company_id: str):
    authority = {}
    for relative in _AUTHORITY:
        digest = sha256_file(path=ROOT/relative)
        _need(sha256_file(path=resolve_repository_file(repo_root=repo_root,repo_relative_path=relative)) == digest,
              "NORMAL_ACCESSION_INSTALLED_AUTHORITY_CHANGED:"+relative)
        authority[relative] = digest
    policy = strict_json_file(path=repo_root/POLICY_PATH)
    _need(policy["record_type"] == "ORDINARY_ACCESSION_METRIC_POLICY" and policy["schema_version"] == 1
          and policy["creates_run"] is False and policy["production_authorized"] is False,"NORMAL_ACCESSION_POLICY_INVALID")
    catalog = _load_deterministic_catalog(repo_root=repo_root)
    current = copy.deepcopy(catalog)
    for metric_id, item in policy["metrics"].items():
        route = current["metrics"][metric_id]
        route["canonical_unit"] = item["canonical_unit"]
        route["result_period_role"] = "current_instant"
        for branch in route["branches"]:
            for component in branch["components"]:component["unit"] = item["canonical_unit"]
    prepared = prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    verify_ordinary_source_proofs(data_root=repo_root,proofs=prepared["source_proofs"])
    period = prepared["table_input"]["target_period"]
    reader = _Sources(repo_root,company_id,prepared["entity"])
    inventory = reader.read(submissions_url(cik=int(prepared["entity"])),role="sec_submissions_inventory",media_type="application/json")
    source = reader.primary(prepared["filing"])
    reader.read(companyfacts_url(cik=int(prepared["entity"])),accession=prepared["filing"]["accessionNumber"],role="companyfacts",media_type="application/json")
    manifest = _exact_filing_source_set(company_id=company_id,source_role="target_accession_instance",
        reference=source["source_reference"],inventory_reference=inventory["source_reference"],inventory_bytes=inventory["raw_bytes"])
    traits = repository_company_traits(repo_root=repo_root,company_id=company_id)
    rows = {}
    for metric_id,item in policy["metrics"].items():
        route = current["metrics"][metric_id]
        spec = _compiled_deterministic_spec(metric_id=metric_id,route=route)
        scope = {"coverage":"deterministic_source_set","fiscal_year":period["fiscal_year"]}
        target = {"company_id":company_id,"period_start":period["period_end"],"period_end":period["period_end"],
                  "scope":scope,"scope_key":scope_key(scope=scope)}
        inspection, observations, selected = None, [], []
        if not metric_is_applicable(applicability=route["applicability"],traits=traits):
            result,trace = _manual_result_trace(metric_id=metric_id,company_id=company_id,period_start=period["period_end"],
                period_end=period["period_end"],scope=scope,spec_closure_hash=spec["spec_closure_hash"],applicability="N_A_STRUCTURAL",
                quality="NONE",reason_code="TRAIT_NOT_APPLICABLE",input_observation_ids=[],steps=[{"event":"N_A_STRUCTURAL"}],
                accession=None,entity=None,unit=None)
        else:
            try:
                _need(not prepared["amendments"],"NORMAL_ACCESSION_AMENDMENT_REPLAY_NOT_IMPLEMENTED")
                _need(prepared["subject_policy"]["mode"] == "CONTINUOUS_PRIMARY","NORMAL_ACCESSION_SUCCESSOR_SCOPE_NOT_IMPLEMENTED")
                inspection = inspect_ordinary_accession_facts(raw_bytes=source["raw_bytes"],source_reference=source["source_reference"],
                    source_set_manifest=manifest,expected_cik=prepared["entity"],period_end=period["period_end"],
                    route=catalog["metrics"][metric_id],metric_id=metric_id,policy=policy)
                _need(inspection["status"] == "SOURCE_SCOPE_PROVEN","NORMAL_ACCESSION_SOURCE_SCOPE_UNRESOLVED")
                selected = sorted(inspection["selected_claims"],key=lambda c:c["verified_claim_id"])
                reference = source["source_reference"]
                observation = structured_observation(metric_id=metric_id,semantic_role="deterministic_value",
                    company_id=company_id,period_start=period["period_end"],period_end=period["period_end"],scope=scope,
                    value=selected[0]["value"],unit=item["canonical_unit"],quality="EXACT",
                    source_binding={"raw_asset_id":reference["raw_asset_id"],"source_reference_id":reference["source_reference_id"],
                        "accession":reference["accession"],"document_name":reference["document_name"],
                        "source_role":reference["source_role"],"source_set_manifest_id":manifest["source_set_manifest_id"],
                        "verified_claim_ids":[c["verified_claim_id"] for c in selected],
                        "ordinary_policy_hash":content_hash(value=policy),"source_measure":item["measure"]})
                result,trace = calculate_observation_metric(compiled_spec=spec,target=target,company_traits=traits,observation=observation)
                observations = [observation]
            except ValueError as error:
                inspection = {**(inspection or {}),"status":"UNRESOLVED","reason":str(error)}
                result,trace = withheld_metric_result(compiled_spec=spec,target=target,reason_code="NORMAL_ACCESSION_ROUTE_UNRESOLVED")
        rows[metric_id] = {"metric_id":metric_id,"measure":item["measure"],"compiled_spec":spec,"target":target,
            "inspection":inspection,"claims":selected,"observations":observations,"result":result,"trace":trace,
            "records":[*observations,trace,result]}
    proofs = list({content_hash(value=p):p for p in [*prepared["source_proofs"],*[s["proof"] for s in reader.proofs.values()]]}.values())
    body = {"record_type":"NORMAL_ACCESSION_NATIVE_RESULTS","company_id":company_id,"prepared_input":prepared,
        "authority_file_hashes":authority,"policy_hash":content_hash(value=policy),"source_records":list(reader.records.values()),
        "source_set":manifest,"source_proofs":proofs,"source_admission":verify_ordinary_source_proofs(data_root=repo_root,proofs=proofs),
        "metrics":rows,"resolver_sha256":sha256_file(path=Path(__file__)),"calls":{"provider":0,"paid":0,"sec":0},
        "native_run_status":"NOT_CREATED","current_latest_verified":False,"production_authorized":False}
    body = exact_json_value(body)
    return {**body,"component_id":content_hash(value=body)}


def verify_ordinary_accession_metrics(*, candidate, repo_root: Path, company_id: str):
    rebuilt = resolve_ordinary_accession_metrics(repo_root=repo_root,company_id=company_id)
    _need(candidate == rebuilt,"NORMAL_ACCESSION_SOURCE_REPLAY_CHANGED")
    return rebuilt
