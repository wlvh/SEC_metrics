"""Explicit SEC release spelling across source/layout; old defaults remain exact."""
import ast,json,subprocess,tempfile,unittest
from pathlib import Path
from tests.vnext.test_text_coverage import annual,BODY,binding
from tests.vnext.test_instant_amendment_paragraph_api import filing_html
from vnext.text_coverage import build_text_document,verify_text_document
from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope
from vnext.instant_balance_amendment_v2 import inspect_instant_balance_amendment
from vnext.sources import raw_blob_record,source_reference_record
from vnext.xbrl_namespace_policy import YEAR_ONLY,YEAR_QUARTER_OR_DATE

class SelectedDeiTextScopeTest(unittest.TestCase):
    def test_date_quarter_source_requires_explicit_policy_and_replays_exact_bytes(self):
        for uri in ('http://xbrl.sec.gov/dei/2020-01-31','https://xbrl.sec.gov/dei/2021q4'):
            raw=annual(BODY).replace(b'http://xbrl.sec.gov/dei/2025',uri.encode());args=binding(raw)
            with self.subTest(uri=uri):
                with self.assertRaisesRegex(ValueError,'ENTITY_MISMATCH_OR_MISSING'):build_text_document(**args)
                doc=build_text_document(**args,namespace_policy=YEAR_QUARTER_OR_DATE)
                self.assertEqual(doc['namespace_policy'],YEAR_QUARTER_OR_DATE)
                self.assertEqual(verify_text_document(document=doc,**args,namespace_policy=YEAR_QUARTER_OR_DATE),doc)
                block=doc['blocks'][0]
                self.assertEqual(raw[block['raw_start_byte']:block['raw_end_byte']],b'Item 1. Business')

    def sources(self,root,uri):
        result=[]
        for amended in (False,True):
            raw=filing_html(amended).replace(b'http://xbrl.sec.gov/dei/2024',uri.encode())
            name='amended.htm' if amended else 'original.htm';(root/name).write_bytes(raw)
            blob=raw_blob_record(repo_root=root,repo_relative_path=name,media_type='text/html');acc='0000000001-25-00000'+('2' if amended else '1')
            ref=source_reference_record(raw_blob=blob,company_id='constructed',source_url='https://www.sec.gov/Archives/edgar/data/1/'+acc.replace('-','')+'/'+name,accession=acc,document_name=name,source_role='target_primary',request_attempt_id='constructed-no-credit')
            result.append({'raw':raw,'blob':blob,'reference':ref,'filing':{'form':'10-K/A' if amended else '10-K','reportDate':'2024-12-31','filingDate':'2025-04-25' if amended else '2025-02-26','accessionNumber':acc,'primaryDocument':name}})
        return result

    def test_explicit_amendment_and_false_correction_flag_share_the_same_policy(self):
        with tempfile.TemporaryDirectory() as d:
            original,amend=self.sources(Path(d),'http://xbrl.sec.gov/dei/2020-01-31')
            args=dict(original=original,amendment=amend,company_id='constructed',cik='1',note_layout='inline-paragraphs-v2')
            with self.assertRaisesRegex(ValueError,'ENTITY_MISMATCH_OR_MISSING'):inspect_annual_amendment_scope(**args)
            scope=inspect_annual_amendment_scope(**args,namespace_policy=YEAR_QUARTER_OR_DATE)
            self.assertEqual(scope['issues'],[]);self.assertEqual(scope['namespace_policy'],YEAR_QUARTER_OR_DATE)
            instant=inspect_instant_balance_amendment(**args,namespace_policy=YEAR_QUARTER_OR_DATE)
            self.assertEqual(instant['decision'],'INPUT_PROPERTY_PROVEN')
            self.assertEqual(instant['details']['native_correction_flag']['namespace'],'http://xbrl.sec.gov/dei/2020-01-31')
            self.assertFalse(instant['metric_result_created'])

    def test_defaults_match_complete_legacy_objects_and_invalid_policy_still_refuses(self):
        args=binding(annual(BODY));a=build_text_document(**args)
        self.assertEqual(a,build_text_document(**args,namespace_policy=YEAR_ONLY));self.assertNotIn('namespace_policy',a)
        for policy in ('*','YEAR_OR_DATE_RELEASE',None):
            with self.subTest(policy=policy),self.assertRaisesRegex(ValueError,'POLICY_UNSUPPORTED'):
                build_text_document(**args,namespace_policy=policy)
        for uri in ('https://example.invalid/dei/2020-01-31','http://xbrl.sec.gov/dei/2021q5','http://xbrl.sec.gov/dei/2020-01-31/extra'):
            raw=annual(BODY).replace(b'http://xbrl.sec.gov/dei/2025',uri.encode())
            with self.subTest(uri=uri),self.assertRaisesRegex(ValueError,'ENTITY_MISMATCH_OR_MISSING'):
                build_text_document(**binding(raw),namespace_policy=YEAR_QUARTER_OR_DATE)

    def test_modern_default_complete_return_matches_fixed_main_function(self):
        from vnext import text_coverage as current
        raw=subprocess.check_output(['git','show','3c2d8f88acf31c87d770ce033dd0c8aedc790b9b:scripts/vnext/text_coverage.py'],text=True)
        node=next(n for n in ast.parse(raw).body if isinstance(n,ast.FunctionDef) and n.name=='build_text_document')
        environment=current.__dict__.copy()
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<fixed-main builder>','exec'),environment)
        args=binding(annual(BODY));self.assertEqual(environment['build_text_document'](**args),build_text_document(**args))

    def test_modern_amendment_default_still_delegates_complete_legacy_object(self):
        from unittest.mock import patch
        from vnext import annual_amendment_scope_v2 as current
        with tempfile.TemporaryDirectory() as d:
            original,amended=self.sources(Path(d),'http://xbrl.sec.gov/dei/2024')
            args=dict(original=original,amendment=amended,company_id='constructed',cik='1')
            legacy=current.legacy.inspect_annual_amendment_scope
            with patch.object(current.legacy,'inspect_annual_amendment_scope',wraps=legacy) as old:
                observed=current.inspect_annual_amendment_scope(**args);old.assert_called_once_with(**args)
            self.assertEqual(observed,legacy(**args));self.assertNotIn('namespace_policy',observed)
