"""Read complete saved C04 cases without network or native Run credit."""
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.c04_registration_successor import EVENT_FORMS
from vnext.normal_run_v3 import prepare_case

SOURCE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')):
    marriott = prepare_case(data_root=ROOT, company_id='marriott_international',
        metric_id='C04', c04_event_forms=EVENT_FORMS)
    salesforce = prepare_case(data_root=SOURCE, company_id='salesforce',
        metric_id='C04', c04_event_forms=EVENT_FORMS)
    paramount = prepare_case(data_root=SOURCE,
        company_id='paramount_skydance_paramount_global', metric_id='C04',
        c04_event_forms=EVENT_FORMS)
    macys = prepare_case(data_root=SOURCE, company_id='macys',
        metric_id='C04', c04_event_forms=EVENT_FORMS)

old_marriott = {'result_id':
    'sha256:a5517d36ec92517b057a4e8e5f1277cc8f2850d9108d563a1adb2ad71cb7c3f9',
    'selection_id':
    'sha256:f0f59a0104b7ec47f286d6f214b43475dcb0649dc0e5a91553ce7ed0d4ea2de3',
    'input_binding_id':
    'sha256:362a177b3dc6374b1fe99158205aab0571b8425a4861b73397b4fe046e1745b2'}
assert marriott['results']['C04']['result_id'] == old_marriott['result_id']
assert marriott['selection']['selection_id'] == old_marriott['selection_id']
assert marriott['input_binding']['c04_registration_successor'][
    'input_binding_id'] == old_marriott['input_binding_id']
assert 'fiscal_year_label_binding' not in marriott['selection']
assert 'verified_annual_document_aliases' not in marriott['selection']

assert salesforce['target_period'] == {'fiscal_year': 2026,
    'period_start': '2025-02-01', 'period_end': '2026-01-31'}
assert salesforce['results']['C04']['publication'] == 'PUBLISHED'
assert salesforce['results']['C04']['value'] == '0'
aliases = salesforce['selection']['verified_annual_document_aliases']
assert len(aliases) == 1
assert aliases[0]['saved_document_name'] == '0002.body'
assert aliases[0]['sec_url_document_name'] == 'crm-20250131.htm'
assert any(ref['source_reference_id'] == aliases[0]['source_reference_id']
           and ref['document_name'] == '0002.body'
           for ref in salesforce['references'])
label = salesforce['selection']['fiscal_year_label_binding']
assert label['selected_fiscal_year'] == 2026
assert label['basis'] == 'EXPLICIT_SOURCE_ISSUER_DEFINITION'
assert label['original_dei_fiscal_year'] == 2025
assert label['metadata_conflict_retained'] is True
assert salesforce['input_binding']['c04_registration_successor'][
    'fiscal_year_label_binding'] == label

assert paramount['results']['C04']['publication'] == 'WITHHELD'
assert paramount['results']['C04']['value'] is None
assert macys['target_period']['fiscal_year'] == 2025
print(json.dumps({'status': 'PASS_REAL_SAVED_C04_ALIAS_AND_FISCAL_LABEL_CASES',
    'marriott_original_result_selection_binding_ids_unchanged': True,
    'salesforce_target_period': salesforce['target_period'],
    'salesforce_result_id': salesforce['results']['C04']['result_id'],
    'salesforce_publication': salesforce['results']['C04']['publication'],
    'salesforce_value': salesforce['results']['C04']['value'],
    'salesforce_original_alias_reference_id': aliases[0]['source_reference_id'],
    'salesforce_saved_document_name': aliases[0]['saved_document_name'],
    'salesforce_sec_url_document_name': aliases[0]['sec_url_document_name'],
    'salesforce_fiscal_label_basis': label['basis'],
    'salesforce_original_dei_fiscal_year': label['original_dei_fiscal_year'],
    'paramount_still_withheld': True, 'macys_fiscal_year': 2025,
    'native_run_created': False, 'new_calls': [0, 0, 0],
    'production_authorized': False}, sort_keys=True))
