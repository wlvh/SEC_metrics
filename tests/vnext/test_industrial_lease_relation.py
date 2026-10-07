"""Tiny relation controls; no company installation or paid requests."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from vnext.industrial_lease_relation import inspect_inclusion
from vnext.ordinary_special_debt_scope import inspect_special_scope, prepare_special_debt_case


def fixture():
    context = {'entity_identifier': '1', 'period_end': '2025-12-31'}
    labels = ['2025', 'Other debt (including finance leases) (a)', 'Total current debt',
              'Other debt (including finance leases) (a)', 'Total noncurrent debt']
    table = {'table_id': 'table_1', 'rows': [{'cells': [{'is_origin': True,
        'text': x, 'column_index': 0}, {'is_origin': True, 'column_index': 1,
        'colspan': 1, 'text': amount}]} for x, amount in zip(labels, ('2025','25','100','50','200'))]}
    body = ('<ix:nonnumeric name="us-gaap:DebtDisclosureTextBlock" contextref="n">'
            '<ix:nonfraction contextref="c">100</ix:nonfraction>'
            '<ix:nonfraction contextref="c">10</ix:nonfraction>'
            '<ix:nonfraction contextref="c">200</ix:nonfraction>'
            '<ix:nonfraction contextref="c">20</ix:nonfraction>'
            '</ix:nonnumeric>').encode()
    parents = {}
    leases = {'primary': {}, 'xml': {}}
    for role, concept, parent_ord, lease_ord, row, parent_value, lease_value in (
        ('current_debt', 'financeleaseliabilitycurrent', 2, 3, 2, '100', '10'),
        ('noncurrent_debt', 'financeleaseliabilitynoncurrent', 4, 5, 4, '200', '20')):
        parents[role] = {'value': parent_value,
            'source_reports': {'primary': [{'context': context, 'ordinal': parent_ord,
                'unit': 'USD', 'value': parent_value, 'reported_scale': '0'}]},
            'visible_table_evidence': [{'ordinal': parent_ord, 'table': table,
                'cell': {'origin_row_index': row, 'column_index': 1, 'colspan': 1,
                    'text': parent_value}, 'column_headers': [{'row_index': 0}]}]}
        for kind in leases:
            leases[kind][concept] = [{'ordinal': lease_ord, 'value': lease_value, 'decimals': 'INF'}]
    return {'primary': {'raw_bytes': body, 'source_reference': {'source': 'TEST_ONLY'}},
            'parsed': SimpleNamespace(contexts={'n': context}),
            'reported_components': parents, 'lease_reports': leases}


class IndustrialLeaseRelationTest(unittest.TestCase):
    def test_explicit_unproved_route_is_suspended_before_source_processing(self):
        with self.assertRaisesRegex(ValueError, 'SUSPENDED_CARRIER_NATIVE_UNIT_UNVERIFIED'):
            inspect_special_scope(primary={}, xml={}, annual={}, financial_institution=False,
                                  rules={}, reported_relations=True)
        with self.assertRaisesRegex(ValueError, 'SUSPENDED_CARRIER_NATIVE_UNIT_UNVERIFIED'):
            prepare_special_debt_case(repo_root=None, company_id='TEST_ONLY', reported_relations=True)

    def test_included_lease_is_not_an_additive_balance(self):
        result = inspect_inclusion(**fixture())
        self.assertEqual('REPORTED_INCLUDED', result['status'])
        self.assertEqual('30', result['component_total'])
        self.assertEqual('0', result['additional_debt_amount'])
        self.assertFalse(result['complete_B06'])

    def test_excluded_caption_cannot_prove_inclusion(self):
        args = fixture()
        for evidence in args['reported_components']['current_debt']['visible_table_evidence']:
            for row in evidence['table']['rows']:
                row['cells'][0]['text'] = row['cells'][0]['text'].replace('including', 'excluding')
        self.assertEqual('UNRESOLVED', inspect_inclusion(**args)['status'])

    def test_lease_elsewhere_is_not_the_table_component(self):
        args = fixture(); raw = args['primary']['raw_bytes']
        lease = b'<ix:nonfraction contextref="c">20</ix:nonfraction>'
        args['primary']['raw_bytes'] = raw.replace(lease, b'').replace(b'</ix:nonnumeric>', b'</ix:nonnumeric>'+lease)
        self.assertEqual('UNRESOLVED', inspect_inclusion(**args)['status'])

    def test_missing_xml_or_excess_component_stays_unresolved(self):
        for change in ('missing', 'excess'):
            args = fixture()
            if change == 'missing': args['lease_reports']['xml'] = {}
            else:
                for kind in args['lease_reports']:
                    args['lease_reports'][kind]['financeleaseliabilitycurrent'][0]['value'] = '101'
            self.assertEqual('UNRESOLVED', inspect_inclusion(**args)['status'])

    def test_disagreeing_originals_do_not_choose_a_convenient_amount(self):
        args = fixture()
        args['lease_reports']['xml']['financeleaseliabilitycurrent'][0]['value'] = '11'
        with self.assertRaisesRegex(ValueError, 'DEBT_SAME_PRECISION_CONFLICT'):
            inspect_inclusion(**args)

    def test_wrong_note_entity_or_period_cannot_supply_relationship(self):
        for key, value in [('entity_identifier', '2'), ('period_end', '2024-12-31')]:
            args = fixture(); args['parsed'].contexts = {'n': {**args['parsed'].contexts['n'], key: value}}
            self.assertEqual('UNRESOLVED', inspect_inclusion(**args)['status'])

    def test_current_caption_cannot_prove_noncurrent_inclusion(self):
        args = fixture()
        args['reported_components']['noncurrent_debt']['visible_table_evidence'][0]['table']['rows'][3]['cells'][0]['text'] = 'Other debt'
        self.assertEqual('UNRESOLVED', inspect_inclusion(**args)['status'])

    def test_same_component_repeated_elsewhere_does_not_require_every_copy_in_one_note(self):
        args = fixture()
        original = args['lease_reports']['primary']['financeleaseliabilitycurrent'][0]
        args['lease_reports']['primary']['financeleaseliabilitycurrent'].append({**original, 'ordinal': 6})
        args['primary']['raw_bytes'] += b'<ix:nonfraction contextref="c">10</ix:nonfraction>'
        self.assertEqual('REPORTED_INCLUDED', inspect_inclusion(**args)['status'])

    def test_component_exceeding_inclusive_row_even_below_total_is_unresolved(self):
        args = fixture()
        for kind in args['lease_reports']:
            args['lease_reports'][kind]['financeleaseliabilitycurrent'][0]['value'] = '30'
        self.assertEqual('UNRESOLVED', inspect_inclusion(**args)['status'])

    def test_scale_missing_changed_or_unit_suffix_cannot_inflate_carrier(self):
        for change in ('missing', 'different', 'suffix'):
            args = fixture(); parent = args['reported_components']['current_debt']
            if change == 'missing': parent['source_reports']['primary'][0].pop('reported_scale')
            elif change == 'different': parent['source_reports']['primary'][0]['reported_scale'] = '6'
            else: parent['visible_table_evidence'][0]['table']['rows'][1]['cells'][1]['text'] = '25 million'
            self.assertEqual('UNRESOLVED', inspect_inclusion(**args)['status'])


if __name__ == '__main__':
    unittest.main()
