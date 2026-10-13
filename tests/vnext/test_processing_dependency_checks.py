"""Small dependency behavior tests; saved-original factory coverage is separate."""
from pathlib import Path
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests.vnext.processing_dependency_checks import (processing_calls,
    undeclared_processing_calls,assert_processing_calls,SOURCE_CHECK_EXCEPTIONS)
from tests.vnext import test_registry_processing_scope as registry_fixtures
from scripts.vnext import ordinary_current_update as update
from scripts.vnext.text_coverage import _byte_offsets
from scripts.vnext.paired_measure_v1 import paired_measure_problem
from scripts.vnext.normal_numeric_projection import _period_label

ROOT=Path(__file__).resolve().parents[2]


class ProcessingDependencyCheckTest(unittest.TestCase):
    def test_period_presentation_is_covered_beyond_candidate_preparation(self):
        configuration=update._configuration(ROOT,'marriott_international','B01')
        period={'period_start':'2025-01-01','period_end':'2025-12-31'}
        with processing_calls(ROOT) as observed:
            label,note=_period_label({**period,'applicability':'APPLICABLE',
                                     'publication':'PUBLISHED'},period)
        self.assertEqual(label,'ANNUAL')
        self.assertIn('source fiscal-year',note)
        assert_processing_calls(observed,configuration)

    def test_guard_observes_top_level_source_locator_module(self):
        from sec_urls import submissions_url
        configuration=update._configuration(ROOT,'marriott_international','B01')
        with processing_calls(ROOT) as observed:
            self.assertEqual(submissions_url(cik=1048286),
                'https://data.sec.gov/submissions/CIK0001048286.json')
        self.assertIn('scripts/sec_urls.py',observed)
        assert_processing_calls(observed,configuration)

    def test_actual_called_parser_and_comparability_modules_are_fingerprinted(self):
        configuration=update._configuration(ROOT,'enphase_energy','B04')
        with processing_calls(ROOT) as observed:
            self.assertEqual(_byte_offsets('éx',[0,1,2]),{0:0,1:2,2:3})
            self.assertEqual(paired_measure_problem(route={'branches':[]},claims=[],
                current_claims=[],accessions={}), (None,[]))
        assert_processing_calls(observed,configuration)

    def test_mechanical_guard_fails_when_a_used_file_is_removed(self):
        with processing_calls(ROOT) as observed:
            _byte_offsets('test',[0,4])
        with self.assertRaisesRegex(AssertionError,'text_coverage.py'):
            assert_processing_calls(observed,{'processing_files':{}})
        assert_processing_calls(observed,{'processing_files':{'scripts/vnext/text_coverage.py':'version'}})

    def test_explicit_consumer_paths_count_but_unknown_files_are_not_exempt(self):
        observed={'scripts/vnext/example_consumer.py':{'prepare'},
                  'scripts/vnext/request_bindings.py':{'validate'}}
        self.assertEqual(undeclared_processing_calls(observed,{},['scripts/vnext/example_consumer.py']),{})
        self.assertEqual(set(undeclared_processing_calls(observed,{})),{'scripts/vnext/example_consumer.py'})
        self.assertEqual(set(SOURCE_CHECK_EXCEPTIONS),{'scripts/vnext/request_bindings.py',
            'scripts/vnext/ordinary_current_update.py'})

    def test_profile_restores_after_failure_and_nested_observation(self):
        prior=sys.getprofile()
        with self.assertRaisesRegex(ValueError,'test-only'):
            with processing_calls(ROOT) as outer:
                with processing_calls(ROOT) as inner:
                    _byte_offsets('test',[0,4])
                raise ValueError('test-only')
        self.assertIs(sys.getprofile(),prior)
        self.assertIn('scripts/vnext/text_coverage.py',inner)
        self.assertIn('scripts/vnext/text_coverage.py',outer)

    def test_current_d01_real_candidate_and_evidence_calls_use_declared_consumer_paths(self):
        from tests.vnext import test_current_risk_heading_case as risk_fixture
        from vnext import current_risk_heading_case as risk
        from vnext import d01_emphasis_results as api
        args=risk_fixture.CurrentRiskHeadingCaseTest().args(2)
        from vnext.text_review import build_text_review_unit
        from vnext.review import (_create_review_decision,_system_approved_claims,
            SYSTEM_REVIEWER_ID,SYSTEM_REVIEW_REASON)
        configuration=update._configuration(ROOT,'enphase_energy','D01')
        with processing_calls(ROOT) as observed:
            candidate,_=risk._candidate(api,args,ROOT)
            evidence=api.build_text_evidence(candidate=candidate,**args)
            unit,_=build_text_review_unit(compiled_spec=args['compiled_spec'],candidate=candidate,
                evidence_check=evidence,source_bindings=args['source_references'])
            decision=_create_review_decision(review_unit=unit,decision='APPROVE',
                approved_claims=_system_approved_claims(review_unit=unit),
                required_claims=args['compiled_spec']['compiled']['required_claims'],
                reviewer_type='SYSTEM',reviewer_id=SYSTEM_REVIEWER_ID,
                decided_at_utc='2026-10-13T00:00:00Z',reason=SYSTEM_REVIEW_REASON,supersedes_decision_id=None)
            api.replay_text_result(company_traits=['non_financial'],candidate=candidate,
                evidence_check=evidence,review_unit=unit,review_decisions=[decision],**args)
        assert_processing_calls(observed,configuration,risk.PROCESSING_FILES)
        reduced=tuple(p for p in risk.PROCESSING_FILES if not p.endswith('scope_contract.py'))
        # Source/evidence checks are real; this missing-file negative protects
        # the per-consumer declaration, independently of the generic paths.
        self.assertIn('scripts/vnext/scope_contract.py',observed)
        changed={**configuration,'processing_files':{k:v for k,v in configuration['processing_files'].items()
                  if k!='scripts/vnext/scope_contract.py'}}
        with self.assertRaisesRegex(AssertionError,'scope_contract.py'):
            assert_processing_calls(observed,changed,reduced)

    def test_shared_scope_and_text_are_not_limited_to_current_numeric_families(self):
        for metric in ('B10','C03','D04'):
            with self.subTest(metric=metric):
                files=update._configuration(ROOT,'marriott_international',metric)['processing_files']
                for path in ('scope_contract','text_coverage','text_results_v2'):
                    self.assertIn('scripts/vnext/'+path+'.py',files)

    def test_storage_or_source_check_exception_does_not_exempt_a_producer(self):
        observed={'scripts/vnext/company_handoff.py':{'_atomic_json','prepare_program'},
                  'scripts/sec_http.py':{'validate_request_log_manifest','_fetch_once'}}
        self.assertEqual(undeclared_processing_calls(observed,{}),{
            'scripts/sec_http.py':['_fetch_once'],
            'scripts/vnext/company_handoff.py':['prepare_program']})

    def test_full_run_material_guard_allows_only_its_new_output_root(self):
        from tests.vnext.test_annual_input import independent_inputs
        with TemporaryDirectory() as directory:
            root=Path(directory);output=root/'new-task';output.mkdir()
            new=output/'metrics_matrix.csv';new.write_text('CONSTRUCTED_NEW_OUTPUT')
            old=root/'metric_evidence.csv';old.write_text('CONSTRUCTED_OLD_ANSWER')
            with independent_inputs(output_roots=(output,)):
                self.assertEqual(new.read_text(),'CONSTRUCTED_NEW_OUTPUT')
                with self.assertRaisesRegex(AssertionError,'Historical result read'):
                    old.read_text()
            with independent_inputs():
                with self.assertRaisesRegex(AssertionError,'Historical result read'):
                    new.read_text()


