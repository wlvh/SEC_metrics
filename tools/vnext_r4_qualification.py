"""Operate the frozen R4 seam; live execution needs real exact-head owner evidence.

``draft`` is PR-B offline shape evidence. ``plan``/``execute`` are future PR-C
entrypoints, not enabled by producing a draft. Neither publishes or acquires
SEC data. Recorded transports are test-only Python capabilities, never a CLI
switch that can relabel synthetic evidence into live qualification.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from vnext.canonical import strict_json_file  # noqa: E402
from vnext.invocation_control import _exclusive_write_json  # noqa: E402
from vnext.r4_live_authority import (  # noqa: E402
    RUNTIME_ROOT, build_r4_pending_live_plan, prepare_r4_execution_context,
    verify_r4_live_owner_comment,
)
from vnext.r4_live_plan import build_r4_draft_plan  # noqa: E402
from vnext.r4_label_policy import CURRENT_R4_REQUIREMENT  # noqa: E402
from vnext.r4_live_qualification import execute_r4_qualification, replay_r4_qualification  # noqa: E402


def _plan_path(identity):
    if (type(identity) is not str or not identity.startswith("sha256:") or len(identity) != 71
            or any(c not in "0123456789abcdef" for c in identity[7:])):
        raise ValueError("An exact content-addressed R4 pending plan ID is required")
    return REPO_ROOT / RUNTIME_ROOT / "plans" / (identity[7:] + ".json")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("draft", help="Print verified 9 + 3 offline call-shape evidence, never a live plan")
    sub.add_parser("plan", help="Future PR-C: create a distinct pending-live plan on clean committed code")
    execute = sub.add_parser("execute", help="Future PR-C: exact-head verified owner comment is mandatory")
    execute.add_argument("--plan-id", required=True)
    execute.add_argument("--owner-comment-url", required=True)
    replay = sub.add_parser("replay", help="Independent disk replay and append-only replay receipt; no network")
    replay.add_argument("--plan-id", required=True)
    sub.add_parser("diagnostic-plan", help="Prepare the approved nine development requests; no qualification credit")
    sub.add_parser("selection-draft", help="Build nine short-cell request artifacts for a NEW authorization; never execute")
    diagnostic = sub.add_parser("diagnostic-execute", help="Run the approved diagnostic through the existing one-shot controller")
    diagnostic.add_argument("--plan-id", required=True)
    diagnostic.add_argument("--owner-comment-url", required=True)
    diagnostic_replay = sub.add_parser("diagnostic-replay", help="Rebuild diagnostic terminals from disk; no provider/SEC")
    diagnostic_replay.add_argument("--plan-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'selection-draft':
            from vnext.r4_development import diagnostic_implementation, prepare_diagnostic_context, RUNTIME_ROOT as diagnostic_root
            from vnext.cell_selection import REVISION
            from vnext.canonical import content_hash
            from vnext.invocation_control import _exclusive_write_bytes
            with diagnostic_implementation(REPO_ROOT, offline_interface_revision=REVISION):
                context=prepare_diagnostic_context(REPO_ROOT)
                entries=[]
                for source in context._session._development.scope['entries']:
                    request=context._requests[source['fixture_id']];identity=request.identity
                    entries.append({'fixture_id':source['fixture_id'],'period':identity['task_period'],
                        'source_sha256':identity['source_sha256'],'source_scope_manifest_id':identity['source_scope_manifest_id'],
                        'request_sha256':identity['provider_request_body_sha256'],
                        'request_bytes':identity['provider_request_body_size'],
                        'output_schema_sha256':identity['provider_output_schema_sha256']})
                body={'record_type':'R4_CELL_SELECTION_RETEST_PROPOSAL','authorization':'NOT_ISSUED',
                    'interface_revision':REVISION,'head':context._state['head'],'tree':context._state['tree'],
                    'request_set_id':content_hash(value=entries),'entries':entries,
                    'maximum_provider_calls_proposed':9,'automatic_retry_count':0,'response_reuse':False,
                    'SEC':False,'publication':False,'qualification_credit':'NONE','execution_eligible':False,
                    'continuation':'SEALED_INDEPENDENT_CONTENT_FAILURE_ONLY_OTHER_FAILURES_STOP'}
                result={**body,'proposal_id':content_hash(value=body)}
                directory=REPO_ROOT/diagnostic_root/'selection_proposals'/result['proposal_id'][7:]
                _exclusive_write_json(path=directory/'proposal.json',value=result)
                for entry in entries:
                    _exclusive_write_bytes(path=directory/(entry['fixture_id']+'.request.json'),
                        content=context._requests[entry['fixture_id']].provider_request_body_bytes)
        elif args.command.startswith('diagnostic-'):
            from vnext.r4_development import diagnostic_implementation, prepare_diagnostic_context
            from vnext.r4_development import build_diagnostic_plan, execute_diagnostic, replay_diagnostic
            from vnext.r4_development import RUNTIME_ROOT as diagnostic_root
            with diagnostic_implementation(REPO_ROOT):
                context = prepare_diagnostic_context(REPO_ROOT)
                if args.command == 'diagnostic-plan':
                    result = build_diagnostic_plan(context)
                    _exclusive_write_json(path=REPO_ROOT / diagnostic_root / 'plans' / (result['pending_plan_id'][7:]+'.json'), value=result)
                else:
                    _plan_path(args.plan_id)  # Same strict content-ID syntax.
                    path = REPO_ROOT / diagnostic_root / 'plans' / (args.plan_id[7:]+'.json')
                    if path.is_symlink() or not path.is_file():
                        raise ValueError('Diagnostic plan is missing or unsafe')
                    plan = strict_json_file(path=path)
                    if plan.get('pending_plan_id') != args.plan_id:
                        raise ValueError('Diagnostic plan path/content differ')
                    if args.command == 'diagnostic-execute':
                        owner = verify_r4_live_owner_comment(context=context, plan=plan, source_url=args.owner_comment_url)
                        _exclusive_write_json(path=REPO_ROOT / diagnostic_root / 'authorizations'
                            / (owner.receipt['receipt_id'][7:]+'.json'), value=owner.receipt)
                        result = execute_diagnostic(context=context, plan=plan, owner=owner)
                    else:
                        result = replay_diagnostic(context, plan)
                        from vnext.canonical import content_hash
                        _exclusive_write_json(path=REPO_ROOT / diagnostic_root / 'replays'
                            / (content_hash(value=result)[7:]+'.json'), value=result)
        elif args.command == "draft":
            result = build_r4_draft_plan(repo_root=REPO_ROOT, requirement_id=CURRENT_R4_REQUIREMENT)
        elif args.command == "plan":
            result = build_r4_pending_live_plan(repo_root=REPO_ROOT)
            _exclusive_write_json(path=_plan_path(result["pending_plan_id"]), value=result)
        else:
            path = _plan_path(args.plan_id)
            if path.is_symlink() or not path.is_file():
                raise ValueError("The repository pending plan is missing or unsafe")
            plan = strict_json_file(path=path)
            if plan.get("pending_plan_id") != args.plan_id:
                raise ValueError("Pending plan path and content ID differ")
            context = prepare_r4_execution_context(repo_root=REPO_ROOT, requirement_id=plan["requirement_id"])
            if args.command == "execute":
                owner = verify_r4_live_owner_comment(context=context, plan=plan, source_url=args.owner_comment_url)
                _exclusive_write_json(path=REPO_ROOT / RUNTIME_ROOT / "authorizations"
                    / (owner.receipt["receipt_id"][7:] + ".json"), value=owner.receipt)
                result = execute_r4_qualification(repo_root=REPO_ROOT, plan=plan, owner_comment=owner, context=context)
            else:
                result = replay_r4_qualification(repo_root=REPO_ROOT, plan=plan, context=context)
                replay_path = REPO_ROOT / RUNTIME_ROOT / "replays" / (result["replay_id"][7:] + ".json")
                if replay_path.exists():
                    if replay_path.is_symlink() or strict_json_file(path=replay_path) != result:
                        raise ValueError("Existing R4 replay receipt has divergent bytes")
                else:
                    _exclusive_write_json(path=replay_path, value=result)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 1 if result.get('status') == 'STOPPED' else 0


if __name__ == "__main__":
    raise SystemExit(main())
