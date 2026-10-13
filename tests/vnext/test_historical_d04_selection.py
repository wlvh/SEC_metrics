"""Small period/source controls; no model answer or business result credit."""
from copy import deepcopy
from unittest import TestCase
from vnext.historical_d04_selection import select_saved_d04_source


class HistoricalD04SelectionTest(TestCase):
    def annual(self, **changes):
        annual={'company_id':'example', 'entity':'12345',
            'filing':{'accessionNumber':'target'}, 'table_input':{'target_period':{
                'fiscal_year':2023,'period_start':'2023-01-29','period_end':'2024-02-03'}}}
        annual.update(changes)
        return annual

    def source(self, annual=None):
        return {'record_type':'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE', 'metric_id':'D04',
            'company_id':'example','prepared_annual_input':annual or self.annual()}

    def test_exact_issuer_and_actual_dates_select_without_modifying_source(self):
        source=self.source();before=deepcopy(source)
        self.assertIs(source,select_saved_d04_source(prepared_annual=self.annual(),sources=[source]))
        self.assertEqual(before,source)

    def test_newest_source_cannot_replace_an_absent_requested_year(self):
        annual=self.annual();annual['table_input']['target_period'].update(
            fiscal_year=2025,period_start='2025-01-01',period_end='2025-12-31')
        with self.assertRaisesRegex(ValueError,'MISSING_OR_AMBIGUOUS:0') as error:
            select_saved_d04_source(prepared_annual=self.annual(),sources=[self.source(annual)])
        self.assertEqual('SOURCE_UNAVAILABLE',error.exception.category)

    def test_wrong_reporter_accession_or_actual_dates_are_not_matching_inputs(self):
        for field in ['entity','accession','start','end','label']:
            source=self.source();annual=source['prepared_annual_input']
            if field=='entity':annual['entity']='99999'
            elif field=='accession':annual['filing']['accessionNumber']='wrong'
            else:annual['table_input']['target_period'][{'start':'period_start','end':'period_end','label':'fiscal_year'}[field]]='wrong'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'MISSING_OR_AMBIGUOUS:0'):
                select_saved_d04_source(prepared_annual=self.annual(),sources=[source])

    def test_two_matching_sources_are_ambiguous_not_first_selected(self):
        with self.assertRaisesRegex(ValueError,'MISSING_OR_AMBIGUOUS:2') as error:
            select_saved_d04_source(prepared_annual=self.annual(),sources=[self.source(),self.source()])
        self.assertEqual('SOURCE_INTEGRITY_ERROR',error.exception.category)

    def test_missing_coordinate_is_integrity_failure_not_no_matching_year(self):
        source=self.source();del source['prepared_annual_input']['filing']
        with self.assertRaisesRegex(ValueError,'SOURCE_COORDINATE_INVALID') as error:
            select_saved_d04_source(prepared_annual=self.annual(),sources=[source])
        self.assertEqual('SOURCE_INTEGRITY_ERROR',error.exception.category)

    def test_other_metric_or_non_native_source_is_not_upgraded(self):
        for change in [{'metric_id':'D02'},{'record_type':'DIAGNOSTIC_SOURCE'}, {'company_id':'other'}]:
            source={**self.source(),**change}
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'MISSING_OR_AMBIGUOUS:0'):
                select_saved_d04_source(prepared_annual=self.annual(),sources=[source])


class HistoricalD04PackageSelectionTest(TestCase):
    """Small constructed archive calls the actual selector; public replay is absent."""
    def setUp(self):
        import tempfile
        from pathlib import Path
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.annual=HistoricalD04SelectionTest().annual()
        self.source={'record_type':'D04_NATIVE_COMPLETE_SEMANTIC_SOURCE',
            'metric_id':'D04','company_id':'example','semantic_source_id':'saved-source',
            'prepared_annual_input':self.annual,'required_unit_ids':['u1','u2']}
        self.requests=[{'company_id':'example','metric_id':'D04','target_cik':'12345',
            'target_period':self.annual['table_input']['target_period'],
            'request_id':'r'+str(n),'units':[{'unit_id':'u'+str(n)}]} for n in [1,2]]

    def package(self, *, missing_second=False, changed_period=False):
        import tarfile,json,io
        path=self.root/'existing-package.tar.gz'
        records={'root/binding.json':{'record_type':'CONSTRUCTED_EXISTING_LEDGER',
            'limits':[35,35,0]}}
        for index,request in enumerate(self.requests,20):
            records[f'root/calls/{index:04d}/source.json']=self.source
            if not (missing_second and index==21):
                records[f'root/calls/{index:04d}/semantic-request.json']=deepcopy(request)
        if changed_period:
            records['root/calls/0021/semantic-request.json']['target_period']={
                **self.annual['table_input']['target_period'],'period_end':'2023-12-31'}
        with tarfile.open(path,'w:gz') as archive:
            for name,record in records.items():
                raw=json.dumps(record).encode();member=tarfile.TarInfo(name);member.size=len(raw)
                archive.addfile(member,io.BytesIO(raw))
        return path

    def select(self, package):
        from unittest.mock import patch
        from vnext import historical_d04_selection as selection
        with patch.object(selection,'resolve_period_selection',return_value={'selected':'constructed'}), \
             patch.object(selection,'prepare_historical_annual_input',return_value=self.annual), \
             patch.object(selection,'validate_request_partition') as shared:
            value=selection.prepare_historical_d04_selection(source_root=self.root,
                company_id='example',fiscal_year=2023,saved_call_package=package)
        return value,shared

    def test_prepared_annual_and_original_complete_call_members_are_preserved(self):
        import hashlib
        package=self.package();before=hashlib.sha256(package.read_bytes()).hexdigest()
        value,shared=self.select(package)
        self.assertIs(value['prepared_annual_input'],self.annual)
        self.assertEqual([20,21],[call['ordinal'] for call in value['original_call_members']])
        self.assertEqual(self.source,value['original_source'])
        self.assertEqual(self.requests,shared.call_args.args[1])
        self.assertEqual(before,hashlib.sha256(package.read_bytes()).hexdigest())
        self.assertFalse(value['metric_executed'])
        self.assertEqual({'provider':0,'paid':0,'sec':0},value['new_calls'])
        self.assertEqual([package],list(self.root.iterdir()))

    def test_missing_request_is_not_silently_a_complete_response_group(self):
        with self.assertRaisesRegex(ValueError,'PACKAGE_MEMBER_MISSING'):
            self.select(self.package(missing_second=True))

    def test_another_actual_period_request_is_refused_before_public_replay(self):
        with self.assertRaisesRegex(ValueError,'REQUEST_COORDINATE_CHANGED'):
            self.select(self.package(changed_period=True))

    def test_duplicate_named_archive_member_is_not_silently_overwritten(self):
        import tarfile,io,json
        package=self.package()
        # Own tiny test archive only: emulate a mistaken double-copy packaging.
        with tarfile.open(package) as archive:
            members=[(m.name,archive.extractfile(m).read()) for m in archive if m.isfile()]
        with tarfile.open(package,'w:gz') as archive:
            for name,raw in [*members,members[0]]:
                member=tarfile.TarInfo(name);member.size=len(raw)
                archive.addfile(member,io.BytesIO(raw))
        with self.assertRaisesRegex(ValueError,'DUPLICATE_PACKAGE_MEMBER'):
            self.select(package)
