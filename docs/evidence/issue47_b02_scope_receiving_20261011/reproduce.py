"""Read one saved original through the actual historical B02 consumer.

This is a developer reproducer, not a revenue selector or financial reference.
It never changes the source root, calls a provider, or creates a company task.
Use the company CLI separately for fresh/save/repeat/results validation.
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from vnext.historical_statement_cases import prepare_historical_statement_year_case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--company', required=True)
    parser.add_argument('--fiscal-year', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        case = prepare_historical_statement_year_case(repo_root=args.source_root,
            company_id=args.company, metric_id='B02', fiscal_year=args.fiscal_year)
    assessment = case.get('input_assessments', {}).get('historical_statement', {})
    result = case['results']['B02']
    report = {'company': args.company, 'fiscal_year': args.fiscal_year,
        'filing': case['prepared_annual_input']['filing'],
        'target_period': case['target_period'], 'result': result,
        'assessment': assessment, 'selection': case.get('selection'),
        'source_proofs': case['source_proofs'], 'new_calls': [0, 0, 0]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'result_id': result['result_id'], 'value': result['value'],
        'reason': assessment.get('reason'),
        'unresolved_revenue_role': assessment.get('unresolved_revenue_role')}))


if __name__ == '__main__':
    main()
