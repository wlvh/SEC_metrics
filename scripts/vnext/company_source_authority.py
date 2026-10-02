"""Company source admission after full-history verification by the preparer.

The package never registers itself. A separate installed trust directory owns
the exact admission record. Original ledger rows and checkpoints are retained;
only the company source bytes are required in the computing environment.
"""
import os
from pathlib import Path

from sec_http import parse_request_log_rows, request_log_attempt_id
from sec_http import validate_request_log_manifest
from .canonical import content_hash, sha256_file, strict_json_file
from .normal_source_authority import ROOT, MANIFEST_PATH, _baseline_file
from .sources import resolve_repository_file

RECORD_TYPE = 'COMPANY_SOURCE_ADMISSION_V1'
EXPORT_PATH = 'config/ordinary_source_checkpoint.json'
TRUST_VARIABLE = 'SEC_METRICS_SOURCE_TRUST_ROOT'


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def trusted_checkpoint(data_root):
    """Read an exact independently installed record; do not enroll input JSON."""
    exported = strict_json_file(path=resolve_repository_file(
        repo_root=data_root, repo_relative_path=EXPORT_PATH))
    need(exported.get('record_type') == RECORD_TYPE,
         'COMPANY_SOURCE_ADMISSION_REQUIRED')
    location = os.environ.get(TRUST_VARIABLE)
    need(bool(location), 'COMPANY_SOURCE_TRUST_ROOT_REQUIRED')
    from git_workspace import first_symlink_in_path
    root = Path(location)
    need(root.is_absolute() and first_symlink_in_path(path=root) is None,
         'COMPANY_SOURCE_TRUST_ROOT_ALIAS')
    root = root.resolve()
    data = Path(data_root).resolve()
    need(root != data and root not in data.parents and data not in root.parents,
         'COMPANY_SOURCE_TRUST_MUST_BE_SEPARATE')
    identity = exported['checkpoint_id']
    need(type(identity) is str and identity.startswith('sha256:')
         and len(identity) == 71
         and all(c in '0123456789abcdef' for c in identity[7:]),
         'COMPANY_SOURCE_ADMISSION_ID_INVALID')
    installed = strict_json_file(path=resolve_repository_file(
        repo_root=root, repo_relative_path=identity[7:] + '.json'))
    need(installed == exported, 'COMPANY_SOURCE_NOT_IN_INSTALLED_TRUST')
    return installed


