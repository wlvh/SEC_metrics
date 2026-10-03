"""Cold read one current-bound D04 private complete-version preparation."""
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]

from vnext.ordinary_release_preparation import verify

HERE = REPO / 'docs/evidence/issue28_continuous/d04-unified-release-20260928'


def tree(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def forbidden(*_args, **_kwargs):
    raise AssertionError('PRIVATE_VERSION_COLD_READ_NETWORK_FORBIDDEN')


def main():
    prepared = json.loads((HERE / 'current-preparation-followup-result.json').read_text())
    root = Path(prepared['output_root'])
    before = tree(root)
    with patch.object(socket.socket, 'connect', side_effect=forbidden), \
         patch.object(socket, 'getaddrinfo', side_effect=forbidden), \
         patch('sec_http.urlopen', side_effect=forbidden):
        checked = verify(preparation_root=root,
            expected_preparation_id=prepared['preparation_id'])
    after = tree(root)
    assert before == after, 'PRIVATE_VERSION_CHANGED_DURING_COLD_READ'
    report = checked['composition']
    assert len(report['selected_results']) == 1
    assert report['selected_results'][0]['result_id'] == prepared['selected_result_id']
    assert report['full390_acceptance'] is False
    result = {'preparation_id': checked['preparation_id'],
        'file_count': len(after), 'package_bytes_unchanged': True,
        'selected_result_id': prepared['selected_result_id'],
        'full390_acceptance': False, 'new_real_calls': [0, 0, 0],
        'production_authorized': False}
    (HERE / 'current-cold-followup-result.json').write_text(json.dumps(result,
        ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
