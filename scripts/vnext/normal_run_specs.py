"""Installed file identities for the ordinary zero-AI native Run successor.

Compiled catalog semantics are materialized as reviewable Spec files without
changing their closure. Existing B01/B03 source files and dependency identities
remain intact. This module never writes files or accepts caller-owned Specs.
"""
import copy
import json
from pathlib import Path

from .canonical import strict_json_file
from .deterministic_router import _compiled_event_spec, load_event_route_catalog
from .normal_source_authority import ROOT
from .specs import SPEC_FIELDS, compile_spec, compile_spec_file
from .zero_ai_r2 import _compiled_deterministic_spec, _load_deterministic_catalog


DIRECT_PATHS = {"B01":"catalog/metrics/B01_revenue.md", "B03":"catalog/metrics/B03_ebitda_margin.md"}
GENERATED_DIRECTORY = "catalog/ordinary_zero_ai"


def _spec_document(spec):
    front = {key:value for key,value in spec["compiled"].items() if key in SPEC_FIELDS}
    # These catalog-owned numeric Specs have no prompt-only instructions. Do
    # not silently drop them if a future catalog adds a different Spec kind.
    if spec["prompt_bundle"]["ai_instructions"] or spec["prompt_bundle"]["prompt_examples"]:
        raise ValueError("ORDINARY_GENERATED_SPEC_MUST_BE_PROMPT_FREE")
    text = "---\n" + json.dumps(front,ensure_ascii=False,indent=2) + "\n---\n" + spec["body"] + "\n"
    if compile_spec(text=text) != spec:
        raise ValueError("ORDINARY_SPEC_DOCUMENT_CHANGED_COMPILED_CLOSURE")
    return text


def installed_ordinary_spec_documents():
    """Return code-owned source paths/text/compiled identities for all22 Specs."""
    catalog = _load_deterministic_catalog(repo_root=ROOT)
    events = load_event_route_catalog(repo_root=ROOT)
    native = strict_json_file(path=ROOT/"config/normal_accession_metrics_v1.json")
    result = {}
    b01 = compile_spec_file(path=ROOT/DIRECT_PATHS["B01"],dependency_specs={})
    for metric,path in DIRECT_PATHS.items():
        compiled = b01 if metric == "B01" else compile_spec_file(path=ROOT/path,dependency_specs={"B01":b01})
        result[metric] = {"path":path,"text":(ROOT/path).read_text(encoding="utf-8"),"compiled_spec":compiled}
    for metric,route in catalog["metrics"].items():
        selected = copy.deepcopy(route)
        if route["adapter_id"] == "accession_xbrl":
            selected["canonical_unit"] = native["metrics"][metric]["canonical_unit"]
            selected["result_period_role"] = "current_instant"
            for branch in selected["branches"]:
                for component in branch["components"]:component["unit"] = selected["canonical_unit"]
        elif route["adapter_id"] != "companyfacts":
            raise ValueError("ORDINARY_CATALOG_ADAPTER_NOT_SUPPORTED")
        compiled = _compiled_deterministic_spec(metric_id=metric,route=selected)
        result[metric] = {"path":GENERATED_DIRECTORY+"/"+metric+".md","text":_spec_document(compiled),"compiled_spec":compiled}
    for metric,route in events["routes"].items():
        compiled = _compiled_event_spec(metric_id=metric,route=route)
        result[metric] = {"path":GENERATED_DIRECTORY+"/"+metric+".md","text":_spec_document(compiled),"compiled_spec":compiled}
    if len(result) != 22 or len({r["path"] for r in result.values()}) != 22:
        raise ValueError("ORDINARY_SPEC_SOURCE_SET_CHANGED")
    return result


def validate_ordinary_spec_files(*, repo_root: Path):
    expected = installed_ordinary_spec_documents()
    from .sources import resolve_repository_file
    for metric,row in expected.items():
        if resolve_repository_file(repo_root=repo_root,repo_relative_path=row["path"]).read_text(encoding="utf-8") != row["text"]:
            raise ValueError("ORDINARY_INSTALLED_SPEC_BYTES_CHANGED:"+metric)
    return expected
