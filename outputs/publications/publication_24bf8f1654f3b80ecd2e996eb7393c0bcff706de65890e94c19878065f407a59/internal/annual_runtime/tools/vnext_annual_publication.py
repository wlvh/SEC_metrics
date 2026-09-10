#!/usr/bin/env python3
"""Prepare and read complete isolated annual versions; actual R3 is protected."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from vnext import annual_publication as annual
from vnext import annual_publication_authority as authority
from vnext.annual_adoption_policy import POLICIES, V1
from vnext.canonical import strict_json_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--candidate-dir', type=Path, required=True)
    prepare.add_argument('--publication-root', type=Path, required=True)
    prepare.add_argument('--policy-id', choices=sorted(POLICIES), default=V1)
    read = commands.add_parser('read')
    read.add_argument('--publication-root', type=Path, required=True)
    read.add_argument('--publication-id')
    switch = commands.add_parser('switch')
    switch.add_argument('--publication-root', type=Path, required=True)
    switch.add_argument('--publication-id', required=True)
    switch.add_argument('--operation', choices=['publish', 'rollback', 'restore', 'recover'], required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('--bundle-dir', type=Path, required=True)
    plan.add_argument('--target-root', type=Path, required=True)
    plan.add_argument('--pull-number', type=int, required=True)
    template = commands.add_parser('approval-template')
    template.add_argument('--plan', type=Path, required=True)
    activate = commands.add_parser('activate')
    activate.add_argument('--plan', type=Path, required=True)
    activate.add_argument('--activation-url', required=True)
    release = commands.add_parser('release')
    release.add_argument('--plan', type=Path, required=True)
    release.add_argument('--activation-url', required=True)
    release.add_argument('--owner-url', required=True)
    release.add_argument('--operation', choices=['deploy', 'publish', 'rollback', 'restore', 'recover'], required=True)
    for p in (prepare, read, switch, plan, template, activate, release):
        p.add_argument('--output-json', type=Path, required=True)
    args = parser.parse_args()
    output = annual.safe_root(args.output_json)
    if output.exists():
        parser.error('Output exists; select a new evidence filename')
    try:
        if args.command == 'prepare':
            result = annual.prepare(candidate_dir=args.candidate_dir, publication_root=args.publication_root, policy_id=args.policy_id)
        elif args.command == 'read':
            result = annual.read_version(publication_root=args.publication_root, publication_id=args.publication_id)
        elif args.command == 'switch':
            result = annual.switch(publication_root=args.publication_root, publication_id=args.publication_id, operation=args.operation)
        elif args.command == 'plan':
            result = authority.plan_publication(bundle_dir=args.bundle_dir, target_root=args.target_root, pull_number=args.pull_number)
        else:
            planned = strict_json_file(path=args.plan)
            if args.command == 'approval-template':
                authority.validate_plan(planned)
                result = {'status': 'TEMPLATES_ONLY_NO_AUTHORITY', 'plan_id': planned['plan_id'],
                    'requirement_transition': authority.expected_activation_approval(planned),
                    'publication_decision': authority.expected_owner_approval(planned)}
            elif args.command == 'activate':
                result = authority.activate_requirement(plan=planned, activation_url=args.activation_url)
            else:
                permission = authority.verify_authorization(plan=planned, activation_url=args.activation_url, owner_url=args.owner_url)
                result = authority.deploy(permission=permission) if args.operation == 'deploy' else authority.execute(permission=permission, operation=args.operation)
        code = 0
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        result = {'status': 'BLOCKED', 'error': str(error), 'error_type': type(error).__name__,
                  'new_provider_paid_sec_calls': [0, 0, 0],
                  'production_effect': 'READ_CURRENT_STATE_AND_PENDING_INTENT' if args.command == 'release' else 'NOT_EXECUTED'}
        code = 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code

if __name__ == '__main__':
    raise SystemExit(main())
