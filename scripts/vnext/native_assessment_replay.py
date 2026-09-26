"""Read original native successes without assigning them to a new invocation.

Only an identical current request may consume original receipts. Original
execution authority is reconstructed from the call's sealed runtime, and the
current source validator must reproduce the original semantic records. This
is input replay, never a new provider execution or a diagnostic upgrade.
"""
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
import tarfile
import tempfile

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file, strict_json_loads
from .capacity_utilization_source import need
from .continuous_call_policy import REQUIREMENT_ID
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


def _acceptor(request, path):
    if request.get('record_type') == 'B13_REFERENCE_SCAN_REQUEST':
        from .capacity_two_stage import build_scan_acceptance
        return build_scan_acceptance
    from .capacity_reference_contract import ASSERTION_SCOPED_VERSION, SCANNED_VERSION
    if request.get('source_reference_contract', {}).get('version') in {
            SCANNED_VERSION, ASSERTION_SCOPED_VERSION}:
        from .capacity_two_stage import build_interpretation_acceptance
        proof = request['two_stage_contract']['scan_execution_proof']
        ordinal = proof['scan_ordinal']
        need(type(ordinal) is int and 0 < ordinal < int(path.name),
             'B13_TWO_STAGE_SCAN_ORDER_INVALID')
        return lambda **kwargs: build_interpretation_acceptance(
            scan_path=path.parent / ('%04d' % ordinal), **kwargs)
    if request['metric_id'] == 'B13':
        from .capacity_native_assessment import build_acceptance
    else:
        need(request['record_type'] == 'D04_NATIVE_INTERPRETATION_REQUEST', 'NATIVE_DIAGNOSTIC_UPGRADE_FORBIDDEN')
        from .d04_native_assessment import build_acceptance
    return build_acceptance


def revalidation_receipt(*, prepared, plan, original, expected):
    """Original receipt IDs stay intact; current semantic checks are separate."""
    need(all(original[k] == value for k, value in expected.items() if k != 'validator_semantic_hash'),
         'NATIVE_ORIGINAL_ACCEPTANCE_SEMANTICS_CHANGED')
    body = {'record_type': 'NATIVE_SOURCE_INPUT_REVALIDATION',
        'original_plan_id': plan['ai_invocation_plan_id'],
        'original_requirement_closure_hash': plan['requirement_closure_hash'],
        'original_acceptance_receipt_id': original['acceptance_receipt_id'],
        'original_validator_semantic_hash': original['validator_semantic_hash'],
        'current_requirement_closure_hash': prepared.requirement['requirement_closure_hash'],
        'current_validator_semantic_hash': expected['validator_semantic_hash'],
        'unchanged_semantic_records_hash': content_hash(value={k:v for k,v in expected.items() if k != 'validator_semantic_hash'}),
        'new_provider_execution': False}
    return {**body, 'revalidation_id': content_hash(value=body)}


@contextmanager
def _original_runtime(path):
    manifest = strict_json_file(path=path / 'execution-rules.json')
    expected = manifest['files']; seen = set()
    with tempfile.TemporaryDirectory(prefix='sec-native-readback-') as temporary:
        root = Path(temporary)
        with tarfile.open(path / 'execution-rules.tar.gz', 'r|gz') as archive:
            for member in archive:
                relative = PurePosixPath(member.name)
                need(member.isfile() and not relative.is_absolute() and '..' not in relative.parts
                     and str(relative) == member.name and member.name in expected and member.name not in seen,
                     'NATIVE_CAPTURED_RUNTIME_MEMBER_CHANGED')
                raw = archive.extractfile(member).read()
                need(expected[member.name] == {'sha256': sha256_bytes(content=raw), 'size': len(raw)},
                     'NATIVE_CAPTURED_RUNTIME_BYTES_CHANGED')
                target = root / member.name; target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(raw)
                seen.add(member.name)
        need(seen == set(expected), 'NATIVE_CAPTURED_RUNTIME_INCOMPLETE')
        yield root


