"""Check the saved JPM A03 quarter-average against its original 10-K table."""
import csv
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STATE = Path('/private/tmp/issue28-jpmorgan_chase-current-36-cli-20260929/'
    'state/jpmorgan_chase/metrics/A03')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


pointer = json.loads((STATE/'current.json').read_text())
attempt = pointer['successful_attempt']
assert type(attempt) is str and attempt
work = STATE/'attempts'/attempt
data = work/'data'
run = work/'runs/A03'
records_raw = (run/'records.jsonl').read_bytes()
records = [json.loads(line) for line in records_raw.splitlines()]
observation, = [row for row in records if row['record_type'] ==
                'VERIFIED_OBSERVATION' and row['metric_id'] == 'A03']
result, = [row for row in records if row['record_type'] ==
           'METRIC_RESULT' and row['metric_id'] == 'A03']
reference, = [row for row in records if row['record_type'] == 'SOURCE_REFERENCE'
              and row['source_reference_id'] == observation['source_binding'][
                  'source_reference_id']]
blob, = [row for row in records if row['record_type'] == 'RAW_BLOB'
         and row['raw_asset_id'] == reference['raw_asset_id']]
installed = (data/blob['storage_uri']).read_bytes()
original = (ROOT/blob['storage_uri']).read_bytes()
assert installed == original
assert reference['raw_asset_id'] == 'sha256:' + digest(original)
assert reference['accession'] == '0001628280-26-008131'
assert reference['company_id'] == 'jpmorgan_chase'
binding = observation['source_binding']
quarter = {'period_start': '2025-10-01', 'period_end': '2025-12-31'}
assert binding['actual_measurement_period']['period_start'] == quarter['period_start']
assert binding['actual_measurement_period']['period_end'] == quarter['period_end']
assert binding['filing_period']['period_start'] == '2025-01-01'
assert binding['filing_period']['period_end'] == '2025-12-31'
assert binding['measurement_time_basis'] == 'SOURCE_DISCLOSED_AVERAGE'
assert observation['scope'] == {'entity_scope': 'firm', 'aggregation': 'average'}
assert observation['value'] == result['value'] == '1.11'
assert observation['scope_key'] == result['scope_key']
assert result['unit'] == 'ratio' and result['quality'] == 'EXACT'
assert all(row['period_start'] == quarter['period_start'] and
           row['period_end'] == quarter['period_end']
           for row in (observation, result))
with (work/'rows/A03/metrics_matrix.csv').open(newline='') as handle:
    public, = list(csv.DictReader(handle))
assert public['metric_id'] == 'A03' and public['value'] == '1.11'
assert public['unit'] == 'ratio' and public['status'] == 'MDA_OK'
assert public['period_start'] == quarter['period_start']
assert public['period_end'] == quarter['period_end']
assert public['fiscal_period'] == 'QUARTER'
saved = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'ordinary-jpmorgan-current-36-cli-20260929/cold.json').read_text())
cold, = [row for row in saved['rows'] if row['metric_id'] == 'A03']
assert cold['result_id'] == result['result_id']
assert cold['period_start'] == quarter['period_start']

start = original.find(b'average LCR for the three months ended')
firm_start = original.find(b'JPMorgan Chase &amp; Co.:', start)
bank_start = original.find(b'JPMorgan Chase Bank, N.A.:', firm_start)
end = original.find(b'Net excess eligible HQLA', bank_start) + len(
    b'Net excess eligible HQLA')
assert 0 < start < firm_start < bank_start < end
span = original[start:end]
text = html.unescape(' '.join(re.sub(rb'<[^>]+>', b' ', span).decode(
    'utf-8', 'replace').split())).replace('\xa0', ' ')
assert re.search(r'three months ended December\s+31,\s*2025', text)
firm = text.split('JPMorgan Chase & Co.:', 1)[1].split(
    'JPMorgan Chase Bank, N.A.:', 1)[0]
bank = text.split('JPMorgan Chase Bank, N.A.:', 1)[1]
assert re.search(r'\bLCR\s+111\s*%', firm)
assert re.search(r'\bLCR\s+115\s*%', bank)
body = {'record_type': 'ISSUE28_JPM_A03_FIRM_QUARTER_AVERAGE_SOURCE_AUDIT',
    'saved_run_id': json.loads((run/'manifest.json').read_text())['run_id'],
    'saved_run_records_sha256': digest(records_raw),
    'saved_result_id': result['result_id'],
    'source_reference_id': reference['source_reference_id'],
    'source_raw_asset_id': reference['raw_asset_id'],
    'source_fact_hash': binding['source_fact_hash'],
    'actual_measurement_period': binding['actual_measurement_period'],
    'filing_period': binding['filing_period'],
    'scope': observation['scope'],
    'value': result['value'], 'public_fiscal_period': public['fiscal_period'],
    'original_table_span': {'start_byte': start, 'end_byte': end,
        'sha256': digest(span), 'firm_lcr_percent': 111,
        'bank_subsidiary_lcr_percent': 115,
        'first_350_visible_characters': text[:350]},
    'independent_prior_cold_read_result_id_matches': True,
    'current_head_native_run_replayed_here': False,
    'historical_pr34_result_upgraded': False,
    'new_result_or_run_created': False,
    'new_real_calls': [0, 0, 0]}
(HERE/'audit.json').write_text(json.dumps(body, ensure_ascii=False,
    indent=2) + '\n')
print(json.dumps({'value': '1.11', 'period': quarter,
    'firm_percent': 111, 'bank_percent': 115,
    'calls': [0, 0, 0]}, sort_keys=True), flush=True)
