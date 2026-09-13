"""Recorded source-update transaction over existing SEC persistence primitives.

This implementation deliberately exposes only a recorded test session. It never
opens a socket, grants a real SEC acquisition or consumes/reopens an old budget.
Original baseline rows remain exact; every appended row must have a session-owned
intent and terminal. A caller-created consistent ledger cannot self-enroll.
"""
from pathlib import Path
from datetime import datetime,timezone
import os

from sec_http import (SecHttpClient,parse_request_log_rows,request_log_prefix_bytes,
                      validate_request_log_manifest,request_log_attempt_id)
from sec_urls import submissions_url,companyfacts_url
from git_workspace import first_symlink_in_path
from .annual_update import saved_source
from .batch_workflow import validate_request_attempt_binding
from .canonical import content_hash,sha256_file,strict_json_file,canonical_json_bytes
from .normal_annual_input import _registry_rows,prepare_saved_annual_input
from .normal_source_authority import ROOT,MANIFEST_PATH,_baseline_file,verify_saved_source_proofs

_FACTORY=object()


class OrdinarySourceSessionError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise OrdinarySourceSessionError(reason)


def _external(path):
    path=Path(path).absolute()
    _need(first_symlink_in_path(path=path) is None,'SOURCE_SESSION_PATH_ALIAS')
    path=path.resolve();root=ROOT.resolve()
    _need(path!=root and root not in path.parents,'SOURCE_SESSION_OUTSIDE_CHECKOUT_REQUIRED')
    _need(not any((p/'outputs/active_publication.json').exists() for p in [path,*path.parents]),
          'SOURCE_SESSION_PUBLICATION_WORKSPACE_FORBIDDEN')
    return path


def _record(path,body):
    _need(first_symlink_in_path(path=path) is None,'SOURCE_SESSION_RECORD_PATH_ALIAS')
    value={**body,'record_id':content_hash(value=body)}
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(canonical_json_bytes(value=value));stream.flush();os.fsync(stream.fileno())
    return value


def _read_record(path):
    value=strict_json_file(path=path)
    _need(value['record_id']==content_hash(value={k:v for k,v in value.items() if k!='record_id'}),
          'SOURCE_SESSION_RECORD_CHANGED')
    return value


