"""Selected registration changes and actual saved-code component comparison."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from vnext import ordinary_saved_result as saved, ordinary_current_update as update
ROOT=Path(__file__).resolve().parents[2]


class SavedResultRegistrationTest(unittest.TestCase):
    def setUp(self):
        self.catalog=saved._route_catalog();self.read=saved.strict_json_file

    def configuration(self,metric,catalog,*,supplied_case=False):
        def read(*,path):
            return deepcopy(catalog) if Path(path)==ROOT/saved.ROUTE_CONFIG_PATH else self.read(path=path)
        with patch.object(saved,'strict_json_file',side_effect=read):
            return update._configuration(ROOT,'marriott_international',metric,supplied_case=supplied_case)

    def test_unrelated_new_registration_does_not_change_existing_inputs(self):
        changed=deepcopy(self.catalog);changed['routes']['A99']=dict(changed['routes']['A04'])
        for metric in ('B01','D04','E01','D02'):
            with self.subTest(metric=metric):
                self.assertEqual(self.configuration(metric,self.catalog),self.configuration(metric,changed))

    def test_supplied_case_does_not_acquire_unused_default_module_dependency(self):
        changed=deepcopy(self.catalog)
        changed['default']={**changed['default'],'module':'vnext.current_b06_case','function':'prepare_current_b06_case'}
        for metric in ('D01','D02','E01'):
            with self.subTest(metric=metric):
                original=self.configuration(metric,self.catalog,supplied_case=True)
                actual=self.configuration(metric,changed,supplied_case=True)
                self.assertEqual(original,actual)
                self.assertEqual({'call_style':'supplied_case'},actual['saved_result_registration'])
                self.assertIn('scripts/vnext/ordinary_saved_result.py',actual['processing_files'])
        # Actual default-dispatch tasks do consume their selected module.
        actual=self.configuration('E01',changed)
        self.assertIn('scripts/vnext/current_b06_case.py',actual['processing_files'])

    def test_used_registration_change_is_a_processing_change(self):
        changed=deepcopy(self.catalog);changed['routes']['D04']['function']='another_producer'
        self.assertFalse(update._same_processing_configuration(self.configuration('D04',self.catalog),
                                                               self.configuration('D04',changed)))

    def test_malformed_unrelated_registration_is_still_rejected(self):
        changed=deepcopy(self.catalog);changed['routes']['A99']={'module':7}
        with self.assertRaisesRegex(ValueError,'SAVED_ROUTE_ENTRY_INVALID'):
            self.configuration('B01',changed)

    def test_selected_registry_still_dispatches_the_same_actual_case(self):
        for metric,module,name in [('B04','vnext.current_statement_metric_case','prepare_current_statement_metric_case'),
                                   ('D04','vnext.ordinary_d04_saved_route','prepare_case')]:
            with self.subTest(metric=metric),patch(module+'.'+name,return_value={'metric':metric}) as factory, \
                 patch.object(saved,'_save_case',side_effect=lambda **kw:kw['factory'](Path('/saved'))):
                result=saved.create_saved_result(source_root=Path('/saved'),output_root=Path('/new'),
                    company_id='sample',metric_id=metric)
                self.assertEqual(result,{'metric':metric})
                factory.assert_called_once_with(source_root=Path('/saved'),company_id='sample',metric_id=metric)

class LegacyRegistrationShapeTest(unittest.TestCase):
    def test_old_selector_arguments_cannot_be_inferred_from_names_only(self):
        import ast
        from vnext.ordinary_result_registration import _legacy_registration
        code='''def create_saved_result():
    def prepare(source):
        if metric_id == 'D04':
            from .ordinary_d04_saved_route import prepare_case
            return prepare_case(source_root=source,company_id=company_id,metric_id=metric_id)
'''
        selected=_legacy_registration(ast.parse(code),'D04')
        self.assertEqual(selected['module'],'vnext.ordinary_d04_saved_route')
        self.assertIsNone(_legacy_registration(ast.parse(code.replace('company_id=company_id',"company_id='another'")),'D04'))
        self.assertIsNone(_legacy_registration(ast.parse(code.replace('source_root=source',"source_root='/another'")),'D04'))

class LegacyStoreComponentTest(unittest.TestCase):
    def test_changed_legacy_wrapper_or_selected_factory_rebinding_is_not_reused(self):
        import hashlib
        from vnext import ordinary_result_registration as registration
        original=(ROOT/'tests/vnext/fixtures/saved_result_inline_dispatch_5612.py.txt').read_text()
        current=update._configuration(ROOT,'marriott_international','D04')
        mutations={
            'selected_factory_rebound':original.replace(
                'return prepare_case(source_root=source,company_id=company_id,metric_id=metric_id)',
                'prepare_case = another_factory\n            return prepare_case(source_root=source,company_id=company_id,metric_id=metric_id)'),
            'outer_source_changed':original.replace(
                '    def prepare(source):',
                "    source_root = source_root / 'different-source'\n    def prepare(source):",1),
            'save_arguments_changed':original.replace(
                'calculation_performed=True, shared_input_root=shared_input_root)',
                'calculation_performed=False, shared_input_root=shared_input_root)',1),
        }
        for name,source in mutations.items():
            with self.subTest(name=name):
                self.assertNotEqual(original,source)
                raw=source.encode();previous=deepcopy(current);previous.pop('saved_result_registration')
                previous['processing_files'][registration.STORE]=hashlib.sha256(raw).hexdigest()
                with patch.object(registration,'_old_source',return_value=raw):
                    self.assertFalse(registration.same_registered_processing(previous,current,{},ROOT))

    def test_dispatch_transition_uses_source_and_rejects_changed_or_missing_functions(self):
        import ast
        from vnext import ordinary_result_registration as registration
        source=(ROOT/registration.STORE).read_text(encoding='utf-8')
        # Python's AST text is deliberately not the serialized signature.
        with patch.object(registration.ast,'dump',side_effect=AssertionError('No versioned AST dump')):
            self.assertEqual(registration.DISPATCH_TRANSITION_V1,
                registration._dispatch_transition_signature(ast.parse(source),source))
            changed=source.replace('def selected_case_registration(', 'def unrelated_registration(',1)
            self.assertIsNone(registration._dispatch_transition_signature(ast.parse(changed),changed))
            changed=source.replace("catalog['routes'].get(metric_id,catalog['default'])",
                                   "catalog['default']",1)
            self.assertNotEqual(source,changed)
            self.assertNotEqual(registration.DISPATCH_TRANSITION_V1,
                registration._dispatch_transition_signature(ast.parse(changed),changed))

    def test_known_old_component_is_reused_but_actual_storage_logic_changes_are_not(self):
        import hashlib,subprocess,ast
        from vnext import ordinary_result_registration as registration
        # Exact earlier component fixture; no un-fetched ancestor required in CI.
        original=(ROOT/'tests/vnext/fixtures/saved_result_inline_dispatch_5612.py.txt').read_bytes()
        current=update._configuration(ROOT,'marriott_international','D04')
        previous=deepcopy(current);previous.pop('saved_result_registration')
        previous['processing_files'][registration.STORE]=hashlib.sha256(original).hexdigest()
        previous['processing_files'].pop('scripts/vnext/ordinary_result_registration.py',None)
        with patch.object(registration,'_old_source',return_value=original):
            self.assertTrue(registration.same_registered_processing(previous,current,{},ROOT))
            altered=deepcopy(current);altered['processing_files']['scripts/vnext/calculator.py']='changed-calculation'
            self.assertFalse(registration.same_registered_processing(previous,altered,{},ROOT))
            parse=ast.parse
            def changed(source,*args,**kwargs):
                if source != original:
                    source=source.replace(b'SAVED_RESULT_PERIOD_CHANGED',b'CHANGED_PERIOD_CHECK') if isinstance(source,bytes) else source.replace('SAVED_RESULT_PERIOD_CHANGED','CHANGED_PERIOD_CHECK')
                return parse(source,*args,**kwargs)
            with patch.object(registration.ast,'parse',side_effect=changed):
                self.assertFalse(registration.same_registered_processing(previous,current,{},ROOT))

    def test_old_default_to_supplied_case_reprocesses_instead_of_key_error(self):
        import hashlib
        from vnext import ordinary_result_registration as registration
        original=(ROOT/'tests/vnext/fixtures/saved_result_inline_dispatch_5612.py.txt').read_bytes()
        for metric in ('E01','A04','A13','C04','B01'):
            with self.subTest(metric=metric):
                current=update._configuration(ROOT,'marriott_international',metric,supplied_case=True)
                previous=deepcopy(current);previous.pop('saved_result_registration')
                previous['processing_files'][registration.STORE]=hashlib.sha256(original).hexdigest()
                with patch.object(registration,'_old_source',return_value=original):
                    self.assertFalse(registration.same_registered_processing(previous,current,{},ROOT))

    def test_supplied_case_does_not_consume_the_unused_legacy_create_wrapper(self):
        import hashlib
        from vnext import ordinary_result_registration as registration
        original=(ROOT/'tests/vnext/fixtures/saved_result_inline_dispatch_5612.py.txt').read_text()
        changed=original.replace('    def prepare(source):',
            "    source_root = source_root / 'unused'\n    def prepare(source):",1).encode()
        current=update._configuration(ROOT,'marriott_international','D04',supplied_case=True)
        current['case_producer']='same-explicit-producer'
        previous=deepcopy(current);previous.pop('saved_result_registration')
        previous['processing_files'][registration.STORE]=hashlib.sha256(changed).hexdigest()
        with patch.object(registration,'_old_source',return_value=changed):
            self.assertTrue(registration.same_registered_processing(previous,current,{},ROOT))

    def test_unavailable_or_wrong_component_never_grants_compatibility(self):
        from vnext import ordinary_result_registration as registration
        current=update._configuration(ROOT,'marriott_international','D04')
        previous=deepcopy(current);previous.pop('saved_result_registration')
        previous['processing_files'][registration.STORE]='unavailable-original'
        with patch.object(registration,'_old_source',return_value=None):
            self.assertFalse(registration.same_registered_processing(previous,current,{},ROOT))

class RegistrationUpdateBehaviorTest(unittest.TestCase):
    def test_changed_legacy_wrapper_reprocesses_once_then_reuses(self):
        import hashlib,json
        from tests.vnext.test_ordinary_current_update import CurrentUpdateTest, update as fixture_update
        from scripts.vnext import ordinary_result_registration as registration
        case=CurrentUpdateTest();case.setUp();self.addCleanup(case.doCleanups)
        original=(ROOT/'tests/vnext/fixtures/saved_result_inline_dispatch_5612.py.txt').read_text()
        changed=original.replace('    def prepare(source):',
            "    source_root = source_root / 'different-source'\n    def prepare(source):",1).encode()
        case.config={'metric_id':'B01','processing_files':{registration.STORE:hashlib.sha256(changed).hexdigest()}}
        first=case.run_update()
        (Path(first['result_root'])/'manifest.json').write_text(json.dumps(case.records[first['result_root']]['manifest']))
        case.config={**case.config,'saved_result_registration':saved.selected_case_registration('B01')}
        with patch.object(registration,'_old_source',return_value=changed):
            second=case.run_update()
        self.assertEqual('CANDIDATE_READY',second['status'],second)
        self.assertEqual(2,case.calculations);self.assertNotEqual(first['result_id'],second['result_id'])
        with patch.object(fixture_update,'create_saved_result',side_effect=AssertionError('No repeated processing')):
            again=case.run_update()
        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',again['status'])
        self.assertEqual(second['result_id'],again['result_id'])
        self.assertEqual(first['result_id'],case.records[first['result_root']]['result']['result_id'])

    def test_default_record_changed_to_current_factory_processes_once_then_reuses(self):
        import hashlib
        from tests.vnext.test_ordinary_current_update import CurrentUpdateTest, update as fixture_update
        from scripts.vnext import ordinary_result_registration as registration
        case=CurrentUpdateTest();case.setUp();self.addCleanup(case.doCleanups)
        original=(ROOT/'tests/vnext/fixtures/saved_result_inline_dispatch_5612.py.txt').read_bytes()
        case.config={'metric_id':'B01','processing_files':{registration.STORE:hashlib.sha256(original).hexdigest()}}
        first=case.run_update()
        import json
        first_root=Path(first['result_root'])
        (first_root/'manifest.json').write_text(json.dumps(case.records[str(first_root)]['manifest']))
        case.config={**case.config,'saved_result_registration':{'call_style':'supplied_case'}}
        calls=[]
        def factory(*,repo_root,company_id,metric_id):calls.append(company_id);return {'test_only':True}
        def save(**kwargs):
            case.calculations+=1;path=kwargs['output_root'];path.mkdir(parents=True)
            value={'manifest':{'company_id':'marriott_international','metric_id':'B01','source_proofs':[case.proof]},
                'result':{'company_id':'marriott_international','metric_id':'B01','publication':'PUBLISHED',
                    'period_end':'2025-12-31','result_id':'result-'+str(case.calculations)}}
            case.records[str(path)]=value;return value
        args={'state_root':case.root,'source_root':ROOT,'company_id':'marriott_international',
              'metric_id':'B01','current_case_factory':factory}
        with patch.object(registration,'_old_source',return_value=original),patch.object(fixture_update,'save_calculated_case',side_effect=save):
            changed=fixture_update.run_once(**args)
        self.assertEqual('CANDIDATE_READY',changed['status'],changed);self.assertEqual(2,case.calculations)
        self.assertEqual(['marriott_international'],calls);self.assertNotEqual(first['result_id'],changed['result_id'])
        with patch.object(fixture_update,'save_calculated_case',side_effect=AssertionError('No second calculation')):
            again=fixture_update.run_once(**args)
        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',again['status']);self.assertEqual(changed['result_id'],again['result_id'])
        self.assertEqual(['marriott_international'],calls)

    def test_other_registration_reuses_and_used_registration_reprocesses_once(self):
        from tests.vnext.test_ordinary_current_update import CurrentUpdateTest
        case=CurrentUpdateTest();case.setUp();self.addCleanup(case.doCleanups)
        catalog=saved._route_catalog()
        # Source/calculation data is intentionally small; selected registry comparison
        # is independently checked against actual configurations above.
        def configured(value):
            return {'processing_files':{'shared-writer':'same'},
                'saved_result_registration':deepcopy(value['default'])}
        case.config=configured(catalog);first=case.run_update()
        other=deepcopy(catalog);other['routes']['A99']=dict(other['routes']['A04'])
        case.config=configured(other)
        before=set((case.root/'results').iterdir())
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No unrelated recomputation')):
            again=case.run_update()
        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',again['status'])
        self.assertEqual(first['result_id'],again['result_id']);self.assertEqual(before,set((case.root/'results').iterdir()))
        relevant=deepcopy(catalog);relevant['default']['function']='changed_actual_case'
        case.config=configured(relevant);changed=case.run_update()
        self.assertTrue(changed['calculation_performed']);self.assertEqual(2,case.calculations)
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No repeated changed calculation')):
            self.assertEqual('NO_SOURCE_CONTENT_CHANGE',case.run_update()['status'])


if __name__=='__main__':unittest.main()
