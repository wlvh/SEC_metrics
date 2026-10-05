"""Prior XML satisfies only the existing prior-period/auditor dependency."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from sec_urls import accession_directory_url,accession_document_url
from vnext.normal_source_requirements import _satisfy_prior_primary_alternatives,source_dependency_satisfied
from vnext.normal_annual_input import NormalAnnualInputError
from vnext.normal_governance_input import NormalGovernanceInputError
from vnext.ordinary_refresh_cycle import _pending


class PriorHtmlDependencyTest(unittest.TestCase):
    def setUp(self):
        self.company={'company_id':'arbitrary_company','primary_cik':'123'}
        self.filing={'accessionNumber':'0000000123-25-000001','primaryDocument':'annual.htm','form':'10-K','reportDate':'2024-12-31'}
        self.html=accession_document_url(cik=123,accession=self.filing['accessionNumber'],document_name='annual.htm')
        self.xml=accession_document_url(cik=123,accession=self.filing['accessionNumber'],document_name='annual.xml')
        self.index=accession_directory_url(cik=123,accession=self.filing['accessionNumber'])
        self.ref={'source_reference_id':'native','source_url':self.xml}
        self.sources=[{'source_reference':self.ref,'raw_bytes':b'native parser tested in actual-source material','raw_blob':{}}]
        self.reader=Mock();self.reader.auditor_filing.return_value=self.sources
        self.reader.records={'index':{'source_reference_id':'index'}}
        self.reader.file_sets=[{'primary_saved':False,'expected_xml_documents':['annual.xml'],'index_source_reference_id':'index'}]
        self.plan=SimpleNamespace(company=self.company,reader=self.reader,requests={
            self.html:{'source_url':self.html,'roles':['prior_annual_primary'],'saved_status':'MISSING_SAVED_SOURCE','refresh_for_new_discovery':False},
            self.xml:{'source_url':self.xml,'roles':['annual_accession_instance'],'saved_status':'VERIFIED_SAVED_SOURCE','source_reference':self.ref,'refresh_for_new_discovery':False},
            self.index:{'source_url':self.index,'roles':['annual_accession_index'],'saved_status':'VERIFIED_SAVED_SOURCE','source_reference':{'source_reference_id':'index'},'refresh_for_new_discovery':False}})
        self.prepared={'entity':'123','table_input':{'target_period':{'period_start':'2025-01-01','period_end':'2025-12-31'}}}
        self.period={'period_start':'2024-01-01','period_end':'2024-12-31'}
        self.auditor={'status':'FOUND','facts':[{'name':'Auditor'}]}

    def run_helper(self):
        with patch('vnext.normal_source_requirements.annual_period',return_value=self.period),patch('vnext.governance_signals._auditor_filing',return_value=self.auditor):
            _satisfy_prior_primary_alternatives(self.plan,self.prepared,{'prior_filing_chain':[self.filing]})
        return self.plan.requests[self.html]

    def assert_pending(self):
        row=self.run_helper();self.assertFalse(source_dependency_satisfied(row))
        if row['saved_status']=='MISSING_SAVED_SOURCE':
            self.assertIn(row,_pending({'requirements':list(self.plan.requests.values())},set(),set()))

    def test_exact_alternative_retains_missing_fact_and_has_no_metric_credit(self):
        row=self.run_helper();self.assertEqual(row['saved_status'],'MISSING_SAVED_SOURCE')
        self.assertTrue(source_dependency_satisfied(row));alternative=row['alternative_dependency']
        self.assertEqual(alternative['source_references'],[self.ref]);self.assertEqual(alternative['auditor_facts'],self.auditor['facts'])
        for field in ('source_acquisition_credit','metric_executed','all_39_metric_source_acceptance_proven'):self.assertFalse(alternative[field])
        self.assertEqual(_pending({'requirements':list(self.plan.requests.values())},set(),set()),[])

    def test_other_html_role_still_requires_original(self):
        self.plan.requests[self.html]['roles'].append('current_annual_primary');self.assert_pending();self.reader.auditor_filing.assert_not_called()

    def test_failed_original_is_not_revived_by_xml(self):
        self.plan.requests[self.html]['saved_status']='SAVED_SOURCE_BLOCKED';self.assert_pending();self.reader.auditor_filing.assert_not_called()

    def test_missing_or_unverified_xml_and_index_stay_pending(self):
        for url in (self.xml,self.index):
            for status in ('MISSING_SAVED_SOURCE','SAVED_SOURCE_BLOCKED'):
                with self.subTest(url=url,status=status):
                    self.setUp();self.plan.requests[url]['saved_status']=status;self.assert_pending()

    def test_missing_native_input_and_saved_primary_race_stay_pending(self):
        self.reader.auditor_filing.side_effect=NormalGovernanceInputError('NATIVE_NOT_SAVED');self.assert_pending()
        self.setUp();self.reader.file_sets[-1]['primary_saved']=True;self.assert_pending()
        self.setUp();self.reader.file_sets[-1]['expected_xml_documents']=[];self.assert_pending()

    def test_subject_and_nonadjacent_prior_stay_pending(self):
        self.prepared['entity']='456';self.assert_pending()
        self.setUp();self.period['period_end']='2023-12-31';self.assert_pending()

    def test_role_difference_is_allowed_but_source_or_attempt_change_is_not(self):
        self.plan.requests[self.xml]['source_reference']=dict(self.ref,source_role='annual_accession_instance',source_reference_id='discovery')
        self.ref['source_role']='auditor_facts'
        self.assertTrue(source_dependency_satisfied(self.run_helper()))
        for field in ('raw_asset_id','request_attempt_id','accession','company_id'):
            with self.subTest(field=field):
                self.setUp();self.plan.requests[self.xml]['source_reference']=dict(self.ref,**{field:'different'})
                self.assert_pending()

    def test_missing_or_conflicting_auditor_stays_pending(self):
        for status in ('MISSING','CONFLICT'):
            with self.subTest(status=status):self.setUp();self.auditor['status']=status;self.assert_pending()

    def test_native_parser_rejection_does_not_form_a_disclosure_limit(self):
        with patch('vnext.normal_source_requirements.annual_period',side_effect=NormalAnnualInputError('ENTITY_PERIOD_OR_AMENDMENT_INVALID')):
            _satisfy_prior_primary_alternatives(self.plan,self.prepared,{'prior_filing_chain':[self.filing]})
        row=self.plan.requests[self.html];self.assertFalse(source_dependency_satisfied(row))
        self.assertEqual(row['alternative_dependency']['status'],'NOT_ESTABLISHED')

    def test_metadata_refresh_remains_required_and_failed_urls_never_retry(self):
        row=self.run_helper();row['refresh_for_new_discovery']=True
        self.assertEqual(_pending({'requirements':[row]},set(),set()),[row])
        self.assertEqual(_pending({'requirements':[row]},set(),{self.html}),[])


if __name__=='__main__':unittest.main()
