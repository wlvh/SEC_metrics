"""JPMorgan FY2021 C02 and C03 through the historical route, with the code tree's own readers.

Usage: python3 route_probe.py <code tree> <restored source root> <out.json>

The code tree must be the one whose trust journal registered the restored
root (the root restored from the acquisition's export), with this change's two
readers in it; ``vnext`` is imported from that tree and the script checks it.
C03 goes through ``resolve_historical_governance_metric``; C02 through the
input admission and the deterministic candidate. Zero calls.
"""
import json, re, sys, time
from pathlib import Path
PROG, ROOT, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(PROG / "scripts"))
import vnext
assert Path(vnext.__file__).resolve().is_relative_to(PROG.resolve()), vnext.__file__
from vnext.normal_history_plan import checkpoint_replayed_once
from vnext.normal_period_selection import resolve_period_selection
from vnext.historical_governance_results import resolve_historical_governance_metric
from vnext.historical_results import TEXT_SPEC_PATHS
from vnext.historical_spec_revision import compile_historical_spec_file
from vnext.historical_text_input import prepare_historical_business_text_input
from vnext.historical_text_results import shared_source_preparation, text_api

out = {"code": "the code tree named on the command line"}
with checkpoint_replayed_once():
    selection = resolve_period_selection(repo_root=ROOT, company_id="jpmorgan_chase", report_end="2021-12-31")
    t = time.time()
    try:
        component = resolve_historical_governance_metric(repo_root=ROOT, company_id="jpmorgan_chase",
                                                         metric_id="C03", period_selection=selection)
        result = component["result"] if "result" in component else component.get("primary_result")
        out["C03"] = {k: result.get(k) for k in ("publication", "quality", "reason_code", "value", "unit")} if result else sorted(component)
    except Exception as e:
        out["C03"] = {"error": type(e).__name__ + ":" + str(e)[:400]}
    out["C03"]["seconds"] = int(time.time() - t)
    print("C03", out["C03"], flush=True)
    t = time.time()
    try:
        with shared_source_preparation():
            prepared = prepare_historical_business_text_input(repo_root=ROOT, company_id="jpmorgan_chase",
                                                              metric_id="C02", period_selection=selection)
            if prepared["input_status"] == "BLOCKED":
                out["C02"] = {"blocked": prepared["input_binding"]["limitations"]}
            else:
                spec = compile_historical_spec_file(repo_root=ROOT, repo_relative_path=TEXT_SPEC_PATHS["C02"], dependency_specs={})
                api, _ = text_api("C02")
                candidate = api.create_deterministic_text_candidate(compiled_spec=spec, **prepared["text_arguments"])
                out["C02"] = {"identity": prepared["input_binding"].get("proxy_cover_identity"),
                              "selected": len(candidate["selected"])}
    except Exception as e:
        out["C02"] = {"error": type(e).__name__ + ":" + str(e)[:400]}
    out["C02"]["seconds"] = int(time.time() - t)
    print("C02", json.dumps(out["C02"])[:600], flush=True)
OUT.write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
