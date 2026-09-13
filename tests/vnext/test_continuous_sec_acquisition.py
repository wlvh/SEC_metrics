"""Actual SEC persistence and source readers, with no real network access."""
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import copy
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest

from sec_http import SecHttpClient,parse_request_log_rows
from sec_urls import submissions_url
from vnext.canonical import content_hash,sha256_file,strict_json_file
from vnext.continuous_sec_acquisition import recorded_sec_session,validate_acquisition_checkpoint
from vnext.normal_governance_input import _Sources
from vnext.normal_source_authority import ROOT,MANIFEST_PATH
from vnext.ordinary_source_authority import verify_ordinary_source_proofs,checkpoint_installation,EXPORT_PATH


class ContinuousSecAcquisitionTest(unittest.TestCase):
    def test_recorded_capture_failure_isolation_native_http_and_checkpoint_binding(self):
        location=os.environ.get('SEC_ACQUISITION_MATERIAL_ROOT')
        if location:
            root=Path(location).resolve();self.assertFalse(root.exists());root.mkdir(parents=True)
        else:
            temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name).resolve()
        url=submissions_url(cik=19617)
        source=_Sources(ROOT,'jpmorgan_chase','19617').read(url,role='sec_submissions_inventory',media_type='application/json')
        raw=source['raw_bytes'];failed_url='https://www.sec.gov/Archives/edgar/data/1108524/000110852425000083/0001108524-25-000083.hdr.sgml'
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',side_effect=AssertionError('NO_RECORDED_SOCKET')):
            session=recorded_sec_session(root=root/'ledger',response=raw)
            reused=session.capture(company_id='jpmorgan_chase',url=url)
            self.assertEqual(reused['status'],'EXISTING_VERIFIED_SOURCE_REUSED')
            self.assertEqual(reused['calls'],[0,0,0])
            first=session.capture(company_id='jpmorgan_chase',url=url,refresh_metadata=True)
            self.assertEqual(first['status'],'SUCCEEDED');self.assertEqual(first['calls'],[0,0,0])
            first_proof=first['receipt']['proof']
            accepted=verify_ordinary_source_proofs(data_root=session.data_root,proofs=[first_proof])
            self.assertEqual(accepted['source_credit'],'RECORDED_TEST_ONLY');self.assertFalse(accepted['real_sec_credit'])
            failed=recorded_sec_session(root=root/'ledger',response=b'RECORDED_SERVICE_UNAVAILABLE',status=503)
            failure=failed.capture(company_id='salesforce',url=failed_url)
            self.assertEqual(failure['status'],'FAILED_TERMINAL');self.assertEqual(failure['calls'],[0,0,0])
            self.assertIsNone(failure['receipt']['proof'])
            # A failed independent URL does not invalidate the successful one.
            accepted=verify_ordinary_source_proofs(data_root=session.data_root,proofs=[first_proof])
            self.assertFalse(accepted['real_sec_credit'])
            with self.assertRaisesRegex(ValueError,'REDRAW_FORBIDDEN'):
                failed.capture(company_id='salesforce',url=failed_url)
            with self.assertRaisesRegex(ValueError,'DECLARED_COMPANY_DEPENDENCY'):
                session.capture(company_id='jpmorgan_chase',url=submissions_url(cik=37996),refresh_metadata=True)
            with session.ledger.locked():
                state=session.ledger.snapshot();self.assertEqual(state['counts'],[0,0,2])
                self.assertEqual(state['stopped_channels'],[])
            self.assertEqual(accepted['selected_new_request_attempt_ids'],[first_proof['request_attempt_id']])
            checkpoint,paths=checkpoint_installation(source_root=session.data_root)
            self.assertEqual(len(checkpoint['captures']),2)
            self.assertIn(first_proof['request_repo_relative_path'],paths)
            forged=copy.deepcopy(checkpoint)
            forged.update(real_sec_credit=True,source_credit='VERIFIED_SEC_ACQUISITION',execution_mode='LIVE')
            forged['checkpoint_id']=content_hash(value={k:v for k,v in forged.items() if k!='checkpoint_id'})
            with self.assertRaisesRegex(ValueError,'CAPTURE_BINDING_CHANGED'):
                validate_acquisition_checkpoint(session.data_root,forged,strict_json_file(path=ROOT/MANIFEST_PATH))
            sidecar=session.data_root/EXPORT_PATH;self.assertFalse(sidecar.exists());sidecar.parent.mkdir(parents=True,exist_ok=True)
            sidecar.write_text(json.dumps(forged)+'\n')
            with self.assertRaisesRegex(ValueError,'IMPORTED_CHECKPOINT_CHANGED'):
                verify_ordinary_source_proofs(data_root=session.data_root,proofs=[first_proof])
            sidecar.unlink()
            # The unchanged company registry and event-window catalog also
            # authorize a registered predecessor's missing source dependency.
            # These deliberately opaque test bytes confer no event-content credit.
            predecessor_url='https://www.sec.gov/Archives/edgar/data/813828/000119312525036747/0001193125-25-036747.hdr.sgml'
            predecessor=recorded_sec_session(root=root/'ledger',response=b'RECORDED_PREDECESSOR_TRANSPORT_ONLY')
            captured=predecessor.capture(company_id='paramount_skydance_paramount_global',url=predecessor_url)
            self.assertEqual(captured['status'],'SUCCEEDED')
            self.assertEqual(captured['calls'],[0,0,0])
            checkpoint,paths=checkpoint_installation(source_root=session.data_root)
            self.assertEqual(len(checkpoint['captures']),3)
            self.assertFalse(checkpoint['real_sec_credit'])
            with session.ledger.locked():
                self.assertEqual(session.ledger.snapshot()['counts'],[0,0,3])
            # Actual HTTP construction uses the existing client in an isolated
            # unregistered workspace. The test response has no LIVE credit.
            wire_root=root/'http-wire';wire_root.mkdir()
            client=SecHttpClient(workdir=wire_root,config_path=ROOT/'config/sec_config.json',log_path=wire_root/'evidence/requests_log.csv')
            client.config={**client.config,'max_retries':0}
            class Response(io.BytesIO):
                status=200
                headers={'Content-Type':'application/json'}
            def reply(*,request,timeout):
                self.assertEqual(request.full_url,url);self.assertEqual(request.get_method(),'GET')
                self.assertEqual(timeout,60);self.assertTrue(request.get_header('User-agent'))
                return Response(raw)
            with patch('sec_http.urlopen',side_effect=reply) as opener:
                observed=client.fetch(url=url,purpose='ISOLATED_OFFLINE_HTTP_PATH',local_path=wire_root/'response.json')
                self.assertEqual(opener.call_count,1);self.assertEqual(observed.status_code,200)
            log_rows=parse_request_log_rows(text=(wire_root/'evidence/requests_log.csv').read_text())
            self.assertEqual(len(log_rows),1);self.assertEqual(log_rows[0]['retry_attempt'],'0')
            # The same public client must not retry even a retryable HTTP error.
            with patch('sec_http.urlopen',side_effect=HTTPError(url,503,'RECORDED',{},io.BytesIO(b'failure'))) as opener:
                failed_http=client.fetch(url=url,purpose='ISOLATED_OFFLINE_503',local_path=wire_root/'failure.json')
                self.assertEqual(opener.call_count,1);self.assertEqual(failed_http.status_code,503)
            from vnext.normal_run_v3 import install_normal_inputs,create_normal_run
            from vnext.ordinary_projection import render_ordinary_run
            native_data=root/'native-data';native_run=root/'native-run'
            install_normal_inputs(data_root=native_data,company_id='jpmorgan_chase',metric_id='A08',source_root=session.data_root)
            native=create_normal_run(data_root=native_data,run_dir=native_run,company_id='jpmorgan_chase',metric_id='A08')
            self.assertEqual(native['result']['quality'],'EXACT')
            self.assertIn(first_proof['request_attempt_id'],native['input_binding']['source_admission']['selected_new_request_attempt_ids'])
            preview=render_ordinary_run(data_root=native_data,run_dir=native_run)
            self.assertEqual(preview['receipt']['source_credit'],'RECORDED_TEST_ONLY')
            self.assertFalse(preview['receipt']['real_sec_credit'])
            cold="""from pathlib import Path
import sys,socket
from unittest.mock import patch
sys.path.insert(0,str(Path(sys.argv[1])/'scripts'))
from vnext.ordinary_projection import render_ordinary_run
with patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')):
 result=render_ordinary_run(data_root=Path(sys.argv[1]),run_dir=Path(sys.argv[2]))
 assert result['receipt']['source_credit']=='RECORDED_TEST_ONLY' and result['receipt']['real_sec_credit'] is False
 print('COLD_SOURCE_CHECKPOINT_PREVIEW_PASS')
"""
            child=subprocess.run([sys.executable,'-c',cold,str(native_data),str(native_run)],capture_output=True,text=True)
            (root/'cold-native.log').write_text(child.stdout+child.stderr)
            self.assertEqual(child.returncode,0,child.stderr)
            with session.ledger.locked():
                recorded_counts=session.ledger.snapshot()['counts']
            result={'status':'OFFLINE_SEC_CAPTURE_PASS','calls':[0,0,0],'recorded_count_simulation':recorded_counts,
                'actual_http_path_verified':True,'retryable_http_zero_retry_verified':True,
                'checkpoint_import_and_failure_isolation_verified':True,
                'test_checkpoint_cannot_be_relabelled_live':True,'source_root':str(session.data_root),
                'native_selected_source_and_cold_preview_verified':True,
                'checkpoint_id':checkpoint['checkpoint_id'],'original_provider_fields_unchanged':True,
                'real_sec_credit':False,'production_authorized':False}
            (root/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result),flush=True)


if __name__=='__main__':unittest.main()
