"""B06 source admission at a trusted execution boundary, separate from inputs.

The installed checkout and its private execution journal are trusted. A caller
may supply data files, not journal entries. This is not protection against an
operator who can replace both the installed code and its execution history.
"""
from pathlib import Path
import os, subprocess
from datetime import datetime, timezone
from .canonical import canonical_json_bytes, content_hash, sha256_bytes, sha256_file, strict_json_file
from .r5_b06_structured import need
from git_workspace import sanitized_git_environment, first_symlink_in_path

ROOT = Path(__file__).resolve().parents[2]
POLICY = 'config/b06_new_source_v1.json'


def _git(args, **kwargs):
    env=sanitized_git_environment();env['GIT_NO_REPLACE_OBJECTS']='1'
    return subprocess.check_output(['git',*args],cwd=ROOT,env=env,**kwargs)


def _journal_root():
    # No caller-controlled trust-root or alternate worktree/object database.
    need((ROOT/'.git').is_dir() and not (ROOT/'.git').is_symlink(),'ADMISSION_TRUSTED_CHECKOUT_REQUIRED')
    root=ROOT/'.git/b06-source-authority'
    need(first_symlink_in_path(path=root) is None,'ADMISSION_UNSAFE_JOURNAL')
    return root


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(canonical_json_bytes(value=value)); f.flush(); os.fsync(f.fileno())


def policy():
    return strict_json_file(path=ROOT / POLICY)


def start_stage():
    """Verify actual delegated authority, then pin one persistent budget ledger."""
    from .annual_candidate import _github
    p = policy(); root = _journal_root(); stage_path = root / 'stage.json'
    if stage_path.exists():
        return strict_json_file(path=stage_path)
    need(not _git(['status','--porcelain'],text=True).strip(), 'ADMISSION_CODE_NOT_COMMITTED')
    comment = _github(p['delegation_api'])
    need(comment.get('html_url') == p['delegation_url'] and comment.get('user', {}).get('login') == p['owner']
         and comment.get('author_association') == 'OWNER' and sha256_bytes(content=comment['body'].encode()) == p['delegation_body_sha256'], 'ADMISSION_OWNER_PROVENANCE_INVALID')
    stage = {'type':'B06_SOURCE_STAGE','comment':comment,'policy':p,'policy_sha256':sha256_file(path=ROOT/POLICY),
             'implementation_head':_git(['rev-parse','HEAD'],text=True).strip(),
             'created_at':datetime.now(timezone.utc).isoformat(),'production_authorized':False}
    stage['stage_id'] = content_hash(value=stage); _write(stage_path,stage)
    return stage


def _stage():
    root=_journal_root(); s=strict_json_file(path=root/'stage.json')
    need(s['policy']==policy() and s['stage_id']==content_hash(value={k:v for k,v in s.items() if k!='stage_id'}), 'ADMISSION_STAGE_CHANGED')
    return s


def _trusted_entries():
    """Prefer installed journal; portable installs use an explicitly pinned export."""
    root = _journal_root()
    if (root/'stage.json').exists():
        stage=_stage()
        return stage,[strict_json_file(path=p) for p in sorted((root/'accepted').glob('*.json'))]
    checkpoint=ROOT/'config/b06_source_checkpoint.json'
    need(checkpoint.is_file(),'TRUSTED_ACQUISITION_OR_IMPORT_REQUIRED')
    anchor=strict_json_file(path=checkpoint)
    export=ROOT/anchor['path']
    need(sha256_file(path=export)==anchor['sha256'],'ADMISSION_CHECKPOINT_CHANGED')
    saved=strict_json_file(path=export)
    return saved['stage'],saved['accepted']


def verify_admission(*, proof):
    stage,entries=_trusted_entries()
    matches=[e for e in entries if e['proof']==proof]
    need(len(matches)==1,'TRUSTED_ACQUISITION_OR_IMPORT_REQUIRED')
    e=matches[0]
    need(e['stage_id']==stage['stage_id'] and e['admission_id']==content_hash(value={k:v for k,v in e.items() if k!='admission_id'}), 'ADMISSION_RECORD_CHANGED')
    need(e['kind'] in {'TRUSTED_SAVED_IMPORT','SEC_FETCH'},'TEST_SOURCE_HAS_NO_SEC_CREDIT')
    return e


