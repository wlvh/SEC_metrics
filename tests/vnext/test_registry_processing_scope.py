"""Actual updater configuration with isolated registries; small state is constructed."""
import csv
from pathlib import Path
from unittest.mock import patch
import unittest
from tests.vnext import test_ordinary_current_update as fixtures
from scripts.vnext import ordinary_current_update as update

PROGRAM=Path(__file__).resolve().parents[2]
ACTUAL_CONFIGURATION=update._configuration


class ProgramRegistryOverlay:
    """Only the test registry is overlaid; every rule/config reads real program bytes."""
    def __init__(self,path,prefix=''):self.path=path;self.prefix=prefix
    def __truediv__(self,relative):
        name=str(Path(self.prefix)/relative) if self.prefix else str(relative)
        if name=='config':return ProgramRegistryOverlay(self.path,'config')
        return self.path if name=='config/company_registry.csv' else PROGRAM/name


class RegistryProcessingScopeTest(unittest.TestCase):
    def setUp(self):
        fixtures.CurrentUpdateTest.setUp(self)
        base=Path(self.temp.name)
        self.source=base/'source';(self.source/'config').mkdir(parents=True)
        self.program_registry=base/'program-registry.csv'
        self.source_registry=self.source/'config/company_registry.csv'
        raw=(PROGRAM/'config/company_registry.csv').read_bytes()
        self.program_registry.write_bytes(raw);self.source_registry.write_bytes(raw)
        p=patch.object(update,'ROOT',ProgramRegistryOverlay(self.program_registry));p.start();self.addCleanup(p.stop)
        p=patch.object(update,'_configuration',side_effect=ACTUAL_CONFIGURATION);p.start();self.addCleanup(p.stop)

    def run_check(self):
        return update.run_once(state_root=self.root,source_root=self.source,
            company_id='marriott_international',metric_id='B01')

    def edit(self,path,company,field,value,add=False):
        with path.open(newline='') as stream:
            reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
        if add:
            row=dict(rows[1]);row.update(company_id='TEST_ONLY_UNRELATED',display_name='Test unrelated company',primary_cik='9999999');rows.append(row)
        else:next(r for r in rows if r['company_id']==company)[field]=value
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)

    def test_unrelated_program_row_add_or_change_keeps_existing_result(self):
        first=self.run_check();self.edit(self.program_registry,'southwest_airlines','display_name','TEST_ONLY changed name')
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No unrelated-row calculation')):
            again=self.run_check()
        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',again['status'])
        self.assertEqual(first['result_id'],again['result_id'])
        self.edit(self.program_registry,None,None,None,add=True)
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No unrelated-add calculation')):
            again=self.run_check()
        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',again['status'])

    def test_unrelated_source_row_add_or_change_keeps_existing_result(self):
        first=self.run_check();self.edit(self.source_registry,'southwest_airlines','ticker','TEST_ONLY')
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No unrelated-row calculation')):
            again=self.run_check()
        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',again['status'])
        self.assertEqual(first['result_id'],again['result_id'])
        self.edit(self.source_registry,None,None,None,add=True)
        with patch.object(update,'create_saved_result',side_effect=AssertionError('No unrelated-add calculation')):
            again=self.run_check()
        self.assertEqual('NO_SOURCE_CONTENT_CHANGE',again['status'])

    def test_target_cik_role_industry_and_period_fields_require_processing(self):
        self.run_check()
        for path in (self.program_registry,self.source_registry):
            for field,value in (('primary_cik','1048287'),('roles','primary:1048287'),
                ('industry_profile','manufacturing'),('fiscal_year_end','0630'),
                ('target_period_policy','TEST_ONLY changed period rule')):
                before=self.calculations;self.edit(path,'marriott_international',field,value)
                answer=self.run_check()
                self.assertEqual('CANDIDATE_READY',answer['status'])
                self.assertEqual(before+1,self.calculations)

    def test_consumed_rule_change_still_requires_processing(self):
        self.run_check();original=update.sha256_file
        with patch.object(update,'sha256_file',side_effect=lambda *,path:
                'TEST_ONLY new selected rule' if path==PROGRAM/'scripts/vnext/normal_annual_input.py' else original(path=path)):
            answer=self.run_check()
        self.assertEqual('CANDIDATE_READY',answer['status']);self.assertEqual(2,self.calculations)

    def test_unrelated_unknown_profile_cannot_reuse_success(self):
        self.run_check();old=(self.root/'current-result.json').read_bytes()
        self.edit(self.program_registry,'southwest_airlines','industry_profile','TEST_ONLY_MISSING_PROFILE')
        with patch.object(update,'create_saved_result',side_effect=AssertionError('Invalid profile must stop')):
            failed=self.run_check()
        self.assertEqual('INPUT_OR_EXECUTION_FAILED',failed['status'])
        self.assertIn('Company registry profile has no trait mapping',failed['reason'])
        self.assertEqual(old,(self.root/'current-result.json').read_bytes())
        self.assertEqual(1,self.calculations)

    def test_registry_integrity_failure_never_reuses_old_success(self):
        self.run_check();old=(self.root/'current-result.json').read_bytes()
        for path in (self.program_registry,self.source_registry):
            original=path.read_bytes()
            with path.open(newline='') as stream:rows=list(csv.reader(stream))
            with path.open('a',newline='') as stream:csv.writer(stream).writerow(rows[2])
            with patch.object(update,'create_saved_result',side_effect=AssertionError('Invalid registry must stop')):
                failed=self.run_check()
            self.assertEqual('INPUT_OR_EXECUTION_FAILED',failed['status'])
            self.assertEqual(old,(self.root/'current-result.json').read_bytes())
            path.write_bytes(original)

    def test_duplicate_header_cannot_hide_behind_equal_target_row(self):
        self.run_check()
        with self.source_registry.open(newline='') as stream:rows=list(csv.reader(stream))
        at=rows[0].index('primary_cik')
        with self.source_registry.open('w',newline='') as stream:
            writer=csv.writer(stream)
            writer.writerows([row+[row[at]] for row in rows])
        with patch.object(update,'create_saved_result',side_effect=AssertionError('Ambiguous header')):
            result=self.run_check()
        self.assertEqual('INPUT_OR_EXECUTION_FAILED',result['status'])
        self.assertIn('FIELDS_AMBIGUOUS',result['reason'])

    def test_target_row_required_and_full_context_retained(self):
        from scripts.vnext.ordinary_registry_scope import registered_company_row
        row=registered_company_row(repo_root=self.source,company_id='marriott_international')
        self.assertEqual('1048286',row['primary_cik']);self.assertEqual('1231',row['fiscal_year_end'])
        self.assertEqual('primary:1048286',row['roles'])
        with self.assertRaisesRegex(ValueError,'TARGET_NOT_UNIQUE'):
            registered_company_row(repo_root=self.source,company_id='TEST_ONLY_ABSENT')

if __name__=='__main__':unittest.main()
