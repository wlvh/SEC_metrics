"""Frozen PR-C R4 release entrypoints. No provider or SEC caller exists here.

All writes require the native release factory. Pointer mutations additionally
read a real exact-head release-owner comment. There is no CLI rehearsal or
recorded-transport bypass; those capabilities exist only for isolated tests.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / 'scripts'))

from vnext.canonical import strict_json_loads  # noqa: E402
from vnext.r4_release import prepare_r4_release_context  # noqa: E402
from vnext.r4_publication import active_terminal, stage_r4_release, validate_r4_release  # noqa: E402
from vnext.r4_publication import switch_r4_release, verify_release_owner_comment, _pinned  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    stage = sub.add_parser('stage', help='Verify live aggregate/activation/merge; stage without switching R3')
    stage.add_argument('--plan-id', required=True)
    stage.add_argument('--replay-id', required=True)
    stage.add_argument('--implementation-merge', required=True)
    for name in ('validate', 'read-back', 'active-terminal', 'publish', 'rollback-to-R3', 'restore-R4', 'recover-mirrors'):
        command = sub.add_parser(name)
        command.add_argument('--publication-id', required=True)
        if name in {'publish', 'rollback-to-R3', 'restore-R4', 'recover-mirrors'}:
            command.add_argument('--owner-comment-url', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'stage':
            context = prepare_r4_release_context(repo_root=REPO_ROOT, plan_id=args.plan_id,
                replay_id=args.replay_id, implementation_commit=args.implementation_merge)
            staged = stage_r4_release(context=context)
            result = {'manifest': staged['manifest'], 'release_receipt': staged['receipt'], 'active_changed': False}
        else:
            pin = validate_r4_release(publication_root=REPO_ROOT, publication_id=args.publication_id)
            if args.command in {'validate', 'read-back'}:
                result = {'status': 'PASS', 'manifest': strict_json_loads(text=pin.manifest.decode()),
                          'release_receipt': pin.receipt, 'provider_paid_sec_calls': [0, 0, 0]}
            elif args.command == 'active-terminal':
                result = active_terminal(publication_root=REPO_ROOT, pin=pin,
                                         expected_publication_id=args.publication_id)
            else:
                owner = verify_release_owner_comment(publication_root=REPO_ROOT, pin=pin,
                                                       source_url=args.owner_comment_url)
                result = switch_r4_release(authority=owner, operation=args.command,
                    committed_at_utc=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'BLOCKED', 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
