"""One D04 pinned source: its semantic source id, request ledger digests, and the loaded scripts modules."""
import hashlib, json, sys
from pathlib import Path
repo = Path(sys.argv[1]).resolve(); company_id, report_end = sys.argv[2].rsplit(":", 1)
sys.path.insert(0, str(repo / "scripts"))
from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
from vnext.continuous_semantic_calls import request_body
from vnext.historical_semantic_results import pinned_native_source, pinned_requests
from vnext.normal_period_selection import resolve_period_selection
FIELDS = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
          "region": "provider-managed-no-residency-guarantee",
          "retention": "provider-managed; no zero-retention claim",
          "data_use": "provider-managed; no training or data-use guarantee",
          "timeout_seconds": 120, "retry_count": 0, "maximum_payload_bytes": 8388608,
          "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}
policy = TransportPolicy.from_mapping(value={**FIELDS, "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
selection = resolve_period_selection(repo_root=repo, company_id=company_id, report_end=report_end)
source = pinned_native_source(repo_root=repo, company_id=company_id, metric_id="D04", period_selection=selection)
digests = ["sha256:" + hashlib.sha256(request_body(r, policy)).hexdigest() for r in pinned_requests(source)]
modules = sorted(str(Path(m.__file__).resolve().relative_to(repo)) for m in list(sys.modules.values())
                 if getattr(m, "__file__", None) and repo in Path(m.__file__).resolve().parents)
print(json.dumps({"semantic_source_id": source["semantic_source_id"], "digests": digests, "modules": modules}))
