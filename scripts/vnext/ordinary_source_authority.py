"""Current source admission through installed execution history.

The historical baseline is unchanged. Recorded append sessions can be admitted
only by their creating process into the installed private journal. A data
directory cannot enroll its own ledger. Portable replay trusts the checkpoint
installed with the runtime, as it already trusts that runtime and its baseline;
it does not protect an operator who replaces both code and execution history.
No recorded response acquires live SEC or publication credit.
"""
from pathlib import Path

from git_workspace import first_symlink_in_path
from sec_http import parse_request_log_rows,request_log_prefix_bytes,request_log_attempt_id,validate_request_log_manifest
from .batch_workflow import validate_request_attempt_binding
from .canonical import canonical_json_bytes,content_hash,sha256_bytes,sha256_file,strict_json_file
from .normal_source_authority import (ROOT,MANIFEST_PATH,_baseline_file,_git_blob_id,
                                      verify_saved_source_proofs)
from .sources import resolve_repository_file

EXPORT_PATH='config/ordinary_source_checkpoint.json'


class OrdinarySourceAuthorityError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise OrdinarySourceAuthorityError(reason)


def _journal():
    path=ROOT/'.git/ordinary-source-authority/recorded'
    _need((ROOT/'.git').is_dir() and not (ROOT/'.git').is_symlink()
          and first_symlink_in_path(path=path) is None,'ORDINARY_SOURCE_TRUSTED_JOURNAL_REQUIRED')
    return path


def _immutable(path,value):
    from sec_http import write_immutable_bytes
    _need(first_symlink_in_path(path=path) is None,'ORDINARY_SOURCE_JOURNAL_ALIAS')
    write_immutable_bytes(path=path,content=canonical_json_bytes(value=value))


def _prefix(data_root,baseline):
    _baseline_file(data_root,'config/company_registry.csv',baseline)
    path=resolve_repository_file(repo_root=data_root,repo_relative_path='evidence/requests_log.csv')
    validate_request_log_manifest(log_path=path)
    raw=path.read_bytes();rows=parse_request_log_rows(text=raw.decode('utf-8'))
    # The reviewed whole-ledger byte identity, not a caller's claimed row count,
    # owns the boundary between history and the new session.
    size=baseline['files']['evidence/requests_log.csv']['size']
    prefix=raw[:size]
    _need(_git_blob_id(prefix)==baseline['files']['evidence/requests_log.csv']['git_blob_id'],
          'ORDINARY_SOURCE_TRUSTED_PREFIX_CHANGED')
    old_rows=parse_request_log_rows(text=prefix.decode('utf-8'))
    _need(request_log_prefix_bytes(text=raw.decode('utf-8'),row_count=len(old_rows))==prefix,
          'ORDINARY_SOURCE_PREFIX_ROW_BOUNDARY_CHANGED')
    return raw,rows,old_rows


def _proof(data_root,proof):
    binding=validate_request_attempt_binding(repo_root=data_root,source_url=proof['source_url'],
        content_sha256=proof['content_sha256'],accession=proof['accession'],document_name=proof['document_name'],
        request_attempt_id=proof['request_attempt_id'],require_immutable=proof['request_locator_kind']=='IMMUTABLE_ATTEMPT')
    _need(binding=={k:v for k,v in proof.items() if k not in {'source_url','accession','document_name','content_sha256'}},
          'ORDINARY_SOURCE_REQUEST_PROOF_CHANGED')


