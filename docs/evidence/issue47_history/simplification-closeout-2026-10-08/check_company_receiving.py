"""One affected-source CLI check; constructed withholding is a state control.

Use the existing source-only Marriott package (no rules or answers). All
production selection, calculation, saving, reading and CSV functions are the
shared company entry. The explicit test control only substitutes a checked
WITHHELD outcome and a related configuration change. No production policy is
changed, and this control is not a financial-report conclusion.
"""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import socket
import time
from unittest.mock import patch

from tools.vnext_company import main
from vnext import historical_lodging_results as history
from vnext import ordinary_current_update as update
from vnext.calculator import withheld_metric_result

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
SOURCE = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/source-only-b01-no-rules-20261007')
PARENT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue47-development-evidence')
PARENT.mkdir(parents=True, exist_ok=True)
TASK = PARENT/'history-consumer-closeout-20261008'
for suffix in range(100):
    candidate = TASK if suffix == 0 else TASK.with_name(TASK.name+'-'+str(suffix))
    if not candidate.exists():
        TASK = candidate
        TASK.mkdir()
        break
else:
    raise RuntimeError('No unused test task path')

original_factory = history.prepare_historical_lodging_year_case
original_configuration = update._configuration
calls, cases, operations = [], {}, []
phase = 'REAL_SAVED_SOURCE'
forbid = False


def controlled_configuration(*args):
    return {**original_configuration(*args), 'constructed_test_control': phase}


def controlled_factory(**kwargs):
    """Actual source calculation first; later same case gets a marked control."""
    key = kwargs['fiscal_year'], kwargs['metric_id']
    calls.append(key)
    if forbid:
        raise AssertionError('Unchanged input must not invoke the factory')
    if key not in cases:
        cases[key] = original_factory(**kwargs)
    case = copy.deepcopy(cases[key])
    if phase == 'CONSTRUCTED_CONTROL_BUSINESS_WITHHELD' and key == (2024, 'B10'):
        old = case['results']['B10']
        result, trace = withheld_metric_result(compiled_spec=case['compiled_specs']['B10'],
            target={k: case['traces']['B10']['calculation_target'][k]
                    for k in ('company_id', 'period_start', 'period_end', 'scope', 'scope_key')},
            reason_code='CONSTRUCTED_CONTROL_BUSINESS_WITHHELD')
        case['expected_records'] = [r for r in case['expected_records']
            if r['record_type'] not in {'METRIC_RESULT', 'EXECUTION_TRACE'}] + [result, trace]
        case['results'] = {'B10': result}
        case['traces'] = {'B10': trace}
    return case


