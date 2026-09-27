"""Compare the private D02 text to the already indexed historical value."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
index_path = ROOT/'docs/evidence/issue28_continuous/review-5207290213/current-390.json'
index_bytes = index_path.read_bytes()
index = json.loads(index_bytes)
row, = [item for item in index['rows']
        if item['company_id'] == 'marriott_international'
        and item['metric_id'] == 'D02']
private = json.loads((HERE/'result.json').read_bytes())
value = row['value']
result = {'current_390_index_sha256': hashlib.sha256(index_bytes).hexdigest(),
    'index_evidence_type': row['evidence_type'],
    'index_value_characters': len(value),
    'index_value_sha256': hashlib.sha256(value.encode()).hexdigest(),
    'private_result_id': private['result_id'],
    'same_value_bytes': len(value) == private['value_characters'] and
        hashlib.sha256(value.encode()).hexdigest() == private['value_sha256'],
    'new_390_coordinate_credit': False}
assert result['same_value_bytes']
(HERE/'index-comparison.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, sort_keys=True))
