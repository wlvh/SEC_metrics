"""Public saved-answer dispatch; constructed cases carry no business credit."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from vnext import historical_d02_case as public
from vnext import company_local


class D02SavedCompanyTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.answers=self.root/'answers';self.answers.mkdir()
        self.request={'request_id':'expected-id','company_id':'ford_motor_company'}
        self.bundle={'requests':[self.request]}

    def test_factory_uses_complete_source_requests_and_existing_business_case(self):
        factory=public.historical_d02_factory(saved_review_root=self.answers)
        review={'original_execution_mode':'LIVE','usage_known':True,'request_id':'expected-id'}
        with patch.object(public,'prepare_historical_legal_sources',return_value=self.bundle) as prepare, \
             patch.object(public,'_answer_roots',return_value={'expected-id':self.answers}), \
             patch.object(public,'read_saved_legal_review',return_value=review) as read, \
             patch.object(public,'finish_historical_legal_case',return_value={'constructed_case':True}) as finish:
            case=factory(repo_root=self.root/'sources',company_id='ford_motor_company',metric_id='D02',fiscal_year=2025)
        self.assertEqual(case,{'constructed_case':True})
        prepare.assert_called_once_with(repo_root=self.root/'sources',company_id='ford_motor_company',fiscal_year=2025)
        read.assert_called_once_with(call_root=self.answers,request=self.request)
        finish.assert_called_once_with(bundle=self.bundle,reviews=[review])

    def test_missing_set_does_not_create_partial_case_or_call_reader(self):
        factory=public.historical_d02_factory(saved_review_root=self.answers)
        with patch.object(public,'prepare_historical_legal_sources',return_value=self.bundle), \
             patch.object(public,'_answer_roots',return_value={}), \
             patch.object(public,'read_saved_legal_review') as read, \
             patch.object(public,'finish_historical_legal_case') as finish, \
             self.assertRaisesRegex(ValueError,'COMPLETE_SAVED_REVIEW_SET_MISSING'):
            factory(repo_root=self.root/'sources',company_id='ford_motor_company',metric_id='D02',fiscal_year=2025)
        read.assert_not_called();finish.assert_not_called()

    def test_package_failure_producer_is_distinct_and_retains_original_error(self):
        error=KeyError('evidence')
        failure=public.invalid_saved_review_factory(error=error)
        normal=public.historical_d02_factory(saved_review_root=self.answers)
        self.assertNotEqual(normal.__qualname__,failure.__qualname__)
        with patch.object(public,'prepare_historical_legal_sources') as prepare, \
             self.assertRaises(KeyError) as raised:
            failure(repo_root=self.root/'sources',company_id='ford_motor_company',metric_id='D02',fiscal_year=2025)
        self.assertIs(error,raised.exception);prepare.assert_not_called()

    def test_recorded_or_unknown_usage_answer_has_no_business_case_credit(self):
        factory=public.historical_d02_factory(saved_review_root=self.answers)
        for review in ({'original_execution_mode':'RECORDED','usage_known':True},
                       {'original_execution_mode':'LIVE','usage_known':False}):
            with self.subTest(review=review), \
                 patch.object(public,'prepare_historical_legal_sources',return_value=self.bundle), \
                 patch.object(public,'_answer_roots',return_value={'expected-id':self.answers}), \
                 patch.object(public,'read_saved_legal_review',return_value=review), \
                 patch.object(public,'finish_historical_legal_case') as finish, \
                 self.assertRaises(ValueError):
                factory(repo_root=self.root/'sources',company_id='ford_motor_company',metric_id='D02',fiscal_year=2025)
            finish.assert_not_called()

    def test_source_and_answer_roots_cannot_hide_model_answers_inside_source_input(self):
        factory=public.historical_d02_factory(saved_review_root=self.answers)
        with patch.object(public,'prepare_historical_legal_sources') as prepare, \
             self.assertRaisesRegex(ValueError,'SEPARATE_FROM_SEC_SOURCES'):
            factory(repo_root=self.root,company_id='ford_motor_company',metric_id='D02',fiscal_year=2025)
        prepare.assert_not_called()

    def test_unsettled_answer_cannot_reach_native_result_or_calculator(self):
        from tests.vnext.test_d02_reviewed_source import fixture,constructed_review
        from vnext import d02_reviewed_source as core,legal_review_contract as contract
        args,prepared=fixture('<p>We face litigation pending in court.</p>')
        request=core.item8_requests(prepared=prepared,target=args['target'])[0]
        block=request['blocks'][0]
        review=constructed_review(request,{'decisions':[{'block_id':block['block_id'],
            'decision':'CANNOT_TELL_FROM_THE_TEXT','quote':block['text']}],'also_in_scope':[]})
        # Only the saved-reader boundary is constructed. Real source/answer
        # validation and the native aggregator must retain the unsettled state.
        review.update(original_execution_mode='LIVE',usage_known=True)
        bundle={'requests':[request],'source_arguments':args}
        factory=public.historical_d02_factory(saved_review_root=self.answers)
        with patch.object(public,'prepare_historical_legal_sources',return_value=bundle), \
             patch.object(public,'_answer_roots',return_value={request['request_id']:self.answers}), \
             patch.object(public,'read_saved_legal_review',return_value=review), \
             patch('vnext.calculator.calculate_text_metric',side_effect=AssertionError('Must not calculate')) as calculate, \
             self.assertRaises(contract.LegalReviewUnsettled):
            factory(repo_root=self.root/'sources',company_id=args['target']['company_id'],metric_id='D02',fiscal_year=2025)
        calculate.assert_not_called()

    def test_answer_set_indexes_exact_requests_and_binds_all_seven_original_members(self):
        call=self.answers/'one';(call/'wire').mkdir(parents=True)
        (call/'invocation_control/requests').mkdir(parents=True)
        request={'record_type':'D02_ITEM_8_LEGAL_REVIEW_REQUEST','request_id':'expected-id',
            'company_id':'ford_motor_company','period_end':'2025-12-31'}
        (call/'semantic-request.json').write_text(json.dumps(request))
        (call/'terminal.json').write_text(json.dumps({'evidence':{'invocation_control/requests/body.bin':'saved-hash'}}))
        files=public.saved_review_input_paths(saved_review_root=self.answers,company_id='ford_motor_company')
        self.assertEqual(len(files),7)
        self.assertEqual({p.relative_to(call).as_posix() for p in files},{'semantic-request.json',
            'source.json','terminal.json','wire/journal.json','wire/raw-response.bin',
            'wire/assistant-output.bin','invocation_control/requests/body.bin'})
        self.assertEqual(public._answer_roots(self.answers),{'expected-id':call})
        duplicate=self.answers/'duplicate';duplicate.mkdir()
        (duplicate/'semantic-request.json').write_text(json.dumps(request))
        with self.assertRaisesRegex(ValueError,'REQUEST_DUPLICATED'):public._answer_roots(self.answers)

    def test_other_company_or_multiple_periods_are_not_one_calculation_answer_set(self):
        for index,end in enumerate(('2024-12-31','2025-12-31')):
            path=self.answers/str(index);path.mkdir()
            (path/'semantic-request.json').write_text(json.dumps({'record_type':'D02_ITEM_8_LEGAL_REVIEW_REQUEST',
                'request_id':str(index),'company_id':'ford_motor_company','period_end':end}))
            (path/'terminal.json').write_text(json.dumps({'evidence':{'invocation_control/requests/body.bin':'hash'}}))
        with self.assertRaisesRegex(ValueError,'MULTIPLE_PERIODS'):
            public.saved_review_input_paths(saved_review_root=self.answers,company_id='ford_motor_company')
        with self.assertRaisesRegex(ValueError,'OTHER_COMPANY'):
            public.saved_review_input_paths(saved_review_root=self.answers,company_id='other')

    def test_public_history_dispatch_retains_neighbours_and_answer_file_binding(self):
        files=(self.answers/'request.json',self.answers/'response.json')
        with patch.object(public,'saved_review_input_paths',return_value=files), \
             patch('vnext.company_current_records.run_saved_company',return_value={'constructed':True}) as shared:
            result=company_local._run_saved_history(company_id='ford_motor_company',source_root=self.root/'sources',
                work_dir=self.root/'state',output_dir=self.root/'out',metric_ids=['D02','B04'],
                fiscal_year_start=2025,fiscal_year_end=2025,saved_legal_reviews=self.answers)
        self.assertEqual(result,{'constructed':True})
        args=shared.call_args.kwargs
        self.assertTrue(callable(args['case_factories']['D02']))
        self.assertEqual(args['processing_files_by_metric']['D02'],public.PROCESSING_FILES)
        self.assertEqual(args['processing_inputs_by_metric'],{'D02':files})
        self.assertEqual(args['case_factories']['B04'].__name__,'prepare_historical_statement_year_case')
        self.assertFalse((self.root/'state').exists())

    def test_cli_does_not_silently_turn_saved_answers_into_online_or_current_mode(self):
        from tools.vnext_company import main
        for extra in ([],['--source-root',str(self.root)],['--period','fiscal-years','--metric','B04']):
            with self.subTest(extra=extra),self.assertRaises(SystemExit), \
                 patch.object(company_local,'run_local') as run:
                main(['run','--company','ford_motor_company','--work-dir',str(self.root/'state'),
                    '--output-dir',str(self.root/'out'),'--saved-legal-reviews',str(self.answers),*extra])
            run.assert_not_called()


if __name__=='__main__':unittest.main()
