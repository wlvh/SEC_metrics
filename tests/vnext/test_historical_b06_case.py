"""Selected B06 controls; the public computation substitute is explicitly constructed."""
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

from vnext import historical_b06_case as history


class HistoricalB06CaseTest(TestCase):
    def setUp(self):
        self.source = Path('/constructed/saved-source')
        self.filing = {'accessionNumber': 'constructed-annual', 'reportDate': '2024-12-31'}
        self.original = {'company_id': 'constructed', 'entity': '1', 'filing': self.filing,
            'subject_policy': {'mode': 'CONTINUOUS_PRIMARY'}, 'amendments': [],
            'source_proofs': []}
        self.annual = {**self.original, 'original_input': self.original}
        self.primary = {'raw_blob': {'media_type': 'text/html'}, 'source_reference': {},
                        'raw_bytes': b'constructed primary'}
        self.xml = {'raw_blob': {'media_type': 'application/xml'}}
        self.reader = Mock()
        self.reader.auditor_filing.return_value = [self.primary, self.xml]
        self.reader.proofs = {}
        self.reader.records = {}
        self.reader.file_sets = []

    def prepare(self):
        return history.prepare_selected_debt_sources(repo_root=self.source,
            company_id='constructed', fiscal_year=2024)

    def test_selected_year_is_revalidated_and_original_filing_reads_both_media(self):
        selection = {'constructed_control': True}
        with patch.object(history, 'resolve_period_selection', return_value=selection) as select, \
             patch.object(history, 'prepare_historical_annual_input', return_value=self.annual) as annual, \
             patch.object(history, '_Sources', return_value=self.reader):
            selected = self.prepare()
        select.assert_called_once_with(repo_root=self.source, company_id='constructed',
                                       fiscal_year=2024, rules_root=history.ROOT)
        annual.assert_called_once_with(repo_root=self.source, company_id='constructed',
                                       period_selection=selection, rules_root=history.ROOT)
        self.reader.auditor_filing.assert_called_once_with(self.filing)
        self.assertIs(selected['preparation']['primary'], self.primary)
        self.assertIs(selected['preparation']['xml'], self.xml)
        self.assertIs(selected['preparation']['input_binding']['prepared_annual_input'], self.original)

    def test_missing_or_multiple_original_media_is_rejected(self):
        for sources in ([self.primary], [self.primary, self.primary, self.xml]):
            with self.subTest(sources=len(sources)), \
                 patch.object(history, 'resolve_period_selection', return_value={}), \
                 patch.object(history, 'prepare_historical_annual_input', return_value=self.annual), \
                 patch.object(history, '_Sources', return_value=self.reader):
                self.reader.auditor_filing.return_value = sources
                with self.assertRaisesRegex(ValueError, 'SOURCE_SET_AMBIGUOUS'):
                    self.prepare()

    def test_unreceived_subject_change_is_an_implementation_gap_before_debt_reads(self):
        self.original['subject_policy']['mode'] = 'SUCCESSOR_REGISTRANT_ONLY'
        with patch.object(history, 'resolve_period_selection', return_value={}), \
             patch.object(history, 'prepare_historical_annual_input', return_value=self.annual), \
             patch.object(history, '_Sources') as sources:
            with self.assertRaises(history.HistoricalDebtInputError) as caught:
                self.prepare()
        self.assertEqual('IMPLEMENTATION_GAP', caught.exception.category)
        sources.assert_not_called()

    def test_same_public_computation_receives_selected_sources_annual_and_packet(self):
        selected = {'selection': {'constructed_control': True}, 'annual': self.annual,
                    'preparation': {'constructed_original_sources': True}}
        packet = {'constructed_amendment_control': True}
        with patch.object(history, 'prepare_selected_debt_sources', return_value=selected), \
             patch.object(history, 'prepare_selected_debt_input', return_value=packet), \
             patch('vnext.current_b06_case.prepare_selected_b06_case', create=True,
                   return_value={'constructed_public_case': True}) as compute:
            case = history.prepare_historical_b06_year_case(repo_root=self.source,
                company_id='constructed', metric_id='B06', fiscal_year=2024)
        compute.assert_called_once_with(source_root=self.source, company_id='constructed',
            preparation=selected['preparation'], annual=self.annual, packet=packet)
        self.assertEqual(selected['selection'], case['historical_period_selection'])

    def test_wrong_metric_does_not_prepare_sources(self):
        with patch.object(history, 'prepare_selected_debt_sources') as prepare:
            with self.assertRaisesRegex(ValueError, 'METRIC_REQUIRED'):
                history.prepare_historical_b06_year_case(repo_root=self.source,
                    company_id='constructed', metric_id='B01', fiscal_year=2024)
        prepare.assert_not_called()

    def packet(self):
        return history.prepare_selected_debt_input(repo_root=self.source, selected={
            'annual': self.annual, 'reader': self.reader,
            'preparation': {'primary': self.primary}})

    def test_amendment_uses_the_same_explicit_layout_and_preserves_withheld_effect(self):
        amendment = {**self.filing, 'accessionNumber': 'constructed-amendment'}
        self.original['amendments'] = [amendment]
        self.reader.primary.return_value = self.primary
        effect = {'decision': 'WITHHELD', 'issues': ['constructed actual correction']}
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',
                   return_value={'constructed_control': True}) as scope, \
             patch('vnext.b06_current_input.inspect_current_debt_amendment', return_value=effect) as check, \
             patch.object(history, 'verify_ordinary_source_proofs', return_value={}), \
             patch.object(history, 'sha256_file', return_value='constructed-policy-version'):
            packet = self.packet()
        for call in (scope, check):
            self.assertEqual(history.NOTE_LAYOUT, call.call_args.kwargs['note_layout'])
            self.assertEqual(amendment, call.call_args.kwargs['amendment']['filing'])
        self.assertEqual('WITHHELD', packet['decision'])
        self.assertEqual([effect], packet['checks'])
        self.assertFalse(packet['debt_completeness_proven'])

    def test_layout_gap_is_separate_from_wrong_identity(self):
        from vnext.annual_amendment_scope import AmendmentScopeError
        self.original['amendments'] = [{**self.filing, 'accessionNumber': 'constructed-amendment'}]
        self.reader.primary.return_value = self.primary
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',
                   side_effect=AmendmentScopeError('AMENDMENT_EXPLANATORY_SCOPE_UNSUPPORTED')):
            with self.assertRaises(history.HistoricalDebtInputError) as caught:
                self.packet()
        self.assertEqual('IMPLEMENTATION_GAP', caught.exception.category)
        identity_error = AmendmentScopeError('AMENDMENT_IDENTITY_CONTEXT_DIFFERS')
        with patch('vnext.annual_amendment_scope_v2.inspect_annual_amendment_scope',
                   side_effect=identity_error):
            with self.assertRaises(AmendmentScopeError) as caught:
                self.packet()
        self.assertIs(identity_error, caught.exception)

    def test_packet_keeps_annual_and_amendment_proofs_before_shared_calculation(self):
        annual_proof = {'constructed_annual_proof': True}
        amendment_proof = {'constructed_amendment_proof': True}
        self.original['source_proofs'] = [annual_proof]
        self.reader.proofs = {'amendment': {'proof': amendment_proof}}
        with patch.object(history, 'verify_ordinary_source_proofs', return_value={}) as verify, \
             patch.object(history, 'sha256_file', return_value='constructed-policy-version'):
            packet = self.packet()
        self.assertEqual([annual_proof, amendment_proof], packet['source_proofs'])
        verify.assert_called_once_with(data_root=self.source, proofs=[annual_proof, amendment_proof])
        self.assertFalse(packet['debt_completeness_proven'])
        self.assertEqual({'provider': 0, 'paid': 0, 'sec': 0}, packet['calls'])
