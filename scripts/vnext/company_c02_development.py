"""Explicit company handoff of development-only C02 answers, never Results.

SEC originals stay in the separately admitted company source. This packet is
enrolled by the preparer and can only create/replay pending review material.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

from .canonical import canonical_json_bytes, content_hash, strict_json_file
from .company_handoff import external, binding, locked_company, recover_import, _atomic_json
from .company_source_authority import need, require_company

TRUST_VARIABLE = 'SEC_METRICS_C02_REVIEW_TRUST_ROOT'
PACKET_FILE = 'company-c02-review-input.json'
MEMBERS = frozenset({'request-body.bin', 'response.bin', 'review-context.json',
    'review.md', 'records.jsonl', 'processing/c02/image-metadata.json'})


def _members(root, expected, extra=()):
    need(not any(p.is_symlink() for p in root.rglob('*')), 'COMPANY_C02_REVIEW_ALIAS')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    need(actual == set(expected) | set(extra), 'COMPANY_C02_REVIEW_MEMBER_SET_CHANGED')
    for name, wanted in expected.items():
        need(name in MEMBERS and binding(root/name) == wanted,
             'COMPANY_C02_REVIEW_BYTES_CHANGED:'+name)


def export_review_input(*, assessment_root, data_root, output_root, trust_root,
                        company_id, expected_candidate_hash, expected_review_unit_hash):
    """Preparer authenticates the original native identities before enrollment."""
    from .c02_image_model_processing import read_image_development_assessment
    source, output, trust = map(external, (assessment_root, output_root, trust_root))
    need(not output.exists(), 'COMPANY_C02_REVIEW_OUTPUT_EXISTS')
    need(all(a != b and a not in b.parents and b not in a.parents for a, b in
             ((source, output), (source, trust), (output, trust))),
         'COMPANY_C02_REVIEW_ROOTS_OVERLAP')
    out = read_image_development_assessment(directory=source, data_root=data_root,
        company_id=company_id, expected_candidate_hash=expected_candidate_hash,
        expected_review_unit_hash=expected_review_unit_hash)
    files = {name: binding(source/name) for name in sorted(MEMBERS)}
    _members(source, files)
    p = out['processing']
    meta = {'record_type': 'COMPANY_C02_DEVELOPMENT_INPUT_V1', 'company_id': company_id,
        'metric_id': 'C02', 'origin': p['origin'], 'policy': p['policy'],
        'original_candidate_hash': expected_candidate_hash,
        'original_review_unit_hash': expected_review_unit_hash,
        'request_sha256': p['request_sha256'], 'response_sha256': p['response_sha256'],
        'source_sha256': p['source_sha256'], 'target': p['annual_target'], 'files': files,
        'new_call_authority': False, 'semantic_acceptance': False, 'production_authorized': False}
    meta['processing_id'] = content_hash(value=meta)
    output.mkdir(parents=True)
    for name in sorted(MEMBERS):
        (output/name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/name, output/name)
    _members(output, files)
    _atomic_json(output/PACKET_FILE, meta)
    trust.mkdir(parents=True, exist_ok=True)
    from sec_http import write_immutable_bytes
    write_immutable_bytes(path=trust/(meta['processing_id'][7:]+'.json'),
                          content=canonical_json_bytes(value=meta))
    return {'status': 'DEVELOPMENT_REVIEW_EXPORTED', 'processing_id': meta['processing_id'],
            'original_candidate_hash': expected_candidate_hash, 'new_business_calls': [0, 0, 0]}


def authenticate_review_input(*, packet_root, company_id):
    packet = external(packet_root)
    need(os.environ.get(TRUST_VARIABLE), 'COMPANY_C02_REVIEW_TRUST_REQUIRED')
    trust = external(os.environ[TRUST_VARIABLE])
    need(packet != trust and packet not in trust.parents and trust not in packet.parents,
         'COMPANY_C02_REVIEW_TRUST_OVERLAP')
    meta = strict_json_file(path=packet/PACKET_FILE)
    identity = meta.get('processing_id', '')
    need(identity == content_hash(value={k: v for k, v in meta.items() if k != 'processing_id'}),
         'COMPANY_C02_REVIEW_ID_CHANGED')
    trust_file = trust/(identity[7:]+'.json')
    need(not trust_file.is_symlink() and strict_json_file(path=trust_file) == meta,
         'COMPANY_C02_REVIEW_NOT_TRUSTED')
    need(meta['record_type'] == 'COMPANY_C02_DEVELOPMENT_INPUT_V1'
         and meta['company_id'] == company_id and meta['metric_id'] == 'C02'
         and meta['origin'] in {'DEVELOPMENT_MODEL', 'RECORDED_PROGRAM_TEST'}
         and meta['new_call_authority'] is False and meta['semantic_acceptance'] is False
         and meta['production_authorized'] is False, 'COMPANY_C02_REVIEW_SCOPE_OR_AUTHORITY')
    need(set(meta['files']) == MEMBERS, 'COMPANY_C02_REVIEW_MEMBER_SET_CHANGED')
    _members(packet, meta['files'], (PACKET_FILE,))
    return meta


def _runtime():
    from .normal_run_v3 import REQUIREMENT_ID
    from .normal_source_authority import ROOT
    from .requirements import load_requirement_snapshot
    from .requirement_profile_v1 import validate_execution_authority
    need(REQUIREMENT_ID == 'issue_54_v1', 'COMPANY_C02_REVIEW_INSTALLED_ORDINARY_RUNTIME_REQUIRED')
    requirement = load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    validate_execution_authority(repo_root=ROOT, requirement=requirement)
    return ROOT, requirement


def import_review(*, state_root, company_id, packet_root):
    """Use actual installed input/mapper; preserve old proposals and native Runs."""
    from .c02_image_model_processing import save_image_development_assessment
    from .company_result_view import save_execution, build_company_view
    with locked_company(state_root) as root:
        current = recover_import(root)
        need(current and current['company_id'] == company_id, 'COMPANY_C02_REVIEW_SOURCE_REQUIRED')
        source = root/'source'
        admission = require_company(source_root=source, company_id=company_id)
        need('C02' in admission['metric_ids'], 'COMPANY_C02_REVIEW_OUTSIDE_SOURCE_SCOPE')
        program, requirement = _runtime()
        packet = external(packet_root)
        meta = authenticate_review_input(packet_root=packet, company_id=company_id)
        key = content_hash(value={'processing_id': meta['processing_id'],
            'checkpoint_id': current['checkpoint_id'],
            'requirement_closure_hash': requirement['requirement_closure_hash']})
        work = root/'development/C02'/key[7:]
        if (work/'receipt.json').is_file():
            receipt, _ = replay_review(work=work, source=source, company_id=company_id)
        else:
            work.mkdir(parents=True, exist_ok=True)
            if not (work/'input').exists():
                staged = work/'input.preparing'
                if staged.exists(): shutil.rmtree(staged)
                shutil.copytree(packet, staged)
                authenticate_review_input(packet_root=staged, company_id=company_id)
                os.rename(staged, work/'input')
            authenticate_review_input(packet_root=work/'input', company_id=company_id)
            original = strict_json_file(path=work/'input/processing/c02/image-metadata.json')
            need(original['source_sha256'] == meta['source_sha256'], 'COMPANY_C02_REVIEW_SOURCE_CHANGED')
            out = save_image_development_assessment(directory=work/'pending', data_root=source,
                company_id=company_id, task_text=original['task_text'],
                request_body=(work/'input/request-body.bin').read_bytes(),
                response_body=(work/'input/response.bin').read_bytes(),
                expected_request_sha256=meta['request_sha256'],
                expected_response_sha256=meta['response_sha256'], origin=meta['origin'])
            need(out['processing']['source_sha256'] == meta['source_sha256']
                 and out['processing']['annual_target'] == meta['target'],
                 'COMPANY_C02_REVIEW_SOURCE_OR_TARGET_CHANGED')
            receipt = {'record_type': 'COMPANY_C02_PENDING_REVIEW_V1', 'company_id': company_id,
                'metric_id': 'C02', 'processing_id': meta['processing_id'],
                'source_checkpoint_id': current['checkpoint_id'], 'target': meta['target'],
                'requirement_id': requirement['requirement_id'],
                'requirement_closure_hash': requirement['requirement_closure_hash'],
                'runtime_root': str(program), 'original_candidate_hash': meta['original_candidate_hash'],
                'original_review_unit_hash': meta['original_review_unit_hash'],
                'candidate_hash': out['records'][2]['candidate_hash'],
                'review_unit_hash': out['records'][5]['review_unit_hash'],
                'status': 'REVIEW_REQUIRED', 'semantic_acceptance': False,
                'business_metric_completed': False, 'new_business_calls': [0, 0, 0]}
            receipt['review_id'] = content_hash(value=receipt)
            _atomic_json(work/'receipt.json', receipt)
        require_company(source_root=source, company_id=company_id)
        report = save_execution(root=root, report={'record_type': 'COMPANY_COMPUTATION_REFERENCES_V1',
            'company_id': company_id, 'source_root': str(source),
            'source_checkpoint_id': current['checkpoint_id'], 'metric_ids': ['C02'],
            'period_request': {'report_end': meta['target']['period_end'],
                               'fiscal_year': meta['target'].get('fiscal_year')},
            'runtime_root': str(program), 'metrics': [{'metric_id': 'C02',
                'status': 'REVIEW_REQUIRED', 'development_review_id': receipt['review_id'],
                'business_metric_completed': False}],
            'new_business_calls': {'provider': 0, 'paid': 0, 'sec': 0}, 'production_authorized': False})
        _atomic_json(root/'company-results.json', build_company_view(
            root=root, company_id=company_id, current=current))
        return {**report, 'review_id': receipt['review_id'], 'candidate_hash': receipt['candidate_hash']}


def replay_review(*, work, source, company_id):
    """Independent read reauthenticates SEC, trust, native files and creator closure."""
    from .c02_image_model_processing import read_image_development_assessment
    work = external(work)
    expected = {'input/'+name for name in (*MEMBERS, PACKET_FILE)} | {'pending/'+name for name in MEMBERS} | {'receipt.json'}
    need(not any(p.is_symlink() for p in work.rglob('*'))
         and {p.relative_to(work).as_posix() for p in work.rglob('*') if p.is_file()} == expected,
         'COMPANY_C02_REVIEW_SAVED_MEMBER_SET_CHANGED')
    receipt = strict_json_file(path=work/'receipt.json')
    need(receipt['review_id'] == content_hash(value={k: v for k, v in receipt.items() if k != 'review_id'})
         and receipt['company_id'] == company_id and receipt['metric_id'] == 'C02'
         and receipt['status'] == 'REVIEW_REQUIRED' and receipt['semantic_acceptance'] is False
         and receipt['business_metric_completed'] is False
         and receipt['new_business_calls'] == [0, 0, 0], 'COMPANY_C02_REVIEW_RECEIPT_CHANGED')
    meta = authenticate_review_input(packet_root=work/'input', company_id=company_id)
    admission = require_company(source_root=source, company_id=company_id)
    program, requirement = _runtime()
    need(receipt['source_checkpoint_id'] == admission['checkpoint_id']
         and receipt['processing_id'] == meta['processing_id']
         and receipt['original_candidate_hash'] == meta['original_candidate_hash']
         and receipt['original_review_unit_hash'] == meta['original_review_unit_hash']
         and receipt['requirement_closure_hash'] == requirement['requirement_closure_hash']
         and receipt['requirement_id'] == requirement['requirement_id']
         and receipt['runtime_root'] == str(program), 'COMPANY_C02_REVIEW_CREATOR_OR_SOURCE_CHANGED')
    out = read_image_development_assessment(directory=work/'pending', data_root=source,
        company_id=company_id, expected_candidate_hash=receipt['candidate_hash'],
        expected_review_unit_hash=receipt['review_unit_hash'])
    need(out['request_body'] == (work/'input/request-body.bin').read_bytes()
         and out['response_body'] == (work/'input/response.bin').read_bytes()
         and out['processing']['source_sha256'] == meta['source_sha256']
         and out['processing']['annual_target'] == receipt['target'] == meta['target'],
         'COMPANY_C02_REVIEW_WIRE_OR_TARGET_CHANGED')
    return receipt, out


def replay_in_creator(*, root, entry, runtime_roots):
    from git_workspace import first_symlink_in_path
    program = Path(entry['runtime_root'])
    need(program.is_absolute() and first_symlink_in_path(path=program) is None,
         'COMPANY_C02_REVIEW_RUNTIME_ALIAS')
    need(program in [Path(p) for p in runtime_roots], 'COMPANY_C02_REVIEW_FIXED_RUNTIME_REQUIRED')
    work = external(entry['work_root'])
    need(root in work.parents, 'COMPANY_C02_REVIEW_STATE_OVERLAP')
    source = root/'versions'/entry['source_checkpoint_id'][7:]
    before = {p.relative_to(work).as_posix(): binding(p) for p in work.rglob('*') if p.is_file()}
    child = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('company_c02_development_read.py')),
        str(program), str(work), str(source), entry['company_id']], capture_output=True, text=True,
        cwd=work, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    need(child.returncode == 0, 'COMPANY_C02_REVIEW_REPLAY_FAILED:'+child.stderr[-1500:])
    from .canonical import strict_json_loads
    result = strict_json_loads(text=child.stdout)
    need(result['review_id'] == entry['development_review_id'], 'COMPANY_C02_REVIEW_ID_CHANGED')
    after = {p.relative_to(work).as_posix(): binding(p) for p in work.rglob('*') if p.is_file()}
    need(before == after, 'COMPANY_C02_REVIEW_CHANGED_DURING_REPLAY')
    result['files'] = after
    return result
