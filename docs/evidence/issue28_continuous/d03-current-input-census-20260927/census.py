"""Offline D03 request census using the current saved #28 source and tokenizer.

No model or SEC request is sent. A count is an input/resource estimate, not
authorization, semantic acceptance, or a complete company result.
"""
import json
import time
from pathlib import Path

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.continuous_request_context import FORMAT_VERSION
from vnext.normal_annual_input import _registry_rows
from vnext.normal_source_authority import ROOT
from vnext.r6_regulatory_semantics import (
    prepare_regulatory_semantic_source, requests_from_source)


def census():
    rows = []
    with original_sources_only():
        for company in (row['company_id'] for row in _registry_rows(repo_root=ROOT)):
            started = time.monotonic()
            try:
                source = prepare_regulatory_semantic_source(
                    repo_root=ROOT, company_id=company,
                    request_context_format=FORMAT_VERSION)
                requests = requests_from_source(source)
                unit_ids = [unit['unit_id'] for request in requests
                            for unit in request['units']]
                if unit_ids != source['required_unit_ids']:
                    raise ValueError('D03_CENSUS_SOURCE_UNIT_COVERAGE_CHANGED')
                row = {'company_id': company, 'status': 'OFFLINE_REQUESTS_BUILT',
                    'source_id': source['semantic_source_id'],
                    'source_unit_count': len(source['units']),
                    'request_count': len(requests),
                    'anchored_request_count': sum(
                        bool(request['source_statement_facts']) for request in requests),
                    'anchored_fact_count': sum(
                        len(request['source_statement_facts']) for request in requests),
                    'request_id_count': len({request['request_id'] for request in requests}),
                    'elapsed_seconds': round(time.monotonic() - started, 3)}
            except Exception as error:
                row = {'company_id': company, 'status': 'OFFLINE_PREPARATION_FAILED',
                    'error_type': type(error).__name__, 'reason': str(error),
                    'elapsed_seconds': round(time.monotonic() - started, 3)}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False, sort_keys=True), flush=True)
    return {'record_type': 'ISSUE28_D03_CURRENT_SAVED_INPUT_REQUEST_CENSUS',
        'request_context_format': FORMAT_VERSION,
        'companies': rows,
        'successful_request_count': sum(row.get('request_count', 0) for row in rows),
        'all_ten_prepared': len(rows) == 10 and all(
            row['status'] == 'OFFLINE_REQUESTS_BUILT' for row in rows),
        'model_calls': 0, 'sec_calls': 0, 'native_result_created': False,
        'full_company_semantics_proven': False,
        'new_live_authorization': False}


if __name__ == '__main__':
    output = Path(__file__).with_name('census.json')
    value = census()
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False,
                                    sort_keys=True, indent=2) + '\n')
    temporary.replace(output)
    print('FINAL_SUMMARY', value['successful_request_count'],
          value['all_ten_prepared'], flush=True)
