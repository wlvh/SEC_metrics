import json
import time
from pathlib import Path

from vnext.d03_model_processing import build_development_company_assessment

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/d03-complete-six-responses-20261004')
index = json.loads((ROOT/'docs/evidence/issue28_continuous/d03-native-input-check-20261003/complete-set.json').read_text())
packets = []
for row in index['requests']:
    folder = BASE/'processing'/str(row['index'])
    packets.append({'request_body': (folder/'request-body.bin').read_bytes(),
        'response_body': (folder/'response.bin').read_bytes(),
        'expected_request_sha256': row['request_sha256'], 'expected_response_sha256': row['response_sha256']})
start = time.monotonic()
out = build_development_company_assessment(data_root=ROOT, company_id='marriott_international',
    packets=packets, expected_source_sha256=index['source_sha256'])
target = BASE/'native-pending-final-display'
target.mkdir(exist_ok=False)
(target/'processing/d03').mkdir(parents=True)
(target/'processing/d03/metadata.json').write_text(json.dumps(out['processing'], ensure_ascii=False, sort_keys=True, separators=(',', ':')))
(target/'records.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n' for r in out['records']))
(target/'review-context.json').write_bytes(out['review_context_bytes'])
(target/'review.md').write_bytes(out['rendered_review_bytes'])
for i, packet in enumerate(packets):
    folder = target/'wires'/str(i)
    folder.mkdir(parents=True)
    (folder/'request-body.bin').write_bytes(packet['request_body'])
    (folder/'response.bin').write_bytes(packet['response_body'])
summary = {'tested_base_sha': 'be21d9f6164c6bbdb8c3ecad39bf4f81a5115732',
    'uncommitted_product_module': True, 'data_root': str(ROOT), 'output': str(target),
    'seconds': round(time.monotonic()-start, 3),
    'candidate_hash': out['records'][1]['candidate_hash'], 'unit_hash': out['records'][3]['review_unit_hash'],
    'review_bytes': len(out['rendered_review_bytes']), 'context_bytes': len(out['review_context_bytes']),
    'native_credit': False, 'new_calls': [0, 0, 0]}
(HERE/'build-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps(summary))
