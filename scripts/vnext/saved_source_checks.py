"""Ordinary saved-input checks for the trusted internal runtime.

No creator journal or Requirement ancestor is consulted. This checks actual
request history/body/header identity; it neither sends a request nor creates
new acquisition or model credit. Business consumers still verify the company,
filing, period, units, source scope and calculation.
"""
from pathlib import Path

from sec_http import parse_request_log_rows, request_log_attempt_id
from sec_http import validate_request_log_manifest, validate_official_sec_url
from .canonical import content_hash
from .request_bindings import validate_request_attempt_binding


class SavedSourceCheckError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise SavedSourceCheckError(reason)


def verify_saved_inputs(*, data_root, proofs):
    """Check selected saved requests and retain current failed observations."""
    root = Path(data_root)
    _need(type(proofs) is list and bool(proofs), 'SAVED_INPUT_PROOFS_REQUIRED')
    log = root/'evidence/requests_log.csv'
    validate_request_log_manifest(log_path=log)
    rows = parse_request_log_rows(text=log.read_text(encoding='utf-8'))
    latest = {}
    for index,row in enumerate(rows):
        if row['method'] == 'GET':
            latest[row['source_url']] = (index,row)
    checked = []
    recorded = False
    for proof in proofs:
        validate_official_sec_url(url=proof['source_url'])
        current = latest.get(proof['source_url'])
        _need(current is not None, 'SAVED_INPUT_CURRENT_REQUEST_MISSING')
        _, row = current
        _need(row['status_code'] == '200' and not row['error'],
              'SAVED_INPUT_LATEST_SOURCE_REQUEST_FAILED:'+proof['source_url'])
        _need(row['content_sha256'] == proof['content_sha256'],
              'SAVED_INPUT_SELECTED_BYTES_ARE_NOT_CURRENT:'+proof['source_url'])
        rebuilt = validate_request_attempt_binding(repo_root=root,source_url=proof['source_url'],
            content_sha256=proof['content_sha256'],accession=proof['accession'],
            document_name=proof['document_name'],request_attempt_id=proof['request_attempt_id'],
            require_immutable=proof['request_locator_kind']=='IMMUTABLE_ATTEMPT')
        expected = {k:v for k,v in proof.items() if k not in
                    {'source_url','accession','document_name','content_sha256'}}
        _need(rebuilt == expected, 'SAVED_INPUT_REQUEST_PROOF_DIFFERS')
        checked.append(proof['request_attempt_id'])
        recorded = recorded or 'RECORDED' in row.get('purpose','').upper()
    return {'record_type':'VERIFIED_SAVED_SOURCE_INPUTS',
        'source_manifest_sha256':content_hash(value={'checked_proofs':proofs})[7:],
        'request_attempt_ids':checked,
        'source_credit':'RECORDED_TEST_ONLY' if recorded else 'SAVED_SOURCE_BYTES_AND_REQUESTS_CHECKED',
        'real_sec_credit':False,'new_business_calls':{'provider':0,'paid':0,'sec':0},
        'production_authorized':False}
