"""Fetch only the two approved fixture filings through the native SEC client.

Default invocation is preflight-only. Each filing has one request, no automatic
retry, no alternate endpoint, and no credit for archived responses. A prior
attempt (including failure) prevents this command from repeating that source.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from sec_http import SecHttpClient, load_config  # noqa: E402
from sec_http import parse_request_log_rows, request_log_attempt_id  # noqa: E402
from sec_http import validate_request_log_manifest  # noqa: E402
from sec_urls import accession_document_url  # noqa: E402
from vnext.canonical import content_hash, sha256_bytes, strict_json_file  # noqa: E402


def preflight(*, repo_root: Path) -> dict:
    """Validate owner policy, exact planned source set, identity and ledger."""
    evidence = strict_json_file(
        path=repo_root / "docs/evidence/issue_28_prb_policy_revision.json",
    )
    if sha256_bytes(content=evidence["raw_body"].encode()) != evidence["body_sha256"]:
        raise ValueError("Owner policy body hash differs")
    policy = json.loads(evidence["raw_body"])
    plan = strict_json_file(path=repo_root / "config/r4_fixture_acquisitions_v1.json")
    if (
        policy["decision"] != "APPROVE_R4_PRB_POLICY_REVISION"
        or policy["scope"] != "PR_B_OFFLINE_IMPLEMENTATION_ONLY"
        or not policy["sec_acquisition"]["existing_two_filing_quota_may_proceed"]
        or policy["sec_acquisition"]["automatic_retry_count"] != 0
        or plan["maximum_new_filings"] != 2
        or plan["automatic_retry_count"] != 0
        or len(plan["sources"]) != 2
        or [s["source_id"] for s in plan["sources"]]
        != policy["sec_acquisition"]["sources"]
        or policy["provider_calls_authorized"]
        or policy["paid_model_calls_authorized"]
    ):
        raise ValueError("Fixture acquisition authority differs")
    # This is exactly the same validator the acquisition client calls, using
    # config fallback without injecting or printing a process credential.
    load_config(config_path=repo_root / "config/sec_config.json")
    log = repo_root / "evidence/requests_log.csv"
    validate_request_log_manifest(log_path=log)
    rows = parse_request_log_rows(text=log.read_text(encoding="utf-8"))
    inventory = strict_json_file(path=repo_root / "docs/r4_offline/source_inventory.json")
    for source in plan["sources"]:
        prior = next(r for r in inventory["issuer_inventory"] if r["cik"] == source["cik"])
        if prior["immutable_sources"]:
            raise ValueError("Existing-source insufficiency is not demonstrated")
        source["source_url"] = accession_document_url(
            cik=int(source["cik"]), accession=source["accession"],
            document_name=source["document_name"],
        )
    return {"sources": plan["sources"], "rows": rows,
            "owner_comment_url": evidence["owner_comment_url"],
            "policy_body_sha256": evidence["body_sha256"]}


def acquire(*, repo_root: Path) -> list[dict]:
    """Execute each never-attempted approved filing once; stop on any failure."""
    state = preflight(repo_root=repo_root)
    log = repo_root / "evidence/requests_log.csv"
    initial_bytes = log.read_bytes()
    client = SecHttpClient(
        workdir=repo_root, config_path=repo_root / "config/sec_config.json",
        log_path=log,
    )
    client.config["max_retries"] = 0
    results = []
    for source in state["sources"]:
        # Never reissue an existing URL, even if an earlier response failed.
        rows = parse_request_log_rows(text=log.read_text(encoding="utf-8"))
        existing = [r for r in rows if r["source_url"] == source["source_url"]]
        if existing:
            raise ValueError("Planned source already has a terminal attempt")
        result = client.fetch(
            url=source["source_url"],
            purpose="R4_OFFLINE_FIXTURE_ONLY:" + source["source_id"],
            local_path=repo_root / "evidence/r4_fixture_inputs"
            / source["source_id"] / source["document_name"],
        )
        validate_request_log_manifest(log_path=log)
        after = log.read_bytes()
        terminal_rows = parse_request_log_rows(text=after.decode("utf-8"))
        if not after.startswith(initial_bytes) or len(terminal_rows) != len(rows) + 1:
            raise ValueError("Acquisition ledger prefix/count differs")
        row = terminal_rows[-1]
        if row["retry_attempt"] != "0" or row["source_url"] != source["source_url"]:
            raise ValueError("Native acquisition attempt differs")
        record = {**source, "status_code": result.status_code,
                  "request_attempt_id": request_log_attempt_id(row_index=len(rows), row=row),
                  "source_repo_relative_path": row["repo_relative_path"],
                  "headers_repo_relative_path": row["headers_repo_relative_path"],
                  "source_sha256": row["content_sha256"],
                  "source_size": int(row["content_length"]),
                  "retry_attempt": 0, "qualification_credit": "NONE_OFFLINE_SOURCE_ONLY"}
        results.append(record)
        print(json.dumps(record, sort_keys=True), flush=True)
        if result.status_code != 200:
            raise RuntimeError("SEC fixture acquisition failed; no retry is authorized")
    print(json.dumps({"status": "PASSED", "provider_paid_sec": [0, 0, len(results)],
                      "acquisition_result_id": content_hash(value=results)}), flush=True)
    return results


def main() -> None:
    """Expose a default no-egress preflight and an explicit bounded execute."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.execute:
        acquire(repo_root=REPO_ROOT)
    else:
        state = preflight(repo_root=REPO_ROOT)
        print(json.dumps({"status": "PREFLIGHT_PASSED", "planned_sources": len(state["sources"]),
                          "provider_paid_sec": [0, 0, 0]}))


if __name__ == "__main__":
    main()
