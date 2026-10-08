"""Registry 4 transforms source text; it does not infer a missing debt balance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vnext.governance_signals import _source_value
from vnext.historical_bond_sections import financing_inventory, source_value
from vnext import historical_bond_sections as reader

REGISTRY = 'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12'


class HistoricalFixedZeroTest(unittest.TestCase):
    def test_missing_or_invalid_version_rule_fails_closed(self):
        original = json.loads((reader.ROOT / reader.FIXED_ZERO_RULE_PATH).read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            path = root / reader.FIXED_ZERO_RULE_PATH
            path.parent.mkdir()
            with patch.object(reader, 'ROOT', root):
                with self.assertRaises(ValueError):
                    source_value(*self.arguments())
                for rule in [[], dict(original, canonical_value='1'),
                             dict(original, schema_version=True),
                             dict(original, local_name='numdash'),
                             dict(original, namespace='http://example.org/transform'),
                             dict(original, extra='unapproved')]:
                    path.write_text(json.dumps(rule))
                    with self.subTest(rule=rule), self.assertRaisesRegex(ValueError,
                            'HISTORICAL_INLINE_FIXED_ZERO_RULE_INVALID'):
                        source_value(*self.arguments())

    def arguments(self, text='no', transform='fixed-zero'):
        return ({'text': text, 'scale': '6', 'sign': ''}, {
            'attrs': {'format': 'ixt:' + transform},
            'namespaces': {'ixt': REGISTRY,
                           'xsi': 'http://www.w3.org/2001/XMLSchema-instance'}})

    def test_exact_registered_transform_accepts_any_text_without_mutation(self):
        for text in ['no', 'none', '', '—', '123', 'There were no loans.']:
            args = self.arguments(text)
            before = copy.deepcopy(args)
            self.assertEqual('0', source_value(*args))
            self.assertEqual(before, args)

    def test_plain_word_or_other_transform_does_not_infer_zero(self):
        for transform in ['', 'numdash', 'num-dot-decimal', 'fixed-empty']:
            args = self.arguments(transform=transform)
            if not transform:
                args[1]['attrs'].pop('format')
            with self.subTest(transform=transform), self.assertRaises(ValueError):
                source_value(*args)

    def test_unregistered_namespace_or_local_name_cannot_supply_zero(self):
        for uri in [REGISTRY + '/extra', REGISTRY.replace('2020-02-12', '2015-02-26'),
                    'https://example.org/inlineXBRL/transformation/2020-02-12', '']:
            args = self.arguments()
            args[1]['namespaces']['ixt'] = uri
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                source_value(*args)
        args = self.arguments(transform='Fixed-Zero')
        with self.assertRaises(ValueError):
            source_value(*args)

    def test_nil_and_unsupported_sign_still_reject(self):
        for attr, value, reason in [('xsi:nil', 'true', 'NIL_TARGET'),
                                    ('xsi:nil', '1', 'NIL_TARGET'),
                                    ('sign', '+', 'UNSUPPORTED_SIGN')]:
            args = self.arguments()
            args[1]['attrs'][attr] = value
            with self.subTest(attr=attr, value=value), self.assertRaisesRegex(ValueError, reason):
                source_value(*args)
        for nil in ['false', '0']:
            args = self.arguments()
            args[1]['attrs'].update({'xsi:nil': nil, 'sign': '-'})
            self.assertEqual('0', source_value(*args))

    def test_numeric_and_legacy_dash_results_keep_frozen_behavior(self):
        for text, transform in [('12.3', 'num-dot-decimal'), ('—', 'numdash'),
                                ('0', 'fixed-zero')]:
            args = self.arguments(text, transform)
            self.assertEqual(_source_value(*args), source_value(*args))
        with self.assertRaisesRegex(ValueError, 'ZERO_TRANSFORM_TEXT_CONFLICT'):
            _source_value(*self.arguments())

    def inventory(self, xml_value='0', unit='USD'):
        namespaces = ('xmlns:xbrli="http://www.xbrl.org/2003/instance" '
            'xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" '
            'xmlns:us-gaap="http://fasb.org/us-gaap/2024" '
            'xmlns:iso4217="http://www.xbrl.org/2003/iso4217" '
            'xmlns:ixt="' + REGISTRY + '"')
        resources = ('<xbrli:context id="c"><xbrli:entity>'
            '<xbrli:identifier scheme="http://www.sec.gov/CIK">987654</xbrli:identifier>'
            '</xbrli:entity><xbrli:period><xbrli:instant>2025-02-01</xbrli:instant>'
            '</xbrli:period></xbrli:context><xbrli:unit id="u">'
            '<xbrli:measure>iso4217:' + unit + '</xbrli:measure></xbrli:unit>')
        primary = ('<html ' + namespaces + '><body>' + resources
            + '<ix:nonFraction name="us-gaap:LineOfCredit" contextRef="c" unitRef="u" '
              'decimals="INF" format="ixt:fixed-zero">no</ix:nonFraction></body></html>').encode()
        xml = ('<xbrli:xbrl ' + namespaces + '>' + resources
            + '<us-gaap:LineOfCredit contextRef="c" unitRef="u" decimals="INF">'
            + xml_value + '</us-gaap:LineOfCredit></xbrli:xbrl>').encode()
        composition = {'balance_reports': {}, 'supplier': {'native_reports': {}},
                       'lease': {'maturity': {}, 'finance_reports': {}}}
        return financing_inventory({'raw_bytes': primary}, {'raw_bytes': xml},
            {'entity': '987654', 'filing': {'reportDate': '2025-02-01'}},
            composition, [], {})

    def test_native_inventory_reconciles_word_zero_with_xml_zero(self):
        result = self.inventory()
        self.assertEqual({'primary', 'xml'}, set(result))
        for rows in result.values():
            self.assertEqual('0', rows[0]['value'])
            self.assertEqual('EXPLICIT_CURRENT_ZERO', rows[0]['disposition'])

    def test_nonzero_xml_and_wrong_currency_cannot_reconcile(self):
        with self.assertRaisesRegex(ValueError, 'UNRESOLVED_FINANCING_FACT'):
            self.inventory(xml_value='1')
        with self.assertRaisesRegex(ValueError, 'UNRESOLVED_FINANCING_FACT'):
            self.inventory(unit='EUR')


if __name__ == '__main__':
    unittest.main()
