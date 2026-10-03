"""Empty-history local adapter over the existing SEC capture and call ledger.

Only a newly installed issue_54_v4 runtime uses this adapter. Old capture code,
source baselines, grants and Run identities stay available in their old trees.
The operator's finite local invocation is not a production/model permission.
"""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import time

from .canonical import canonical_json_bytes, content_hash, sha256_file, strict_json_file
from .continuous_call_policy import need

REQUIREMENT_ID = 'issue_54_v4'
SEED = 'config/company_empty_source_seed'
MANIFEST = 'config/company_empty_source_baseline_v1.json'
ACQUISITION_TRUST = 'SEC_METRICS_ACQUISITION_TRUST_ROOT'


def install_empty_seed(program):
    """Create native empty CSV+integrity manifest, never copy financial data."""
    from sec_http import SecHttpClient
    from .normal_source_authority import _git_blob_id
    seed = program/SEED
    seed.mkdir(parents=True)
    registry = (program/'config/company_registry.csv').read_bytes()
    (seed/'config').mkdir()
    (seed/'config/company_registry.csv').write_bytes(registry)
    # Constructor writes only a native empty log; it performs no HTTP request.
    SecHttpClient(workdir=seed, config_path=program/'config/sec_config.json',
                  log_path=seed/'evidence/requests_log.csv')
    files = {p.relative_to(seed).as_posix(): {
        'git_blob_id': _git_blob_id(p.read_bytes()), 'size': p.stat().st_size}
        for p in seed.rglob('*') if p.is_file()}
    need(set(files) == {'config/company_registry.csv', 'evidence/requests_log.csv',
                        'evidence/requests_log_manifest.json'}, 'LOCAL_SEED_UNEXPECTED_FILE')
    manifest = {'record_type': 'TRUSTED_SAVED_SOURCE_BASELINE', 'schema_version': 1,
        'baseline_commit': 'EMPTY_NEW_TASK_HISTORY',
        'source_credit': 'PREEXISTING_SAVED_ACQUISITIONS_ONLY',
        'identity_basis': 'CODE_OWNED_EMPTY_LEDGER_NO_SAVED_SEC_ORIGINALS', 'files': files}
    (program/MANIFEST).write_bytes(canonical_json_bytes(value=manifest))


def patch_local_acquisition(program):
    """Narrow installation seams; the HTTP/capture/receipt algorithm is reused."""
    from .company_runtime_install import _replace
    originals = {}

    def replace(relative, old, new):
        path = program/relative
        originals.setdefault(relative, path.read_text())
        _replace(path, old, new)

    replace('scripts/vnext/normal_source_authority.py',
        'MANIFEST_PATH = "config/normal_candidate_sources_v1.json"',
        'MANIFEST_PATH = "'+MANIFEST+'"')
    capture = 'scripts/vnext/continuous_sec_acquisition.py'
    replace(capture, 'from .continuous_call_policy import REQUIREMENT_ID,need,load_delegation',
        'from .company_local_acquisition import REQUIREMENT_ID, need, load_delegation')
    replace(capture, 'def _journal():\n'
        '    from git_workspace import first_symlink_in_path\n'
        "    path=ROOT/'.git/ordinary-source-authority/acquired'\n"
        "    need((ROOT/'.git').is_dir() and first_symlink_in_path(path=path) is None,\n"
        "         'SEC_ACQUISITION_INSTALLED_JOURNAL_REQUIRED')\n"
        '    return path',
        'def _journal():\n'
        '    from .company_local_acquisition import acquisition_journal\n'
        '    return acquisition_journal()')
    replace(capture, '        for relative in baseline[\'files\']:\n'
        '            _baseline_file(ROOT,relative,baseline)\n'
        '            original=resolve_repository_file(repo_root=ROOT,repo_relative_path=relative)',
        '        for relative in baseline[\'files\']:\n'
        '            seed=ROOT/"'+SEED+'"\n'
        '            _baseline_file(seed,relative,baseline)\n'
        '            original=resolve_repository_file(repo_root=seed,repo_relative_path=relative)')
    replace(capture, "    processing_requirement=requirement['parent_snapshot']",
        '    processing_requirement=requirement')
    replace(capture, "    presentation_paths=set(processing_requirement['policy']['presentation_paths'])",
        '    from .company_local_acquisition import presentation_paths\n'
        '    presentation_paths=presentation_paths(processing_requirement)')
    replace('scripts/vnext/ordinary_source_authority.py',
        "        acquired=ROOT/'.git/ordinary-source-authority/acquired'/(ledger+'.json')",
        '        from .company_local_acquisition import acquisition_journal\n'
        "        acquired=acquisition_journal()/(ledger+'.json')")
    relative = 'config/sec_config.json'
    originals[relative] = (program/relative).read_text()
    cfg = strict_json_file(path=program/relative)
    cfg.update(rate_limit_per_sec=1, max_retries=0)
    (program/relative).write_bytes(canonical_json_bytes(value=cfg))
    files = (MANIFEST, *(SEED+'/'+p for p in ('config/company_registry.csv',
        'evidence/requests_log.csv', 'evidence/requests_log_manifest.json')))
    return originals, files


