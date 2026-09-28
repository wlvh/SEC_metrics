"""Read #28's current originals; no network, acquisition or Result writes."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.b03_depreciation_scope import assess_direct_depreciation_scope
from vnext.normal_run_v3 import prepare_case
from vnext.normal_source_authority import ROOT as CODE_ROOT


companies = ('marriott_international', 'southwest_airlines',
    'ford_motor_company', 'pfizer', 'jpmorgan_chase', 'salesforce',
    'lumen_technologies', 'macys',
    'paramount_skydance_paramount_global', 'enphase_energy')
rows = []
with original_sources_only():
    for company_id in companies:
        case = prepare_case(data_root=CODE_ROOT, company_id=company_id,
                            metric_id='B03')
        finding = assess_direct_depreciation_scope(case=case,
            data_root=CODE_ROOT)
        rows.append({'company_id': company_id,
            'historical_native_result_id': case['results']['B03']['result_id'],
            'historical_native_publication': case['results']['B03']['publication'],
            'scope_check': finding})
body = {'record_type': 'B03_CURRENT_SOURCE_SCOPE_AUDIT',
    'source': 'ISSUE28_SAVED_ORIGINALS_ONLY',
    'current_result_adoption_credit': False,
    'unflagged_means_complete_scope_proven': False,
    'new_provider_paid_sec_calls': [0, 0, 0],
    'rows': rows}
path = Path(__file__).with_name('audit.json')
path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'companies': len(rows),
    'blocked': [row['company_id'] for row in rows
        if row['scope_check']['blocked']],
    'calls': [0, 0, 0]}, sort_keys=True))
