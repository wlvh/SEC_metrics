"""Successor annual input: issuer fiscal label and raw metadata stay distinct."""
import json
from collections import OrderedDict
from collections.abc import Mapping
from pathlib import Path

from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_file, strict_json_loads
from . import fiscal_year_labels
from .normal_annual_input import NormalAnnualInputError, prepare_saved_annual_input as prepare_original_input
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .sources import resolve_repository_file


POLICY_PATH = "config/normal_fiscal_year_labels_v1.json"
_INSPECTOR_SHA = sha256_file(path=Path(fiscal_year_labels.__file__))
_INSPECTIONS = OrderedDict()
_MAX_INSPECTIONS = 16


def exact_json_value(value):
    """Validate the existing JSON domain without NFC-rewriting source quotes."""
    canonical_json_bytes(value=value)
    def plain(item):
        if isinstance(item,Mapping):
            return {key:plain(part) for key,part in item.items()}
        if isinstance(item,(tuple,list)):
            return [plain(part) for part in item]
        return item
    return strict_json_loads(text=json.dumps(plain(value),ensure_ascii=False,allow_nan=False))


def _choose_fiscal_year(inspected):
    status = inspected["status"]
    explicit = inspected["source_defined_fiscal_year"]
    if inspected["invalid_companyfacts_fy_rows"] or status == "EXPLICIT_DEFINITION_UNRESOLVED":
        raise NormalAnnualInputError("ORDINARY_FISCAL_LABEL_UNRESOLVED:"+status,"SOURCE_LABEL_UNRESOLVED")
    if status == "METADATA_LABEL_ONLY":
        year, basis = inspected["dei_fiscal_year"], "CONSISTENT_SOURCE_METADATA"
    elif type(explicit) is int and status in {"SOURCE_LABELS_CONSISTENT","SOURCE_LABEL_CONFLICT"}:
        year, basis = explicit, "EXPLICIT_SOURCE_ISSUER_DEFINITION"
    else:
        raise NormalAnnualInputError("ORDINARY_FISCAL_LABEL_UNRESOLVED:"+status,"SOURCE_LABEL_UNRESOLVED")
    return year, basis


def prepare_saved_annual_input(*, repo_root: Path, company_id: str):
    policy = strict_json_file(path=resolve_repository_file(repo_root=repo_root,repo_relative_path=POLICY_PATH))
    if policy != strict_json_file(path=ROOT/POLICY_PATH) or policy["policy_id"] != "ordinary_fiscal_year_labels_v1":
        raise NormalAnnualInputError("ORDINARY_FISCAL_LABEL_INSTALLED_POLICY_CHANGED","AUTHORITY_CONFLICT")
    # Always re-read filing selection, latest request outcome and all admitted
    # body/header bytes before reusing an interpretation. Cached JSON is only
    # process-local parsing of those exact inputs, never source or call credit.
    original = prepare_original_input(repo_root=repo_root,company_id=company_id)
    admission = verify_saved_source_proofs(data_root=repo_root,proofs=original["source_proofs"])
    if sha256_file(path=Path(fiscal_year_labels.__file__)) != _INSPECTOR_SHA:
        raise NormalAnnualInputError("FISCAL_INSPECTOR_CHANGED_DURING_SESSION","RUNTIME_CHANGED")
    key = (original["input_id"],admission["source_manifest_sha256"],_INSPECTOR_SHA)
    if key not in _INSPECTIONS:
        report = fiscal_year_labels._inspect_prepared_input(repo_root=repo_root,prepared=original)
        _INSPECTIONS[key] = json.dumps(report["inspection"],ensure_ascii=False,allow_nan=False)
        if len(_INSPECTIONS) > _MAX_INSPECTIONS:
            _INSPECTIONS.popitem(last=False)
    else:
        _INSPECTIONS.move_to_end(key)
    inspected = strict_json_loads(text=_INSPECTIONS[key])
    year, basis = _choose_fiscal_year(inspected)
    status = inspected["status"]
    period = {**original["table_input"]["target_period"],"fiscal_year":year}
    resolution = {"record_type":"ORDINARY_FISCAL_YEAR_LABEL_RESOLUTION","policy_id":policy["policy_id"],
        "policy_sha256":sha256_file(path=ROOT/POLICY_PATH),"selected_fiscal_year":year,"basis":basis,
        "source_inspection_status":status,"original_dei_fiscal_year":inspected["dei_fiscal_year"],
        "original_companyfacts_fiscal_year_values":inspected["companyfacts_fiscal_year_values"],
        "metadata_conflict_retained":status == "SOURCE_LABEL_CONFLICT",
        "source_inspection":inspected,"actual_dates_changed":False,"historical_input_or_run_changed":False}
    body = {k:v for k,v in original.items() if k != "input_id"}
    body.update(table_input={**original["table_input"],"target_period":period},
                companyfacts_input={**original["companyfacts_input"],"target_period":period},
                original_input=original,fiscal_year_label_resolution=resolution,
                fiscal_label_policy="SOURCE_ISSUER_YEAR_WITH_RAW_METADATA_RETAINED")
    # Exact source quote characters remain intact; only IDs use canonical JSON.
    body = exact_json_value(body)
    return {**body,"input_id":content_hash(value=body)}
