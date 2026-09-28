"""Compare the current default D03 source identity with prior recorded census."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
BASE = '79468174f1ad168a1dee7dd1e3e01903790b962a'
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from vnext.canonical import strict_json_loads
from vnext.continuous_semantic_calls import prepare_d03_replay_only_requests

previous = json.loads((ROOT/'docs/evidence/issue28_continuous/'
    'd03-current-input-census-20260927/census.json').read_text())
old = next(row for row in previous['companies']
    if row['company_id'] == 'marriott_international')
prepared = prepare_d03_replay_only_requests(company_id='marriott_international')
source = strict_json_loads(text=prepared[0].source_bytes.decode())
prior_module = subprocess.check_output(['git', 'show',
    BASE+':scripts/vnext/r6_regulatory_semantics.py'], cwd=ROOT)
body = {'record_type': 'D03_DEFAULT_IDENTITY_AFTER_CURRENT_RULE_CHANGE',
    'company_id': 'marriott_international',
    'prior_census_source_id': old['source_id'],
    'current_source_id': source['semantic_source_id'],
    'same_source_id': source['semantic_source_id'] == old['source_id'],
    'prior_module_sha256': hashlib.sha256(prior_module).hexdigest(),
    'current_module_sha256': source['regulatory_module_sha256'],
    'default_external_replay_marker_absent': 'external_replay_only' not in source,
    'default_root_preserved': all(row.data_root == ROOT for row in prepared),
    'default_request_count': len(prepared),
    'current_request_ids': [strict_json_loads(text=row.request_bytes.decode())['request_id']
                            for row in prepared],
    'new_real_calls': [0, 0, 0]}
(HERE/'default-identity.json').write_text(json.dumps(body,
    ensure_ascii=False, indent=2)+'\n')
print(json.dumps({k: body[k] for k in ('same_source_id',
    'default_request_count', 'default_external_replay_marker_absent',
    'default_root_preserved')}, sort_keys=True))
