#!/usr/bin/env python3
"""Read-only census of complete D04/B13/D03 request envelopes and obligations.

No plans are authorized, no ledgers are changed, and no provider or SEC client
is opened. Results are preparation evidence, not business acceptance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.canonical import sha256_file, content_hash
from vnext.continuous_request_context import FORMAT_VERSION, measure_request
from vnext.continuous_semantic_calls import request_body
from vnext.normal_annual_input import _registry_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--company', action='append')
    parser.add_argument('--metric', action='append', choices=['D04', 'B13', 'D03'])
    parser.add_argument('--complete-response-contract', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output == ROOT or ROOT in output.parents:
        parser.error('Output must be a new file outside the source checkout')
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    metrics = args.metric or ['D04', 'B13', 'D03']
    for entry in _registry_rows(repo_root=ROOT):
        company = entry['company_id']
        if args.company and company not in args.company:
            continue
        for metric in metrics:
            if metric == 'B13' and company not in {'ford_motor_company', 'enphase_energy'}:
                rows.append({'company_id': company, 'metric_id': metric, 'status': 'N_A_STRUCTURAL',
                             'requests': [], 'utilization_calculated': False})
                continue
            try:
                if metric == 'D04':
                    from vnext.r6_semantic_source import prepare_d04_semantic_source
                    from vnext.d04_native_assessment import native_source, requests_from_source, source_statement_relations
                    original = prepare_d04_semantic_source(repo_root=ROOT, company_id=company)
                    old = native_source(original)
                    old_count = len(requests_from_source(old))
                    source = native_source(original, request_context_format=FORMAT_VERSION,
                        complete_response_contract=args.complete_response_contract)
                elif metric == 'B13':
                    from vnext.capacity_semantic_source import prepare_capacity_semantic_source
                    from vnext.capacity_semantic_review import requests_from_source
                    source = prepare_capacity_semantic_source(repo_root=ROOT, company_id=company,
                                                              request_context_format=FORMAT_VERSION)
                    old = {k: v for k, v in source.items() if k not in {'request_context_format', 'semantic_source_id'}}
                    old_count = len(requests_from_source({**old, 'semantic_source_id': content_hash(value=old)}))
                else:
                    from vnext.r6_regulatory_semantics import prepare_regulatory_semantic_source, requests_from_source
                    source = prepare_regulatory_semantic_source(repo_root=ROOT, company_id=company,
                                                                request_context_format=FORMAT_VERSION)
                    old = {k: v for k, v in source.items() if k not in {'request_context_format', 'semantic_source_id'}}
                    old_count = len(requests_from_source({**old, 'semantic_source_id': content_hash(value=old)}))
                requests = requests_from_source(source)
                sources = {u['unit_id']: u for u in source['units']}
                documents = {d['document_id']: d for d in source['documents']}
                measured = []
                from vnext.r6_semantic_review import _source_items
                for request in requests:
                    body = request_body(request, SimpleNamespace(model='deepseek-flash'))
                    result = measure_request(body, require_reference=True)
                    relations = []
                    if metric == 'D04':
                        for packed in request['units']:
                            unit = sources[packed['unit_id']]
                            _, items = _source_items(unit)
                            names = documents[unit['document_id']]['registrant_name_binding']['accepted_source_names']
                            for item in items.values():
                                relations.extend(source_statement_relations(
                                    text=item.get('text', item.get('raw_xml', '')), names=names,
                                    period=request['target_period'], quoted=item.get('html_quotation_context', False)))
                    measured.append({**result, 'request_id': request['request_id'],
                        'document_id': request['document_context']['document_id'],
                        'unit_ids': [u['unit_id'] for u in request['units']],
                        'unit_kinds': dict(Counter(u['kind'] for u in request['units'])),
                        'required_source_units': len(request['units']),
                        'required_candidates': len(request['required_candidate_assessments']),
                        'native_quantity_role_assessments': len(request.get('native_capacity_role_assessments', [])),
                        'bounded_statement_relations': len(relations),
                        'relation_kinds': dict(Counter(r['kind'] or 'UNRESOLVED' for r in relations)),
                        'd03_source_statement_facts': len(request.get('source_statement_facts', [])),
                        'proposals_requiring_separate_verification': metric == 'D03'})
                row = {'company_id': company, 'metric_id': metric, 'status': 'REQUESTS_MEASURED',
                       'source_id': source['semantic_source_id'], 'source_period': source['prepared_annual_input']['table_input']['target_period'],
                       'request_context_format': source.get('request_context_format'),
                       'old_byte_groups': old_count, 'requests': measured,
                       'full_source_unit_order_preserved': [u['unit_id'] for r in requests for u in r['units']] == source['required_unit_ids'],
                       'business_result_completed': False}
            except (ValueError, KeyError) as error:
                row = {'company_id': company, 'metric_id': metric, 'status': 'PREPARATION_FAILED',
                       'error_type': type(error).__name__, 'reason': str(error), 'requests': []}
            rows.append(row)
            print(company, metric, row['status'], len(row['requests']), row.get('reason', ''), flush=True)
            # This checkpoint is only this run's own new measurement artifact.
            output.write_text(json.dumps({'format_version': FORMAT_VERSION, 'rows': rows,
                'new_provider_paid_sec_calls': [0, 0, 0], 'business_acceptance': False,
                'counter_implementation_sha256': sha256_file(path=ROOT / 'scripts/vnext/continuous_request_context.py')},
                ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
