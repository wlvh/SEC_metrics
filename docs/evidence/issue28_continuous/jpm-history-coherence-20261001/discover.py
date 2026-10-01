import json
from pathlib import Path
import sys

repo = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(repo), str(repo / 'scripts')]
from vnext.normal_source_requirements import discover_saved_source_requirements

root = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
result = discover_saved_source_requirements(repo_root=root, company_id='jpmorgan_chase')
url = 'https://data.sec.gov/submissions/CIK0000019617-submissions-001.json'
selected, = [row for row in result['requirements'] if row['source_url'] == url]
body = {'record_type': 'ISSUE28_JPM_CURRENT_SAVED_HISTORY_DISCOVERY_READ_ONLY',
    'source_root': str(root), 'source_requirements_id': result['requirements_id'],
    'status': result['status'], 'metadata': result['metadata'],
    'selected_url': url, 'selected_source': selected,
    'calls': [0, 0, 0], 'production_authorized': False}
Path('/private/tmp/issue28_jpm_current_history_discovery.json').write_text(
    json.dumps(body, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': body['status'],
    'metadata_status': body['metadata']['status'],
    'conflicts': len(body['metadata']['history_conflicts']),
    'unavailable': len(body['metadata']['unavailable_history_urls']),
    'selected_saved_status': selected['saved_status'],
    'selected_refreshable': selected['refresh_for_new_discovery']}, sort_keys=True))
