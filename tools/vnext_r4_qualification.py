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
    args = parser.parse_args(argv)
    try:
        if args.command == "draft":
            result = build_r4_draft_plan(repo_root=REPO_ROOT)
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
            context = prepare_r4_execution_context(repo_root=REPO_ROOT)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