class ProcessingChangeReentryTest(unittest.TestCase):
    """Reuse only the small fixture; don't inherit the other registry tests."""
    setUp=registry_fixtures.RegistryProcessingScopeTest.setUp
    run_check=registry_fixtures.RegistryProcessingScopeTest.run_check
    def test_shared_scope_presentation_and_locator_changes_process_once(self):
        self.run_check();original=update.sha256_file
        for relative in ('scripts/vnext/normal_numeric_projection.py',
                         'scripts/vnext/scope_contract.py','scripts/sec_urls.py'):
            with self.subTest(relative=relative):
                before=self.calculations;target=ROOT/relative
                with patch.object(update,'sha256_file',side_effect=lambda *,path:
                        'TEST_ONLY changed consumed dependency' if path==target else original(path=path)):
                    result=self.run_check()
                    self.assertEqual(result['status'],'CANDIDATE_READY')
                    self.assertEqual(self.calculations,before+1)
                    with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated calculation')):
                        again=self.run_check()
                    self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
                self.run_check()

    def test_real_configuration_parser_or_pairing_change_processes_once(self):
        self.run_check();original=update.sha256_file
        for filename in ('text_coverage.py','normal_governance_input.py','text_results_v2.py'):
            before=self.calculations;target=ROOT/'scripts/vnext'/filename
            with self.subTest(filename=filename),patch.object(update,'sha256_file',
                    side_effect=lambda *,path: 'TEST_ONLY modified dependency' if path==target else original(path=path)):
                result=self.run_check()
                self.assertEqual(result['status'],'CANDIDATE_READY')
                self.assertEqual(self.calculations,before+1)
                with patch.object(update,'create_saved_result',side_effect=AssertionError('No second calculation')):
                    again=self.run_check()
                self.assertEqual(again['status'],'NO_SOURCE_CONTENT_CHANGE')
            # Restore original versions through normal processing before the next mutation.
            self.run_check()
