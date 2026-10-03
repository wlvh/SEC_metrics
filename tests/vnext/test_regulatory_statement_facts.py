"""Aggregate present facts do not require named cases or imply case counts."""
from copy import deepcopy
import json
import os
import unittest

from vnext.regulatory_statement_facts import aggregate_involvement_facts, check_aggregate_classification
from vnext.normal_source_authority import ROOT
from tests.vnext.test_normal_zero_ai_results import original_sources_only


class RegulatoryStatementFactsTest(unittest.TestCase):
    def setUp(self):
        self.aliases = [{'text': 'Example Bank', 'basis': 'SOURCE_ALIAS', 'support': None},
                        {'text': 'We', 'basis': 'SOURCE_AUTHOR_FIRST_PERSON', 'support': None}]
        self.sentence = ('Example Bank is named as a defendant or is otherwise involved in many civil and '
                         'governmental legal proceedings, including class actions, derivative actions and '
                         'other litigation or disputes with third parties, as well as investigations and '
                         'enforcement actions by U.S. and non-U.S. governmental authorities, including '
                         'criminal proceedings.')

    def test_affirmative_aggregate_fact_keeps_case_details_unextracted(self):
        rows = aggregate_involvement_facts(text=self.sentence, aliases=self.aliases)
        self.assertEqual(len(rows), 1)
        fact = rows[0]
        self.assertEqual((fact['assertion'], fact['reported_time'], fact['detail_level']),
                         ('AFFIRMATIVE', 'CURRENT_AS_REPORTED', 'AGGREGATE_INVOLVEMENT'))
        self.assertEqual(fact['status'], 'SOURCE_REPORTED_FACT')
        self.assertIsNone(fact['case_count']); self.assertIsNone(fact['case_identity'])
        self.assertFalse(fact['unlawfulness_or_guilt_asserted'])
        self.assertFalse(fact['whole_source_coverage_proven'])

    def test_hypothetical_negated_other_subject_and_past_are_not_current_facts(self):
        texts = [self.sentence.replace('is named', 'may be named'),
                 self.sentence.replace('is named', 'was named'),
                 self.sentence.replace('is otherwise involved', 'is not otherwise involved'),
                 self.sentence.replace('Example Bank', 'A customer'),
                 self.sentence.replace('as well as investigations', 'excluding investigations'),
                 self.sentence.replace('as well as investigations', 'as well as possible investigations'),
                 'If regulators act, ' + self.sentence]
        for text in texts:
            with self.subTest(text=text):
                self.assertFalse(any(f['status'] == 'SOURCE_REPORTED_FACT'
                                     for f in aggregate_involvement_facts(text=text, aliases=self.aliases)))

    def test_government_elsewhere_does_not_prove_the_action_relationship(self):
        text = ('We are involved in various legal matters, including private investigations '
                'by customers and disputes with governmental authorities.')
        self.assertEqual(aggregate_involvement_facts(text=text, aliases=self.aliases), [])
        for phrase in ['litigation challenging government investigations',
                       'private claims about regulatory investigations',
                       'government investigations conducted by private investigators']:
            text = 'We are involved in various legal matters, including ' + phrase + '.'
            self.assertFalse(any(f['status'] == 'SOURCE_REPORTED_FACT'
                                 for f in aggregate_involvement_facts(text=text, aliases=self.aliases)))

    def test_quote_historical_intro_or_linked_closure_requires_interpretation(self):
        for arguments in [{'quoted': True}, {'context': ['In our 2017 annual report:']},
                          {'context': ['These investigations have been closed.']}]:
            with self.subTest(arguments=arguments):
                rows = aggregate_involvement_facts(text=self.sentence, aliases=self.aliases, **arguments)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['status'], 'SEMANTIC_REVIEW_REQUIRED')

    def test_fact_conflict_rejects_erasure_without_rewriting_proposal(self):
        facts = aggregate_involvement_facts(text=self.sentence, aliases=self.aliases)
        before = deepcopy(facts)
        for kind, status in [('CONDITIONAL_OR_BOILERPLATE', 'CONDITIONAL'),
                             ('OTHER_MEANING', 'NOT_AN_ACTION_STATEMENT'),
                             ('CURRENT_REGULATORY_ACTION', 'NOT_STATED')]:
            with self.assertRaisesRegex(ValueError, 'AGGREGATE_FACT_CLASSIFICATION_CONFLICT'):
                check_aggregate_classification(facts=facts, kind=kind, reported_status=status)
        self.assertEqual(facts, before)
        self.assertEqual(check_aggregate_classification(facts=facts, kind='CURRENT_REGULATORY_ACTION',
                                                       reported_status='ONGOING_AS_REPORTED'), facts)

    def test_preserved_jpm_repair_sample_is_regression_not_unseen_holdout(self):
        saved = json.loads((ROOT / 'docs/evidence/issue28_continuous/regulatory-current-involvement/holdout-assessment.json').read_text())
        # Read the already committed exact source excerpt; the full source
        # identity/alias test is a separate material test, not inferred here.
        def find_text(value):
            if isinstance(value, dict):
                if isinstance(value.get('text'), str) and value['text'].startswith('JPMorganChase is named'):
                    return value['text']
                for child in value.values():
                    found = find_text(child)
                    if found: return found
            if isinstance(value, list):
                for child in value:
                    found = find_text(child)
                    if found: return found
        text = find_text(saved)
        self.assertIsNotNone(text)
        facts = aggregate_involvement_facts(text=text, aliases=[
            {'text': 'JPMorganChase', 'basis': 'REGRESSION_FIXTURE_ONLY', 'support': None}])
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]['status'], 'SOURCE_REPORTED_FACT')
        self.assertEqual(facts[0]['statement_text'], text.split(' Actions currently')[0])


