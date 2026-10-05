"""Main foundation audit using reviewed syntax exceptions, not result values.

The old check_no_company_literals.py and sec_pipeline scanner stay byte-exact.
This explicit successor reuses the ordinary AST/source-hash checker. Publication
selects it only when the installed program carries this tool and its policy.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from sec_pipeline import SCALABILITY_AUDIT_FIELDNAMES, write_csv_file
from vnext.ordinary_scalability_audit import successor_scalability_snapshot

POLICY = 'config/main_scalability_exemptions_v1.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT/args.output
    rows = successor_scalability_snapshot(ROOT, policy_path=POLICY)
    write_csv_file(path=output, fieldnames=SCALABILITY_AUDIT_FIELDNAMES, rows=rows)
    failures = [r for r in rows if r['allowed'] != '1']
    print('Main source-aware scalability audit: '+('FAIL' if failures else 'PASS'))
    for row in failures[:20]:
        print(row['file']+':'+row['line']+' '+row['type']+' '+row['literal'])
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
