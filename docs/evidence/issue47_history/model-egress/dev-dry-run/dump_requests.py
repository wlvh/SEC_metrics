"""Write the exact messages each E01 and D02 request would send, for a development dry run.

Section 5.8 of #28 (adopted by #47's body, 2026-10-03) asks for a development
model's answer to the real input package before any paid call: a fresh context
gets only what DeepSeek would get, and its answer goes through the contract's
own checks. This writes that input. Each request is built by the route
(``e01_confirmation_request``, ``d02_review_request``), its provider body by
``request_body`` under the fixed transport, and the messages are read back out
of the body bytes - so what a dry-run context sees is what the provider would
receive, not a re-rendering. The ledger digest must equal the one the request
measurement recorded; a request that changed since is refused, not dumped.

Usage (from a #47 runtime tree at the sealed commit):
    python3 <this file> <output dir> [E01,D02,D04]   (default E01,D02)

Each request gets <name>.request.json, <name>.messages.json and <name>.txt, the
one file its dry-run context is told to read (``render_input``);
``inputs-index.json`` records the digests of the 19 files read on 2026-10-03.

Zero calls.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "scripts"))
E01_MEASUREMENT = REPO / "docs/evidence/issue47_history/e01-content-confirmed/request-measurement.json"
D02_MEASUREMENT = REPO / "docs/evidence/issue47_history/d02-item-8-review/request-measurement.json"
D04_MEASUREMENT = REPO / "docs/evidence/issue47_history/model-egress/d04-request-measurement.json"
TRANSPORT_FIELDS = {"provider": "deepseek", "model": "deepseek-flash", "api": "chat_completions",
                    "region": "provider-managed-no-residency-guarantee",
                    "retention": "provider-managed; no zero-retention claim",
                    "data_use": "provider-managed; no training or data-use guarantee",
                    "timeout_seconds": 120, "retry_count": 0, "maximum_payload_bytes": 8388608,
                    "filing_egress_policy": "PUBLIC_SEC_FILING_CONTENT_ONLY"}


READING_NOTE = ("(The user message is one JSON object. It is shown here with indentation for "
                "reading; every key and string value is exactly as sent.)")


def render_input(messages):
    """The one file a dry-run context reads: the system prompt, then the user message.

    The user message is shown indented with sorted keys so a reader can page
    through it; every key and string value is the sent one, which
    ``check_answers.py`` relies on when it holds quotes to the request's texts.
    """
    roles = [message["role"] for message in messages]
    if roles != ["system", "user"]:
        raise SystemExit("UNEXPECTED_MESSAGE_ROLES: " + ",".join(roles))
    user = json.dumps(json.loads(messages[1]["content"]), ensure_ascii=False, indent=1, sort_keys=True)
    return ("SYSTEM PROMPT\n=============\n" + messages[0]["content"] + "\n\nUSER MESSAGE\n"
            "============\n" + READING_NOTE + "\n\n" + user + "\n")


def _requests(metrics):
    """Each measured request, rebuilt by its route, with the digest it was measured at."""
    from vnext.historical_semantic_results import pinned_native_source, pinned_requests
    from vnext.historical_text_input import d02_review_request
    from vnext.historical_zero_ai_results import e01_confirmation_request
    from vnext.normal_period_selection import resolve_period_selection
    measured = []
    if "E01" in metrics:
        measured += [("E01", w["company_id"], w["report_end"], [w["ledger_digest"]])
                     for w in json.loads(E01_MEASUREMENT.read_text())["windows"] if "ledger_digest" in w]
    if "D02" in metrics:
        measured += [("D02", p["company_id"], p["report_end"], [p["ledger_digest"]])
                     for p in json.loads(D02_MEASUREMENT.read_text())["positions"]]
    if "D04" in metrics:
        for position, row in json.loads(D04_MEASUREMENT.read_text())["positions"].items():
            company_id, report_end = position.rsplit(":", 1)
            measured.append(("D04", company_id, report_end, [r["ledger_digest"] for r in row["requests"]]))
    for metric, company_id, report_end, recorded in sorted(measured):
        selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                             report_end=report_end)
        if metric == "D04":
            source = pinned_native_source(repo_root=REPO, company_id=company_id, metric_id="D04",
                                          period_selection=selection)
            built = list(pinned_requests(source))
        else:
            build = e01_confirmation_request if metric == "E01" else d02_review_request
            built = [build(repo_root=REPO, company_id=company_id, period_selection=selection)[0]]
        if len(built) != len(recorded):
            raise SystemExit("REQUEST_COUNT_CHANGED_SINCE_MEASURED: %s %s %s" % (metric, company_id, report_end))
        for number, (request, digest) in enumerate(zip(built, recorded), start=1):
            name = "%s-%s-%s" % (metric, company_id, report_end)
            yield (name if metric != "D04" else name + "-r%d" % number), metric, company_id, report_end, request, digest


def main(out, metrics=("E01", "D02")):
    from vnext.ai_adapter import _DEEPSEEK_ENDPOINT_HOST, TransportPolicy
    from vnext.continuous_semantic_calls import request_body
    from vnext.historical_model_calls import ledger_digest
    policy = TransportPolicy.from_mapping(value={**TRANSPORT_FIELDS,
                                                 "endpoint_host": _DEEPSEEK_ENDPOINT_HOST})
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    index = []
    for name, metric, company_id, report_end, request, recorded in _requests(set(metrics)):
        digest = ledger_digest(request, policy)
        if digest != recorded:
            raise SystemExit("REQUEST_CHANGED_SINCE_MEASURED: " + name)
        body = request_body(request, policy)
        sent = json.loads(body.decode("utf-8"))
        (out / (name + ".request.json")).write_text(json.dumps(request, ensure_ascii=False) + "\n")
        (out / (name + ".messages.json")).write_text(
            json.dumps(sent["messages"], ensure_ascii=False, indent=1) + "\n")
        (out / (name + ".txt")).write_text(render_input(sent["messages"]))
        index.append({"metric": metric, "company_id": company_id, "report_end": report_end,
                      "ledger_digest": digest, "provider_body_sha256": hashlib.sha256(body).hexdigest(),
                      "sent_fields": sorted(k for k in sent if k != "messages"),
                      "max_tokens": sent.get("max_tokens"), "file": name})
        print(name, digest[:19], flush=True)
    (out / "index.json").write_text(json.dumps(index, indent=1) + "\n")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    main(sys.argv[1], *(() if len(sys.argv) == 2 else (sys.argv[2].split(","),)))
