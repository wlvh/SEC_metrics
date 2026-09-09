"""Small deterministic permission boundaries; no fake core validation success."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from vnext import annual_candidate, annual_publication_authority as auth, publication as pub
from vnext.annual_adoption_policy import policy, resolve_embedded, V1, V2, POLICIES
from vnext.annual_adoption import ROOT, git
from vnext.canonical import sha256_file, content_hash
from vnext.requirements import load_requirement_snapshot


class AnnualPublicationAuthorityTest(unittest.TestCase):
    def test_frozen_policies_are_explicit_and_unknown_or_mixed_rules_refuse(self):
        for identity in (V1, V2):
            value = policy(policy_id=identity)
            self.assertEqual(value, resolve_embedded(value))
            self.assertEqual(POLICIES[identity][1], sha256_file(path=ROOT / POLICIES[identity][0]))
            altered = copy.deepcopy(value); altered['policy_id'] = V2 if identity == V1 else V1
            with self.assertRaisesRegex(ValueError, 'POLICY_CHANGED'):
                resolve_embedded(altered)
        for identity in ('annual_candidate_adoption_v99', None, '../../policy'):
            with self.assertRaisesRegex(ValueError, 'UNKNOWN_ADOPTION_POLICY'):
                policy(policy_id=identity)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'config').mkdir()
            value = policy(policy_id=V2); value['company_id'] = 'foreign'
            (root / POLICIES[V2][0]).write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'BYTES_CHANGED'):
                policy(root, V2)

    def test_new_requirement_is_pending_and_parent_remains_native(self):
        parent = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v6')
        new = load_requirement_snapshot(snapshot_dir=ROOT / 'requirements/issue_28_v7')
        self.assertEqual('NOT_ACTIVATED', new['activation_state'])
        self.assertEqual(parent['requirement_closure_hash'], new['parent_requirement_closure_hash'])
        self.assertEqual('PENDING_EXTERNAL_APPROVAL', new['effective_decisions']['S-ANNUAL-ADOPTION']['status'])
        self.assertEqual(parent['effective_decisions']['S-ANNUAL-REPAIR'], new['effective_decisions']['S-ANNUAL-REPAIR'])
        self.assertEqual(policy(policy_id=V2), new['adoption_policy'])

    def _plan(self):
        chosen = policy(policy_id=V2)
        return {'repository': 'wlvh/SEC_metrics', 'pull_number': 999, 'planned_at_utc': '2026-09-09T00:00:00Z',
            'plan_id': 'sha256:' + '1' * 64, 'environment': 'ISOLATED_TEST',
            'code': {'exact_head': git('rev-parse', 'HEAD').decode().strip()},
            'binding': {'requirement_id': chosen['adoption_requirement_id'], 'requirement_closure_hash': 'sha256:' + '2' * 64,
                'policy_id': V2, 'policy_hash': content_hash(value=chosen)}}

    def test_publication_template_has_no_model_grant_and_is_distinct(self):
        plan = self._plan(); approved = auth.expected_owner_approval(plan)
        self.assertEqual('TEST_ONLY_APPROVE_REQUIREMENT_TRANSITION', auth.expected_activation_approval(plan)['decision'])
        self.assertEqual('TEST_ONLY_AUTHORIZE_ISOLATED_PUBLICATION', approved['decision'])
        self.assertEqual([0, 0, 0], approved['new_provider_paid_sec_calls'])
        self.assertNotIn('maximum_new_executions', approved)
        self.assertNotIn('provider_calls_authorized', approved)
        plan['environment'] = 'PRODUCTION'
        self.assertEqual('APPROVE_REQUIREMENT_TRANSITION', auth.expected_activation_approval(plan)['decision'])
        self.assertNotEqual(approved, auth.expected_owner_approval(plan))
        self.assertEqual('AUTHORIZE_CANDIDATE_SPECIFIC_PUBLICATION', auth.expected_owner_approval(plan)['decision'])

    def test_real_comment_boundary_rejects_wrong_author_edit_time_body_and_location(self):
        plan = self._plan(); expected = auth.expected_owner_approval(plan)
        url = 'https://github.com/wlvh/SEC_metrics/pull/999#issuecomment-123'
        comment = {'id': 123, 'html_url': url, 'issue_url': 'https://api.github.com/repos/wlvh/SEC_metrics/issues/999',
            'user': {'login': 'wlvh'}, 'body': json.dumps(expected),
            'created_at': '2026-09-09T01:00:00Z', 'updated_at': '2026-09-09T01:00:00Z'}
        with mock.patch.object(annual_candidate, '_github', return_value=comment) as boundary:
            self.assertEqual(expected, json.loads(auth._comment(plan, url, expected)['body']))
            boundary.assert_called_once_with('repos/wlvh/SEC_metrics/issues/comments/123')
        variants = []
        for key, value in [('id', 124), ('html_url', url + 'x'), ('issue_url', comment['issue_url'] + '0'),
                           ('user', {'login': 'other'}), ('updated_at', '2026-09-09T02:00:00Z'),
                           ('body', json.dumps({**expected, 'decision': 'AUTHORIZE_ORDINARY_ANNUAL_CANDIDATE'})),
                           ('body', json.dumps({**expected, 'plan_id': 'sha256:' + '9' * 64}))]:
            variants.append({**comment, key: value})
        variants.append({**comment, 'created_at': '2020-01-01T00:00:00Z', 'updated_at': '2020-01-01T00:00:00Z'})
        for changed in variants:
            with self.subTest(changed=changed), mock.patch.object(annual_candidate, '_github', return_value=changed), self.assertRaises(ValueError):
                auth._comment(plan, url, expected)
        with self.assertRaisesRegex(ValueError, 'LOCATION_INVALID'):
            auth._comment(plan, url.replace('/999#', '/998#'), expected)

    def test_no_local_dict_or_old_permission_can_enter_deploy_or_switch(self):
        for fake in ({'approved': True}, object(), None):
            with self.subTest(fake=fake), self.assertRaisesRegex(ValueError, 'VERIFIED_GITHUB_PERMISSION_REQUIRED'):
                auth.deploy(permission=fake)
            with self.assertRaisesRegex(ValueError, 'VERIFIED_GITHUB_PERMISSION_REQUIRED'):
                auth.execute(permission=fake, operation='publish')
        with self.assertRaisesRegex(ValueError, 'VERIFIED_GITHUB_PERMISSION_REQUIRED'):
            auth.PublicationPermission(factory=object(), binding={})
        with self.assertRaisesRegex(ValueError, 'PRODUCTION_SWITCH_PERMISSION_REQUIRED'):
            auth.commit_authority(bundle_dir=ROOT, manifest={})

    def test_journal_binding_has_an_exact_plan_action_and_permission_shape(self):
        valid = {k: 'sha256:' + str(i) * 64 for i, k in enumerate(('plan_id', 'action_id', 'permission_id'), 1)}
        pub._validate_annual_switch_authority(valid)
        for changed in ({}, {**valid, 'allow_any': True}, {**valid, 'action_id': 'fake'}):
            with self.assertRaises(pub.PublicationError):
                pub._validate_annual_switch_authority(changed)


if __name__ == '__main__':
    unittest.main()