class RecordedSourceSession:
    def __init__(self,*,data_root,journal_root,company_id,max_responses,_factory=None):
        _need(_factory is _FACTORY,'SOURCE_SESSION_FACTORY_REQUIRED')
        self.data_root=_external(data_root);self.journal_root=_external(journal_root)
        _need(self.data_root!=self.journal_root and self.data_root not in self.journal_root.parents
              and self.journal_root not in self.data_root.parents,'SOURCE_SESSION_ROOTS_OVERLAP')
        _need(not self.journal_root.exists(),'SOURCE_SESSION_JOURNAL_ALREADY_EXISTS')
        _need(type(max_responses) is int and 0<max_responses<=100,'SOURCE_SESSION_RECORDED_LIMIT_INVALID')
        self.company=next((c for c in _registry_rows(repo_root=ROOT) if c['company_id']==company_id),None)
        _need(self.company is not None,'SOURCE_SESSION_COMPANY_NOT_CONFIGURED')
        self.baseline=strict_json_file(path=ROOT/MANIFEST_PATH)
        for relative in ('config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'):
            _baseline_file(self.data_root,relative,self.baseline)
        self.prefix=(self.data_root/'evidence/requests_log.csv').read_bytes()
        self.prefix_rows=parse_request_log_rows(text=self.prefix.decode('utf-8'))
        self.journal_root.mkdir(parents=True)
        self.header=_record(self.journal_root/'session.json',{
            'record_type':'RECORDED_ORDINARY_SOURCE_SESSION','mode':'RECORDED_TEST_ONLY',
            'company_id':company_id,'data_root':str(self.data_root),'max_responses':max_responses,
            'baseline_manifest_sha256':sha256_file(path=ROOT/MANIFEST_PATH),
            'baseline_ledger_sha256':sha256_file(path=self.data_root/'evidence/requests_log.csv'),
            'baseline_row_count':len(self.prefix_rows),'created_at':datetime.now(timezone.utc).isoformat(),
            'real_sec_credit':False,'production_authorized':False})
        self._terminal_ids=[]

    def _check(self):
        _need(_external(self.data_root)==self.data_root and _external(self.journal_root)==self.journal_root,
              'SOURCE_SESSION_ROOT_CHANGED')
        _need(_read_record(self.journal_root/'session.json')==self.header,'SOURCE_SESSION_HEADER_CHANGED')
        _need(sha256_file(path=ROOT/MANIFEST_PATH)==self.header['baseline_manifest_sha256'],
              'SOURCE_SESSION_BASELINE_CHANGED')
        log=self.data_root/'evidence/requests_log.csv';validate_request_log_manifest(log_path=log)
        raw=log.read_text(encoding='utf-8');rows=parse_request_log_rows(text=raw)
        _need(request_log_prefix_bytes(text=raw,row_count=len(self.prefix_rows))==self.prefix,
              'SOURCE_SESSION_BASELINE_PREFIX_CHANGED')
        intents=sorted((self.journal_root/'intents').glob('*.json'))
        paths=sorted((self.journal_root/'terminals').glob('*.json'))
        _need(len(intents)==len(paths),'SOURCE_SESSION_OUTCOME_UNKNOWN')
        terminals=[_read_record(p) for p in paths]
        _need([r['record_id'] for r in terminals]==self._terminal_ids,'SOURCE_SESSION_TERMINAL_NOT_OWNED')
        _need(len(rows)==len(self.prefix_rows)+len(terminals),'SOURCE_SESSION_UNOWNED_LEDGER_APPEND')
        for ordinal,(intent_path,terminal) in enumerate(zip(intents,terminals),start=1):
            intent=_read_record(intent_path)
            _need(intent['session_id']==self.header['record_id'] and intent['ordinal']==ordinal
                  and terminal['intent_id']==intent['record_id'] and terminal['mode']=='RECORDED_TEST_ONLY'
                  and terminal['ledger_row']==rows[len(self.prefix_rows)+ordinal-1],
                  'SOURCE_SESSION_INTENT_OR_ROW_CHANGED')
        return rows,terminals

    def _allowed_url(self,url):
        cik=int(self.company['primary_cik'])
        allowed={submissions_url(cik=cik),companyfacts_url(cik=cik)}
        prefix='https://www.sec.gov/Archives/edgar/data/'+str(cik)+'/'
        _need(url in allowed or url.startswith(prefix),'SOURCE_SESSION_COMPANY_URL_SCOPE')

    def record_saved_response(self,*,url,accession='',status_code=200,historical_test_attempt_id=None):
        """Replay known original bytes through native persistence, without HTTP."""
        self._allowed_url(url);_need(status_code in {200,404,500},'SOURCE_SESSION_TEST_STATUS_UNSUPPORTED')
        rows,terminals=self._check()
        _need(not any(t['status']!='SUCCEEDED' for t in terminals),'SOURCE_SESSION_FAILED_TERMINAL_CLOSED')
        _need(len(terminals)<self.header['max_responses'],'SOURCE_SESSION_RECORDED_BUDGET_EXHAUSTED')
        if historical_test_attempt_id is None:
            original=saved_source(repo_root=ROOT,url=url,accession=accession)
        else:
            # Test history is selected only from immutable, already trusted
            # acquisitions. It is never a replacement SEC body or live fetch.
            from .sources import resolve_repository_file
            candidates=[(i,r) for i,r in enumerate(self.prefix_rows)
                if request_log_attempt_id(row_index=i,row=r)==historical_test_attempt_id and r['source_url']==url]
            _need(len(candidates)==1,'SOURCE_SESSION_HISTORICAL_ATTEMPT_NOT_IN_BASELINE')
            _,row=candidates[0]
            binding=validate_request_attempt_binding(repo_root=ROOT,source_url=url,content_sha256=row['content_sha256'],
                accession=accession,document_name=row['document_name'],request_attempt_id=historical_test_attempt_id,
                require_immutable=True)
            proof={'source_url':url,'accession':accession,'document_name':row['document_name'],
                   'content_sha256':row['content_sha256'],**binding}
            original={'proof':proof,'raw':resolve_repository_file(repo_root=ROOT,repo_relative_path=proof['request_repo_relative_path']).read_bytes()}
        _need(original is not None,'SOURCE_SESSION_ORIGINAL_NOT_SAVED')
        verify_saved_source_proofs(data_root=ROOT,proofs=[original['proof']])
        from .sources import resolve_repository_file
        from sec_http import write_immutable_bytes
        for key in ['request_repo_relative_path','request_headers_repo_relative_path']:
            relative=original['proof'][key]
            write_immutable_bytes(path=self.data_root/relative,
                content=resolve_repository_file(repo_root=ROOT,repo_relative_path=relative).read_bytes())
        client=SecHttpClient(workdir=self.data_root,config_path=ROOT/'config/sec_config.json',
                             log_path=self.data_root/'evidence/requests_log.csv')
        _need(self._check()[0]==rows,'SOURCE_SESSION_PRECHECK_CHANGED_LEDGER')
        ordinal=len(terminals)+1
        intent=_record(self.journal_root/'intents'/('{:06d}.json'.format(ordinal)),{
            'record_type':'RECORDED_SOURCE_INTENT','session_id':self.header['record_id'],'ordinal':ordinal,
            'mode':'RECORDED_TEST_ONLY','url':url,'origin_proof':original['proof'],'retry':0,
            'ledger_before_rows':len(rows)})
        # Calling persistence directly is intentional: no fetch/urlopen method
        # is reached, and the terminal can never be interpreted as real SEC.
        result=client._persist_result(url=url,status_code=status_code,
            body=original['raw'] if status_code==200 else b'RECORDED_TEST_SOURCE_FAILURE',
            headers={'Content-Type':'application/octet-stream','X-Recorded-Test':'true'},
            local_path=self.data_root/'evidence/ordinary_source_replay'/str(ordinal)/original['proof']['document_name'],
            error='' if status_code==200 else 'RECORDED_TEST_SOURCE_FAILURE')
        client._append_log_row(result=result,purpose='recorded_ordinary_source_update',attempt=0)
        after=parse_request_log_rows(text=(self.data_root/'evidence/requests_log.csv').read_text())
        _need(after[:-1]==rows and len(after)==len(rows)+1,'SOURCE_SESSION_APPEND_OUTCOME_UNKNOWN')
        terminal=_record(self.journal_root/'terminals'/('{:06d}.json'.format(ordinal)),{
            'record_type':'RECORDED_SOURCE_TERMINAL','intent_id':intent['record_id'],'mode':'RECORDED_TEST_ONLY',
            'ledger_row':after[-1],'status':'SUCCEEDED' if status_code==200 else 'FAILED',
            'actual_sec_egress_count':0,'real_sec_credit':False})
        self._terminal_ids.append(terminal['record_id']);self._check()
        return terminal

    def verify(self,proofs):
        _need(type(proofs) is list and bool(proofs),'SOURCE_SESSION_PROOFS_REQUIRED')
        rows,terminals=self._check();ids=[]
        by_id={request_log_attempt_id(row_index=len(self.prefix_rows)+i,row=t['ledger_row']):t for i,t in enumerate(terminals)}
        for proof in proofs:
            attempt=proof['request_attempt_id']
            if attempt not in by_id:
                for key in ('request_repo_relative_path','request_headers_repo_relative_path'):
                    _baseline_file(self.data_root,proof[key],self.baseline)
                _need(any(request_log_attempt_id(row_index=i,row=r)==attempt for i,r in enumerate(self.prefix_rows)),
                      'SOURCE_SESSION_UNKNOWN_BASELINE_ATTEMPT')
            else:_need(by_id[attempt]['status']=='SUCCEEDED','SOURCE_SESSION_FAILED_SOURCE_HAS_NO_VALUE')
            binding=validate_request_attempt_binding(repo_root=self.data_root,source_url=proof['source_url'],
                content_sha256=proof['content_sha256'],accession=proof['accession'],document_name=proof['document_name'],
                request_attempt_id=attempt,require_immutable=proof['request_locator_kind']=='IMMUTABLE_ATTEMPT')
            _need(binding=={k:v for k,v in proof.items() if k not in {'source_url','accession','document_name','content_sha256'}},
                  'SOURCE_SESSION_PROOF_CHANGED')
            ids.append(attempt)
        return {'record_type':'RECORDED_ORDINARY_INPUT_ADMISSION','session_id':self.header['record_id'],
            'request_attempt_ids':ids,'source_credit':'RECORDED_TEST_ONLY','real_sec_credit':False,
            'recorded_responses':len(terminals),'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}

    def prepare_annual_input(self):
        self._check()
        prepared=prepare_saved_annual_input(repo_root=self.data_root,company_id=self.company['company_id'])
        admission=self.verify(prepared['source_proofs'])
        return {'prepared_input':prepared,'source_admission':admission,'native_run_created':False}


def recorded_source_session(*,data_root,journal_root,company_id,max_responses=3):
    return RecordedSourceSession(data_root=data_root,journal_root=journal_root,company_id=company_id,
                                 max_responses=max_responses,_factory=_FACTORY)


def compare_annual_inputs(*,previous,current):
    """Compare already verified inputs; this function grants no authenticity.

    Attempts, header timestamps and storage paths do not change financial input
    content. A changed original body or amended filing still requires processing.
    """
    _need(previous['company_id']==current['company_id'] and previous['entity']==current['entity'],
          'SOURCE_UPDATE_SUBJECT_CHANGED')
    identity=('accessionNumber','form','reportDate','filingDate','primaryDocument')
    def filing(value):return {k:value[k] for k in identity}
    def bodies(value):
        result={}
        for proof in value['source_proofs']:
            key=(proof['source_url'],proof['accession'],proof['document_name'])
            _need(key not in result or result[key]==proof['content_sha256'],'SOURCE_UPDATE_CONFLICTING_BODIES')
            result[key]=proof['content_sha256']
        return result
    old,new=filing(previous['filing']),filing(current['filing'])
    if new['reportDate']<old['reportDate']:
        status='SOURCE_SELECTION_REGRESSED';process=False
    elif new!=old:status='ANNUAL_FILING_CHANGED';process=True
    elif [filing(f) for f in previous['amendments']]!=[filing(f) for f in current['amendments']]:
        status='AMENDMENT_INPUT_CHANGED';process=True
    elif previous['table_input']['target_period']!=current['table_input']['target_period']:
        status='PERIOD_INTERPRETATION_CHANGED';process=True
    elif bodies(previous)!=bodies(current):status='SOURCE_CONTENT_CHANGED';process=True
    else:status='NO_SOURCE_CONTENT_CHANGE';process=False
    return {'status':status,'requires_candidate_processing':process,
            'input_authenticity_verified_by_comparison':False,'production_authorized':False}
