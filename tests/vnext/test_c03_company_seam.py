"""C03 explicit-case gate only; no fabricated company business result."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from copy import deepcopy
from sec_urls import accession_document_url

from vnext import company_current_records as company
from vnext import ordinary_current_update as update
from vnext.ordinary_saved_result import EXPLICIT_CASE_METRICS, SAVED_METRIC_IDS
from tests.vnext.common import REPO_ROOT


class C03CompanySeamTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()

    def test_default_current_route_and_unselected_controller_remain_closed(self):
        self.assertIn('C03',EXPLICIT_CASE_METRICS)
        self.assertNotIn('C03',SAVED_METRIC_IDS)
        with patch.object(company,'run_once',side_effect=AssertionError('No default C03')):
            report=company.run_saved_company(company_id='marriott_international',source_root=REPO_ROOT,
                work_dir=self.root/'state',output_dir=self.root/'out',metric_ids=['C03'])
        self.assertEqual('PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED',report['metrics'][0]['status'])
        with self.assertRaisesRegex(ValueError,'CURRENT_UPDATE_METRIC_UNSUPPORTED'):
            update.run_once(state_root=self.root/'direct',source_root=REPO_ROOT,
                company_id='marriott_international',metric_id='C03')

    def test_explicit_selected_case_reaches_real_controller_and_failure_is_readable(self):
        seen=[]
        def factory(**kw):
            seen.append(kw)
            raise ValueError('C03_CONSTRUCTED_FACTORY_CONTROL_NO_BUSINESS_RESULT')
        # Only discovery/configuration are isolated: actual selected-year
        # controller, intents, failure records, company export and read run.
        with patch.object(update,'_configuration',return_value={'gate_control_only':True}), \
             patch.object(update,'_source_census',return_value=[]), \
             patch.object(update,'create_saved_result',side_effect=AssertionError('No default calculator')):
            report=company.run_saved_company(company_id='marriott_international',source_root=REPO_ROOT,
                work_dir=self.root/'selected',output_dir=self.root/'runs',metric_ids=['C03'],
                fiscal_years=[2022],case_factories={'C03':factory},
                processing_files_by_metric={'C03':('scripts/vnext/xbrl_namespace_policy.py',)})
        self.assertEqual(1,len(seen));self.assertEqual('C03',seen[0]['metric_id'])
        self.assertEqual(2022,seen[0]['fiscal_year'])
        self.assertEqual('INPUT_OR_EXECUTION_FAILED',report['metrics'][0]['status'])
        self.assertEqual('C03_CONSTRUCTED_FACTORY_CONTROL_NO_BUSINESS_RESULT',report['metrics'][0]['reason'])
        with patch.object(company,'run_once',side_effect=AssertionError('No update while reading')):
            view=company.read_current_company(state_root=self.root/'selected',company_id='marriott_international')
        self.assertEqual('C03_CONSTRUCTED_FACTORY_CONTROL_NO_BUSINESS_RESULT',view['metrics'][0]['reason'])
        self.assertIsNone(view['metrics'][0]['value'])
        self.assertFalse(list((self.root/'selected').rglob('current-result.json')))

    def test_selected_proxy_metadata_keeps_source_form_for_value_and_hold(self):
        from vnext.ordinary_projection import _selected_proxy_display
        proxy={'form':'DEF 14A','filingDate':'2023-03-23',
               'accessionNumber':'0001140361-23-014123','primaryDocument':'proxy.htm'}
        annual={'company_id':'marriott_international','entity':'1048286',
                'filing':{'form':'10-K','filingDate':'2023-02-14'}}
        ref={'company_id':annual['company_id'],'accession':proxy['accessionNumber'],
             'document_name':proxy['primaryDocument'],'source_role':'governance_proxy',
             'source_url':accession_document_url(cik=1048286,accession=proxy['accessionNumber'],
                                                document_name=proxy['primaryDocument'])}
        case={'primary_metric_id':'C03','selected_proxy':proxy,'input_binding':{'selected_proxy':deepcopy(proxy)},
              'references':[ref]}
        for evidence in ([],[{'accession':proxy['accessionNumber']}]):
            before=deepcopy(annual)
            display=_selected_proxy_display(case=case,annual=annual,evidence=evidence)
            self.assertEqual(('DEF 14A','2023-03-23'),(display['form'],display['filingDate']))
            self.assertEqual(before,annual)
        for key,value in (('company_id','macys'),('document_name','different.htm'),
                          ('source_role','target_primary'),('source_url',ref['source_url'].replace('/1048286/','/794367/'))):
            bad=deepcopy(case);bad['references'][0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'PROXY_SOURCE_NOT_BOUND'):
                _selected_proxy_display(case=bad,annual=annual,evidence=[])
        bad=deepcopy(case);bad['input_binding']['selected_proxy']['filingDate']='2023-03-24'
        with self.assertRaisesRegex(ValueError,'PROXY_METADATA_NOT_BOUND'):
            _selected_proxy_display(case=bad,annual=annual,evidence=[])
        with self.assertRaisesRegex(ValueError,'PROXY_SOURCE_NOT_BOUND'):
            _selected_proxy_display(case=case,annual=annual,evidence=[{'accession':'other-proxy'}])
        self.assertIsNone(_selected_proxy_display(case={'primary_metric_id':'B01'},annual=annual,evidence=[]))


if __name__=='__main__':unittest.main()
