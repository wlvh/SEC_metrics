"""A reported instrument can occur in both maturity classes without merging them."""
import copy
import unittest

from vnext.b06_bond_leases import _bond_schedule, _native_bond_members
from vnext.historical_bond_sections import bond_schedule, native_bond_members

END = '2025-02-01'
LABEL = '7.60% Senior debentures due 2025'
OTHER = '6.70% Senior debentures due 2028'
NS = ('xmlns:xbrli="http://www.xbrl.org/2003/instance" '
      'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" '
      'xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" '
      'xmlns:iso4217="http://www.xbrl.org/2003/iso4217" '
      'xmlns:us-gaap="http://fasb.org/us-gaap/2024" '
      'xmlns:m="http://example.org/issuer/2024"')


def fixture(*, long=7, repeated=True):
    current_label = LABEL if repeated else '7.60% Senior debentures due 2026'
    labels = [current_label, LABEL, OTHER]
    amounts = [6, long, 1]
    roles = ['DebtCurrent', 'DebtInstrumentCarryingAmount', 'DebtInstrumentCarryingAmount']
    contexts = []
    xml_facts = []
    cells = []
    for i, (amount, role) in enumerate(zip(amounts, roles)):
        member = 'CurrentBondMember' if i == 0 and not repeated else 'BondMember' if i < 2 else 'OtherBondMember'
        contexts.append('<xbrli:context id="c' + str(i) + '"><xbrli:entity>'
            '<xbrli:identifier scheme="http://www.sec.gov/CIK">987654</xbrli:identifier>'
            '<xbrli:segment><xbrldi:explicitMember dimension="us-gaap:DebtInstrumentAxis">m:'
            + member + '</xbrldi:explicitMember></xbrli:segment></xbrli:entity>'
            '<xbrli:period><xbrli:instant>' + END + '</xbrli:instant></xbrli:period></xbrli:context>')
        xml_facts.append('<us-gaap:' + role + ' contextRef="c' + str(i)
            + '" unitRef="usd" decimals="-6">' + str(amount * 1000000) + '</us-gaap:' + role + '>')
        cells.append('<ix:nonFraction name="us-gaap:' + role + '" contextRef="c' + str(i)
            + '" unitRef="usd" decimals="-6" scale="6">' + str(amount) + '</ix:nonFraction>')
    row = lambda label, value: '<tr><td>' + label + '</td><td>' + str(value) + '</td><td>0</td></tr>'
    table = ('<table>' + row('', 'February 1, 2025')
        .replace('<td>0</td>', '<td>February 3, 2024</td>')
        + row('', '(millions)') + '<tr><td>Short-term debt:</td></tr>'
        + row(labels[0], cells[0]) + row('', 6) + '<tr><td>Long-term debt:</td></tr>'
        + row(labels[1], cells[1]) + row(labels[2], cells[2])
        + row('Unamortized debt issue costs and discount', '(1)')
        + row('Premium on acquired debt, using an effective interest yield of 6.0% to 7.0%', 2)
        + row('', long + 2) + '</table>')
    unit = '<xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>'
    resources = unit + ''.join(contexts)
    primary = ('<html ' + NS + '><body>' + resources + '<p>The Company\'s debt is as follows:</p>'
               + table + '</body></html>').encode()
    xml = ('<xbrli:xbrl ' + NS + '>' + resources + ''.join(xml_facts) + '</xbrli:xbrl>').encode()
    reports = {k: {'chosen': {'value': str(v * 1000000)}} for k, v in
        {'current': 6, 'gross': long + 7, 'cost': 1, 'premium': 2,
         'carrying': long + 2, 'total_borrowing': long + 8}.items()}
    note = {'text': '<p>The Company\'s debt is as follows:</p>' + table}
    args = {'primary': {'raw_bytes': primary}, 'xml': {'raw_bytes': xml},
            'prepared': {'entity': '987654', 'filing': {'reportDate': END}}}
    return note, reports, args


