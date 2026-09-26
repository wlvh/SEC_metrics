"""B13 at a pinned period, where the approved definition puts the company outside it.

The approved definition names B13's companies in its own heading - "B13
Capacity utilization (Ford / Enphase)" in 02_指标定义_SEC_10公司单年指标.md - and
for every other company the ordinary route answers without reading a filing:
capacity_run builds an N_A_STRUCTURAL text result with reason
TRAIT_NOT_APPLICABLE from the latest annual input, under category
APPROVED_B13_COMPANY_SCOPE. The historical frame had no route at all, so all
of those positions read as "not built yet" for a question the definition
already answers.

The scope is read from the definition, not from where the ordinary route reads
it. capacity_run takes the company set from Issue #28's continuous-call
policy, which also carries that Issue's budget and delegation; a historical
route that loaded it would make its answers depend on another Issue's spending
authority. The same two companies are named in the definition this frame's
parent already carries, and the differential test holds the two sources to
each other: for every company the ordinary route calls out of scope at the
newest period, this route's result is required to be field for field the same.

This route answers only the out-of-scope side. For Ford and Enphase B13 needs
the semantic review of capacity disclosures, which is a model call, and that
is refused here by name rather than answered as "not applicable" - which
would be a false statement about the issuer standing in for a missing route.
The coverage frame counts B13 as implemented only where this route answers.

Like the trait-gated structural route, the Run still carries the period's
admitted sources: the result takes no value from them, and they bind the Run
to the year that was asked for.
"""
import re
from pathlib import Path

from .canonical import content_hash, sha256_file
from .historical_annual_input import prepare_historical_annual_input
from .normal_annual_input import _registry_rows
from .ordinary_source_authority import verify_ordinary_source_proofs
from .sources import raw_blob_record, source_reference_record
from .specs import compile_spec_file
from .text_results import build_text_result_and_trace

RECORD_TYPE = "HISTORICAL_CAPACITY_SCOPE_RESULT"
SUPPORTED_METRICS = ("B13",)
# The text Spec the ordinary out-of-scope case is built under, so the two
# routes' results can be compared field for field.
SPEC_PATH = "catalog/r5/B13_capacity_disclosures_v1.md"
DEFINITION_PATH = "02_指标定义_SEC_10公司单年指标.md"
_HEADING = re.compile(r"^### B13 [^\n（]*（(?P<names>[^）\n]+)）[ \t]*$", re.M)


class HistoricalCapacityError(ValueError):
    """A scope limitation or a missing route, never a disclosure conclusion."""

    def __init__(self, reason, category="IMPLEMENTATION_GAP"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="IMPLEMENTATION_GAP"):
    if not condition:
        raise HistoricalCapacityError(reason, category)


def approved_scope(*, repo_root: Path):
    """The companies the approved definition names for B13, by registry id.

    Each name in the heading has to be the first word of exactly one
    registered company's display name. A heading that names nobody, or a name
    two companies could answer to, stops here: the scope is the whole of this
    route's authority, and a guess at it would be a guess at every answer.
    """
    text = (Path(repo_root) / DEFINITION_PATH).read_text(encoding="utf-8")
    headings = _HEADING.findall(text)
    _need(len(headings) == 1, "HISTORICAL_B13_DEFINITION_HEADING_NOT_UNIQUE:" + str(len(headings)))
    names = [name.strip() for name in headings[0].split("/")]
    _need(bool(names) and all(names), "HISTORICAL_B13_DEFINITION_NAMES_NO_COMPANY")
    rows = _registry_rows(repo_root=Path(repo_root))
    company_ids = []
    for name in names:
        matched = [row["company_id"] for row in rows
                   if row["display_name"].split()[0].casefold() == name.casefold()]
        _need(len(matched) == 1, "HISTORICAL_B13_DEFINITION_NAME_NOT_ONE_COMPANY:" + name)
        company_ids.append(matched[0])
    return {"definition_path": DEFINITION_PATH, "heading_names": names,
            "company_ids": sorted(company_ids),
            "definition_sha256": sha256_file(path=Path(repo_root) / DEFINITION_PATH)}


def out_of_scope(*, repo_root: Path, company_id: str, metric_id: str = "B13"):
    """Whether this route answers here: B13, for a company the definition leaves out."""
    return (metric_id in SUPPORTED_METRICS
            and company_id not in approved_scope(repo_root=repo_root)["company_ids"])


