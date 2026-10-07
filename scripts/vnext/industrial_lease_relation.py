"""A reported finance-lease component is not another additive debt balance.

This reads a specific inclusive table assertion, not a debt-completeness rule.
The caller has already checked each original's subject, period, USD, dimensions,
amount and visible industrial column. Missing evidence stays unresolved.
"""
from decimal import Decimal
import re

from .b06_disclosure import label
from .b06_inclusive_table import _InclusiveInlineNotes
from .deterministic_router import _numeric_xbrl_value
from .r5_b06_scope import precision_choice


def inspect_inclusion(*, primary, parsed, reported_components, lease_reports):
    notes = _InclusiveInlineNotes()
    notes.feed(primary['raw_bytes'].decode('utf-8-sig')); notes.close()
    if notes.active or notes.excluded:
        raise ValueError('INDUSTRIAL_LEASE_NOTE_TRUNCATED')
    debt_notes = [f for f in notes.facts
                  if f['attrs'].get('name', '').split(':')[-1] == 'DebtDisclosureTextBlock']
    unresolved = {'status': 'UNRESOLVED', 'additional_debt_amount': None,
                  'reason': 'REPORTED_LEASE_INCLUSION_NOT_ESTABLISHED', 'relationships': []}
    relationships = []
    for role, concept in [('current_debt', 'financeleaseliabilitycurrent'),
                          ('noncurrent_debt', 'financeleaseliabilitynoncurrent')]:
        parent = reported_components.get(role)
        component = {kind: rows.get(concept, []) for kind, rows in lease_reports.items()}
        if not parent or not component.get('primary') or not component.get('xml'):
            return unresolved
        choice = precision_choice(component['primary'] + component['xml'])
        value = Decimal(choice['value'])
        if value < 0 or value > Decimal(parent['value']):
            return unresolved
        supported = []
        for evidence in parent['visible_table_evidence']:
            table, cell = evidence['table'], evidence['cell']
            start = min((c['row_index'] for c in evidence['column_headers']), default=0)
            end = cell['origin_row_index']
            previous_totals = [e['cell']['origin_row_index']
                for other_role, other in reported_components.items() if other_role != role
                for e in other['visible_table_evidence']
                if e['table']['table_id'] == table['table_id']
                and start <= e['cell']['origin_row_index'] < end]
            if previous_totals:
                start = max(previous_totals) + 1
            rows = [(i, r) for i, r in enumerate(table['rows'][start:end], start)
                    if re.fullmatch(r'Other debt \(including finance leases\)\s*\([a-z]\)',
                                    label(r), re.I)]
            if not rows:
                continue
            row_index, row = rows[-1]
            parent_reports = [r for r in parent['source_reports']['primary']
                              if r['ordinal'] == evidence['ordinal'] and r['unit'] == 'USD']
            carrier_cells = [c for c in row['cells'] if c['is_origin']
                             and c['column_index'] == cell['column_index']
                             and c['colspan'] == cell['colspan']]
            if len(parent_reports) != 1 or len(carrier_cells) != 1:
                continue
            scale = parent_reports[0].get('reported_scale')
            if scale is None:
                continue
            try:
                parent_visible = _numeric_xbrl_value(text=cell['text'], scale=scale, sign='')
                carrier_amount = _numeric_xbrl_value(text=carrier_cells[0]['text'], scale=scale, sign='')
            except ValueError:
                continue
            if (Decimal(parent_visible) != Decimal(parent_reports[0]['value'])
                    or value > Decimal(carrier_amount)):
                continue
            # The same original note must contain the proved parent and the
            # lease facts. A similarly named balance elsewhere is insufficient.
            lease_ordinals = {r['ordinal'] for r in component['primary']}
            parent_context = parent['source_reports']['primary'][0]['context']
            matching = [n for n in debt_notes
                        if evidence['ordinal'] in notes.ordinals(n)
                        and lease_ordinals.intersection(notes.ordinals(n))
                        and n['attrs'].get('contextref') in parsed.contexts
                        and parsed.contexts[n['attrs']['contextref']]['period_end'] == parent_context['period_end']
                        and parsed.contexts[n['attrs']['contextref']]['entity_identifier'] == parent_context['entity_identifier']]
            if len(matching) != 1:
                continue
            supported.append({'parent_role': role, 'parent_amount': parent['value'],
                'component_amount': choice['value'], 'unit': 'USD',
                'table_id': table['table_id'], 'inclusive_row_index': row_index,
                'inclusive_label': label(row), 'total_cell': cell,
                'inclusive_amount': carrier_amount, 'inclusive_cell': carrier_cells[0],
                'reporting_scale': scale,
                'source_reference': primary['source_reference'],
                'parent_ordinal': evidence['ordinal'],
                'component_reports': {**component, 'primary': [r for r in component['primary']
                    if r['ordinal'] in notes.ordinals(matching[0])]},
                'note_attributes': matching[0]['attrs']})
        if not supported:
            return unresolved
        relationships.append({'role': role, 'amount': choice['value'],
                              'status': 'ALREADY_INCLUDED', 'evidence': supported})
    return {'status': 'REPORTED_INCLUDED', 'additional_debt_amount': '0',
            'reason': 'INCLUSIVE_REPORTED_DEBT_TABLE', 'relationships': relationships,
            'component_total': str(sum(Decimal(r['amount']) for r in relationships)),
            'complete_B06': False}
