"""Reconcile recorded Marriott B01 fiscal-year transition without call credit."""
import csv
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
PRIVATE = Path('/private/tmp/issue28-b01-crossyear-auto-20260928')
HISTORY = PRIVATE/'state/marriott_international/metrics/B01'
sys.path[:0] = [str(REPO/'scripts'),
    str(REPO/'docs/evidence/issue28_continuous/c04-adjacent-year-rehearsal-20260927')]
from rehearse import saved_response, derived_prior_response
from sec_urls import submissions_url


def read(path):
    return json.loads(path.read_bytes())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


auto = read(HERE/'auto-result.json')
old = read(HERE/'cold-2024.json')
new = read(HERE/'cold-2025.json')
repeat = read(HERE/'repeat-result.json')
url = submissions_url(cik=1048286)
current_raw, original_row = saved_response(url)
prior_raw, annual = derived_prior_response(current_raw)
old_id = auto['old_step']['attempt_id']
new_id = auto['new_step']['attempt_id']
old_manifest = read(HISTORY/'attempts'/old_id/'runs/B01/manifest.json')
new_manifest = read(HISTORY/'attempts'/new_id/'runs/B01/manifest.json')
new_intent = read(HISTORY/'attempts'/new_id/'intent.json')
pointer = read(HISTORY/'current.json')
repeat_terminal = read(HISTORY/'attempts'/pointer['latest_attempt']/'terminal.json')
old_primary = 'https://www.sec.gov/Archives/edgar/data/1048286/000162828025004818/mar-20241231.htm'
new_primary = 'https://www.sec.gov/Archives/edgar/data/1048286/000104828626000007/mar-20251231.htm'

assert all((HERE/name).read_text().strip() == '0' for name in
    ('auto.exit', 'cold.exit', 'repeat.exit'))
assert sha(prior_raw) == auto['derived_old_submissions_sha256'] == sha(
    (PRIVATE/'ledger/calls/0001/sec-wire/body.bin').read_bytes())
assert sha(current_raw) == auto['original_current_submissions_sha256'] == \
    original_row['content_sha256'] == sha((PRIVATE/
    'ledger/calls/0002/sec-wire/body.bin').read_bytes())
assert annual[0][1] == '2026-02-10'
assert auto['derived_old_metadata_is_authentic_SEC_response'] is False
assert auto['new_step']['captures'] == [
    {'source_url': url, 'status': 'SUCCEEDED'}]
assert auto['old_step']['metric_status'] == \
    auto['new_step']['metric_status'] == 'CANDIDATE_READY'
assert auto['old_step']['report_status'] == \
    auto['new_step']['report_status'] == 'UPDATES_INCOMPLETE'
assert auto['old_step']['result_id'] == old['result_id'] != \
    auto['new_step']['result_id'] == new['result_id']
assert (auto['old_row']['value'], auto['old_row']['fiscal_year'],
        auto['old_row']['accession']) == \
    ('25100000000', '2024', '0001628280-25-004818')
assert (auto['new_row']['value'], auto['new_row']['fiscal_year'],
        auto['new_row']['accession']) == \
    ('26186000000', '2025', '0001048286-26-000007')
assert old['status'] == new['status'] == 'PASS'
assert old['run_id'] == old_manifest['run_id'] != \
    new['run_id'] == new_manifest['run_id']
assert old['requirement_closure_hash'] == \
    new['requirement_closure_hash'] == \
    old_manifest['requirement_closure_hash'] == \
    new_manifest['requirement_closure_hash']
assert old['history_bytes_unchanged'] and new['history_bytes_unchanged']
assert old_primary in {x['source_url'] for x in old_manifest['source_references']}
assert new_primary in {x['source_url'] for x in new_manifest['source_references']}
assert new_intent['previous_successful_attempt'] == old_id == \
    auto['new_intent_predecessor']
assert auto['old_success_package_unchanged']
assert repeat['metric_status'] == repeat_terminal['status'] == \
    'NO_SOURCE_CONTENT_CHANGE'
assert repeat['new_candidate_created'] is False
assert repeat['old_success_package_unchanged'] and \
    repeat['new_success_package_unchanged']
assert repeat['successful_attempt_unchanged'] and \
    repeat['latest_attempt_advanced']
assert pointer['successful_attempt'] == new_id and \
    pointer['latest_attempt'] == repeat_terminal['attempt_id']
assert auto['recorded_ledger_counts'] == [0, 0, 2] and \
    repeat['ledger_counts_before_after'] == [[0, 0, 2], [0, 0, 2]]
assert auto['real_calls'] == old['real_calls'] == new['real_calls'] == \
    repeat['real_calls'] == [0, 0, 0]

body = {
    'record_type': 'ISSUE28_MARRIOTT_B01_RECORDED_CROSS_YEAR_RECONCILIATION',
    'status': 'PASS_RECORDED_AUTO_METADATA_REFRESH_TWO_FISCAL_RUNS',
    'company_id': 'marriott_international', 'metric_id': 'B01',
    'old_fiscal_year': '2024', 'new_fiscal_year': '2025',
    'old_result_id': old['result_id'], 'new_result_id': new['result_id'],
    'old_run_id': old['run_id'], 'new_run_id': new['run_id'],
    'old_primary_url': old_primary, 'new_primary_url': new_primary,
    'original_current_submissions_path': original_row['repo_relative_path'],
    'original_current_submissions_sha256': sha(current_raw),
    'derived_prior_submissions_sha256': sha(prior_raw),
    'old_metadata_is_derived_not_historical_SEC_response': True,
    'second_metadata_capture_automatically_selected_url': url,
    'old_success_package_unchanged': True,
    'both_installed_cold_reads_pass': True,
    'repeat_status': repeat['metric_status'],
    'repeat_retained_new_successful_attempt': True,
    'recorded_sec_attempt_count': 2,
    'real_provider_paid_sec_calls': [0, 0, 0],
    'overall_source_refresh_incomplete': True,
    'authentic_online_new_filing_transition_proven': False,
    'all_390_acceptance': False, 'production_authorized': False,
}
(HERE/'reconciliation.json').write_text(json.dumps(body,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: body[k] for k in ('status', 'old_result_id',
    'new_result_id', 'recorded_sec_attempt_count',
    'overall_source_refresh_incomplete', 'real_provider_paid_sec_calls')},
    ensure_ascii=False))