def resolve_historical_capacity_metric(*, repo_root: Path, company_id: str, metric_id: str,
                                       period_selection):
    """One pinned period's out-of-scope B13 result, with the period's sources."""
    repo_root = Path(repo_root)
    _need(metric_id in SUPPORTED_METRICS, "HISTORICAL_CAPACITY_METRIC_NOT_WIRED:" + str(metric_id))
    scope_record = approved_scope(repo_root=repo_root)
    _need(company_id not in scope_record["company_ids"],
          "HISTORICAL_B13_IN_SCOPE_NEEDS_THE_SEMANTIC_REVIEW:" + company_id)
    spec = compile_spec_file(path=repo_root / SPEC_PATH, dependency_specs={})
    _need(spec["compiled"]["metric_id"] == metric_id,
          "HISTORICAL_CAPACITY_SPEC_METRIC_CHANGED:" + SPEC_PATH)
    prepared = prepare_historical_annual_input(repo_root=repo_root, company_id=company_id,
                                               period_selection=period_selection)
    admission = verify_ordinary_source_proofs(data_root=repo_root,
                                              proofs=prepared["source_proofs"])
    period = prepared["table_input"]["target_period"]
    scope = spec["compiled"]["required_claims"]
    # The ordinary out-of-scope case's own target shape: no entity and no
    # accession, because the answer is about the definition's scope and not
    # about anything a filing says.
    target = {"company_id": company_id, "entity": None, "accession": None,
              "period_start": period["period_start"], "period_end": period["period_end"],
              "scope": scope, "scope_key": content_hash(value=scope)}
    result, trace = build_text_result_and_trace(compiled_spec=spec, target=target,
                                                structural=True,
                                                reason_code="TRAIT_NOT_APPLICABLE")
    _need(result["applicability"] == "N_A_STRUCTURAL" and result["value"] is None,
          "HISTORICAL_CAPACITY_RESULT_IS_NOT_STRUCTURAL")
    source_records, references = [], []
    for proof in prepared["source_proofs"]:
        blob = raw_blob_record(
            repo_root=repo_root, repo_relative_path=proof["request_repo_relative_path"],
            media_type=("application/json" if proof["document_name"].endswith(".json")
                        else "text/plain"))
        reference = source_reference_record(
            raw_blob=blob, company_id=company_id, source_url=proof["source_url"],
            accession=proof["accession"] or "SUBMISSIONS-" + prepared["entity"],
            document_name=proof["document_name"], source_role="supporting_input",
            request_attempt_id=proof["request_attempt_id"])
        source_records.extend([blob, reference])
        references.append(reference)
    source_records = list({content_hash(value=r): r for r in source_records}.values())
    body = {"record_type": RECORD_TYPE, "company_id": company_id, "metric_id": metric_id,
            "period_selection": period_selection, "spec_path": SPEC_PATH,
            "spec_origin": {"spec_path": SPEC_PATH}, "compiled_spec": spec,
            "approved_scope": scope_record, "prepared_input": prepared,
            "target_period": period, "target": target,
            "source_records": source_records,
            "source_references": [r for r in source_records
                                  if r["record_type"] == "SOURCE_REFERENCE"],
            "source_proofs": prepared["source_proofs"], "source_admission": admission,
            "source_set_manifests": [], "claims": [], "observations": [],
            "dependency_specs": {}, "dependency_records": [],
            "selection": {"status": "N_A_STRUCTURAL",
                          "category": "APPROVED_DEFINITION_COMPANY_SCOPE",
                          "reason_code": "B13_OUTSIDE_APPROVED_APPLICABILITY",
                          "disclosure_absence_asserted": False,
                          "value_taken_from_any_filing": False},
            "result": result, "trace": trace,
            "records": list({content_hash(value=r): r
                             for r in [*source_records, trace, result]}.values()),
            "resolver_sha256": sha256_file(path=Path(__file__)),
            "native_run_status": "NOT_CREATED", "current_latest_verified": False,
            "latest_restated_values_used": False,
            "calls": {"provider": 0, "paid": 0, "sec": 0}, "production_authorized": False}
    return {**body, "component_id": content_hash(value=body)}
