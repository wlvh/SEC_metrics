"""Historical D04 dependency discovery uses saved metadata and existing SEC recording."""
import json
import os
from pathlib import Path
import socket
import tempfile
import tarfile
import hashlib
import unittest
from unittest.mock import patch
from vnext.normal_source_authority import ROOT
from vnext.r6_historical_controls import discover_control_sources,prepare_control_source
from vnext.continuous_sec_acquisition import recorded_sec_session
from vnext.ordinary_source_authority import verify_ordinary_source_proofs


class HistoricalControlSourceTest(unittest.TestCase):
    def test_original_noninline_control_and_header_identity_rejection(self):
        packet=ROOT/'docs/evidence/issue28_continuous/historical-semantic-acquisition'
        index=json.loads((packet/'actual-controls-index.json').read_text())
        def body(ordinal):
            item=index['files'][f'calls/{ordinal:04d}/sec-wire/body.bin']
            with tarfile.open(packet/index['archive']) as tar:raw=tar.extractfile(item['archive_member']).read()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256']);return raw
        primary,header=body(47),body(48)
        discovery=discover_control_sources(repo_root=ROOT,company_id='enphase_energy',control_id='enphase_2016_annual_primary')
        urls={x['roles'][0]:x['source_url'] for x in discovery['requirements']}
        with tempfile.TemporaryDirectory() as d,patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
            for name,chosen_header in [('original',header),('wrong-company',header.replace(b'<CIK>0001463101',b'<CIK>0000000001'))]:
                root=Path(d)/name
                session=recorded_sec_session(root=root,response=primary)
                session.capture(company_id='enphase_energy',url=urls['target_primary'],control_id='enphase_2016_annual_primary')
                recorded_sec_session(root=root,response=chosen_header).capture(company_id='enphase_energy',
                    url=urls['historical_control_header'],control_id='enphase_2016_annual_primary')
                if name=='wrong-company':
                    with self.assertRaisesRegex(ValueError,'CONTROL_HEADER_IDENTITY_CHANGED'):
                        prepare_control_source(repo_root=session.data_root,company_id='enphase_energy',control_id='enphase_2016_annual_primary')
                else:
                    source=prepare_control_source(repo_root=session.data_root,company_id='enphase_energy',control_id='enphase_2016_annual_primary')
                    self.assertEqual(len(source['units']),8)
                    self.assertEqual(sum(len(u['payload']['blocks']) for u in source['units']),4217)
                    self.assertIsNone(source['prepared_annual_input']['table_input']['target_period']['period_start'])
                    self.assertFalse(source['normal_update_input']);self.assertFalse(source['whole_filing_absence_credit'])
                    self.assertEqual(source['source_admission']['source_credit'],'RECORDED_TEST_ONLY')
                    self.assertTrue(any('raise substantial doubt' in b['text'] for u in source['units'] for b in u['payload']['blocks']))

    def test_declared_historical_primary_capture_remains_recorded(self):
        location=os.environ.get('HISTORICAL_CONTROL_MATERIAL_ROOT')
        if location:
            root=Path(location).resolve();self.assertFalse(root.exists());root.mkdir(parents=True)
        else:
            temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name).resolve()
        with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), \
             patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')), \
             patch('sec_http.urlopen',side_effect=AssertionError('SEC_FORBIDDEN')):
            found=[]
            for year in [2016,2017]:
                control=f'enphase_{year}_annual_primary'
                discovery=discover_control_sources(repo_root=ROOT,company_id='enphase_energy',control_id=control)
                self.assertEqual(discovery['filing']['reportDate'],f'{year}-12-31')
                self.assertEqual(discovery['filing']['isInlineXBRL'],0)
                self.assertFalse(discovery['normal_update_input']);self.assertFalse(discovery['production_authorized'])
                self.assertEqual(discovery['limitations'],[])
                self.assertEqual(len(discovery['requirements']),3)
                found.append(discovery)
            session=recorded_sec_session(root=root/'ledger',response=b'RECORDED_HISTORICAL_TRANSPORT_TEST_NOT_A_FILING')
            url=next(r['source_url'] for r in found[0]['requirements'] if r['roles']==['target_primary'])
            wrong=next(r['source_url'] for r in found[1]['requirements'] if r['roles']==['target_primary'])
            with self.assertRaisesRegex(ValueError,'DECLARED_COMPANY_DEPENDENCY'):
                session.capture(company_id='enphase_energy',url=wrong,control_id='enphase_2016_annual_primary')
            with self.assertRaisesRegex(ValueError,'CONTROL_SOURCE_NOT_CONFIGURED'):
                session.capture(company_id='jpmorgan_chase',url=url,control_id='enphase_2016_annual_primary')
            with self.assertRaisesRegex(ValueError,'CONTROL_METADATA_REFRESH_NOT_REQUESTED'):
                session.capture(company_id='enphase_energy',url=url,control_id='enphase_2016_annual_primary',refresh_metadata=True)
            result=session.capture(company_id='enphase_energy',url=url,control_id='enphase_2016_annual_primary')
            self.assertEqual(result['status'],'SUCCEEDED');self.assertEqual(result['calls'],[0,0,0])
            proof=result['receipt']['proof'];admission=verify_ordinary_source_proofs(data_root=session.data_root,proofs=[proof])
            self.assertEqual(admission['source_credit'],'RECORDED_TEST_ONLY');self.assertFalse(admission['real_sec_credit'])
            again=session.capture(company_id='enphase_energy',url=url,control_id='enphase_2016_annual_primary')
            self.assertEqual(again['status'],'EXISTING_VERIFIED_SOURCE_REUSED')
            with session.ledger.locked():self.assertEqual(session.ledger.snapshot()['counts'],[0,0,1])
            plan=json.loads((root/'ledger/calls/0001/sec-plan.json').read_text())
            self.assertFalse(plan['current_metric_or_publication_credit']);self.assertEqual(plan['historical_semantic_control_id'],'enphase_2016_annual_primary')
            summary={'status':'HISTORICAL_CONTROL_DISCOVERY_AND_RECORDED_CAPTURE_PASS','closure':session.requirement['requirement_closure_hash'],
                'discovered_accessions':[x['filing']['accessionNumber'] for x in found],
                'recorded_capture_count':1,'wrong_company_url_and_refresh_rejected':True,'source_identity':'RECORDED_TEST_ONLY',
                'calls':[0,0,0],'network_disabled':True,'native_result_created':False,'production_authorized':False}
            (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)


if __name__=='__main__':unittest.main()