def _validate_checkpoint(data_root,checkpoint,baseline):
    _need(checkpoint.get('record_type')=='RECORDED_ORDINARY_SOURCE_CHECKPOINT'
          and checkpoint.get('schema_version')==1 and checkpoint.get('source_credit')=='RECORDED_TEST_ONLY'
          and checkpoint.get('real_sec_credit') is False and checkpoint.get('production_authorized') is False
          and checkpoint.get('checkpoint_id')==content_hash(value={k:v for k,v in checkpoint.items() if k!='checkpoint_id'})
          and checkpoint['baseline_manifest_sha256']==sha256_file(path=ROOT/MANIFEST_PATH),
          'ORDINARY_SOURCE_CHECKPOINT_INVALID')
    raw,rows,old_rows=_prefix(data_root,baseline)
    _need(checkpoint['ledger_sha256']==sha256_bytes(content=raw)
          and checkpoint['baseline_row_count']==len(old_rows),'ORDINARY_SOURCE_CHECKPOINT_LEDGER_CHANGED')
    header=checkpoint['session'];intents=checkpoint['intents'];terminals=checkpoint['terminals']
    _need(header['record_id']==content_hash(value={k:v for k,v in header.items() if k!='record_id'})
          and header['mode']=='RECORDED_TEST_ONLY' and header['real_sec_credit'] is False
          and header['production_authorized'] is False and len(intents)==len(terminals)
          and 0<len(terminals)<=header['max_responses']
          and len(rows)==len(old_rows)+len(terminals),'ORDINARY_SOURCE_CHECKPOINT_SESSION_CHANGED')
    baseline_ids={request_log_attempt_id(row_index=i,row=r) for i,r in enumerate(old_rows)}
    admitted={}
    for ordinal,(intent,terminal) in enumerate(zip(intents,terminals),1):
        for record in (intent,terminal):
            _need(record['record_id']==content_hash(value={k:v for k,v in record.items() if k!='record_id'}),
                  'ORDINARY_SOURCE_CHECKPOINT_RECORD_CHANGED')
        row=rows[len(old_rows)+ordinal-1];origin=intent['origin_proof']
        _need(intent['session_id']==header['record_id'] and intent['ordinal']==ordinal and intent['retry']==0
              and intent['mode']==terminal['mode']=='RECORDED_TEST_ONLY'
              and terminal['intent_id']==intent['record_id'] and terminal['ledger_row']==row
              and terminal['status']=='SUCCEEDED' and terminal['actual_sec_egress_count']==0
              and terminal['real_sec_credit'] is False,'ORDINARY_SOURCE_UNSUCCESSFUL_OR_UNBOUND_TERMINAL')
        _need(origin['request_attempt_id'] in baseline_ids and intent['url']==origin['source_url']==row['source_url']
              and row['content_sha256']==origin['content_sha256'],'ORDINARY_SOURCE_RECORDED_ORIGIN_CHANGED')
        for key in ('request_repo_relative_path','request_headers_repo_relative_path'):
            _baseline_file(data_root,origin[key],baseline)
        _proof(data_root,origin)
        attempt=request_log_attempt_id(row_index=len(old_rows)+ordinal-1,row=row)
        binding=validate_request_attempt_binding(repo_root=data_root,source_url=row['source_url'],
            content_sha256=row['content_sha256'],accession=origin['accession'],document_name=row['document_name'],
            request_attempt_id=attempt,require_immutable=True)
        admitted[attempt]={'origin':origin,'binding':binding}
    return raw,baseline_ids,admitted


def register_recorded_session(*,session):
    """Called by the actual creator, not with caller-supplied receipt JSON."""
    from .ordinary_source_session import RecordedSourceSession
    _need(type(session) is RecordedSourceSession,'ORDINARY_SOURCE_OWNED_SESSION_REQUIRED')
    rows,terminals=session._check()
    _need(terminals and all(t['status']=='SUCCEEDED' for t in terminals),'ORDINARY_SOURCE_SUCCESSFUL_SESSION_REQUIRED')
    intents=[strict_json_file(path=p) for p in sorted((session.journal_root/'intents').glob('*.json'))]
    body={'record_type':'RECORDED_ORDINARY_SOURCE_CHECKPOINT','schema_version':1,
        'baseline_manifest_sha256':sha256_file(path=ROOT/MANIFEST_PATH),
        'baseline_row_count':len(session.prefix_rows),
        'ledger_sha256':sha256_file(path=session.data_root/'evidence/requests_log.csv'),
        'session':session.header,'intents':intents,'terminals':terminals,
        'source_credit':'RECORDED_TEST_ONLY','real_sec_credit':False,'production_authorized':False}
    checkpoint={**body,'checkpoint_id':content_hash(value=body)}
    _validate_checkpoint(session.data_root,checkpoint,strict_json_file(path=ROOT/MANIFEST_PATH))
    # Fixed installed trust root. A sidecar in session.data_root cannot replace
    # this journal or nominate a different journal location.
    _immutable(_journal()/(body['ledger_sha256']+'.json'),checkpoint)
    _need(session._check()==(rows,terminals),'ORDINARY_SOURCE_SESSION_CHANGED_DURING_REGISTRATION')
    return checkpoint


