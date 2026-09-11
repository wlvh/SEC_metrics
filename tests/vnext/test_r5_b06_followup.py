"""Annual metadata must fail closed before sorting or amendment filtering."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from vnext import r5_b06_structured as primary

class B06DiscoveryFollowupTest(unittest.TestCase):
    def call(self, extra=None, end='2025-12-31', shards=None):
        filing={'form':'10-K','accessionNumber':'0000000001-26-000001','reportDate':end,'filingDate':'2026-02-10','primaryDocument':'annual.htm'}
        rows=[filing]+([] if extra is None else [extra]);recent={k:[r[k] for r in rows] for k in filing}
        payload={'cik':1,'filings':{'recent':recent,'files':shards or []}}
        facts={'cik':1,'facts':{'us-gaap':{'StockholdersEquity':{'units':{'USD':[{'accn':filing['accessionNumber'],'end':end,'form':'10-K','fp':'FY','fy':2025,'val':100}]}}}}}
        def source(**kwargs):
            v=payload if '/submissions/' in kwargs['url'] else facts
            return {'source_url':kwargs['url'],'document_name':'CIK0000000001.json','request_repo_relative_path':'unused','request_headers_repo_relative_path':'unused'},json.dumps(v).encode()
        with patch('vnext.annual_input._saved_source',side_effect=source),patch('vnext.annual_update._rows',return_value=[]):
            return primary.discover(data_root=Path('/nonexistent-b06-test-root'),company={'primary_cik':'1','company_id':'synthetic','display_name':'Synthetic'})
    def extra(self, form='10-K', report=''):
        return {'form':form,'accessionNumber':'0000000001-26-000002','reportDate':report,'filingDate':'2026-03-01','primaryDocument':'new.htm'}
    def test_newer_unknown_report_date_10k_cannot_disappear(self):
        with self.assertRaisesRegex(ValueError,'DATE'):self.call(self.extra())
    def test_unknown_amendment_period_cannot_disappear(self):
        with self.assertRaisesRegex(ValueError,'DATE'):self.call(self.extra('10-K/A'))
    def test_noncalendar_period_remains_supported(self):
        self.assertEqual('2026-01-31',self.call(end='2026-01-31')['target_period']['period_end'])
    def test_invalid_annual_identity_and_dates_are_rejected(self):
        for key,value in [('accessionNumber','unknown'),('reportDate','2025-99-99'),('filingDate',''),('primaryDocument','../bad.htm')]:
            row=self.extra('10-K/A','2025-12-31');row[key]=value
            with self.subTest(field=key),self.assertRaises(ValueError):self.call(row)
    def test_relevant_history_shard_requires_complete_saved_list(self):
        with self.assertRaisesRegex(ValueError,'HISTORY'):self.call(shards=[{'name':'history.json','filingFrom':'2026-01-01','filingTo':'2026-03-01'}])
if __name__=='__main__':unittest.main()

class B06AmendmentImpactTest(unittest.TestCase):
    def material(self):
        from vnext.canonical import strict_json_file
        root=Path(__file__).resolve().parents[2]
        review=strict_json_file(path=root/'docs/evidence/r5_b06_followup/amendment_assessments.json')
        return root,review
    def test_complete_reviewed_amendments_release_only_data_blocker(self):
        from vnext.r5_b06_amendments import verify_reviewed_impact
        root,review=self.material()
        for decision in review['decisions']:
            original=decision['original'];amendment=decision['amendment'];cik=original['identity'][0]['text']
            value=verify_reviewed_impact(original_raw=(root/original['request_ledger_row']['repo_relative_path']).read_bytes(),amendment_raw=(root/amendment['request_ledger_row']['repo_relative_path']).read_bytes(),original=original['filing'],amendment=amendment['filing'],cik=cik,decision=decision)
            self.assertEqual('NO_B06_SOURCE_IMPACT',value['decision']);self.assertFalse(value['production_permission']);self.assertTrue(value['preserved_anomalies'])
    def test_changed_unknown_financial_or_wrong_relation_cannot_borrow_review(self):
        from vnext.r5_b06_amendments import verify_reviewed_impact
        root,review=self.material();d=review['decisions'][0];o=d['original'];a=d['amendment'];ob=(root/o['request_ledger_row']['repo_relative_path']).read_bytes();ab=(root/a['request_ledger_row']['repo_relative_path']).read_bytes()
        for content in [ab+b' ',ab.replace(b'Explanatory Note',b'Financial Restatement'),b'<html>Part III only</html>',b'']:
            with self.assertRaisesRegex(ValueError,'BYTES_CHANGED'):verify_reviewed_impact(original_raw=ob,amendment_raw=content,original=o['filing'],amendment=a['filing'],cik=o['identity'][0]['text'],decision=d)
        bad={**a['filing'],'reportDate':'2024-12-31'}
        with self.assertRaisesRegex(ValueError,'RELATION_CHANGED'):verify_reviewed_impact(original_raw=ob,amendment_raw=ab,original=o['filing'],amendment=bad,cik=o['identity'][0]['text'],decision=d)

class B06AmendmentFinancialNegativeTest(unittest.TestCase):
    def test_rehashed_financial_fact_and_section_are_rejected(self):
        import xml.etree.ElementTree as ET
        from vnext.r5_b06_amendments import verify_reviewed_impact,document_identity
        from vnext.canonical import strict_json_file,sha256_bytes
        root=Path(__file__).resolve().parents[2];review=strict_json_file(path=root/'docs/evidence/r5_b06_followup/amendment_assessments.json');d=review['decisions'][0];o=d['original'];a=d['amendment'];ob=(root/o['request_ledger_row']['repo_relative_path']).read_bytes();ab=(root/a['request_ledger_row']['repo_relative_path']).read_bytes();cik=o['identity'][0]['text']
        for kind,error in [('fact','FINANCIAL_FACTS_PRESENT'),('section','FINANCIAL_SECTION_PRESENT')]:
            tree=ET.fromstring(ab)
            if kind=='fact':ET.SubElement(tree,'{http://www.xbrl.org/2013/inlineXBRL}nonFraction',{'name':'us-gaap:LongTermDebt'}).text='123'
            else:ET.SubElement(tree,'{http://www.w3.org/1999/xhtml}div').text='Item 8. Financial Statements'
            modified=ET.tostring(tree);fake=copy.deepcopy(d);v=document_identity(modified,'10-K/A',cik,a['filing']['reportDate']);fake['amendment'].update(sha256=sha256_bytes(content=modified),complete_normalized_text_sha256=v['complete_text_sha256'],inline_fact_count=v['inline_fact_count'],body_headings=[{'text':s} for s in v['headings']])
            with self.assertRaisesRegex(ValueError,error):verify_reviewed_impact(original_raw=ob,amendment_raw=modified,original=o['filing'],amendment=a['filing'],cik=cik,decision=fake)

class B06CarryingMeasurementTest(unittest.TestCase):
    def material(self,cid):
        from vnext.batch_workflow import _registry_rows,repository_company_ciks
        from vnext.sources import raw_blob_record,source_reference_record,companyfacts_structured_facts
        from vnext.specs import compile_spec_file
        from vnext.observations import scope_key
        from vnext.r5_b06_measurement import measurement_inputs
        root=Path(__file__).resolve().parents[2];company=next(c for c in _registry_rows(repo_root=root) if c['company_id']==cid);sel=primary.discover(data_root=root,company=company);spec=compile_spec_file(path=root/"catalog/r5/history/B06_carrying_v2.md",dependency_specs={});scope={'entity_scope':'consolidated'};target={'company_id':cid,'period_start':sel['target_period']['period_start'],'period_end':sel['target_period']['period_end'],'accession':sel['filing']['accessionNumber'],'entity':sel['entity'],'scope':scope,'scope_key':scope_key(scope=scope)};facts=[];measurement=None
        for proof in sel['sources']:
            cf='/companyfacts/' in proof['source_url'];xml=proof['document_name'].endswith('_htm.xml')
            if not (cf or xml):continue
            raw=(root/proof['request_repo_relative_path']).read_bytes();blob=raw_blob_record(repo_root=root,repo_relative_path=proof['request_repo_relative_path'],media_type='application/json' if cf else 'application/xml');source=source_reference_record(raw_blob=blob,company_id=cid,source_url=proof['source_url'],accession=proof['accession'],document_name=proof['document_name'],source_role='companyfacts' if cf else 'accession_xbrl',request_attempt_id=proof['request_attempt_id'])
            if cf:facts=companyfacts_structured_facts(raw_bytes=raw,source_reference=source,approved_concepts=primary.concepts(spec),allowed_ciks=repository_company_ciks(repo_root=root,company_id=cid),include_instant=True)
            else:measurement=measurement_inputs(raw=raw,source=source,spec=spec,target=target,filed=sel['filing']['filingDate'],data_root=root)
        return spec,target,facts,measurement
    def test_two_source_reconciliations_and_nonpositive_equity(self):
        for cid,amount,quality in [('lumen_technologies','17441000000','NOT_MEANINGFUL'),('southwest_airlines','4901000000','EXACT')]:
            spec,target,facts,m=self.material(cid);self.assertEqual(amount,m['carrying_amount']);r,t,o,a=primary.resolve_primary(spec=spec,target=target,traits=['non_financial'],facts=facts,measurement=m);self.assertEqual(quality,r['quality']);self.assertFalse(a['reasons']);self.assertTrue(any('xbrl_fact_ordinal' in x['source_binding'] for x in o))
    def test_same_basis_conflict_is_not_erased_by_reconciliation(self):
        spec,target,facts,m=self.material('lumen_technologies');bad=copy.deepcopy(facts)
        for f in bad:
            if f['concept']=='us-gaap:DebtAndCapitalLeaseObligations' and f['period_start']==f['period_end']==target['period_end']:f['value']='18000000000'
        r,t,o,a=primary.resolve_primary(spec=spec,target=target,traits=['non_financial'],facts=bad,measurement=m);self.assertEqual('WITHHELD',r['publication']);self.assertTrue(any('MEASUREMENT_COMPANYFACTS_XBRL_DIFFER' in e for e in a['reasons']))
        r,t,o,a=primary.resolve_primary(spec=spec,target=target,traits=['non_financial'],facts=facts,measurement=None);self.assertEqual('WITHHELD',r['publication']);self.assertIn('DIRECT_TOTAL_CONFLICT',a['reasons'])
