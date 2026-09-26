"""Read each persisted C04 Run without rebuilding its source or input."""
import json
from pathlib import Path

from vnext.canonical import strict_json_file
from vnext.run_store import _mechanically_replay_open_run


HERE = Path(__file__).resolve().parent
WORK = Path('/private/tmp/issue28-c04-normal-update-20260926-01')


def read(work):
    manifest, records, _ = _mechanically_replay_open_run(
        run_dir=work/'runs/C04', repo_root=work/'data',
        require_complete_results=True)
    result = next(row for row in records
        if row['record_type'] == 'METRIC_RESULT' and row['metric_id'] == 'C04')
    return {'attempt_id': work.name, 'run_id': manifest['run_id'],
        'result_id': result['result_id'], 'value': result['value'],
        'publication': result['publication'],
        'reason_code': result.get('reason_code'),
        'period_end': result['period_end']}


def main():
    summary = strict_json_file(path=HERE/'recorded-update-summary.json')
    marriott = WORK/'state/marriott_international/metrics/C04-registration-v3/attempts'
    rows = [read(marriott/identity) for identity in
            (summary['marriott_first_success'],
             summary['marriott_changed_source_success'])]
    paramount = WORK/'paramount-state/paramount_skydance_paramount_global/metrics/C04-registration-v3/attempts'
    held = [work for work in paramount.iterdir()
            if strict_json_file(path=work/'terminal.json')['status'] == 'CANDIDATE_WITHHELD']
    assert len(held) == 1
    withheld = read(held[0])
    assert len({row['run_id'] for row in rows}) == 2
    assert len({row['result_id'] for row in rows}) == 2
    assert all(row['value'] == '0' and row['publication'] == 'PUBLISHED'
               for row in rows)
    assert withheld['value'] is None and withheld['publication'] == 'WITHHELD'
    value = {'status': 'PASS_C04_UPDATE_VERSIONED_RUN_READBACK',
             'marriott_versions': rows, 'paramount_withheld': withheld,
             'new_real_calls': [0, 0, 0], 'production_authorized': False}
    (HERE/'result-readback.json').write_text(
        json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    main()