def load_delegation(*, requirement, online=False):
    # This adapter never reads/borrows the original #28 online budget grant.
    need(requirement['requirement_id'] == REQUIREMENT_ID,
         'LOCAL_ACQUISITION_FIXED_RUNTIME_REQUIRED')
    return {'delegation_url': 'https://github.com/wlvh/SEC_metrics/issues/54',
            'provider_paid_authorized': False}


def presentation_paths(requirement):
    """The native parent retains the ordinary presentation policy in V13."""
    cursor = requirement
    while cursor:
        if 'presentation_paths' in cursor.get('policy', {}):
            return set(cursor['policy']['presentation_paths'])
        cursor = cursor.get('parent_snapshot')
    raise ValueError('LOCAL_ORDINARY_PRESENTATION_POLICY_MISSING')


def acquisition_journal():
    from .company_handoff import external
    location = os.environ.get(ACQUISITION_TRUST)
    need(bool(location), 'LOCAL_ACQUISITION_TRUST_REQUIRED')
    return external(Path(location))


@contextmanager
def rate_scope():
    """One stable gate shared by local company commands under this Unix user.

    Other SEC clients must also coordinate their total rate with the operator.
    This does not allocate 10 requests/s separately to each company process.
    """
    from git_workspace import first_symlink_in_path
    root = Path('/tmp')/('sec-metrics-sec-rate-'+str(os.getuid()))
    need(first_symlink_in_path(path=root) is None, 'LOCAL_SEC_RATE_ALIAS')
    root.mkdir(mode=0o700, exist_ok=True)
    need(root.stat().st_uid == os.getuid(), 'LOCAL_SEC_RATE_OWNER_CHANGED')
    fd = os.open(root, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        stamp = root/'last-request.json'
        if stamp.exists():
            wait = 1 - (time.time() - float(strict_json_file(path=stamp)['at']))
            if wait > 0:
                time.sleep(min(wait, 1))
        from .company_handoff import _atomic_json
        _atomic_json(stamp, {'at': format(time.time(), '.6f')})
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


class RuleAuthority:
    """The existing capture archives this exact installed execution closure."""
    def __init__(self, requirement):
        self.requirement = requirement
        self._files = canonical_json_bytes(value=requirement['execution_authority']['files'])

    def _check(self):
        from .normal_source_authority import ROOT
        from .requirement_profile_v1 import validate_execution_authority
        validate_execution_authority(repo_root=ROOT, requirement=self.requirement)


def local_session(*, root, company_id, allowance, response=None, status=200):
    """New local namespace only; native ledger still owns every claim/terminal.

    A recorded namespace cannot be changed into LIVE or get a new allowance.
    A missing last terminal/removed claim keeps the original native stop rule.
    """
    from . import continuous_sec_acquisition as capture
    from . import continuous_call_ledger as calls
    from .normal_source_authority import ROOT
    from .requirements import load_requirement_snapshot
    from .company_handoff import external
    root = external(root)
    need(type(allowance) is int and 0 < allowance <= 120, 'LOCAL_SEC_ALLOWANCE_INVALID')
    requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    live = response is None
    body = {'record_type': 'CONTINUOUS_CALL_ALLOWANCE', 'root': str(root),
        'limits': [0, 0, allowance], 'company_id': company_id,
        'runtime_requirement_closure_hash': requirement['requirement_closure_hash'],
        'empty_baseline_sha256': sha256_file(path=ROOT/MANIFEST),
        'purposes': ['remaining_development_feasibility'],
        'execution_mode': 'LIVE' if live else 'RECORDED_TEST_ONLY',
        'delegation_url': 'https://github.com/wlvh/SEC_metrics/issues/54',
        'production_authorized': False}
    binding = {**body, 'binding_id': content_hash(value=body)}
    ledger = calls.CallLedger(factory=calls._FACTORY, root=root, binding=binding, live=live)

    class LocalSession(capture.SecAcquisitionSession):
        def __init__(self):
            self._factory = capture._FACTORY
            self.requirement = {**requirement, 'policy': {**requirement['policy'],
                'delegation_url': body['delegation_url']}}
            self.ledger = ledger
            self.authority = RuleAuthority(requirement)
            self.response, self.response_status = response, status
            self.data_root = root/'source-inputs'

        def _check(self):
            need(self._factory is capture._FACTORY and self.ledger.binding == binding
                 and self.data_root == root/'source-inputs', 'LOCAL_ACQUISITION_BINDING_CHANGED')
            self.authority._check()
            load_delegation(requirement=self.requirement)

        def capture(self, **kwargs):
            need(kwargs.get('company_id') == company_id
                 and kwargs.get('control_id') is None,
                 'LOCAL_ACQUISITION_COMPANY_OR_HISTORY_SCOPE_CHANGED')
            if live:
                with rate_scope():
                    return super().capture(**kwargs)
            return super().capture(**kwargs)

    return LocalSession()


def acquire_only(*, session, company_id, max_requests):
    """Follow the existing discovery graph without calling any calculator."""
    from .continuous_sec_acquisition import initialize_source_inputs
    from .normal_source_requirements import discover_saved_source_requirements, source_dependency_satisfied
    from sec_http import parse_request_log_rows, validate_request_log_manifest
    need(type(max_requests) is int and 0 <= max_requests <= 120, 'LOCAL_SEC_REQUEST_LIMIT_INVALID')
    with session.ledger.locked():
        before = session.ledger.snapshot()['counts']
        initialize_source_inputs(root=session.data_root, requirement=session.requirement)
    attempted, captures = set(), []
    log = session.data_root/'evidence/requests_log.csv'
    validate_request_log_manifest(log_path=log)
    latest = {r['source_url']: r for r in parse_request_log_rows(text=log.read_text())}
    failed = {u for u, r in latest.items() if r['status_code'] != '200' or r['error']}
    stop = None
    capture_error = False
    for _ in range(max_requests + 1):
        discovery = discover_saved_source_requirements(repo_root=session.data_root, company_id=company_id)
        pending = [r for r in discovery['requirements'] if r['source_url'] not in attempted | failed
            and r['saved_status'] != 'SAVED_SOURCE_BLOCKED'
            and (r['refresh_for_new_discovery'] or not source_dependency_satisfied(r))]
        if not pending:
            break
        if len(captures) == max_requests:
            stop = 'INVOCATION_SEC_LIMIT_REACHED'
            break
        item = pending[0]
        attempted.add(item['source_url'])
        try:
            result = session.capture(company_id=company_id, url=item['source_url'],
                refresh_metadata=item['refresh_for_new_discovery'])
        except Exception as error:
            stop = str(error)
            capture_error = True
            break
        captures.append({'source_url': item['source_url'], 'roles': item['roles'], 'result': result})
        if result['status'] != 'SUCCEEDED':
            failed.add(item['source_url'])
        if result['receipt']['stop_reason']:
            stop = result['receipt']['stop_reason']
            break
    with session.ledger.locked():
        after = session.ledger.snapshot()['counts']
    unresolved = [r for r in discovery['requirements'] if not source_dependency_satisfied(r)]
    return {'record_type': 'LOCAL_COMPANY_ACQUISITION_V1', 'company_id': company_id,
        'execution_mode': 'LIVE' if session.ledger.live else 'RECORDED_TEST_ONLY',
        'status': 'SOURCES_READY' if not unresolved and not discovery['limitations'] and not stop else 'SOURCES_PARTIAL',
        'source_root': str(session.data_root), 'captures': captures,
        'reused_source_urls': sorted(r['source_url'] for r in discovery['requirements']
            if source_dependency_satisfied(r) and r['source_url'] not in attempted),
        'unresolved': unresolved, 'discovery': discovery, 'stop_reason': stop,
        'calls': {'provider': 0, 'paid': 0, 'sec': (None if capture_error and after[2]-before[2] > len(captures)
            else sum(c['result']['calls'][2] for c in captures)) if session.ledger.live else 0},
        'charged_sec_claims': after[2]-before[2],
        'simulated_sec_claims': after[2]-before[2] if not session.ledger.live else 0,
        'metric_executed': False, 'production_authorized': False}
