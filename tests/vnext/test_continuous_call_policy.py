"""New approval scope and unavailable observations retain explicit meaning."""
from copy import deepcopy
import json
import unittest

from vnext.canonical import sha256_bytes,strict_json_file
from vnext.continuous_call_policy import POLICY_PATH,delegation_fields
from vnext.normal_source_authority import ROOT
from vnext.continuous_semantic_calls import usage_observation,usage_error


class ContinuousCallPolicyTest(unittest.TestCase):
    def setUp(self):
        self.policy=strict_json_file(path=ROOT/POLICY_PATH)
        self.comment=strict_json_file(path=ROOT/self.policy['delegation_record_path'])

    def altered(self,key,value):
        comment=deepcopy(self.comment);body=json.loads(comment['body']);body[key]=value
        comment['body']=json.dumps(body,ensure_ascii=False)
        policy=deepcopy(self.policy);policy['delegation_body_sha256']=sha256_bytes(content=comment['body'].encode())
        return comment,policy

    def test_real_record_loads_but_limits_model_retry_and_money_cannot_be_changed(self):
        self.assertEqual(delegation_fields(self.comment,policy=self.policy)['model'],'deepseek-flash')
        for key,value in [('model','another-model'),('automatic_retry_count',1),
            ('maximum_additional_provider_paid_sec_calls',[241,240,80]),
            ('repository_monetary_budget_enforcement','ENABLED'),
            ('estimated_or_actual_cost_may_block_provider_call',True),
            ('unknown_usage_may_be_zero',True),('closed_stage_credit_reuse_authorized',True)]:
            with self.subTest(key=key):
                comment,policy=self.altered(key,value)
                with self.assertRaises(ValueError):delegation_fields(comment,policy=policy)

    def test_production_permission_or_edited_comment_is_not_this_approval(self):
        for key in ['ready_authorized','merge_authorized','formal_adoption_authorized',
                    'deployment_authorized','active_switch_authorized','account_inspection_authorized']:
            comment,policy=self.altered(key,True)
            with self.assertRaises(ValueError):delegation_fields(comment,policy=policy)
        comment=deepcopy(self.comment);comment['updated_at']='2026-09-14T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'PROVENANCE_INVALID'):delegation_fields(comment,policy=self.policy)

    def test_missing_or_invalid_usage_is_not_zero_and_actual_cost_is_unavailable(self):
        for raw in [None,b'{}',b'{"usage":{"prompt_tokens":true,"completion_tokens":-1}}']:
            observation=usage_observation(raw)
            self.assertIsNone(observation['input_tokens']);self.assertIsNone(observation['output_tokens'])
            self.assertIsNone(observation['actual_cost'])
        self.assertEqual(usage_observation(b'{"usage":{"prompt_tokens":0,"completion_tokens":0}}')['input_tokens'],0)
        self.assertEqual(usage_error(b'{"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":13}}'),'USAGE_UNKNOWN')
        self.assertEqual(usage_error(b'{"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}'),'')


if __name__=='__main__':unittest.main()
