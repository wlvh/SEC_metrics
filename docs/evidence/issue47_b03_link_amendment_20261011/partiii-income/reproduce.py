"""Read the existing Part III source and income property, without new calls.

The actual company CLI failure is recorded separately. This reproducer does
not calculate a value or turn an amendment declaration into financial credit.
"""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.instant_balance_amendment import _correction_flag
from vnext.normal_governance_input import _Sources
from vnext.normal_period_selection import resolve_period_selection
from vnext.ordinary_income_input import inspect_income_amendment
from vnext.normal_source_authority import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--company', required=True)
    parser.add_argument('--fiscal-year', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with patch('socket.socket.connect', side_effect=AssertionError('NETWORK_FORBIDDEN')):
        selection = resolve_period_selection(repo_root=args.source_root,
            company_id=args.company, fiscal_year=args.fiscal_year)
        prepared = prepare_historical_annual_input(repo_root=args.source_root,
            company_id=args.company, period_selection=selection)
        reader = _Sources(args.source_root, args.company, prepared['entity'])
        original = reader.primary(prepared['filing'])
        report = {'company':args.company, 'fiscal_year':args.fiscal_year,
                  'filing':prepared['filing'], 'checks':[], 'new_calls':[0,0,0]}
        for filing in prepared['amendments']:
            amendment = reader.primary(filing)
            source = lambda item, identity: {'raw':item['raw_bytes'],
                'blob':item['raw_blob'], 'reference':item['source_reference'], 'filing':identity}
            scope = inspect_annual_amendment_scope(original=source(original,prepared['filing']),
                amendment=source(amendment,filing), company_id=args.company,
                cik=prepared['entity'], note_layout='inline-paragraphs-v2')
            check = {key:scope[key] for key in ('scope_id','classification','issues',
                'fiscal_window_unchanged','unchanged_input_classes',
                'original_statement_admission_requires_further_review','explanatory_note')}
            check['source_references'] = [original['source_reference'], amendment['source_reference']]
            try:
                check['explicit_false_correction_flag'] = _correction_flag(amendment['raw_bytes'],scope)
                rules = json.loads((ROOT/'config/ordinary_income_input_v1.json').read_text())
                check['income_property'] = inspect_income_amendment(scope,amendment['raw_bytes'],rules)
            except ValueError as error:
                check['refusal'] = {'reason':str(error), 'error_type':type(error).__name__}
            report['checks'].append(check)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2,default=dict)
        stream.write('\n')
    print(json.dumps([{'classification':c['classification'], 'refusal':c.get('refusal')}
                      for c in report['checks']]))


if __name__ == '__main__':
    main()