def _captured_policy_view(*, root, prepared, plan):
    """Validate archived policy as data; never execute archived Python code."""
    from . import invocation_control as control
    from .continuous_call_policy import POLICY_PATH, delegation_fields
    snapshot = root / 'requirements' / REQUIREMENT_ID
    baseline = strict_json_file(path=snapshot / 'baseline_manifest.json')
    decisions = strict_json_file(path=snapshot / 'decision_register.json')
    policy = strict_json_file(path=root / POLICY_PATH)
    hashes = {key: sha256_file(path=snapshot / name) for key, name in (
        ('baseline_sha256', 'baseline_manifest.json'), ('contract_sha256', 'CONTRACT.md'),
        ('decision_register_sha256', 'decision_register.json'), ('invariant_profile_sha256', 'invariant_profile.json'),
        ('transfer_manifest_sha256', 'transfer_manifest.json'))}
    hashes.update(parent_requirement_closure_hash=baseline['parent']['requirement_closure_hash'],
                  validator_sha256=baseline['validator']['sha256'])
    need(baseline['requirement_id'] == REQUIREMENT_ID
         and baseline['requirement_generation'] == 'PROFILE_DRIVEN_V15'
         and baseline['validator']['path'] == 'scripts/vnext/requirement_profile_v15.py'
         and hashes == plan['requirement_hashes'] and content_hash(value=hashes) == plan['requirement_closure_hash']
         and sha256_file(path=root / baseline['validator']['path']) == hashes['validator_sha256'],
         'NATIVE_CAPTURED_REQUIREMENT_IDENTITY_CHANGED')
    for bindings in (baseline['execution_authority']['files'], baseline['new_rule_files']):
        for relative, binding in bindings.items():
            path = resolve_repository_file(repo_root=root, repo_relative_path=relative)
            need(binding == {'sha256': sha256_file(path=path), 'size': path.stat().st_size},
                 'NATIVE_CAPTURED_EXECUTION_BINDING_CHANGED')
    need(decisions['policy'] == policy and all(policy[k] == prepared.requirement['policy'][k] for k in
         ('delegation_url', 'delegation_body_sha256', 'budget_root', 'maximum_additional_provider_paid_sec_calls')),
         'NATIVE_ORIGINAL_ALLOWANCE_CHANGED')
    delegation_fields(strict_json_file(path=resolve_repository_file(repo_root=root,
        repo_relative_path=policy['delegation_record_path'])), policy=policy)
    for key in ('S-PROVIDER-TRANSPORT', 'S-TRANSPORT-RETRY', 'D-36', 'S-ISSUE28-CONTINUOUS-CALLS'):
        need(decisions['successor_decisions'][key] == prepared.requirement['effective_decisions'][key],
             'NATIVE_CAPTURED_INVOCATION_POLICY_CHANGED')
    _, current_policy, transport = prepared.authority._check()
    identity = {'artifact_requirement_generation': 'EXPLICIT_REQUIREMENT_V1', 'requirement_id': REQUIREMENT_ID,
                'requirement_closure_hash': plan['requirement_closure_hash'], 'requirement_hashes': hashes}
    invocation_policy = {**current_policy, 'requirement_closure_hash': plan['requirement_closure_hash']}
    class CapturedPolicy:
        def _check(self):
            return identity, invocation_policy, transport
    # This established wrapper is accepted only by read validation; all
    # execution contexts reject its type, so no old authority is reactivated.
    return control.HistoricalAnnualInvocationView(factory=control._SUCCESSOR_AUTHORITY_FACTORY,
                                                  authority=CapturedPolicy())


def replay_native_response(*, prepared, path):
    """Verify saved origin and current meaning, without opening a model socket."""
    from .continuous_semantic_calls import build_plan
    from . import invocation_control as control
    request = strict_json_loads(text=prepared.request_bytes.decode())
    need((path / 'semantic-request.json').read_bytes() == prepared.request_bytes
         and (path / 'source.json').read_bytes() == prepared.source_bytes,
         'NATIVE_SAVED_REQUEST_OR_SOURCE_CHANGED')
    terminal = strict_json_file(path=path / 'terminal.json')
    need(terminal['terminal_id'] == content_hash(value={k:v for k,v in terminal.items() if k != 'terminal_id'})
         and terminal['status'] == 'SUCCEEDED' and not terminal['stop_reason'],
         'NATIVE_SUCCESSFUL_ORIGINAL_TERMINAL_REQUIRED')
    for relative, digest in terminal['evidence'].items():
        need(sha256_file(path=resolve_repository_file(repo_root=path, repo_relative_path=relative)) == digest,
             'NATIVE_ORIGINAL_EVIDENCE_CHANGED')
    intent = strict_json_file(path=path / 'intent.json')
    need(intent['intent_id'] == terminal['intent_id'] and intent['channel'] == 'PROVIDER'
         and intent['requirement_id'] == REQUIREMENT_ID
         and intent['intent_id'] == content_hash(value={k:v for k,v in intent.items() if k != 'intent_id'}),
         'NATIVE_ORIGINAL_INTENT_CHANGED')
    _, current_plan = build_plan(prepared)
    plan = strict_json_file(path=resolve_repository_file(repo_root=path,
        repo_relative_path='invocation_control/plans/' + intent['plan_id'][7:] + '.json'))
    need(plan['ai_invocation_plan_id'] == intent['plan_id']
         and plan['requirement_closure_hash'] == intent['requirement_closure_hash']
         and plan['provider_request_body_sha256'] == sha256_bytes(content=prepared.provider_request_body_bytes),
         'NATIVE_ORIGINAL_PLAN_OR_BODY_CHANGED')
    if plan == current_plan:
        with control._successor_plan_context(repo_root=ROOT, authority=prepared.authority):
            success = control.load_successful_response(workspace_dir=path, plan=plan)
    else:
        with _original_runtime(path) as root:
            view = _captured_policy_view(root=root, prepared=prepared, plan=plan)
            # The identical current D-36 policy supplies nullable-observation
            # formatting. Requirement identity still comes only from the
            # validation-only original view, not from a new invocation plan.
            with control._successor_plan_context(repo_root=ROOT, authority=prepared.authority):
                success = control.load_successful_response(workspace_dir=path, plan=plan, _historical_view=view)
    expected = _acceptor(request, path)(prepared=prepared, plan=plan,
                                       response_body=success['response_body'])
    revalidation = revalidation_receipt(prepared=prepared, plan=plan,
        original=success['acceptance_receipt'], expected=expected)
    return {'plan': plan, 'success': success, 'revalidation': revalidation}
