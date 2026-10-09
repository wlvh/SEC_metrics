"""The inspected three-file transition only; unknown changes reprocess."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from vnext import ordinary_current_update as update
from vnext import ordinary_update_compatibility as compat

ROOT=Path(__file__).resolve().parents[2]


def old_configuration(current):
    old=deepcopy(current);files=old['processing_files']
    files.pop(compat.BRIDGE)
    files[compat.SESSION]=compat.OLD_SESSION
    files[compat.CONTROLLER]=compat.OLD_CONTROLLER
    files[compat.PRESENTATION]=compat.OLD_PRESENTATION
    return old


class FiniteConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.current={**update._configuration(ROOT,'jpmorgan_chase','A03'),
            'requested_fiscal_year':2021,'declared_processing_files':{'source-rule':'same'},
            'case_producer':{'name':'source_factory','sha256':'same'}}
        self.old=old_configuration(self.current)

    def test_only_proven_transition_is_compatible_without_mutation(self):
        old,new=deepcopy(self.old),deepcopy(self.current)
        self.assertTrue(compat.compatible_configuration(old,new))
        self.assertEqual(old,self.old);self.assertEqual(new,self.current)

    def test_meaningful_or_unknown_changes_are_not_compatible(self):
        for field,value in [('company_id','another-company'),('metric_id','B12'),
                ('requested_fiscal_year',2022),('source_root','another-root'),
                ('source_registry_sha256','another-registry'),('case_producer',{'sha256':'new'}),
                ('declared_processing_files',{'source-rule':'new'}),('provider_enabled',True)]:
            with self.subTest(field=field):
                changed=deepcopy(self.current);changed[field]=value
                self.assertFalse(compat.compatible_configuration(self.old,changed))
        for path in (compat.CONTROLLER,compat.PRESENTATION,'scripts/vnext/normal_annual_input.py'):
            with self.subTest(path=path):
                changed=deepcopy(self.current);changed['processing_files'][path]='unknown-change'
                self.assertFalse(compat.compatible_configuration(self.old,changed))
        old=deepcopy(self.old);old['processing_files'][compat.SESSION]='unknown-old-session'
        self.assertFalse(compat.compatible_configuration(old,self.current))
        old=deepcopy(self.old);old['processing_files']['unknown-required-file']='required'
        self.assertFalse(compat.compatible_configuration(old,self.current))

    def test_d04_or_default_current_scope_does_not_use_this_bridge(self):
        for metric in ('D04','E01','B01'):
            old,new=deepcopy(self.old),deepcopy(self.current)
            old['metric_id']=new['metric_id']=metric
            self.assertFalse(compat.compatible_configuration(old,new))
        self.old.pop('requested_fiscal_year');self.current.pop('requested_fiscal_year')
        self.assertFalse(compat.compatible_configuration(self.old,self.current))


class CompatibleCheckRecoveryTest(unittest.TestCase):
    def exercise(self,publication,crash=False):
        calls=[];records={}
        def factory(**kwargs):
            calls.append(kwargs);return {'target_period':{'fiscal_year':2021}}
        def save(**kwargs):
            path=kwargs['output_root'];path.mkdir(parents=True)
            saved={'manifest':{'company_id':'jpmorgan_chase','metric_id':'A03','source_proofs':[]},
                'result':{'company_id':'jpmorgan_chase','metric_id':'A03','publication':publication,
                    'period_end':'2021-12-31','result_id':'synthetic-compatibility-result'}}
            records[str(path)]=saved;return saved
        original=update._configuration
        with tempfile.TemporaryDirectory() as folder,patch.object(update,'_source_census',return_value=[]), \
             patch.object(update,'_current_sources',return_value=[]), \
             patch.object(update,'save_calculated_case',side_effect=save), \
             patch.object(update,'read_saved_result',side_effect=lambda **kwargs:deepcopy(records[str(kwargs['output_root'])])):
            args=dict(state_root=Path(folder)/'state',source_root=ROOT,company_id='jpmorgan_chase',
                metric_id='A03',fiscal_year=2021,case_factory=factory)
            with patch.object(update,'_configuration',side_effect=lambda *a:old_configuration(original(*a))):
                first=update.run_once(**args)
            state=args['state_root']/'periods/FY2021'
            terminal=state/'checks'/first['attempt_id']/'terminal.json';old_terminal=terminal.read_bytes()
            success=state/'current-result.json';success_bytes=success.read_bytes() if success.exists() else None
            results=set((state/'results').iterdir());write=update._write
            def interrupt(path,value):
                if path.name=='completed-check.json':raise KeyboardInterrupt('After compatible terminal commit')
                write(path,value)
            with patch.object(update,'save_calculated_case',side_effect=AssertionError('No compatible recalculation')):
                if crash:
                    with patch.object(update,'_write',side_effect=interrupt),self.assertRaises(KeyboardInterrupt):
                        update.run_once(**args)
                second=update.run_once(**args)
                third=update.run_once(**args)
            expected='PREVIOUS_INPUT_WITHHELD' if publication=='WITHHELD' else 'NO_SOURCE_CONTENT_CHANGE'
            self.assertEqual(second['status'],expected);self.assertEqual(third['status'],expected)
            self.assertFalse(second['calculation_performed']);self.assertEqual(len(calls),1)
            self.assertEqual(second['result_id'],first['result_id'])
            self.assertEqual(set((state/'results').iterdir()),results)
            self.assertEqual(terminal.read_bytes(),old_terminal)
            self.assertEqual(success.read_bytes() if success.exists() else None,success_bytes)
            # A real later consumed source change must not inherit the bridge.
            actual_hash=update.sha256_file
            with patch.object(update,'sha256_file',side_effect=lambda *,path:
                    'changed-consumed-period-rule' if path==ROOT/'scripts/vnext/normal_annual_input.py'
                    else actual_hash(path=path)):
                changed=update.run_once(**args)
            self.assertTrue(changed['calculation_performed']);self.assertEqual(len(calls),2)

    def test_published_conclusion_and_original_success_are_kept(self):self.exercise('PUBLISHED')
    def test_stable_withheld_is_kept_without_becoming_success(self):self.exercise('WITHHELD')
    def test_interrupted_compatible_check_recovers_without_computing(self):self.exercise('PUBLISHED',crash=True)


if __name__=='__main__':unittest.main()