def digest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def protected():
    return {str(p.relative_to(TASK)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (TASK/'state').rglob('*') if p.is_file()
            and ('/results/' in str(p) or p.name in {'current-result.json', 'completed-check.json'})}


def invoke(label, args):
    out = io.StringIO()
    before = len(calls)
    started = time.monotonic()
    with patch('sys.stdout', out):
        code = main(args)
    raw = out.getvalue()
    (EVIDENCE/(label+'.json')).write_text(raw)
    assert code in (0, 2), (label, code, raw[:400])
    report = json.loads(raw)
    operations.append({'label': label, 'seconds': time.monotonic()-started,
        'factory_calls': len(calls)-before, 'status': report.get('status')})
    return report


def rows(report):
    return list(csv.DictReader(io.StringIO(
        (Path(report['output_root'])/'metrics_matrix.csv').read_text(encoding='utf-8-sig'))))


def values(report):
    return {(r['metric_id'], r['fiscal_year']): r['value'] for r in rows(report)}


def run():
    global phase, forbid
    assert not (SOURCE/'catalog').exists() and not (SOURCE/'scripts').exists()
    source_before = digest(SOURCE)
    ledger = Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-sec-ledger-resume-20261006/claims.jsonl')
    ledger_before = ledger.read_bytes()
    common = ['run', '--company', 'marriott_international', '--source-root', str(SOURCE),
        '--work-dir', str(TASK/'state'), '--output-dir', str(TASK/'outputs'),
        '--metric', 'B10', '--metric', 'B11', '--period', 'fiscal-years',
        '--fiscal-year-start', '2024', '--fiscal-year-end', '2025']
    expected = {('B10', '2024'): '69.8', ('B11', '2024'): '128.23',
        ('B10', '2025'): '69.3', ('B11', '2025'): '128.8'}
    with (patch.object(socket.socket, 'connect', side_effect=AssertionError('No business network')),
          patch.object(history, 'prepare_historical_lodging_year_case', controlled_factory),
          patch.object(update, '_configuration', controlled_configuration)):
        first = invoke('real-history-first', common)
        assert values(first) == expected, first
        assert operations[-1]['factory_calls'] == 4
        assert all((r['period_start'], r['period_end']) ==
                   (r['fiscal_year']+'-01-01', r['fiscal_year']+'-12-31') for r in rows(first))
        success = protected()
        forbid = True
        repeated = invoke('real-history-repeat', common)
        assert operations[-1]['factory_calls'] == 0 and protected() == success
        assert all(m['status'] == 'NO_SOURCE_CONTENT_CHANGE' for m in repeated['metrics'])
        forbid = False
        phase = 'CONSTRUCTED_CONTROL_BUSINESS_WITHHELD'
        held = invoke('constructed-withheld-first', common)
        assert values(held) == {**expected, ('B10', '2024'): ''}, held
        assert held['metrics'][0]['status'] == 'CANDIDATE_WITHHELD'
        assert all(v == protected()[k] for k, v in success.items() if '/results/' in k)
        state = TASK/'state/updates/B10/periods/FY2024'
        last_success = json.loads((state/'current-result.json').read_text())
        completed = json.loads((state/'completed-check.json').read_text())
        assert completed['version'] != last_success['version']
        held_bytes = protected()
        forbid = True
        repeated_held = invoke('constructed-withheld-repeat', common)
        assert operations[-1]['factory_calls'] == 0 and protected() == held_bytes
        assert repeated_held['metrics'][0]['status'] == 'PREVIOUS_INPUT_WITHHELD'
        read = invoke('read-with-current-withheld', ['results', '--company', 'marriott_international',
            '--state-root', str(TASK/'state'), '--output-root', str(TASK/'daily')])
        assert values(read) == {**expected, ('B10', '2024'): ''}, read
        assert operations[-1]['factory_calls'] == 0 and protected() == held_bytes
        row = next(r for r in read['metrics'] if r['metric_id'] == 'B10' and r['fiscal_year'] == 2024)
        assert row['value'] is None and row['publication'] == 'WITHHELD'
        assert row['reason_code'] == phase
    assert digest(SOURCE) == source_before and ledger.read_bytes() == ledger_before
    return {'record_type': 'HISTORICAL_SHARED_COMPANY_CONSUMER_CLOSEOUT',
        'program_root': str(ROOT), 'source_root': str(SOURCE), 'task_root': str(TASK),
        'operations': operations, 'actual_values': [{'metric': k[0], 'year': k[1], 'value': v}
            for k, v in expected.items()], 'constructed_withholding_not_financial_conclusion': True,
        'repeat_success_factory_calls': 0, 'repeat_withheld_factory_calls': 0,
        'repeat_and_read_result_bytes_unchanged': True, 'last_success_retained_current_withheld_null': True,
        'source_tree_copies': 0, 'rule_tree_copies': 0, 'source_files_unchanged': True,
        'calls': {'provider': 0, 'paid': 0, 'sec': 0},
        'ledger_sha256': hashlib.sha256(ledger_before).hexdigest(),
        'automatic_historical_source_acquisition': False, 'full_five_year_business_acceptance': False}


if __name__ == '__main__':
    record = run()
    (EVIDENCE/'company-consumer.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(record, ensure_ascii=False))
