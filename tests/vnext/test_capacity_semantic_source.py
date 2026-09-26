"""B13 complete-source coverage cannot be replaced by a keyword selection."""
from copy import deepcopy
from collections import Counter
import json
import os
from pathlib import Path
import unittest

from tests.vnext.test_normal_zero_ai_results import original_sources_only
from vnext.canonical import content_hash
from vnext.capacity_utilization_source import policy
from vnext.capacity_semantic_source import capacity_source_from_complete_annual, prepare_capacity_semantic_source, native_capacity_roles
from vnext.normal_source_authority import ROOT
from vnext.r6_semantic_source import _seal_unit


def sealed(body):
    return {**body, 'semantic_source_id': content_hash(value=body)}


class CapacitySemanticSourceTest(unittest.TestCase):
    def setUp(self):
        self.rules, _ = policy()
        visible = _seal_unit('doc', 'VISIBLE_TEXT', {'blocks': [
            {'block_index': 0, 'text': 'The factory can make 80 units a year.'},
            {'block_index': 1, 'text': 'Relevant information without any navigation keyword.'}]}, 0)
        native = _seal_unit('doc', 'NATIVE_FACTS', {'facts': [{'fact': {
            'ordinal': 1, 'qualified_name': 'custom:HiddenOutput', 'text': '75'}}]}, 0)
        self.body = {'company_id': 'enphase_energy', 'metric_id': 'D04',
                     'units': [visible, native], 'required_unit_ids': [visible['unit_id'], native['unit_id']],
                     'source_serialization_complete': True, 'documents': [{
                         'document_id': 'doc', 'visible_block_count': 2,
                         'native_coverage': {'fact_count': 1, 'supplement_count': 0},
                         'source_unit_ids': [visible['unit_id'], native['unit_id']]}]}

    def test_keyword_miss_retains_every_visible_and_hidden_item(self):
        original = sealed(self.body)
        result = capacity_source_from_complete_annual(source=original, rules=self.rules)
        self.assertEqual(result['units'], original['units'])
        self.assertEqual(result['capacity_navigation'], [])
        self.assertFalse(result['absence_established'])
        self.assertFalse(result['numeric_pair_completeness_verified'])
        self.assertFalse(result['native_result_created'])

    def test_resealed_omission_duplicate_and_wrong_document_do_not_pass_coverage(self):
        for attack in ['omit_native', 'duplicate_unit', 'wrong_document', 'omit_visible_block']:
            body = deepcopy(self.body)
            if attack == 'omit_native':
                body['units'].pop(); body['required_unit_ids'].pop()
                body['documents'][0]['source_unit_ids'].pop()
            elif attack == 'duplicate_unit':
                body['units'].append(body['units'][0]); body['required_unit_ids'].append(body['required_unit_ids'][0])
            elif attack == 'wrong_document':
                body['units'][0]['document_id'] = 'foreign'
            else:
                body['units'][0]['payload']['blocks'].pop()
            with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, 'B13_.*(?:SET|COVERAGE)_CHANGED'):
                capacity_source_from_complete_annual(source=sealed(body), rules=self.rules)

    def test_credit_capacity_requires_concept_namespace_and_actual_currency_unit(self):
        unit = {'unit_id': 'test-native-unit', 'kind': 'NATIVE_FACTS', 'payload': {
            'facts': [{'expanded_concept': ['http://fasb.org/us-gaap/2025', 'LineOfCreditFacilityMaximumBorrowingCapacity'],
                       'fact': {'ordinal': 1, 'qualified_name': 'us-gaap:LineOfCreditFacilityMaximumBorrowingCapacity',
                                'unit_ref': 'u', 'text': '100'}}],
            'units': {'u': {'namespace_environment_id': 'env', 'raw_xml':
                '<xbrli:unit id="u"><xbrli:measure>iso:USD</xbrli:measure></xbrli:unit>'}},
            'namespace_environments': {'env': {'xbrli': 'http://www.xbrl.org/2003/instance',
                                              'iso': 'http://www.xbrl.org/2003/iso4217'}}}}
        result = native_capacity_roles([unit])[0]
        self.assertEqual(result['role'], 'MONETARY_CREDIT_FACILITY_CAPACITY')
        self.assertFalse(result['production_or_physical_capacity_quantity'])
        for attack in ['concept_namespace', 'unit_namespace', 'physical_unit', 'ratio_unit']:
            bad = deepcopy(unit)
            if attack == 'concept_namespace':
                bad['payload']['facts'][0]['expanded_concept'][0] = 'https://issuer.example/2025'
            elif attack == 'unit_namespace':
                bad['payload']['namespace_environments']['env']['iso'] = 'https://issuer.example/units'
            elif attack == 'physical_unit':
                bad['payload']['units']['u']['raw_xml'] = '<xbrli:unit id="u"><xbrli:measure>units</xbrli:measure></xbrli:unit>'
            else:
                bad['payload']['units']['u']['raw_xml'] = '<xbrli:unit id="u"><xbrli:divide><xbrli:unitNumerator><xbrli:measure>iso:USD</xbrli:measure></xbrli:unitNumerator><xbrli:unitDenominator><xbrli:measure>units</xbrli:measure></xbrli:unitDenominator></xbrli:divide></xbrli:unit>'
            with self.subTest(attack=attack):
                result = native_capacity_roles([bad])[0]
                self.assertEqual(result['role'], 'ROLE_UNRESOLVED')
                self.assertIsNone(result['production_or_physical_capacity_quantity'])


class CapacityCompleteSourceMaterialTest(unittest.TestCase):
    def test_actual_ford_and_enphase_complete_sources_are_preserved(self):
        output = os.environ.get('B13_COMPLETE_SOURCE_OUTPUT')
        directory = Path(output).resolve() if output else None
        if directory:
            self.assertFalse(directory.exists()); directory.mkdir(parents=True)
        with original_sources_only():
            for company in ['ford_motor_company', 'enphase_energy']:
                result = prepare_capacity_semantic_source(repo_root=ROOT, company_id=company)
                counts = dict(Counter(u['kind'] for u in result['units']))
                self.assertGreater(counts['VISIBLE_TEXT'], 0)
                self.assertGreater(counts['NATIVE_FACTS'], 0)
                self.assertGreater(counts['NATIVE_SUPPLEMENTS'], 0)
                self.assertFalse(result['absence_established'])
                self.assertFalse(result['native_result_created'])
                self.assertEqual(result['required_unit_ids'], [u['unit_id'] for u in result['units']])
                roles = result['native_capacity_role_assessments']
                if company == 'ford_motor_company':
                    self.assertEqual(len(roles), 13)
                    self.assertTrue(all(r['role'] == 'MONETARY_CREDIT_FACILITY_CAPACITY' for r in roles))
                    self.assertTrue(all(r['declared_unit']['measures'][0][1] == 'USD' for r in roles))
                if directory:
                    (directory / (company + '.json')).write_text(json.dumps(result, ensure_ascii=False) + '\n')
                print(company, counts, 'complete source units; semantic/native assessment pending', flush=True)


if __name__ == '__main__':
    unittest.main()
