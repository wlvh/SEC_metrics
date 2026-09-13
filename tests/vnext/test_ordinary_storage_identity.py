"""Pinned immutable storage aliases cannot change requested document identity."""
from pathlib import Path
import tempfile
import unittest

from sec_http import SecHttpClient,parse_request_log_rows,request_log_attempt_id
from vnext.batch_workflow import validate_request_attempt_binding,BatchWorkflowError
from vnext.normal_source_authority import ROOT
from tests.vnext.test_publication import write_request_ledger_rows


class OrdinaryStorageIdentityTest(unittest.TestCase):
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
