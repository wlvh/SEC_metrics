"""Match two #47 C02 leads to #28's exact archived and current private results."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PEER_SHA = '48b46a2d742eb3e3b8bd5a6404908745046b5d2f'
PEER_PATH = 'docs/evidence/issue47_history/c02-board-read/excerpt-judgements.json'
PRIVATE = {
    'marriott_international': {
        'records': Path('/private/tmp/issue28-marriott-current-36-20260929/state/metrics/C02/attempts/1a24edf5e4b64dcb8e9268ec2e4ccab4/runs/C02/records.jsonl'),
        'block': 402,
        'old_result': 'sha256:d2b64d11d63776aa2213330104a8878cdc1b30967d1834877d134a4b3b0f28d5',
        'private_result': 'sha256:20070857450124148530e85b3c8135666b455579c162320efbf46cacefc68e00',
    },
    'pfizer': {
        'records': Path('/private/tmp/issue28-pfizer-current-36-cli-20260929/state/pfizer/metrics/C02/attempts/7247e8bca1f14e458ed41d6aec241ba6/runs/C02/records.jsonl'),
        'block': 1239,
        'old_result': 'sha256:cd35101fa8013371da3dff7f8f0d9c46d55bf32954417d399cbd90d3dddd9108',
        'private_result': 'sha256:cd35101fa8013371da3dff7f8f0d9c46d55bf32954417d399cbd90d3dddd9108',
    },
}


def main():
    peer_raw = subprocess.check_output(['git', 'show', f'{PEER_SHA}:{PEER_PATH}'], cwd=ROOT)
    peer = json.loads(peer_raw)['positions']
    index_path = ROOT / 'docs/evidence/issue28_continuous/d04-remaining-20260922/current-390.json'
    index = json.loads(index_path.read_text())
    rows = []
    for company, item in PRIVATE.items():
        archived = next(r for r in index['rows']
                        if r['company_id'] == company and r['metric_id'] == 'C02')
        records = [json.loads(line) for line in item['records'].read_text().splitlines()]
        candidate = next(r for r in records if r['record_type'] == 'DETERMINISTIC_TEXT_CANDIDATE')
        result = next(r for r in records if r['record_type'] == 'METRIC_RESULT')
        manifest = json.loads(item['records'].with_name('manifest.json').read_text())
        excerpt = next(r for r in candidate['selected'].values()
                       if r['block_index'] == item['block'])
        judgement = next(r for r in peer[f'{company}:2025-12-31']
                         if r['block_index'] == item['block'])
        assert judgement['category'] == 'NOT_BOARD_COMPOSITION'
        assert excerpt['text'].startswith(judgement['text_start'])
        assert archived['implementation_identity']['result_id'] == item['old_result']
        assert result['result_id'] == item['private_result']
        assert archived['value'] == result['value']
        assert manifest['target_period']['period_end'] == result['period_end'] == '2025-12-31'
        rows.append({
            'company_id': company, 'metric_id': 'C02', 'period_end': result['period_end'],
            'archived_result_id': item['old_result'],
            'archived_run_id': archived['implementation_identity']['run_id'],
            'private_result_id': item['private_result'],
            'private_run_id': manifest['run_id'],
            'private_requirement_closure_hash': manifest['requirement_closure_hash'],
            'archived_and_private_value_identical': True,
            'selected_block_count': len(candidate['selected']),
            'source_block': {
                'block_index': item['block'], 'document_id': excerpt['document_id'],
                'source_reference_id': excerpt['source_reference_id'],
                'raw_span_sha256': excerpt['raw_span_sha256'],
                'text_sha256': hashlib.sha256(excerpt['text'].encode()).hexdigest(),
                'text_start': excerpt['text'][:240],
            },
            'peer_category': judgement['category'],
            'peer_reason': judgement['reason'],
            'own_review': ('Executive pay alignment is not a board or committee composition fact.'
                           if company == 'marriott_international' else
                           'Shareholder proposal engagement and voting outreach are not composition facts.'),
            'private_records_path': str(item['records']),
        })
    body = {
        'record_type': 'ISSUE28_C02_CURRENT_RESULT_IMPACT_AUDIT',
        'peer_commit': PEER_SHA, 'peer_read_path': PEER_PATH,
        'peer_read_sha256': hashlib.sha256(peer_raw).hexdigest(),
        'archived_index_path': str(index_path.relative_to(ROOT)),
        'archived_index_sha256': hashlib.sha256(index_path.read_bytes()).hexdigest(),
        'affected_coordinate_count': 2,
        'affected_distinct_result_id_count': len({rid for r in rows for rid in
             (r['archived_result_id'], r['private_result_id'])}),
        'rows': rows,
        'limit': 'Only two source blocks and their exact current result identities were inspected. No finding about the other eight C02 coordinates or full C02 recall is implied.',
    }
    (HERE / 'impact.json').write_text(json.dumps(body, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'affected_coordinates': 2,
                      'distinct_result_ids': body['affected_distinct_result_id_count'],
                      'peer_commit': PEER_SHA}, sort_keys=True))


if __name__ == '__main__':
    main()
