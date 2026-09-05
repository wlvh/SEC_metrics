"""Full fifteen-Run release rehearsal shared with the recorded execution test."""

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from unittest import mock

from vnext.canonical import canonical_json_bytes, content_hash, strict_json_file
from vnext import publication as pub
from vnext import r4_publication as release
from vnext.r4_release import _construct, _prepare_recorded_release_context, validate_r4_release_context


def exercise_recorded_release(case, *, root, plan, replay, real_root):
    before = pub.publication_state_snapshot(publication_root=real_root)
    temporary_before = pub.publication_state_snapshot(publication_root=root)
    context = _prepare_recorded_release_context(repo_root=root, plan=plan, replay=replay)
    case.assertEqual(context.mode, 'RECORDED_REHEARSAL')
    case.assertEqual(context.proof['publication_credit'], release.REHEARSAL_CREDIT)
    case.assertEqual(6, len(context.production_runs))
    case.assertEqual(54, sum(row['applicability'] == 'N_A_STRUCTURAL' for row in context.expected_keys))
    # This copied graph deliberately has no Git metadata. Supply only the
    # source-commit read prerequisite so the real factory reaches its actual
    # recorded/LIVE discriminator; no Requirement/Run/replay gate is replaced.
    def source_commit_only(checkout, *args):
        case.assertEqual(checkout, root.resolve())
        case.assertEqual(args, ('rev-parse', 'HEAD'))
        return 'a' * 40
    with mock.patch('vnext.r4_release._git', side_effect=source_commit_only) as git_read:
        with case.assertRaisesRegex(ValueError, 'Recorded execution cannot acquire LIVE'):
            _construct(root=root, pending=plan, replay=replay, mode='LIVE')
        git_read.assert_called_once()
    # Mutate actual post-replay files, not a caller-authored successful helper.
    namespace = root / 'artifacts/vnext/qualification/r4_scoped' / plan['pending_plan_id'][7:]
    paths = [namespace / 'execution_summary.json',
             namespace / 'entries' / plan['entries'][0]['entry_id'][7:] / 'qualification_terminal.json',
             root / 'config/release_plans/issue_28_r4_scoped_engine_v2.json',
             root / context.proof['spec_bindings']['A13']['path']]
    mutation_names = []
    for path in paths:
        saved = path.read_bytes()
        try:
            if path.name == 'qualification_terminal.json':
                changed = strict_json_file(path=path)
                changed['status'] = 'FAILED'
                changed['terminal_id'] = content_hash(value={key: value for key, value in changed.items()
                                                           if key != 'terminal_id'})
                path.write_bytes(canonical_json_bytes(value=changed) + b'\n')
            else:
                path.write_bytes(saved + b' ')
            with case.subTest(mutated_path=path.relative_to(root).as_posix()):
                with case.assertRaises((ValueError, pub.PublicationError)):
                    validate_r4_release_context(context)
            mutation_names.append(path.relative_to(root).as_posix())
        finally:
            path.write_bytes(saved)
    original = context._production
    selection_mutations = []
    for mutation in ('missing', 'extra', 'duplicate', 'alternate', 'stability', 'bac', 'citi'):
        try:
            context._production = [dict(row) for row in original]
            if mutation == 'missing':
                context._production.pop()
            elif mutation == 'extra':
                context._production.append(dict(original[0]))
            elif mutation == 'duplicate':
                context._production[1] = dict(original[0])
            elif mutation in ('bac', 'citi'):
                context._production[0]['company_id'] = mutation
            else:
                context._production[0]['fixture_id'] = 'r4_a03_' + mutation
                context._production[0]['run_path'] = namespace.relative_to(root).as_posix() + '/entries/' + mutation + '/run'
            with case.subTest(production_selection=mutation), case.assertRaisesRegex(ValueError, 'selection changed'):
                validate_r4_release_context(context)
            selection_mutations.append(mutation)
        finally:
            context._production = original
    with case.assertRaises((ValueError, pub.PublicationError)):
        release.stage_r4_release(context={'verified': True, 'root': real_root})
    print('R4_RELEASE: native aggregate/selection negatives passed', flush=True)
    staged = release.stage_r4_release(context=context)
    manifest, pin, receipt = staged['manifest'], staged['pin'], staged['receipt']
    identity, predecessor = manifest['publication_id'], manifest['previous_publication_id']
    case.assertEqual(manifest['record_type'], 'R4_SUCCESSOR_PUBLICATION_MANIFEST')
    case.assertEqual(manifest['publication_credit'], release.REHEARSAL_CREDIT)
    case.assertEqual(receipt['completeness_proof']['delta_result_count'], 60)
    case.assertEqual(receipt['completeness_proof']['cumulative_result_count'], 300)
    case.assertEqual(pub.publication_state_snapshot(publication_root=root), temporary_before)
    case.assertEqual(pub.publication_state_snapshot(publication_root=real_root), before)
    directory = root / 'outputs/publications' / identity
    batch = strict_json_file(path=directory / release.BATCH_DOCUMENT)
    projection_manifest = strict_json_file(path=directory / 'projection_manifest.json')
    case.assertEqual(projection_manifest['projection_manifest_id'], content_hash(value={
        key: value for key, value in projection_manifest.items() if key != 'projection_manifest_id'}))
    case.assertEqual(manifest['projection_manifest_id'], projection_manifest['projection_manifest_id'])
    selected = batch['native_result_bindings']
    case.assertEqual(len(selected), 60)
    case.assertEqual(sum(row['kind'] == 'NATIVE_STRUCTURAL' for row in selected), 54)
    case.assertEqual(sum(row['kind'] == 'VERIFIED_PRODUCTION' for row in selected), 6)
    case.assertEqual(len({row['run_id'] for row in selected}), 60)
    print('R4_RELEASE: staged native6+54 with unchanged real/temporary R3', flush=True)
    # Rebound envelope mutations must still hit the inner receipt binding.
    original_manifest = (directory / 'publication_manifest.json').read_bytes()
    # Strip the release subtype's guards on the actual complete artifact. The
    # old wrapper cannot interpret the R4 closure as its own projection proof.
    disguised = deepcopy(manifest)
    disguised['record_type'] = 'SUCCESSOR_PUBLICATION_MANIFEST'
    del disguised['r4_release_receipt_id'], disguised['publication_credit']
    disguised['publication_id'] = 'publication_' + content_hash(value={k: v for k, v in disguised.items()
        if k not in {'record_type', 'publication_id'}})[7:]
    hidden = directory.parent / ('.' + identity + '.downgrade-test')
    directory.rename(hidden)
    try:
        (hidden / 'publication_manifest.json').write_bytes(canonical_json_bytes(value=disguised) + b'\n')
        with case.assertRaisesRegex(pub.PublicationError, 'file exact set differs'):
            pub.verify_publication_bundle(bundle_dir=hidden)
    finally:
        (hidden / 'publication_manifest.json').write_bytes(original_manifest)
        hidden.rename(directory)
    metric_path = directory / 'metrics_matrix.csv'
    metric_bytes = metric_path.read_bytes()
    try:
        metric_path.write_bytes(metric_bytes + b'\n')
        with case.assertRaises((ValueError, pub.PublicationError)):
            pub.verify_publication_bundle(bundle_dir=directory)
    finally:
        metric_path.write_bytes(metric_bytes)
    with release._pinned(pin):
        # Existing public/private legacy entrypoints do not issue an R4 cap.
        for function in (pub._commit_publication, pub._commit_recorded_sandbox_publication):
            with case.assertRaises((ValueError, pub.PublicationError)):
                function(publication_root=root, publication_id=identity,
                    expected_active_publication_id=predecessor, committed_at_utc='2026-09-04T02:00:00Z')
        with case.assertRaises((ValueError, pub.PublicationError)):
            release.verify_release_owner_comment(publication_root=root, pin=pin,
                source_url='https://github.com/wlvh/SEC_metrics/pull/30#issuecomment-1')
    case.assertEqual(pub.publication_state_snapshot(publication_root=root), temporary_before)
    # A fresh interpreter imports its own frozen production files and performs
    # full native replay, while the OS denies all network and bundle writes.
    code = textwrap.dedent('''
        import json, pathlib, socket, sys
        from contextlib import ExitStack
        from unittest.mock import patch
        bundle = pathlib.Path(sys.argv[1]).resolve()
        authority = bundle / 'internal/r4_authority'
        sys.path.insert(0, str(authority / 'scripts'))
        import sec_http
        from vnext import ai_adapter, publication, r4_release, r4_publication
        from vnext.canonical import strict_json_file
        with ExitStack() as stack:
            guards = [stack.enter_context(patch.object(ai_adapter, '_open_provider_request', side_effect=AssertionError('NO_PROVIDER'))),
                stack.enter_context(patch.object(sec_http, 'urlopen', side_effect=AssertionError('NO_SEC'))),
                stack.enter_context(patch.object(socket.socket, 'connect', side_effect=AssertionError('NO_SOCKET'))),
                stack.enter_context(patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('NO_SOCKET_EX')))]
            manifest = publication.verify_publication_bundle(bundle_dir=bundle)
            for guard in guards: guard.assert_not_called()
        for module in (ai_adapter, publication, r4_release, r4_publication):
            assert pathlib.Path(module.__file__).resolve().is_relative_to(authority)
        receipt = strict_json_file(path=bundle / r4_publication.RELEASE_RECEIPT)
        print(json.dumps({'status': 'PASS', 'publication_id': manifest['publication_id'],
            'release_receipt_id': receipt['release_receipt_id'], 'publication_credit': manifest['publication_credit'],
            'provider_paid_sec_calls': [0,0,0], 'authority_python': 'FROZEN_BUNDLE_ONLY'}))
    ''')
    endpoint = subprocess.run(['docker', 'context', 'inspect', '--format', '{{ (index .Endpoints "docker").Host }}'],
        capture_output=True, text=True, check=True).stdout.strip()
    case.assertTrue(endpoint.startswith('unix:///'), 'Cold rehearsal permits only the existing local Docker Unix socket')
    docker_socket = endpoint.removeprefix('unix://')
    policy = ('(version 1)(allow default)(deny network*)'
        + '(allow network-outbound (remote unix-socket (path ' + json.dumps(docker_socket) + ')))'
        + '(deny file-write* (subpath ' + json.dumps(str(directory)) + '))'
        + '(deny file-read* (subpath ' + json.dumps(str(real_root.resolve())) + '))')
    process = subprocess.run(['/usr/bin/sandbox-exec', '-p', policy, sys.executable, '-B', '-c', code, str(directory)],
        cwd=directory.parent, capture_output=True, text=True, check=False, timeout=1800)
    case.assertEqual(process.returncode, 0, process.stdout[-4000:] + process.stderr[-12000:])
    readback = json.loads(process.stdout.strip().splitlines()[-1])
    case.assertEqual(readback['publication_credit'], release.REHEARSAL_CREDIT)
    print('R4_RELEASE: fresh frozen-authority readback PASS, OS socket/write denial active', flush=True)
    owner = release._rehearsal_authority(publication_root=root, pin=pin)
    def stop_mid_mirrors(*, fault_point):
        if fault_point == 'MID_MIRROR_WRITE':
            raise SystemExit('simulated process death before pointer commit')
    with mock.patch.object(pub, '_fault_injection_checkpoint', side_effect=stop_mid_mirrors), case.assertRaises(SystemExit):
        release.switch_r4_release(authority=owner, operation='publish', committed_at_utc='2026-09-04T01:58:00Z')
    with release._pinned(pin), case.assertRaises((ValueError, pub.PublicationError)):
        pub.recover_publication_mirrors(publication_root=root)
    recovered = release.switch_r4_release(authority=owner, operation='recover-mirrors', committed_at_utc='2026-09-04T01:59:00Z')
    case.assertEqual(recovered['terminal']['publication_id'], predecessor)
    published = release.switch_r4_release(authority=owner, operation='publish', committed_at_utc='2026-09-04T02:00:00Z')
    case.assertEqual(published['terminal']['publication_id'], identity)
    with release._pinned(pin), case.assertRaises((ValueError, pub.PublicationError)):
        pub.rollback_publication(publication_root=root, target_publication_id=predecessor,
            expected_active_publication_id=identity, committed_at_utc='2026-09-04T02:01:00Z')
    matrix = root / 'outputs/metrics_matrix.csv'
    saved = matrix.read_bytes()
    try:
        matrix.write_bytes(saved + b' ')
        with case.assertRaisesRegex(ValueError, 'mirror drift'):
            release.switch_r4_release(authority=owner, operation='rollback-to-R3', committed_at_utc='2026-09-04T02:01:00Z')
    finally:
        matrix.write_bytes(saved)
    rolled = release.switch_r4_release(authority=owner, operation='rollback-to-R3', committed_at_utc='2026-09-04T02:02:00Z')
    case.assertEqual(rolled['terminal']['publication_id'], predecessor)
    def stop_after_pointer(*, fault_point):
        if fault_point == 'POINTER_WRITTEN_BEFORE_SWITCH_RECEIPT':
            raise SystemExit('simulated process death after pointer commit')
    with mock.patch.object(pub, '_fault_injection_checkpoint', side_effect=stop_after_pointer), case.assertRaises(SystemExit):
        release.switch_r4_release(authority=owner, operation='restore-R4', committed_at_utc='2026-09-04T02:02:10Z')
    with release._pinned(pin), case.assertRaises((ValueError, pub.PublicationError)):
        pub.recover_publication_mirrors(publication_root=root)
    after_pointer = release.switch_r4_release(authority=owner, operation='recover-mirrors', committed_at_utc='2026-09-04T02:02:20Z')
    case.assertEqual(after_pointer['terminal']['publication_id'], identity)
    release.switch_r4_release(authority=owner, operation='rollback-to-R3', committed_at_utc='2026-09-04T02:02:30Z')
    restored = release.switch_r4_release(authority=owner, operation='restore-R4', committed_at_utc='2026-09-04T02:03:00Z')
    case.assertEqual(restored['terminal']['publication_id'], identity)
    pointer = root / 'outputs/active_publication.json'
    saved = pointer.read_bytes()
    try:
        invalid = strict_json_file(path=pointer)
        invalid['bundle_manifest_sha256'] = '0' * 64
        pointer.write_bytes(canonical_json_bytes(value=invalid) + b'\n')
        with case.assertRaises((ValueError, pub.PublicationError)):
            release.active_terminal(publication_root=root, pin=pin)
    finally:
        pointer.write_bytes(saved)
    final = release.active_terminal(publication_root=root, pin=pin)
    case.assertEqual(final['mirror_count'], 14)
    case.assertEqual(pub.publication_state_snapshot(publication_root=real_root), before)
    case.assertEqual((directory / 'publication_manifest.json').read_bytes(), original_manifest)
    result = {'status': 'PASS', 'release_context_id': context.release_context_id,
        'publication_id': identity, 'release_receipt_id': receipt['release_receipt_id'],
        'batch_manifest_id': batch['batch_manifest_id'], 'read_back': readback,
        'publish_receipt_id': published['receipt_id'], 'rollback_receipt_id': rolled['receipt_id'],
        'crash_recovery_receipt_id': recovered['receipt_id'],
        'post_pointer_crash_recovery_receipt_id': after_pointer['receipt_id'],
        'restore_receipt_id': restored['receipt_id'], 'active_terminal_receipt_id': final['receipt_id'],
        'completeness_proof': receipt['completeness_proof'], 'mutation_paths': mutation_names,
        'production_selection_mutations_rejected': selection_mutations,
        'publication_credit': release.REHEARSAL_CREDIT, 'qualification_credit': release.REHEARSAL_CREDIT,
        'real_root_unchanged': True, 'provider_paid_sec_calls': [0, 0, 0]}
    destination = os.environ.get('R4_TEST_EVIDENCE_OUTPUT')
    if destination:
        output = Path(destination)
        case.assertTrue(output.is_absolute())
        case.assertFalse(output.resolve().is_relative_to(real_root.resolve()))
        case.assertFalse(output.resolve().is_relative_to(root.resolve()))
        body = {'record_type': 'R4_RECORDED_RELEASE_REHEARSAL_EVIDENCE', 'schema_version': 1,
            'status': 'PASS', 'summary': result, 'context_document': pin.context_document,
            'publication_manifest': manifest, 'release_receipt': receipt, 'batch_manifest': batch,
            'compatibility_receipt': strict_json_file(path=directory / release.COMPATIBILITY_DOCUMENT),
            'publication_validation_receipt': strict_json_file(path=directory / 'publication_validation_receipt.json'),
            'selected_public_results': [record for run in context._production for record in run['records']
                                        if record['record_type'] == 'METRIC_RESULT'],
            'publish': published, 'rollback': rolled, 'restore': restored,
            'before_pointer_recovery': recovered, 'after_pointer_recovery': after_pointer,
            'final_active_terminal': final, 'real_root_before_and_after': before,
            'full_runtime_graph': 'TEMPORARY_TEST_ONLY_REPRODUCIBLE_BY_INTEGRATION_COMMAND',
            'qualification_credit': release.REHEARSAL_CREDIT, 'publication_credit': release.REHEARSAL_CREDIT}
        body['receipt_id'] = content_hash(value=body)
        with output.open('xb') as stream:
            stream.write(canonical_json_bytes(value=body) + b'\n')
    print('R4_RELEASE_REHEARSAL_RESULT=' + json.dumps(result, sort_keys=True), flush=True)
    return result
