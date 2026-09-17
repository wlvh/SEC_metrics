"""Pinned immutable storage aliases cannot change requested document identity."""
from pathlib import Path
import copy
import json
import tempfile
import unittest

from sec_http import SecHttpClient,parse_request_log_rows,request_log_attempt_id
from vnext.batch_workflow import validate_request_attempt_binding,BatchWorkflowError
from vnext.normal_source_authority import ROOT
from tests.vnext.test_publication import write_request_ledger_rows
from vnext.canonical import content_hash
from vnext.deterministic_router import source_set_manifest
from vnext.ordinary_storage_identity import auditor_document_views
from vnext.sources import raw_blob_record, source_reference_record


class OrdinaryStorageIdentityTest(unittest.TestCase):
    def test_current_and_history_names_rebuild_only_the_inventory_view(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();log=root/'evidence/requests_log.csv'
            client=SecHttpClient(workdir=root,config_path=ROOT/'config/sec_config.json',log_path=log)
            empty={'accessionNumber':[],'filingDate':[],'form':[]}
            documents=[('CIK0000000001.json',{'cik':1,'filings':{'recent':empty,'files':[]}}),
                       ('CIK0000000001-submissions-001.json',empty)]
            records=[];inputs=[]
            for i,(name,payload) in enumerate(documents):
                raw=json.dumps(payload).encode();url='https://data.sec.gov/submissions/'+name
                result=client._persist_result(url=url,status_code=200,body=raw,
                    headers={'Content-Type':'application/json'},local_path=root/(str(i)+'.body'),error='')
                client._append_log_row(result=result,purpose='RECORDED_IDENTITY_TEST',attempt=0)
                row=parse_request_log_rows(text=log.read_text())[-1]
                blob=raw_blob_record(repo_root=root,repo_relative_path=row['repo_relative_path'],media_type='application/json')
                ref=source_reference_record(raw_blob=blob,company_id='test_company',source_url=url,
                    accession='SUBMISSIONS-1',document_name=row['document_name'],source_role='submissions',
                    request_attempt_id=request_log_attempt_id(row_index=i,row=row))
                manifest=source_set_manifest(company_id='test_company',source_role='fy_8k_item_inventory',
                    form_types=['8-K','8-K/A'],fiscal_or_date_window={'period_start':'2025-01-01','period_end':'2025-12-31'},
                    discovery_policy='PINNED_SUBMISSIONS',inventory_source_reference=ref,inventory_bytes=raw,
                    ordered_source_references=[],cutoff_timestamp_or_pinned_submissions_attempt=ref['request_attempt_id'])
                records.extend([blob,ref]);inputs.append({'filing_documents':[],'source_set_manifest':manifest,
                    'inventory_source_reference':ref,'inventory_bytes':raw})
            body={'record_type':'TEST_ORIGINAL_PREPARATION'}
            preparation={'records':records,'input_binding':{**body,'input_binding_id':content_hash(value=body)},
                'resolver_inputs':{'c04':{'arguments':{'event_input':{**inputs[0],'history_inputs':[inputs[1]]}}}}}
            original=copy.deepcopy(preparation);ledger=log.read_bytes()
            view=auditor_document_views(repo_root=root,preparation=preparation)
            self.assertEqual(preparation,original);self.assertEqual(log.read_bytes(),ledger)
            event=view['resolver_inputs']['c04']['arguments']['event_input']
            for old,new,(name,_) in zip(inputs,[event,*event['history_inputs']],documents):
                ref=new['inventory_source_reference']
                self.assertEqual(ref['document_name'],name)
                self.assertEqual(ref['request_attempt_id'],old['inventory_source_reference']['request_attempt_id'])
                self.assertEqual(new['inventory_bytes'],old['inventory_bytes'])
                self.assertEqual(new['source_set_manifest']['inventory_source_reference_id'],ref['source_reference_id'])
                self.assertNotEqual(new['source_set_manifest']['source_set_manifest_id'],old['source_set_manifest']['source_set_manifest_id'])
            self.assertEqual(len(view['input_binding']['inventory_manifest_views']),2)
            forged=copy.deepcopy(preparation)
            manifest=forged['resolver_inputs']['c04']['arguments']['event_input']['history_inputs'][0]['source_set_manifest']
            manifest['discovered_accession_set_hash']=content_hash(value=['invented-accession'])
            manifest['source_set_manifest_id']=content_hash(value={k:v for k,v in manifest.items() if k!='source_set_manifest_id'})
            with self.assertRaisesRegex(ValueError,'DOCUMENT_IDENTITY_SOURCE_SET_CONTENT_CHANGED'):
                auditor_document_views(repo_root=root,preparation=forged)

    def test_logical_name_reuses_the_exact_immutable_request_without_rewriting_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();log=root/'evidence/requests_log.csv'
            client=SecHttpClient(workdir=root,config_path=ROOT/'config/sec_config.json',log_path=log)
            url='https://www.sec.gov/Archives/edgar/data/1/000000000125000001/report.htm'
            result=client._persist_result(url=url,status_code=200,body=b'original test source',
                headers={'Content-Type':'text/html'},local_path=root/'0001.body',error='')
            client._append_log_row(result=result,purpose='RECORDED_IDENTITY_TEST',attempt=0)
            original=log.read_bytes();row=parse_request_log_rows(text=original.decode())[0]
            args={'repo_root':root,'source_url':url,'content_sha256':row['content_sha256'],
                  'accession':'0000000001-25-000001','request_attempt_id':request_log_attempt_id(row_index=0,row=row),
                  'require_immutable':True}
            physical=validate_request_attempt_binding(document_name='0001.body',**args)
            logical=validate_request_attempt_binding(document_name='report.htm',**args)
            self.assertEqual(physical,logical);self.assertEqual(original,log.read_bytes())
            self.assertTrue(logical['request_repo_relative_path'].endswith('/0001.body'))
            for changed in [{'document_name':'another.htm'},
                            {'document_name':'report.htm','source_url':url.replace('/1/','/2/')},
                            {'document_name':'report.htm','request_attempt_id':'sha256:'+'0'*64}]:
                with self.assertRaises(BatchWorkflowError):
                    validate_request_attempt_binding(**{**args,**changed})

            # A mutable legacy working file cannot acquire the same alias.
            legacy = root / 'evidence/legacy_working'
            legacy.mkdir()
            for field, name in [('repo_relative_path', '0001.body'),
                                ('headers_repo_relative_path', '0001.body.headers.json')]:
                target = legacy / name
                target.write_bytes((root / row[field]).read_bytes())
                row[field] = target.relative_to(root).as_posix()
            write_request_ledger_rows(repo_root=root, rows=[row])
            args.update(request_attempt_id=request_log_attempt_id(row_index=0, row=row),
                        require_immutable=False)
            with self.assertRaises(BatchWorkflowError):
                validate_request_attempt_binding(document_name='report.htm', **args)


if __name__=='__main__':unittest.main()