class HistoricalBondSectionTest(unittest.TestCase):
    def composition(self, **kwargs):
        note, reports, args = fixture(**kwargs)
        bonds = bond_schedule(note, END, reports)
        return bonds, native_bond_members(**args, bonds=bonds)

    def test_both_positive_classes_have_separate_native_values(self):
        bonds, members = self.composition()
        self.assertEqual('15000000', bonds['reported_borrowing'])
        self.assertEqual(3, len(members))
        split = [m for m in members if list(m['dimensions'].values()) == ['m:BondMember']]
        self.assertEqual({'current': '6000000', 'noncurrent': '7000000'},
                         {m['classification']: m['value'] for m in split})

    def test_zero_class_is_preserved_as_a_distinct_source_occurrence(self):
        bonds, members = self.composition(long=0)
        self.assertEqual('8000000', bonds['reported_borrowing'])
        self.assertEqual(3, len(members))
        self.assertTrue(any(m['classification'] == 'noncurrent' and m['value'] == '0' for m in members))

    def test_unique_labels_keep_the_complete_frozen_proof(self):
        note, reports, args = fixture(repeated=False)
        bonds = bond_schedule(note, END, reports)
        self.assertEqual(_bond_schedule(note, END, reports), bonds)
        self.assertEqual(_native_bond_members(**args, bonds=bonds), native_bond_members(**args, bonds=bonds))

    def test_duplicate_within_one_section_is_still_rejected(self):
        note, reports, _ = fixture()
        note['text'] = note['text'].replace('<tr><td></td><td>6</td><td>0</td></tr>',
            '<tr><td>' + LABEL + '</td><td>0</td><td>0</td></tr><tr><td></td><td>6</td><td>0</td></tr>')
        with self.assertRaisesRegex(ValueError, 'BOND_MEMBER_DUPLICATED'):
            bond_schedule(note, END, reports)

    def test_current_and_gross_reconciliations_are_retained(self):
        for role in ['current', 'gross', 'cost', 'premium', 'carrying', 'total_borrowing']:
            with self.subTest(role=role):
                note, reports, _ = fixture()
                reports[role]['chosen']['value'] = '999000000'
                with self.assertRaisesRegex(ValueError, 'RECONCILIATION_CONFLICT|ADJUSTMENT_CONFLICT'):
                    bond_schedule(note, END, reports)

    def test_matching_amount_cannot_move_a_native_fact_to_the_other_class(self):
        note, reports, args = fixture(long=6)
        bonds = bond_schedule(note, END, reports)
        for source in args['primary'], args['xml']:
            source['raw_bytes'] = source['raw_bytes'].replace(b'DebtCurrent', b'DebtInstrumentCarryingAmount')
        with self.assertRaisesRegex(ValueError, 'BOND_MEMBER_NOT_IN_CURRENT_COMPOSITION'):
            native_bond_members(**args, bonds=bonds)

    def test_disagreeing_xml_amount_cannot_use_the_visible_note(self):
        note, reports, args = fixture()
        bonds = bond_schedule(note, END, reports)
        args['xml']['raw_bytes'] = args['xml']['raw_bytes'].replace(b'>6000000<', b'>9000000<')
        with self.assertRaisesRegex(ValueError, 'PRECISION_CONFLICT'):
            native_bond_members(**args, bonds=bonds)

    def test_unrelated_grid_or_changed_context_is_not_a_member_witness(self):
        note, reports, original = fixture()
        bonds = bond_schedule(note, END, reports)
        for before, after in [(b'<td>0</td>', b'<td>99</td>'),
                              (b'http://www.sec.gov/CIK', b'http://example.org/not-cik')]:
            with self.subTest(change=before):
                args = copy.deepcopy(original)
                args['primary']['raw_bytes'] = args['primary']['raw_bytes'].replace(before, after)
                with self.assertRaisesRegex(ValueError, 'BOND_MEMBER_NOT_IN_CURRENT_COMPOSITION|ENTITY_SCHEME_NOT_PROVEN'):
                    native_bond_members(**args, bonds=bonds)

    def test_generated_table_order_and_entity_spelling_do_not_change_source_cells(self):
        note, reports, args = fixture()
        bonds = bond_schedule(note, END, reports)
        args['primary']['raw_bytes'] = args['primary']['raw_bytes'].replace(b'<body>',
            b'<body><table><tr><td>Unrelated preceding table</td></tr></table>').replace(
            b'<td>0</td>', b'<td>&#48;</td>')
        self.assertEqual(3, len(native_bond_members(**args, bonds=bonds)))

    def test_changed_cell_span_cannot_keep_the_old_schedule_identity(self):
        note, reports, args = fixture()
        bonds = bond_schedule(note, END, reports)
        args['primary']['raw_bytes'] = args['primary']['raw_bytes'].replace(
            b'<td>0</td>', b'<td colspan="2">0</td>', 1)
        with self.assertRaisesRegex(ValueError, 'BOND_MEMBER_NOT_IN_CURRENT_COMPOSITION'):
            native_bond_members(**args, bonds=bonds)


if __name__ == '__main__':
    unittest.main()
