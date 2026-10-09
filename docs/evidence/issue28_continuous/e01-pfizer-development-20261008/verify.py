import hashlib,json,subprocess,sys,types
from pathlib import Path
r=Path(__file__).resolve().parent
repo=r.parents[3]
sys.path.insert(0,str(repo/'scripts'))
sha='b4b57e7cba3d2f8ea82a22b7510d5aba27bb9b05'
source=subprocess.check_output(['git','show',sha+':scripts/vnext/historical_ma_confirmation.py'],cwd=repo)
expected=json.loads((r/'comparison.json').read_text())
assert hashlib.sha256(source).hexdigest()==expected['contract_source_sha256']
m=types.ModuleType('vnext._developer_e01');m.__package__='vnext'
exec(source,m.__dict__)
q=json.loads((r/'request.json').read_text());raw=(r/'raw-response.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==expected['raw_response_sha256']
actual=m.validate_answer(request=q,raw_output=raw)
reference={x['item_id']:x['decision'] for x in json.loads((r/'parent-reference.json').read_text())['reference']}
assert {i:x['decision'] for i,x in actual.items()}==reference
print('PASS_DEVELOPMENT_LIMITED:3 reference matches and exact quotes; no MetricResult or target-model credit')
