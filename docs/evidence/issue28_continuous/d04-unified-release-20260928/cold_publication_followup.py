"""Independent process read of the completed private D04 publication."""
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path('/Users/lyuhongwang/Developer/SEC_metrics')
sys.path[:0] = [str(REPO), str(REPO / 'scripts')]

from vnext import ordinary_isolated_publication as release, publication as pub

HERE = REPO / 'docs/evidence/issue28_continuous/d04-unified-release-20260928'
ROOT = Path('/private/tmp/issue28-d04-enphase-private-publication-dea6-20260928')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forbidden(*_args, **_kwargs):
    raise AssertionError('PRIVATE_PUBLICATION_COLD_NETWORK_FORBIDDEN')


def main():
    original_summary = (ROOT / 'rehearsal-summary.json').read_bytes()
    summary = json.loads(original_summary)
    assert summary['status'] == 'PASS' and summary['new_calls'] == [0, 0, 0]
    candidate = summary['staged']['publication_id']
    official = REPO / 'outputs/active_publication.json'
    official_before = sha(official)
    private_pointer = ROOT / 'outputs/active_publication.json'
    before = {str(path): sha(path) for path in [private_pointer,
        ROOT / 'outputs/publications' / candidate / 'publication_manifest.json',
        ROOT / 'outputs/publications' / candidate / 'metrics_matrix.csv',
        ROOT / 'outputs/publications' / candidate / 'metric_evidence.csv']}
    with patch.object(socket.socket, 'connect', side_effect=forbidden), \
         patch.object(socket, 'getaddrinfo', side_effect=forbidden), \
         patch('sec_http.urlopen', side_effect=forbidden):
        observed = release.read_back(publication_root=ROOT)
        view = pub.PublicationView.open(publication_root=ROOT)
        rows = list(csv.DictReader(io.StringIO(view.read_bytes(
            relative_path='metrics_matrix.csv').decode('utf-8'))))
    matched = [row for row in rows if row['company'] == 'Enphase Energy'
               and row['metric_id'] == 'D04']
    assert len(matched) == 1 and matched[0]['status'] == 'TEXT_QUAL'
    assert matched[0]['value'] == '' and matched[0]['fiscal_year'] == '2025'
    assert observed == summary['candidate_read_back']
    assert observed['publication_id'] == candidate
    assert sha(official) == official_before
    assert before == {path: sha(Path(path)) for path in before}
    result = {'publication_id': candidate,
        'preparation_id': summary['staged']['preparation_id'],
        'private_read_back': observed,
        'd04_row': matched[0],
        'private_selected_files_unchanged': True,
        'official_active_pointer_unchanged': True,
        'new_real_calls': [0, 0, 0],
        'production_authorized': False}
    (HERE / 'publication-cold-result.json').write_text(json.dumps(result,
        ensure_ascii=False, indent=2) + '\n')
    (HERE / 'publication-private-summary.json').write_bytes(original_summary)
    print(json.dumps({key: result[key] for key in ('publication_id',
        'preparation_id', 'private_selected_files_unchanged',
        'official_active_pointer_unchanged', 'new_real_calls')},
        ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
