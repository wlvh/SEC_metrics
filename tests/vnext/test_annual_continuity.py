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

    def test_actual_root_and_local_permission_dict_are_not_execution_authority(self):
        from vnext import annual_publication_authority as authority,annual_runtime as runtime
        with self.assertRaises(ValueError):continuity._external(ROOT)
        with self.assertRaises(ValueError):authority._permission({'verified':True})
        with self.assertRaises(ValueError):runtime.RuntimeAuthorization(factory=object(),binding={})
        with self.assertRaises(ValueError):runtime.execute_native_candidate(authorization={'verified':True})
        with self.assertRaises(ValueError):continuity.verify_stage(approval_url=str(ROOT/'local-approval.json'))

if __name__=='__main__':unittest.main()