def _trusted_checkpoint(data_root):
    ledger=sha256_file(path=resolve_repository_file(repo_root=data_root,repo_relative_path='evidence/requests_log.csv'))
    if (ROOT/'.git').exists():
        path=_journal()/(ledger+'.json')
        _need(path.is_file(),'ORDINARY_SOURCE_UNREGISTERED_LEDGER')
    else:
        path=resolve_repository_file(repo_root=ROOT,repo_relative_path=EXPORT_PATH)
    checkpoint=strict_json_file(path=path)
    _need(checkpoint['ledger_sha256']==ledger,'ORDINARY_SOURCE_INSTALLED_CHECKPOINT_DIFFERS')
    exported=data_root/EXPORT_PATH
    if exported.exists():
        _need(strict_json_file(path=resolve_repository_file(repo_root=data_root,repo_relative_path=EXPORT_PATH))==checkpoint,
              'ORDINARY_SOURCE_IMPORTED_CHECKPOINT_CHANGED')
    return checkpoint


def verify_ordinary_source_proofs(*,data_root:Path,proofs:list):
    baseline=strict_json_file(path=ROOT/MANIFEST_PATH)
    ledger=resolve_repository_file(repo_root=data_root,repo_relative_path='evidence/requests_log.csv').read_bytes()
    original=baseline['files']['evidence/requests_log.csv']
    if len(ledger)==original['size'] and _git_blob_id(ledger)==original['git_blob_id']:
        return verify_saved_source_proofs(data_root=data_root,proofs=proofs)
    _need(type(proofs) is list and proofs,'ORDINARY_SOURCE_PROOFS_REQUIRED')
    checkpoint=_trusted_checkpoint(data_root)
    _,old_ids,admitted=_validate_checkpoint(data_root,checkpoint,baseline)
    for proof in proofs:
        _need(proof['request_attempt_id'] in old_ids or proof['request_attempt_id'] in admitted,
              'ORDINARY_SOURCE_UNADMITTED_ATTEMPT')
        if proof['request_attempt_id'] in old_ids:
            for key in ('request_repo_relative_path','request_headers_repo_relative_path'):_baseline_file(data_root,proof[key],baseline)
        _proof(data_root,proof)
    return {'record_type':'VERIFIED_ORDINARY_RECORDED_INPUTS','trusted_baseline_commit':baseline['baseline_commit'],
        'source_manifest_sha256':sha256_bytes(content=canonical_json_bytes(value=checkpoint)),
        'checkpoint_id':checkpoint['checkpoint_id'],'request_attempt_ids':[p['request_attempt_id'] for p in proofs],
        'source_credit':'RECORDED_TEST_ONLY','real_sec_credit':False,
        'new_business_calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}


def checkpoint_installation(*,source_root):
    """Return the trusted checkpoint and all its data dependencies for copying."""
    baseline=strict_json_file(path=ROOT/MANIFEST_PATH)
    ledger=(source_root/'evidence/requests_log.csv').read_bytes();entry=baseline['files']['evidence/requests_log.csv']
    if len(ledger)==entry['size'] and _git_blob_id(ledger)==entry['git_blob_id']:return None,set()
    checkpoint=_trusted_checkpoint(source_root)
    _,_,admitted=_validate_checkpoint(source_root,checkpoint,baseline);paths=set()
    for item in admitted.values():
        for proof in [item['origin'],item['binding']]:
            paths.update(proof[k] for k in ['request_repo_relative_path','request_headers_repo_relative_path'])
    return checkpoint,paths


def require_installed_checkpoint(*,data_root,admission):
    """A Run must carry its source history into a portable data installation."""
    if admission['source_credit']!='RECORDED_TEST_ONLY':return
    _need((data_root/EXPORT_PATH).is_file(),'ORDINARY_SOURCE_CHECKPOINT_NOT_INSTALLED')
    checkpoint=_trusted_checkpoint(data_root)
    _need(checkpoint['checkpoint_id']==admission['checkpoint_id'],'ORDINARY_SOURCE_RUN_CHECKPOINT_CHANGED')
