#!/usr/bin/env python3
"""Generate or independently replay only the versioned R4 offline evidence set."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from vnext.r4_offline_qualification import build_offline_case, load_case_definitions
from vnext.r4_offline_qualification import prepare_source_bundle, replay_case_artifacts
from vnext.r4_offline_qualification import write_offline_case, write_offline_index
from vnext.requirements import load_requirement_snapshot
from vnext.r4_task_contracts import resolve_r4_task_contract
from vnext.evidence import prepare_offline_evidence_context
from vnext.reader_input import build_reader_payload
from vnext.canonical import canonical_json_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirement-id", default="issue_28_v2")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--fixture-id", action="append")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    requirement = load_requirement_snapshot(snapshot_dir=root / "requirements" / args.requirement_id)
    fixtures = load_case_definitions(repo_root=root)
    selected = fixtures if not args.fixture_id else [f for f in fixtures if f["fixture_id"] in args.fixture_id]
    if args.fixture_id and {f["fixture_id"] for f in selected} != set(args.fixture_id):
        parser.error("Unknown fixture ID")
    bundles, contexts, results = {}, {}, []
    for fixture in selected:
        source_id = fixture["source_id"]
        if source_id not in bundles:
            bundles[source_id] = prepare_source_bundle(repo_root=root, source_id=source_id)
        if args.write:
            if source_id not in contexts:
                task_ids = sorted({f["task_contract_id"] for f in selected if f["source_id"] == source_id})
                tasks = [resolve_r4_task_contract(repo_root=root, requirement=requirement,
                                                 task_contract_id=identity) for identity in task_ids]
                bundle = bundles[source_id]
                payload = build_reader_payload(manifest=bundle["reader_manifest"],
                    derived_asset=bundle["full_derived_asset"], task_contract=tasks[0])["body"]
                contexts[source_id] = prepare_offline_evidence_context(
                    repo_root=root, requirement=requirement, source_bytes=bundle["source_bytes"],
                    raw_blob=bundle["raw_blob"], source_reference=bundle["source_reference"],
                    derived_asset_bytes=canonical_json_bytes(value=bundle["full_derived_asset"]),
                    reader_manifest=bundle["reader_manifest"], full_table_transport=payload["untrusted_table_data"],
                    task_contracts=tasks, task_generation="R4_V2")
            result = build_offline_case(repo_root=root, requirement=requirement,
                fixture_id=fixture["fixture_id"], source_bundle=bundles[source_id],
                evidence_context=contexts[source_id])
            results.append(write_offline_case(repo_root=root, fixture=fixture, result=result))
            print(json.dumps(result["summary"], ensure_ascii=False), flush=True)
        else:
            summary = replay_case_artifacts(repo_root=root, requirement=requirement,
                fixture=fixture, source_bundle=bundles[source_id])
            results.append(summary)
            print(json.dumps(summary, ensure_ascii=False), flush=True)
    if args.write and not args.fixture_id:
        index = write_offline_index(repo_root=root, requirement=requirement, cases=results)
        print(json.dumps({"index_id": index["index_id"], "case_count": len(results)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
