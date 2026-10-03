"""One request set's identities (what an approval names), the scripts modules loaded and the non-evidence files read."""
import hashlib, json, sys
from pathlib import Path
repo = Path(sys.argv[1]).resolve(); metric = sys.argv[2]; company_id, report_end = sys.argv[3].rsplit(":", 1)
sys.path.insert(0, str(repo / "scripts"))
reads = set()
def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, Path)):
        try:
            p = Path(args[0]).resolve()
        except Exception:
            return
        if repo in p.parents and ".git" not in p.parts and "__pycache__" not in p.parts:
            reads.add(str(p.relative_to(repo)))
sys.addaudithook(hook)
from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
from vnext.continuous_semantic_calls import request_body
from vnext.normal_period_selection import resolve_period_selection
FIELDS = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
          "region": "provider-managed-no-residency-guarantee",
          "retention": "provider-managed; no zero-retention claim",
          "data_use": "provider-managed; no training or data-use guarantee",
          "timeout_seconds": 120, "retry_count": 0, "maximum_payload_bytes": 8388608,
          "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}
policy = TransportPolicy.from_mapping(value={**FIELDS, "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
selection = resolve_period_selection(repo_root=repo, company_id=company_id, report_end=report_end)
if metric == "D04":
    from vnext.historical_semantic_results import pinned_native_source, pinned_requests
    source = pinned_native_source(repo_root=repo, company_id=company_id, metric_id="D04", period_selection=selection)
    requests = list(pinned_requests(source)); ids = {"source_id": source["semantic_source_id"]}
elif metric == "E01":
    from vnext.historical_zero_ai_results import e01_confirmation_request
    request, _ = e01_confirmation_request(repo_root=repo, company_id=company_id, period_selection=selection)
    requests = [request]; ids = {"source_id": request["source_id"]}
elif metric == "D02":
    from vnext.historical_text_input import d02_review_request
    request, _ = d02_review_request(repo_root=repo, company_id=company_id, period_selection=selection)
    requests = [request]; ids = {}
ids["request_ids"] = [r["request_id"] for r in requests]
ids["body_digests"] = ["sha256:" + hashlib.sha256(request_body(r, policy)).hexdigest() for r in requests]
modules = sorted(str(Path(m.__file__).resolve().relative_to(repo)) for m in list(sys.modules.values())
                 if getattr(m, "__file__", None) and repo in Path(m.__file__).resolve().parents)
data = sorted(r for r in reads if not r.startswith("evidence/") and not r.endswith(".py"))
print(json.dumps({"ids": ids, "modules": modules, "data_reads": data}))
