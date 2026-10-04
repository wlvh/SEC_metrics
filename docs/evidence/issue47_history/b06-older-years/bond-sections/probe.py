"""Reproduce the Macy's FY2024 component repair on an already restored root.

Usage: python probe.py <restored-source-inputs> <new-output.json>
No acquisition, provider request, Run, acceptance or production operation.
"""
import hashlib
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / 'scripts'))
from vnext import b06_bond_leases as frozen
from vnext import historical_debt_results as debt
from vnext.historical_bond_sections import inspect_bond_lease_composition, native_bond_members
from vnext.historical_dei import release_aware
from vnext.normal_history_plan import checkpoint_replayed_once
from vnext.normal_period_selection import resolve_period_selection


def main(root, output):
    output = Path(output)
    if output.exists():
        raise ValueError('Output exists; retain previous evidence')
    captured = {}
    original = debt._RECONCILED_GRAMMARS['bond']['inspect']

    def capture(**args):
        captured.update(args)
        return original(**args)

    debt._RECONCILED_GRAMMARS['bond']['inspect'] = capture
    try:
        with patch.object(socket, 'socket', side_effect=AssertionError('NETWORK_FORBIDDEN')):
            with checkpoint_replayed_once():
                selection = resolve_period_selection(repo_root=Path(root), company_id='macys',
                                                     report_end='2025-02-01')
                component = debt.resolve_historical_debt_metric(repo_root=Path(root), company_id='macys',
                    metric_id='B06', period_selection=selection)
            try:
                release_aware(frozen.inspect_bond_debt_scope)(**captured)
                old_reason = None
            except ValueError as error:
                old_reason = str(error)
            composition = inspect_bond_lease_composition(**captured)
            members = native_bond_members(**captured, bonds=composition['bonds'])
    finally:
        debt._RECONCILED_GRAMMARS['bond']['inspect'] = original
    notes = release_aware(frozen)._notes(**captured)
    report = {
        'record_type': 'ISSUE47_REPORTED_BOND_SECTIONS_COMPONENT_DEVELOPMENT',
        'company_id': 'macys', 'fiscal_year': 2024, 'report_end': '2025-02-01',
        'filing': captured['prepared']['filing'],
        'sources': {kind: {'sha256': hashlib.sha256(captured[kind]['raw_bytes']).hexdigest(),
                          'source_reference': captured[kind]['source_reference']}
                    for kind in ['primary', 'xml']},
        'frozen_scope_reason': old_reason,
        'candidate_full_scope_selection': component.get('selection'),
        'candidate_result': component['result'],
        'reported_composition_component': composition,
        'section_native_members': members,
        'source_note_texts': {role: release_aware(frozen).disclosure.text(note['text'])
                              for role, note in notes.items()},
        'calls': [0, 0, 0], 'network_disabled': True,
        'new_runs': 0, 'new_acceptances': 0, 'complete_b06_proven': False,
        'production_authorized': False,
    }
    output.write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps({'frozen_reason': old_reason,
        'candidate_selection': report['candidate_full_scope_selection'],
        'borrowings': composition['bonds']['reported_borrowing'],
        'finance_leases': composition['lease']['recognized_finance_lease'],
        'component_amount': composition['proven_composition_amount'],
        'native_member_count': len(members), 'result_value': component['result']['value']}))


if __name__ == '__main__':
    main(*sys.argv[1:])