def _accept(proof, kind, basis):
    stage=_stage(); e={'type':'B06_SOURCE_ADMISSION','stage_id':stage['stage_id'],'kind':kind,'proof':proof,'basis':basis}
    e['admission_id']=content_hash(value=e);path=_journal_root()/'accepted'/(e['admission_id'][7:]+'.json')
    if path.exists():need(strict_json_file(path=path)==e,'ADMISSION_RECORD_CHANGED')
    else:_write(path,e)
    return e


def import_saved(*, data_root, url, accession=''):
    """Import exact historical acquisition bytes from the fixed reviewed baseline."""
    from .annual_input import _saved_source
    from .annual_update import _rows
    p=policy(); stage=_stage()
    proof,raw=_saved_source(repo_root=ROOT,rows=_rows(ROOT),url=url,accession=accession)
    paths=['evidence/requests_log.csv','evidence/requests_log_manifest.json',proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']]
    for relative in paths:
        expected=_git(['show',p['trusted_import_commit']+':'+relative])
        need((ROOT/relative).read_bytes()==expected,'TRUSTED_IMPORT_BASELINE_DIFFERS')
        out=data_root/relative;out.parent.mkdir(parents=True,exist_ok=True)
        if out.exists():need(out.read_bytes()==expected,'IMPORT_WOULD_OVERWRITE_INPUT')
        else:out.write_bytes(expected)
    return _accept(proof,'TRUSTED_SAVED_IMPORT',{'reviewed_commit':p['trusted_import_commit'],'paths':paths})


def fetch_primary(*, data_root, company_id):
    """One-shot fixed-sample fetch. Intent consumes a slot before transport."""
    from sec_http import SecHttpClient
    from sec_urls import accession_document_url
    from .annual_input import _saved_source
    from .annual_update import _rows
    stage=_stage(); p=policy(); sample=p['samples'][company_id]
    root=_journal_root(); need(not (root/'closed.json').exists(),'ADMISSION_STAGE_CLOSED')
    intents=list((root/'intents').glob('*.json'))
    for path in intents:
        need((root/'terminals'/path.name).exists(),'SEC_COUNT_UNKNOWN')
    need(len(intents)<p['budget']['sec'],'SEC_BUDGET_EXHAUSTED')
    url=accession_document_url(cik=int(sample['cik']),accession=sample['accession'],document_name=sample['primary_document'])
    key=sha256_bytes(content=url.encode()); need(not (root/'intents'/(key+'.json')).exists(),'SEC_REQUEST_ALREADY_CONSUMED')
    # Single stage-wide O_EXCL lock also protects independent-process budgets.
    lock=root/'fetch.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    try:
        need(len(list((root/'intents').glob('*.json')))<p['budget']['sec'],'SEC_BUDGET_EXHAUSTED')
        intent={'stage_id':stage['stage_id'],'url':url,'company_id':company_id,'max_retries':0,'implementation_sha256':sha256_file(path=Path(__file__))}
        _write(root/'intents'/(key+'.json'),intent)
        client=SecHttpClient(workdir=data_root,config_path=ROOT/'config/sec_config.json',log_path=data_root/'evidence/requests_log.csv')
        client.config={**client.config,'max_retries':0}
        result=client.fetch(url=url,purpose='b06_new_source_primary',local_path=data_root/'evidence/new_primary'/sample['primary_document'])
        terminal={'intent':intent,'result':result.__dict__,'status':'RECEIVED'}
        _write(root/'terminals'/(key+'.json'),terminal)
        need(result.status_code==200 and not result.error,'SEC_FETCH_FAILED')
        proof,raw=_saved_source(repo_root=data_root,rows=_rows(data_root),url=url,accession=sample['accession'])
        return _accept(proof,'SEC_FETCH',{'intent':intent,'terminal':terminal,'external_before_git':True})
    finally:
        os.close(fd);lock.unlink()


def export_checkpoint(path, *, close=False):
    root=_journal_root(); stage=_stage()
    payload={'stage':stage,'accepted':[strict_json_file(path=p) for p in sorted((root/'accepted').glob('*.json'))],
             'intents':[strict_json_file(path=p) for p in sorted((root/'intents').glob('*.json'))],
             'terminals':[strict_json_file(path=p) for p in sorted((root/'terminals').glob('*.json'))]}
    payload['counts']={'provider':0,'paid':0,'sec':len(payload['intents']),'unknown':len(payload['intents'])-len(payload['terminals'])}
    _write(path,payload)
    if close and not (root/'closed.json').exists():_write(root/'closed.json',{'checkpoint':content_hash(value=payload)})
    return payload
