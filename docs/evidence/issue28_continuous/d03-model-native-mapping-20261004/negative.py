import json
import shutil
import tempfile
from pathlib import Path

from vnext.d03_model_processing import read_development_company_assessment
from vnext.review import create_system_review_decision
from vnext.requirements import load_requirement_snapshot

HERE = Path(__file__).resolve().parent
saved = json.loads((HERE/'build-summary.json').read_text())
results = []
for attack in ['response', 'review', 'expected_unit']:
    with tempfile.TemporaryDirectory(prefix='issue28-d03-native-negative-') as tmp:
        root = Path(tmp)/'copy'
        shutil.copytree(saved['output'], root)
        unit = saved['unit_hash']
        if attack == 'response':
            p = root/'wires/0/response.bin';p.write_bytes(p.read_bytes()+b' ')
        elif attack == 'review':
            p = root/'review.md';p.write_bytes(p.read_bytes()+b'changed')
        else:
            unit = 'sha256:'+'0'*64
        try:
            read_development_company_assessment(directory=root, data_root=saved['data_root'],
                company_id='marriott_international', expected_candidate_hash=saved['candidate_hash'],
                expected_review_unit_hash=unit)
        except ValueError as error:
            results.append({'case': attack, 'rejected': str(error)})
        else:
            raise AssertionError('Accepted '+attack)
records = [json.loads(s) for s in (Path(saved['output'])/'records.jsonl').read_text().splitlines()]
requirement = load_requirement_snapshot(snapshot_dir=Path(saved['data_root'])/'requirements/issue_28_v13')
try:
    create_system_review_decision(review_unit=records[3], requirement=requirement,
        required_claims=records[3]['required_claims'], decided_at_utc='2026-10-04T00:00:00Z')
except ValueError as error:
    results.append({'case': 'SYSTEM_approve_actual_pending', 'rejected': str(error)})
else:
    raise AssertionError('SYSTEM approved unverified model proposals')
(HERE/'negative-summary.json').write_text(json.dumps(results, indent=2)+'\n')
print(json.dumps(results))
