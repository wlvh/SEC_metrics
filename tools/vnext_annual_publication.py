#!/usr/bin/env python3
"""Prepare and read complete isolated annual versions; actual R3 is protected."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from vnext import annual_publication as annual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--candidate-dir', type=Path, required=True)
    prepare.add_argument('--publication-root', type=Path, required=True)
    read = commands.add_parser('read')
    read.add_argument('--publication-root', type=Path, required=True)
    switch = commands.add_parser('switch')
    switch.add_argument('--publication-root', type=Path, required=True)
    switch.add_argument('--publication-id', required=True)
    switch.add_argument('--operation', choices=['publish', 'rollback', 'restore', 'recover'], required=True)
    for p in (prepare, read, switch):
        p.add_argument('--output-json', type=Path, required=True)
    args = parser.parse_args()
    output = annual.safe_root(args.output_json)
    if output.exists():
        parser.error('Output exists; select a new evidence filename')
    try:
        if args.command == 'prepare':
            result = annual.prepare(candidate_dir=args.candidate_dir, publication_root=args.publication_root)
        elif args.command == 'read':
            result = annual.read_version(publication_root=args.publication_root)
        else:
            result = annual.switch(publication_root=args.publication_root, publication_id=args.publication_id, operation=args.operation)
        code = 0
    except (ValueError, OSError, RuntimeError) as error:
        result = {'status': 'BLOCKED', 'error': str(error), 'error_type': type(error).__name__,
                  'new_provider_paid_sec_calls': [0, 0, 0], 'formal_publication_authorized': False}
        code = 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code

if __name__ == '__main__':
    raise SystemExit(main())
