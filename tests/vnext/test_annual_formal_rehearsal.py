"""Real v2 bundle integration; only GitHub I/O and native faults are injected.

ANNUAL_FORMAL_TEST_ROOT/ID must point to a genuinely prepared complete package.
Missing material is SKIP, never acceptance. Every test grant is TEST_ONLY and
targets a temporary marker-owned root. The actual publication root is read-only.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest import mock

from vnext import annual_publication as annual, annual_publication_authority as auth
from vnext import annual_candidate, publication as pub
from vnext import invocation_control as controller
from vnext.annual_adoption import read, record, git, _tree_files
from vnext.annual_adoption_policy import V1, V2, policy
from vnext.canonical import canonical_json_bytes, content_hash


class HardCrash(BaseException):
    pass


def save(path, value):
    path.write_bytes(canonical_json_bytes(value=value))


class AnnualFormalRehearsalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        supplied = os.environ.get('ANNUAL_FORMAL_TEST_ROOT')
        cls.identity = os.environ.get('ANNUAL_FORMAL_TEST_ID')
        if not supplied or not cls.identity:
            raise unittest.SkipTest('Requires an actually prepared complete v2 candidate package')
        cls.root = Path(supplied).resolve()
        cls.directory = cls.root / 'outputs/publications' / cls.identity
        cls.manifest = pub.verify_publication_bundle(bundle_dir=cls.directory)
        cls.pin = annual._Verified(annual._FACTORY, cls.manifest)
        cls.context = read(cls.directory, annual.SNAPSHOT + '/context.json')
        cls.origin = Path(cls.context['origin']['candidate_directory'])
        cls.before = _tree_files(root=cls.origin)
        cls.formal = _tree_files(root=annual.ROOT / 'outputs/publications')
        cls.protected = {p: (annual.ROOT / p).read_bytes() for p in read(annual.ROOT,
            'docs/evidence/annual_runtime/repair/post-live-protection.json')['files']}
        cls.log = []

    @classmethod
    def tearDownClass(cls):
        assert _tree_files(root=cls.origin) == cls.before
        assert _tree_files(root=annual.ROOT / 'outputs/publications') == cls.formal
        assert all((annual.ROOT / p).read_bytes() == b for p, b in cls.protected.items())
        output = os.environ.get('ANNUAL_FORMAL_TEST_REPORT')
        if output:
            save(Path(output), {'status': 'COMPLETED_CHECK_LOG', 'evidence_origin': 'ISOLATED_TEST_GITHUB_IO_ONLY',
                'publication_id': cls.identity, 'implementation_head': read(cls.directory, annual.META)['implementation_head'],
                'checks': cls.log, 'original_candidate_and_actual_root_unchanged': True,
                'new_provider_paid_sec_calls': [0, 0, 0], 'production_grant_issued': False})

    def setUp(self):
        patch = mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('NETWORK_FORBIDDEN'))
        patch.start(); self.addCleanup(patch.stop)
        self.material = tempfile.TemporaryDirectory(prefix='annual-formal-test-', dir=self.root.parent)
        self.addCleanup(self.material.cleanup)
        self.target = Path(self.material.name) / 'publication'
        annual.initialize(publication_root=self.target)
        self.pin_scope = annual._verified(self.pin); self.pin_scope.__enter__()
        self.addCleanup(lambda: self.pin_scope.__exit__(None, None, None))

    def _permission(self, target=None):
        plan = auth.plan_publication(bundle_dir=self.directory, target_root=target or self.target, pull_number=999999)
        prefix = 'https://github.com/' + plan['repository'] + '/pull/' + str(plan['pull_number'])
        urls = [prefix + '#issuecomment-' + str(i) for i in (910000001, 910000002)]
        created = annual.utc()
        comments = {}
        for url, body in zip(urls, (auth.expected_activation_approval(plan), auth.expected_owner_approval(plan))):
            identity = int(url.rsplit('-', 1)[1])
            comments['repos/' + plan['repository'] + '/issues/comments/' + str(identity)] = {
                'id': identity, 'html_url': url, 'issue_url': 'https://api.github.com/repos/' + plan['repository'] + '/issues/' + str(plan['pull_number']),
                'user': {'login': plan['repository'].split('/')[0]}, 'body': json.dumps(body),
                'created_at': created, 'updated_at': created}
        comments['repos/' + plan['repository'] + '/pulls/' + str(plan['pull_number'])] = {
            'number': plan['pull_number'], 'state': 'open', 'merged': False, 'merge_commit_sha': None,
            'head': {'sha': git('rev-parse', 'HEAD').decode().strip(), 'repo': {'full_name': plan['repository']}},
            'base': {'ref': 'main', 'repo': {'full_name': plan['repository']}}}
        def github(path):
            return copy.deepcopy(comments[path])
        with mock.patch.object(annual_candidate, '_github', side_effect=github):
            permission = auth.verify_authorization(plan=plan, activation_url=urls[0], owner_url=urls[1])
        self.assertEqual('ISOLATED_TEST', plan['environment'])
        self.assertEqual('ISOLATED_REQUIREMENT_TRANSITION_REHEARSAL', auth._permission(permission)['activation']['record_type'])
        return plan, permission, urls, github

    def test_complete_version_permission_switch_and_finite_directions(self):
        prepared = annual.read_version(publication_root=self.root, publication_id=self.identity)
        self.assertEqual(327, prepared['public_row_count'])
        self.assertEqual(2, len(prepared['verified_source_locations']))
        batch = read(self.directory, annual.BATCH)
        self.assertEqual((2, 238, 240), (batch['selected_result_count'], batch['inherited_result_count'], len(batch['cumulative_result_bindings'])))
        self.assertEqual({'B01', 'B10'}, {r['metric_id'] for r in batch['cumulative_result_bindings'] if r['origin'] == 'ADOPTED_NATIVE_CANDIDATE'})
        plan, permission, urls, github = self._permission()
        invocation = json.loads(next((self.directory / annual.SNAPSHOT / 'candidate/invocation_control/plans').glob('*.json')).read_text())
        with self.assertRaises(controller.InvocationControlError):
            controller.execute_successor_invocation(repo_root=annual.ROOT, authority=permission, plan=invocation)
        old = (self.target / 'outputs/active_publication.json').read_bytes()
        auth.deploy(permission=permission)
        self.assertEqual(old, (self.target / 'outputs/active_publication.json').read_bytes())
        for call in (lambda: pub._commit_publication(publication_root=self.target, publication_id=self.identity,
                        expected_active_publication_id=plan['predecessor']['publication_id'], committed_at_utc=annual.utc()),
                     lambda: annual.switch(publication_root=self.target, publication_id=self.identity, operation='publish')):
            with self.assertRaises((ValueError, pub.PublicationError)):
                call()
        published = auth.execute(permission=permission, operation='publish')
        self.assertEqual(self.identity, published['publication_id'])
        native = pub._switch_receipt_for_pointer(pointer_path=self.target / 'outputs/active_publication.json',
            pointer=read(self.target, 'outputs/active_publication.json'))
        self.assertEqual(2, native['schema_version'])
        self.assertEqual(plan['plan_id'], native['annual_authority']['plan_id'])
        before = _tree_files(root=self.target)
        self.assertEqual('AUTHORIZED_OPERATION_ALREADY_RESERVED', auth.execute(permission=permission, operation='publish')['status'])
        self.assertEqual(before, _tree_files(root=self.target))
        # Re-verification from the same immutable external facts is stable.
        with mock.patch.object(annual_candidate, '_github', side_effect=github):
            reopened = auth.verify_authorization(plan=plan, activation_url=urls[0], owner_url=urls[1])
        self.assertEqual(permission._bytes, reopened._bytes)
        self.assertEqual(plan['predecessor']['publication_id'], auth.execute(permission=reopened, operation='rollback')['publication_id'])
        self.assertEqual(self.identity, auth.execute(permission=reopened, operation='restore')['publication_id'])
        after = _tree_files(root=self.target)
        self.assertEqual('AUTHORIZED_OPERATION_ALREADY_RESERVED', auth.execute(permission=reopened, operation='rollback')['status'])
        self.assertEqual(after, _tree_files(root=self.target))
        view = annual.read_version(publication_root=self.target)
        self.assertEqual(prepared['selected_rows'], view['selected_rows'])
        self.assertEqual(prepared['selected_evidence'], view['selected_evidence'])
        self.assertEqual(prepared['verified_source_locations'], view['verified_source_locations'])
        self.log.append({'check': 'COMPLETE_NATIVE_2_INHERITED_238_PUBLISH_ROLLBACK_RESTORE_DEDUP', 'status': 'PASS',
                         'plan_id': plan['plan_id'], 'sources': prepared['verified_source_locations']})

    def test_soft_failure_retains_old_complete_version(self):
        plan, permission, _, _ = self._permission(); auth.deploy(permission=permission)
        old = annual.read_version(publication_root=self.target)
        def fail(*, fault_point):
            if fault_point == 'MID_MIRROR_WRITE':
                raise OSError('ISOLATED_INJECTED_MIRROR_FAILURE')
        with mock.patch.object(pub, '_fault_injection_checkpoint', side_effect=fail), self.assertRaises(pub.PublicationError):
            auth.execute(permission=permission, operation='publish')
        self.assertEqual(old, annual.read_version(publication_root=self.target))
        self.assertEqual('NO_PENDING_AUTHORIZED_SWITCH', auth.execute(permission=permission, operation='recover')['status'])
        self.assertEqual('AUTHORIZED_OPERATION_ALREADY_RESERVED', auth.execute(permission=permission, operation='publish')['status'])
        self.log.append({'check': 'SOFT_FAILURE_OLD_VERSION_AND_RESERVED_ATTEMPT', 'status': 'PASS', 'plan_id': plan['plan_id']})

    def test_reserved_action_without_native_intent_preserves_old_and_does_not_retry(self):
        plan, permission, _, _ = self._permission(); auth.deploy(permission=permission)
        old = annual.read_version(publication_root=self.target)
        def crash(*, fault_point):
            if fault_point == 'ANNUAL_ACTION_RESERVED_BEFORE_NATIVE_SWITCH':
                raise HardCrash(fault_point)
        with mock.patch.object(pub, '_fault_injection_checkpoint', side_effect=crash), self.assertRaises(HardCrash):
            auth.execute(permission=permission, operation='publish')
        self.assertIsNone(pub._load_switch_intent(pointer_path=self.target / 'outputs/active_publication.json'))
        self.assertEqual(old, annual.read_version(publication_root=self.target))
        self.assertEqual('NO_PENDING_AUTHORIZED_SWITCH', auth.execute(permission=permission, operation='recover')['status'])
        self.assertEqual('AUTHORIZED_OPERATION_ALREADY_RESERVED', auth.execute(permission=permission, operation='publish')['status'])
        self.assertEqual(old, annual.read_version(publication_root=self.target))
        self.log.append({'check': 'PRE_INTENT_CRASH_OLD_COMPLETE_NO_AUTOMATIC_RETRY', 'status': 'PASS', 'plan_id': plan['plan_id']})

    def test_pre_and_post_pointer_recovery_is_bound_to_the_same_action(self):
        for point in ('MIRRORS_WRITTEN_BEFORE_POINTER_COMMIT', 'POINTER_WRITTEN_BEFORE_SWITCH_RECEIPT'):
            with self.subTest(point=point):
                target = Path(self.material.name) / point
                annual.initialize(publication_root=target)
                plan, permission, _, _ = self._permission(target); auth.deploy(permission=permission)
                def crash(*, fault_point):
                    if fault_point == point:
                        raise HardCrash(point)
                with mock.patch.object(pub, '_fault_injection_checkpoint', side_effect=crash), self.assertRaises(HardCrash):
                    auth.execute(permission=permission, operation='publish')
                with self.assertRaises(pub.PublicationError):
                    pub.PublicationView.open(publication_root=target)
                intent = pub._load_switch_intent(pointer_path=target / 'outputs/active_publication.json')
                self.assertEqual(plan['plan_id'], intent['annual_authority']['plan_id'])
                path = target / 'outputs/publication_switch_intents' / (intent['intent_id'][7:] + '.json')
                changed = copy.deepcopy(intent); changed['annual_authority']['action_id'] = 'sha256:' + '0' * 64
                changed = record({k: v for k, v in changed.items() if k != 'intent_id'}, 'intent_id')
                renamed = path.parent / (changed['intent_id'][7:] + '.json')
                original = path.read_bytes(); path.unlink(); save(renamed, changed)
                with self.assertRaisesRegex(ValueError, 'DIFFERENT_TRANSACTION'):
                    auth.execute(permission=permission, operation='recover')
                renamed.unlink(); path.write_bytes(original)
                result = auth.execute(permission=permission, operation='recover')
                expected = self.identity if point.startswith('POINTER_WRITTEN') else plan['predecessor']['publication_id']
                self.assertEqual(expected, result['publication_id'])
                again = auth.execute(permission=permission, operation='recover')
                self.assertEqual(expected, again['publication_id'])
                self.log.append({'check': point + '_BOUND_RECOVERY', 'status': 'PASS', 'plan_id': plan['plan_id']})

    def test_rebound_plan_and_approval_errors_never_write(self):
        plan, _, urls, github = self._permission()
        before = _tree_files(root=self.target)
        paths = [('binding', 'original_execution_id'), ('binding', 'source_snapshot_id'), ('binding', 'candidate_file_set_id'),
                 ('binding', 'selected_results_id'), ('binding', 'policy_hash'), ('binding', 'manifest_sha256'),
                 ('binding', 'requirement_closure_hash'), ('code', 'implementation_tree'), ('predecessor', 'manifest_sha256')]
        for parent, field in paths:
            changed = copy.deepcopy(plan); changed[parent][field] = 'sha256:' + '0' * 64
            changed = record({k: v for k, v in changed.items() if k != 'plan_id'}, 'plan_id')
            with self.subTest(field=field), self.assertRaises(ValueError):
                auth.validate_plan(changed)
        for field, value in [('target_root', str(annual.ROOT)), ('environment', 'PRODUCTION')]:
            changed = record({**{k: v for k, v in plan.items() if k != 'plan_id'}, field: value}, 'plan_id')
            with self.assertRaises(ValueError):
                auth.validate_plan(changed)
        for bad in ('author', 'edited', 'body', 'activation', 'old_execution', 'test_for_production'):
            changed = copy.deepcopy(plan)
            if bad == 'test_for_production':
                changed = auth.plan_publication(bundle_dir=self.directory, target_root=annual.ROOT, pull_number=plan['pull_number'])
            def wrong(path):
                result = github(path)
                if '/issues/comments/' in path:
                    if bad == 'author': result['user']['login'] = 'wrong-owner'
                    elif bad == 'edited': result['updated_at'] = '2099-01-01T00:00:00Z'
                    elif bad == 'body': result['body'] = '{}'
                    elif bad == 'activation' and path.endswith('910000001'): result['body'] = '{}'
                    elif bad == 'old_execution': result['body'] = json.dumps({'decision': 'AUTHORIZE_ORDINARY_ANNUAL_CANDIDATE'})
                return result
            with self.subTest(bad=bad), mock.patch.object(annual_candidate, '_github', side_effect=wrong), self.assertRaises(ValueError):
                auth.verify_authorization(plan=changed, activation_url=urls[0], owner_url=urls[1])
        self.assertEqual(before, _tree_files(root=self.target))
        self.log.append({'check': 'REHASHED_PLAN_BINDINGS_AND_EXTERNAL_APPROVAL_NEGATIVES', 'status': 'PASS', 'case_count': len(paths) + 8})

    def test_v1_and_actual_r3_remain_readable_and_v1_cannot_be_adopted(self):
        supplied = os.environ.get('ANNUAL_FORMAL_V1_ROOT')
        if not supplied:
            self.fail('Actual v1 material is required for this integration acceptance')
        root = Path(supplied)
        old = annual.read_version(publication_root=root)
        self.assertEqual(annual.CREDIT, old['publication_credit'])
        self.assertEqual(2, len(old['verified_source_locations']))
        directory = root / 'outputs/publications' / old['publication_id']
        with self.assertRaisesRegex(ValueError, 'V1_HAS_NO_PRODUCTION_CREDIT'):
            auth.plan_publication(bundle_dir=directory, target_root=self.target, pull_number=999999)
        r3 = pub.PublicationView.open(publication_root=annual.ROOT)
        self.assertEqual(policy(policy_id=V1)['baseline_publication']['publication_id'], r3.publication_id)
        self.log.append({'check': 'ACTUAL_R3_AND_V1_COMPATIBLE_NO_CREDIT_UPGRADE', 'status': 'PASS'})

    def test_rehashed_package_policy_mixing_is_rejected(self):
        for case in ('unknown_id', 'changed_content', 'mixed_version'):
            with self.subTest(case=case):
                directory = Path(self.material.name) / case
                shutil.copytree(self.directory, directory)
                meta = read(directory, annual.META)
                if case == 'unknown_id':
                    meta['policy']['policy_id'] = 'annual_candidate_adoption_v999'
                elif case == 'changed_content':
                    meta['policy']['operations']['publish'] = 9
                else:
                    meta['policy'] = policy(policy_id=V1)
                save(directory / annual.META, meta)
                manifest = copy.deepcopy(self.manifest)
                for entry in manifest['files']:
                    raw = (directory / entry['path']).read_bytes()
                    entry.update(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
                body = {k: v for k, v in manifest.items() if k not in {'record_type', 'publication_id'}}
                manifest['publication_id'] = 'publication_' + content_hash(value=body)[7:]
                save(directory / 'publication_manifest.json', manifest)
                with self.assertRaises(ValueError):
                    pub.verify_publication_bundle(bundle_dir=directory)
        self.log.append({'check': 'UNKNOWN_CHANGED_OR_MIXED_POLICY_AFTER_OUTER_REHASH', 'status': 'PASS', 'case_count': 3})

    def test_exact_approved_merge_relation_uses_real_git_objects_without_open_pr_rule(self):
        # Exercise the merge rule with actual completed PR39 Git objects. This
        # is not a B production grant and never calls its permission factory.
        old = read(annual.ROOT, 'docs/evidence/annual_publication/close/run-binding.json')
        supplied = os.environ.get('ANNUAL_FORMAL_PR39_MERGE')
        self.assertTrue(supplied, 'Actual PR39 merge identity must be supplied')
        parents = git('show', '-s', '--format=%P', supplied).decode().split()
        plan = {'repository': 'wlvh/SEC_metrics', 'pull_number': 39, 'code': auth._code(old['code']['head'])}
        pull = {'number': 39, 'state': 'closed', 'merged': True, 'merge_commit_sha': supplied,
            'head': {'sha': parents[1], 'repo': {'full_name': plan['repository']}},
            'base': {'ref': 'main', 'repo': {'full_name': plan['repository']}}}
        with mock.patch.object(annual_candidate, '_github', return_value=pull):
            self.assertEqual(supplied, auth._pull(plan, require_merge=True)['merge_commit_sha'])
        for changed in ({**pull, 'merged': False}, {**pull, 'merge_commit_sha': parents[0]},
                        {**pull, 'head': {**pull['head'], 'sha': old['code']['head']}}):
            with mock.patch.object(annual_candidate, '_github', return_value=changed), self.assertRaises(ValueError):
                auth._pull(plan, require_merge=True)
        self.log.append({'check': 'REAL_GIT_CLOSED_PR_MERGE_AND_NONARBITRARY_ANCESTRY', 'status': 'PASS',
            'merge_commit': supplied, 'scope': 'READ_ONLY_MERGE_RULE_NO_PRODUCTION_AUTHORIZATION'})


if __name__ == '__main__':
    unittest.main()
