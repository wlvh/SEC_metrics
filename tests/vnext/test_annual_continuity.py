"""Short real boundary checks; synthetic metadata here grants no execution."""
import copy
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vnext import annual_continuity as continuity,annual_update as update,publication as pub
from vnext.annual_adoption_policy import V1,V2,V3,policy,resolve_embedded
from vnext.annual_continuity_sources import visible_submissions
from vnext.annual_adoption import record
from vnext.canonical import content_hash

ROOT=Path(__file__).resolve().parents[2]


class AnnualContinuityBoundaryTest(unittest.TestCase):
    def test_cli_result_preserves_decimal_identity_and_never_leaves_partial_json(self):
        from decimal import Decimal
        from contextlib import redirect_stdout
        import io
        from tools.vnext_annual_continuity import write_result
        from vnext.canonical import strict_json_file
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();output=root/'result.json'
            value=record({'review':{'duration':Decimal('3807.637')}},'stage_id')
            with redirect_stdout(io.StringIO()):write_result(output,value)
            found=strict_json_file(path=output)
            continuity.check_id(found,'stage_id');self.assertEqual(content_hash(value=value),content_hash(value=found))
            with self.assertRaises(FileExistsError):write_result(output,value)
            with self.assertRaises(ValueError):write_result(root/'invalid.json',{'unsupported':1.2})
            self.assertFalse((root/'invalid.json').exists())

    def test_only_unused_identical_registration_can_resume_proposal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();stage=root/'stage';data=root/'data';budget=root/'budget'
            import sec_http
            sec_http.SecHttpClient(workdir=data,config_path=ROOT/'config/sec_config.json',log_path=data/'evidence/requests_log.csv')
            start=datetime.now(timezone.utc)
            first=continuity._register_unused_budget(stage,data,budget,start)
            original=(budget/'registration.json').read_bytes()
            self.assertEqual(first,continuity._register_unused_budget(stage,data,budget,start+timedelta(seconds=1)))
            self.assertEqual(original,(budget/'registration.json').read_bytes())
            other=root/'other-data'
            sec_http.SecHttpClient(workdir=other,config_path=ROOT/'config/sec_config.json',log_path=other/'evidence/requests_log.csv')
            with self.assertRaisesRegex(ValueError,'REGISTRATION_CHANGED'):
                continuity._register_unused_budget(stage,other,budget,start)
            (budget/'provider-1.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'HAS_EXECUTION_STATE'):
                continuity._register_unused_budget(stage,data,budget,start)
            self.assertEqual(original,(budget/'registration.json').read_bytes())

    def test_current_native_results_belong_to_current_annual_snapshot(self):
        pointer=json.loads((ROOT/'outputs/active_publication.json').read_text())
        directory=ROOT/'outputs/publications'/pointer['publication_id']
        manifest=json.loads((directory/'publication_manifest.json').read_text())
        # Resolver unit coverage over real immutable bytes. Full validation is
        # separately exercised by PublicationView.open in material integration.
        view=pub.PublicationView(publication_id=pointer['publication_id'],bundle_dir=directory,manifest=manifest)
        for metric in ('B01','B10'):
            found=view.native_result(company_id=policy(policy_id=V3)['company_id'],metric_id=metric)
            self.assertEqual(view.publication_id,found['owner_publication_id'])
            self.assertTrue(found['run_path'].startswith('internal/annual_snapshot/candidate/'))
            self.assertEqual(metric,found['result']['metric_id'])
            self.assertTrue(found['sources'])
        old=policy(policy_id=V2)['baseline_publication']['publication_id']
        path=ROOT/'outputs/publications'/old
        previous=pub.PublicationView(publication_id=old,bundle_dir=path,manifest=json.loads((path/'publication_manifest.json').read_text()))
        self.assertEqual(old,previous.native_result(company_id=policy(policy_id=V3)['company_id'],metric_id='B10')['owner_publication_id'])
        with self.assertRaisesRegex(ValueError,'NATIVE_CONTENT_NOT_EMBEDDED'):
            previous.native_result(company_id=policy(policy_id=V3)['company_id'],metric_id='B01')

    def test_new_rule_does_not_embed_input_answers_or_fixed_predecessor(self):
        new=policy(policy_id=V3)
        self.assertNotIn('exact_candidate',new);self.assertNotIn('baseline_publication',new)
        self.assertFalse(new['input_git_commit_required']);self.assertFalse(new['new_year_policy_revision_required'])
        self.assertFalse(new['production_root_writes'])
        for identity in (V1,V2,V3):self.assertEqual(policy(policy_id=identity),resolve_embedded(policy(policy_id=identity)))
        changed=copy.deepcopy(new);changed['normal_provider_calls_max']=3
        with self.assertRaises(ValueError):resolve_embedded(changed)
        changed=copy.deepcopy(new);changed['automatic_retry_count']=False
        with self.assertRaises(ValueError):resolve_embedded(changed)

    def test_visibility_is_derived_from_unchanged_list_not_an_answer_parameter(self):
        from sec_urls import submissions_url
        company=update.supported_company(repo_root=ROOT)
        saved=update.saved_source(repo_root=ROOT,url=submissions_url(cik=int(company['primary_cik'])))
        payload=json.loads(saved['raw']);before=copy.deepcopy(payload)
        periods=[];receipts=[]
        for cutoff in ('2025-12-31T23:59:59Z','2026-09-01T00:00:00Z'):
            visible,receipt=visible_submissions(payload,{'record_type':'SIMULATED_HISTORICAL_SUBMISSIONS_VISIBILITY','as_of_utc':cutoff},saved['proof'])
            filing,_=update._select_filing(company=company,payload=visible)
            periods.append(filing['reportDate']);receipts.append(receipt)
        self.assertEqual(['2024-12-31','2025-12-31'],periods)
        self.assertEqual(before,payload)
        self.assertNotEqual(receipts[0]['visibility_id'],receipts[1]['visibility_id'])
        self.assertEqual(receipts[0]['original_source_proof'],receipts[1]['original_source_proof'])
        with self.assertRaises(ValueError):visible_submissions(payload,{'fiscal_year':2024},saved['proof'])

    def test_expiration_is_enforced_for_execution_but_history_can_be_read(self):
        start=datetime.now(timezone.utc)-timedelta(days=2)
        stage={'created_at_utc':start.isoformat(),'expires_at_utc':(start+timedelta(days=1)).isoformat()}
        continuity.validate_lifetime(stage)
        with self.assertRaisesRegex(ValueError,'EXPIRED'):continuity.validate_lifetime(stage,execution=True)
        stage['expires_at_utc']=(start+timedelta(days=8)).isoformat()
        with self.assertRaisesRegex(ValueError,'EXPIRY_INVALID'):continuity.validate_lifetime(stage)

    def test_reservation_without_terminal_is_unknown_and_cannot_reset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();budget=root/'budget';budget.mkdir();workspace=root/'run';workspace.mkdir()
            registration=record({'budget_root':str(budget),'stage_root':str(workspace)},'registration_id')
            stage={'stage_root':str(workspace),'budget_root':str(budget),'budget_registration':registration,'normal_provider_calls':2}
            slot=record({'registration_id':registration['registration_id'],'ordinal':1,'plan_id':'sha256:'+'a'*64,
                'input_id':'sha256:'+'b'*64},'slot_id')
            (budget/'provider-1.json').write_text(json.dumps(slot))
            count=continuity.budget_counts(stage)
            self.assertEqual([slot['plan_id']],count['uncertain_plans'])
            with self.assertRaisesRegex(ValueError,'COUNT_UNKNOWN'):continuity._reserve_provider(stage,{})
            (budget/'provider-1.json').rename(budget/'provider-2.json')
            with self.assertRaisesRegex(ValueError,'SLOT_CHANGED'):continuity.budget_counts(stage)

    def test_frozen_receipt_read_does_not_rewrite_active_mirror(self):
        from vnext.annual_continuity_sources import frozen_foundation_receipts
        from vnext.canonical import sha256_bytes
        before=(ROOT/'outputs/scalability_audit.csv').read_bytes()
        expected=json.loads((ROOT/'requirements/issue_15_v1/foundation_verification_receipt.json').read_text())
        found=frozen_foundation_receipts()
        for entry in expected['receipt_bindings']:
            self.assertEqual(entry['sha256'],sha256_bytes(content=found[entry['path']]['bytes']))
        self.assertEqual(before,(ROOT/'outputs/scalability_audit.csv').read_bytes())

    def test_trigger_path_and_record_parent_alias_are_rejected(self):
        from vnext import annual_continuity_trigger as trigger
        import os
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();stage={'stage_id':'sha256:'+'a'*64}
            state={'stage_id':stage['stage_id'],'trigger_id':'/outside','process_id':os.getpid(),'running':True}
            current=root/'current.json';current.write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError,'TRIGGER_STATE_CHANGED'):trigger._state(current,stage)
            outside=root/'outside';outside.mkdir();(root/'alias').symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'ALIAS'):continuity._write_once(root/'alias/record.json',{'a':1})
            self.assertFalse((outside/'record.json').exists())

    def test_sec_failed_status_cannot_be_changed_to_success(self):
        import io
        from urllib.error import HTTPError
        import sec_http
        from sec_urls import submissions_url
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();data=root/'data';budget=root/'budget';budget.mkdir()
            client=sec_http.SecHttpClient(workdir=data,config_path=ROOT/'config/sec_config.json',log_path=data/'evidence/requests_log.csv')
            client.config={**client.config,'max_retries':0}
            rows=update._rows(data)
            registration=record({'budget_root':str(budget),'stage_root':str(root/'stage'),
                'sec_ledger_origin':{'row_count':len(rows),'rows_id':content_hash(value=rows)}},'registration_id')
            stage={'stage_id':'sha256:'+'a'*64,'stage_root':str(root/'stage'),'data_root':str(data),'budget_root':str(budget),'budget_registration':registration}
            url=submissions_url(cik=int(update.supported_company(repo_root=ROOT)['primary_cik']))
            slot=record({'registration_id':registration['registration_id'],'stage_id':stage['stage_id'],'ordinal':1,
                'item':{'kind':'SUBMISSIONS','url':url},'reserved_at_utc':datetime.now(timezone.utc).isoformat(),
                'ledger_before_count':len(rows),'ledger_before_rows_id':content_hash(value=rows)},'sec_slot_id')
            continuity._write_once(budget/'sec-1.json',slot)
            error=HTTPError(url,500,'SIMULATED_HTTP_FAILURE',{},io.BytesIO(b'SIMULATED_FAILURE_BODY'))
            with patch.object(sec_http,'urlopen',side_effect=error) as opened:
                result=client.fetch(url=url,purpose='annual_continuity_submissions',local_path=data/'evidence/test-response.json')
                self.assertEqual(1,opened.call_count)
            terminal=record({'slot':slot,'result':result.__dict__,'ledger_row':update._rows(data)[-1],'status':'FAILED'},'sec_terminal_id')
            path=budget/'sec-terminals/sec-1.json';continuity._write_once(path,terminal)
            self.assertEqual(['sec-1.json'],continuity.budget_counts(stage)['failed_sec'])
            terminal['status']='SUCCEEDED';terminal.pop('sec_terminal_id');terminal=record(terminal,'sec_terminal_id')
            path.write_text(json.dumps(terminal))
            with self.assertRaisesRegex(ValueError,'SEC_TERMINAL_CHANGED'):continuity.budget_counts(stage)

    def test_single_seed_is_refused_before_any_stage_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            with self.assertRaisesRegex(ValueError,'SEED_PARAMETERS_MUST_BE_PAIRED'):
                continuity.stage_proposal(stage_root=root/'stage',data_root=root/'data',budget_root=root/'budget',
                    review_file=root/'review.json',seed_b01=root/'one-seed',seed_b10=None,
                    expires_at_utc='2026-09-11T00:00:00Z',historical_period_start='2023-01-01',historical_period_end='2025-12-31')
            self.assertEqual([],list(root.iterdir()))

    def test_null_stage_cannot_construct_a_historical_seed(self):
        from vnext.annual_continuity_snapshot import create_seed_candidate
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            with self.assertRaisesRegex(ValueError,'EXPLICIT_SEED_REQUIRED'):
                create_seed_candidate({'stage_root':str(root),'seed':None},{})
            self.assertEqual([],list(root.iterdir()))

    def test_root_separation_and_period_scope_are_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            with self.assertRaisesRegex(ValueError,'ROOTS_OVERLAP'):
                continuity._root_separation(root/'stage',root/'data',root/'data/budget')
            with self.assertRaises(ValueError):continuity._period_scope('not-a-date','2025-12-31')
            with self.assertRaises(ValueError):continuity._period_scope('2025-01-01','2024-12-31')

    def test_actual_root_and_local_permission_dict_are_not_execution_authority(self):
        from vnext import annual_publication_authority as authority,annual_runtime as runtime
        with self.assertRaises(ValueError):continuity._external(ROOT)
        with self.assertRaises(ValueError):authority._permission({'verified':True})
        with self.assertRaises(ValueError):runtime.RuntimeAuthorization(factory=object(),binding={})
        with self.assertRaises(ValueError):runtime.execute_native_candidate(authorization={'verified':True})
        with self.assertRaises(ValueError):continuity.verify_stage(approval_url=str(ROOT/'local-approval.json'))

if __name__=='__main__':unittest.main()