def validate_checkpoint(data_root, checkpoint, baseline):
    """Recheck the whole ledger and every retained byte, then admit scoped IDs."""
    need(checkpoint == trusted_checkpoint(data_root),
         'COMPANY_SOURCE_TRUST_RECORD_CHANGED')
    need(checkpoint['checkpoint_id'] == content_hash(value={
        k: v for k, v in checkpoint.items() if k != 'checkpoint_id'}),
         'COMPANY_SOURCE_ADMISSION_CHANGED')
    need(checkpoint['schema_version'] == 1
         and checkpoint['production_authorized'] is False
         and checkpoint['baseline_manifest_sha256'] == sha256_file(path=ROOT/MANIFEST_PATH),
         'COMPANY_SOURCE_BASELINE_OR_MODE_CHANGED')
    from .ordinary_source_authority import _prefix, _proof
    raw, rows, old_rows = _prefix(data_root, baseline)
    log = resolve_repository_file(repo_root=data_root,
                                  repo_relative_path='evidence/requests_log.csv')
    validate_request_log_manifest(log_path=log)
    need(sha256_file(path=log) == checkpoint['ledger_sha256'],
         'COMPANY_SOURCE_LEDGER_CHANGED')
    urls = checkpoint['source_urls']
    need(type(urls) is list and urls == sorted(set(urls)) and urls,
         'COMPANY_SOURCE_URL_SCOPE_INVALID')
    for relative, binding in checkpoint['files'].items():
        path = resolve_repository_file(repo_root=data_root,
                                       repo_relative_path=relative)
        need({'sha256': sha256_file(path=path), 'size': path.stat().st_size} == binding,
             'COMPANY_SOURCE_BYTES_CHANGED:' + relative)
    original = checkpoint['original_checkpoint']
    old_ids = {request_log_attempt_id(row_index=i, row=row)
               for i, row in enumerate(old_rows)}
    admitted = {}
    # The independently installed record was minted only after the original
    # validator checked every capture in a full preparation environment.
    # Recheck proofs that the computing company may actually consume.
    if original is not None:
        need(original['ledger_sha256'] == checkpoint['ledger_sha256']
             and original['checkpoint_id'] == checkpoint['original_checkpoint_id']
             and original['real_sec_credit'] is checkpoint['real_sec_credit']
             and original['source_credit'] == checkpoint['source_credit'],
             'COMPANY_SOURCE_ORIGINAL_HISTORY_CHANGED')
        if original['record_type'] == 'ORDINARY_SEC_ACQUISITION_CHECKPOINT':
            for capture in original['captures']:
                receipt = capture['receipt']
                proof = receipt['proof']
                if proof is not None and proof['source_url'] in urls:
                    need(receipt['company_id'] == checkpoint['company_id'],
                         'COMPANY_SOURCE_CAPTURE_BELONGS_TO_ANOTHER_COMPANY')
                    _proof(data_root, proof)
                    admitted[proof['request_attempt_id']] = {
                        'origin': proof, 'binding': proof}
        else:
            need(original['record_type'] == 'RECORDED_ORDINARY_SOURCE_CHECKPOINT',
                 'COMPANY_SOURCE_CHECKPOINT_KIND_UNSUPPORTED')
            for intent, terminal in zip(original['intents'], original['terminals']):
                if intent['url'] not in urls:
                    continue
                origin = intent['origin_proof']
                for key in ('request_repo_relative_path', 'request_headers_repo_relative_path'):
                    _baseline_file(data_root, origin[key], baseline)
                _proof(data_root, origin)
                row = terminal['ledger_row']
                indices = [i for i, value in enumerate(rows) if value == row]
                need(len(indices) == 1, 'COMPANY_SOURCE_RECORDED_ROW_AMBIGUOUS')
                from .batch_workflow import validate_request_attempt_binding
                proof = validate_request_attempt_binding(
                    repo_root=data_root, source_url=row['source_url'],
                    content_sha256=row['content_sha256'], accession=origin['accession'],
                    document_name=row['document_name'],
                    request_attempt_id=request_log_attempt_id(row_index=indices[0], row=row),
                    require_immutable=True)
                admitted[proof['request_attempt_id']] = {'origin': origin, 'binding': proof}
    else:
        need(len(rows) == len(old_rows)
             and checkpoint['original_checkpoint_id'] is None
             and checkpoint['real_sec_credit'] is False
             and checkpoint['source_credit'] == 'PREEXISTING_SAVED_ACQUISITIONS_ONLY',
             'COMPANY_SOURCE_BASELINE_HISTORY_CHANGED')
    # Every usable target row must carry its declared body/header pair,
    # including prior attempts with the same response identity. Failed rows
    # remain in the unchanged ledger; consumers retain latest-failure rules.
    for row in rows:
        if row['source_url'] in urls:
            for field in ('repo_relative_path', 'headers_repo_relative_path'):
                relative = row[field]
                if relative:
                    need(relative in checkpoint['files']
                         or row['status_code'] == '0',
                         'COMPANY_SOURCE_DECLARED_LOCATOR_NOT_CARRIED:' + relative)
    return raw, old_ids, admitted


def require_company(*, source_root, company_id):
    """Guard the requested company before source discovery or processing."""
    checkpoint = trusted_checkpoint(source_root)
    need(checkpoint['company_id'] == company_id, 'COMPANY_SOURCE_WRONG_COMPANY')
    baseline = strict_json_file(path=ROOT/MANIFEST_PATH)
    validate_checkpoint(source_root, checkpoint, baseline)
    return checkpoint
