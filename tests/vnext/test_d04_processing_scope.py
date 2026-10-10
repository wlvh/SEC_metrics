"""Small states with actual dependency configuration; no model executions."""
from copy import deepcopy
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from tests.vnext import test_selected_history_result_state as state_controls

update = state_controls.update
ROOT = state_controls.ROOT

CONTROLLER = 'scripts/vnext/ordinary_current_update.py'
STORE = 'scripts/vnext/ordinary_saved_result.py'
BEFORE_D04 = {
    CONTROLLER: '5c3657bd9023f1b5a0afb865d039a2e81cabef58e3c396c508b71f292132dcca',
    STORE: 'f71cca5ed3ab7260764a83d58feb9e835eb8ce8da5b911c6b14b887623318a2d',
}
AFTER_D04 = {
    CONTROLLER: '434c645f5cfa61999483d1927b06158a51a58c9d977e552c801c7d7de1e20713',
    STORE: 'ff23e46659e065bbc1c98c6eb4fef6702e9ebba594bf0f2c7e5110d0f49202dd',
}

class D04ProcessingScopeTest(TestCase):
    # Reuse only the small state preparation, not its test methods.
    setUp = state_controls.SelectedHistoryResultStateTest.setUp
    factory = state_controls.SelectedHistoryResultStateTest.factory
    save_control = state_controls.SelectedHistoryResultStateTest.save_control
    run_control = state_controls.SelectedHistoryResultStateTest.run_control
    period_root = state_controls.SelectedHistoryResultStateTest.period_root

    def extracted_configuration(self, source, company, metric):
        """Current configuration at the bridge's recorded extracted version.

        Later merges may change the shared controller/store bytes; the bridge
        then correctly stops recognising old tasks and they reprocess. These
        tests exercise the recorded transition itself, so they pin it here.
        """
        from scripts.vnext import ordinary_update_compatibility as compat
        config = self.actual_configuration(source, company, metric)
        config['processing_files'][CONTROLLER], config['processing_files'][STORE] = compat.EXTRACTED_MAIN_F51
        return config

    def test_proven_d04_only_transition_keeps_success_and_withheld(self):
        self.outcomes[2025, 'B11'] = 'WITHHELD'
        current_hash = update.sha256_file
        def configuration_for(hashes):
            def override(*, path):
                relative = str(Path(path).relative_to(ROOT))
                return hashes.get(relative, current_hash(path=path))
            with patch.object(update, 'sha256_file', side_effect=override):
                config = self.actual_configuration(ROOT, 'marriott_international', 'B10')
            # The old snapshots predate the bounded compatibility helper.
            config['processing_files'].pop('scripts/vnext/ordinary_update_compatibility.py', None)
            return config
        def old_config(source, company, metric):
            config = configuration_for(BEFORE_D04); config['metric_id'] = metric; return config
        def new_config(source, company, metric):
            config = configuration_for(AFTER_D04); config['metric_id'] = metric; return config
        with patch.object(update, '_configuration', side_effect=old_config):
            first = [self.run_control(2024), self.run_control(2025, 'B11')]
        paths = {p: p.read_bytes() for p in self.root.rglob('current-result.json')}
        original_checks = {p: p.read_bytes() for p in self.root.rglob('terminal.json')}
        directories = set(self.root.rglob('results/*'))
        self.forbid_factory = True
        with patch.object(update, '_configuration', side_effect=new_config):
            again = [self.run_control(2024), self.run_control(2025, 'B11')]
        self.assertEqual(['NO_SOURCE_CONTENT_CHANGE', 'PREVIOUS_INPUT_WITHHELD'], [r['status'] for r in again])
        self.assertEqual([r['version'] for r in first], [r['version'] for r in again])
        self.assertEqual(2, len(self.factory_calls))
        self.assertEqual(directories, set(self.root.rglob('results/*')))
        self.assertTrue(all(p.read_bytes() == raw for p, raw in paths.items()))
        self.assertTrue(all(p.read_bytes() == raw for p, raw in original_checks.items()))

    def test_extracted_d04_rules_change_only_d04_configuration(self):
        before = {metric:self.actual_configuration(ROOT, 'marriott_international', metric)
                  for metric in ('B04', 'B10', 'D04')}
        original = update.sha256_file
        route = ROOT/'scripts/vnext/ordinary_d04_saved_route.py'
        with patch.object(update, 'sha256_file', side_effect=lambda *,path:
                'changed-only-d04-route' if path==route else original(path=path)):
            after = {metric:self.actual_configuration(ROOT, 'marriott_international', metric)
                     for metric in before}
        self.assertEqual(before['B04'], after['B04'])
        self.assertEqual(before['B10'], after['B10'])
        self.assertNotEqual(before['D04'], after['D04'])

    def test_main_before_extraction_reuses_and_consumed_period_changes_reprocess(self):
        from scripts.vnext import ordinary_update_compatibility as compat
        def main_before(source, company, metric):
            config = self.actual_configuration(source, company, metric)
            config['processing_files'].pop(compat.BRIDGE)
            config['processing_files'][CONTROLLER],config['processing_files'][STORE] = compat.MAIN_C99
            return config
        self.outcomes[2025, 'B11'] = 'WITHHELD'
        with patch.object(update, '_configuration', side_effect=main_before):
            first=[self.run_control(2024), self.run_control(2025, 'B11')]
        old_pointer={p:p.read_bytes() for p in self.root.rglob('current-result.json')}
        self.forbid_factory=True
        with patch.object(update, '_configuration', side_effect=self.extracted_configuration):
            repeated=[self.run_control(2024), self.run_control(2025, 'B11')]
            self.assertEqual([r['version'] for r in first], [r['version'] for r in repeated])
            self.assertEqual(['NO_SOURCE_CONTENT_CHANGE', 'PREVIOUS_INPUT_WITHHELD'], [r['status'] for r in repeated])
            self.assertTrue(all(p.read_bytes()==raw for p,raw in old_pointer.items()))
            self.forbid_factory=False
            original=update.sha256_file
            with patch.object(update, 'sha256_file', side_effect=lambda *,path:
                    'changed-period' if path==ROOT/'scripts/vnext/normal_annual_input.py' else original(path=path)):
                changed=[self.run_control(2024),self.run_control(2025,'B11')]
                self.forbid_factory=True
                again=[self.run_control(2024),self.run_control(2025,'B11')]
        self.assertTrue(all(a['version']!=b['version'] for a,b in zip(first,changed)))
        self.assertEqual([r['version'] for r in changed], [r['version'] for r in again])
        self.assertEqual(4,len(self.factory_calls))

    def test_actual_main_f51_and_prior_extracted_pairs_keep_business_dependencies(self):
        from scripts.vnext import ordinary_update_compatibility as compat
        current=self.extracted_configuration(ROOT,'marriott_international','B04')
        for pair in (compat.MAIN_F51, compat.EXTRACTED_D04):
            old=deepcopy(current)
            old['processing_files'][CONTROLLER],old['processing_files'][STORE]=pair
            if pair==compat.EXTRACTED_D04:
                old['processing_files'][compat.BRIDGE]=compat.EXTRACTED_BRIDGE
            else:old['processing_files'].pop(compat.BRIDGE)
            self.assertTrue(compat.compatible_configuration(old,current))
            unknown=deepcopy(old);unknown['processing_files']['scripts/vnext/normal_annual_input.py']='unknown-business-version'
            self.assertFalse(compat.compatible_configuration(unknown,current))
        income=self.extracted_configuration(ROOT,'marriott_international','B01')
        old=deepcopy(income);old['processing_files'].pop(compat.BRIDGE)
        old['processing_files'][CONTROLLER],old['processing_files'][STORE]=compat.MAIN_C99
        old['processing_files'].pop('scripts/vnext/selected_fiscal_definition_scope_v1.py')
        self.assertFalse(compat.compatible_configuration(old,income))
        old=deepcopy(current);old['processing_files'][CONTROLLER],old['processing_files'][STORE]=compat.EXTRACTED_D04
        old['processing_files'][compat.BRIDGE]='unknown-migration-implementation'
        self.assertFalse(compat.compatible_configuration(old,current))

    def test_unknown_business_scope_or_source_change_cannot_inherit_compatibility(self):
        from scripts.vnext import ordinary_update_compatibility as compat
        current=self.extracted_configuration(ROOT,'marriott_international','B10')
        old=deepcopy(current);old['processing_files'].pop(compat.BRIDGE)
        old['processing_files'][CONTROLLER],old['processing_files'][STORE]=compat.MAIN_C99
        self.assertTrue(compat.compatible_configuration(old,current))
        originals=deepcopy(old),deepcopy(current)
        for path in (CONTROLLER,STORE,'scripts/vnext/normal_annual_input.py','scripts/vnext/calculator.py'):
            changed=deepcopy(current);changed['processing_files'][path]='unknown-consumed-change'
            self.assertFalse(compat.compatible_configuration(old,changed))
        for field,value in (('company_id','other'),('metric_id','B11'),('source_root','other'),
                            ('requested_fiscal_year',2023),('declared_processing_files',{'input':'new'}),
                            ('case_producer',{'sha256':'new'}),('source_registry_sha256','new'),('provider_enabled',True)):
            changed=deepcopy(current);changed[field]=value
            self.assertFalse(compat.compatible_configuration(old,changed))
        old_d04,new_d04=deepcopy(old),deepcopy(current)
        old_d04['metric_id']=new_d04['metric_id']='D04'
        self.assertFalse(compat.compatible_configuration(old_d04,new_d04))
        self.assertEqual(originals,(old,current))

    def test_compatible_completion_recovers_without_recalculating_or_rewriting_old_success(self):
        from scripts.vnext import ordinary_update_compatibility as compat
        def main_before(source,company,metric):
            config=self.actual_configuration(source,company,metric)
            config['processing_files'].pop(compat.BRIDGE)
            config['processing_files'][CONTROLLER],config['processing_files'][STORE]=compat.MAIN_C99
            return config
        with patch.object(update,'_configuration',side_effect=main_before):
            first=self.run_control(2024)
        root=self.period_root(2024);old_success=(root/'current-result.json').read_bytes()
        old_terminal=(root/'checks'/first['attempt_id']/'terminal.json').read_bytes()
        self.forbid_factory=True;write=update._write
        def interrupted(path,value):
            if path.name=='completed-check.json':raise KeyboardInterrupt('after compatible terminal')
            write(path,value)
        with patch.object(update,'_configuration',side_effect=self.extracted_configuration):
            with patch.object(update,'_write',side_effect=interrupted),self.assertRaises(KeyboardInterrupt):
                self.run_control(2024)
            again=self.run_control(2024)
        self.assertEqual(first['version'],again['version']);self.assertEqual(1,len(self.factory_calls))
        self.assertEqual(old_success,(root/'current-result.json').read_bytes())
        self.assertEqual(old_terminal,(root/'checks'/first['attempt_id']/'terminal.json').read_bytes())