class RegulatoryStatementSourceMaterialTest(unittest.TestCase):
    def test_current_jpm_source_alias_and_proposal_conflict(self):
        from vnext.r6_regulatory_semantics import prepare_regulatory_semantic_source, requests_from_source, validate_response
        from vnext.canonical import canonical_json_bytes
        output = os.environ.get('D03_STATEMENT_MATERIAL_OUTPUT')
        if output:
            from pathlib import Path
            path = Path(output); self.assertFalse(path.exists())
        with original_sources_only():
            source = prepare_regulatory_semantic_source(repo_root=ROOT, company_id='jpmorgan_chase')
            requests = requests_from_source(source)
        request = next(r for r in requests if any(f['status'] == 'SOURCE_REPORTED_FACT'
                                                 for f in r['source_statement_facts']))
        fact = next(f for f in request['source_statement_facts'] if f['status'] == 'SOURCE_REPORTED_FACT')
        self.assertEqual(fact['subject_binding']['basis'], 'EXPLICIT_SAME_NAME_PARENTHETICAL')
        self.assertIn('JPMorgan Chase & Co.', fact['subject_binding']['support']['text'])
        unit = request['units'][0]
        response = {'request_id': request['request_id'], 'units': [{
            'unit_id': unit['unit_id'], 'reviewed': True, 'findings': [{
                'kind': 'CURRENT_REGULATORY_ACTION', 'subject': 'TARGET_REGISTRANT',
                'reported_status': 'ONGOING_AS_REPORTED', 'event_dates': [],
                'evidence': [{'kind': 'VISIBLE_BLOCK', 'source_index': fact['block_index']}],
                'reason': 'Recorded test of the source-bound aggregate relation; case details not inferred.'}],
            'context_only_source_indices': [a['source_index'] for a in request['required_candidate_assessments']
                                           if a['source_index'] != fact['block_index']],
            'unresolved': ['Other source findings have not been semantically assessed in this test.']}]}
        checked = validate_response(request=request, raw_response=canonical_json_bytes(value=response))
        self.assertFalse(checked['semantic_correctness_verified'])
        self.assertEqual(checked['findings'][0]['event_dates'], [])
        for mutation in ['conditional', 'other_entity', 'context_only']:
            bad = deepcopy(response)
            row = bad['units'][0]
            if mutation == 'conditional':
                row['findings'][0].update(kind='CONDITIONAL_OR_BOILERPLATE', reported_status='CONDITIONAL')
            elif mutation == 'other_entity':
                row['findings'][0].update(kind='OTHER_ENTITY', subject='OTHER_ENTITY')
            else:
                row['findings'] = []; row['context_only_source_indices'].append(fact['block_index'])
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'AGGREGATE_FACT_CLASSIFICATION_CONFLICT'):
                validate_response(request=request, raw_response=canonical_json_bytes(value=bad))
        if output:
            path.write_text(json.dumps({'source_id': source['semantic_source_id'], 'source_fact': fact,
                'request_id': request['request_id'], 'negative_cases': ['conditional', 'other_entity', 'context_only'],
                'sample_role': 'PREVIOUSLY_USED_REPAIR_REGRESSION', 'model_calls': 0,
                'native_result_created': False, 'semantic_correctness_verified': False}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main()
