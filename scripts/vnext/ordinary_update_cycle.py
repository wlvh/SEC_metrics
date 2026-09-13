"""Persistent zero-egress update checks over the ordinary source/Run pipeline.

The current runtime admits saved and explicitly recorded sources. This module
does not fetch, enable model calls, publish or reuse closed execution budgets.
It keeps failed attempts separate from the last completely verified candidate.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import fcntl
from pathlib import Path
from uuid import uuid4

from git_workspace import first_symlink_in_path
from . import normal_run_v3 as normal
from .canonical import atomic_write_json,content_hash,sha256_file,strict_json_file
from .normal_annual_input import _registry_rows
from .ordinary_projection import render_ordinary_run
from .requirements import load_requirement_snapshot
from .run_store import _mechanically_replay_open_run


class OrdinaryUpdateError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise OrdinaryUpdateError(reason)


def _now():return datetime.now(timezone.utc).isoformat()


def _write(path,value):normal._write(path,normal._bytes(value))


def _record(path,body):
    value={**body,'record_id':content_hash(value=body)};_write(path,value);return value


def _read(path):
    _need(first_symlink_in_path(path=path) is None,'UPDATE_STATE_PATH_ALIAS')
    value=strict_json_file(path=path)
    _need(value['record_id']==content_hash(value={k:v for k,v in value.items() if k!='record_id'}),'UPDATE_RECORD_CHANGED')
    return value


@contextmanager
def _locked(root):
    _need(first_symlink_in_path(path=root) is None,'UPDATE_STATE_PATH_ALIAS')
    root.mkdir(parents=True,exist_ok=True);path=root/'update.lock'
    _need(first_symlink_in_path(path=path) is None,'UPDATE_STATE_PATH_ALIAS')
    with path.open('a+b') as handle:
        try:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:raise OrdinaryUpdateError('UPDATE_ALREADY_RUNNING') from error
        yield


def _config(root,source_root,company_id,metrics):
    policy=normal._policy(normal.ROOT)
    _need(policy['provider_enabled'] is False and policy['sec_fetch_enabled'] is False
          and policy['freeze_enabled'] is False,'UPDATE_ZERO_EGRESS_RUNTIME_REQUIRED')
    _need(company_id in {c['company_id'] for c in _registry_rows(repo_root=normal.ROOT)},'UPDATE_COMPANY_NOT_CONFIGURED')
    _need(type(metrics) is list and metrics and len(metrics)==len(set(metrics))
          and set(metrics)<=set(policy['metric_ids']),'UPDATE_METRIC_SCOPE_INVALID')
    requirement=load_requirement_snapshot(snapshot_dir=normal.ROOT/'requirements'/normal.REQUIREMENT_ID)
    body={'record_type':'ORDINARY_UPDATE_CONFIGURATION','schema_version':1,'company_id':company_id,
        'metric_ids':sorted(metrics),'source_root':str(source_root),
        'requirement_closure_hash':requirement['requirement_closure_hash'],
        'provider_enabled':False,'sec_fetch_enabled':False,'production_authorized':False}
    path=root/'configuration.json'
    if path.exists():
        configured=_read(path)
        _need({k:v for k,v in configured.items() if k!='record_id'}==body,'UPDATE_CONFIGURATION_OR_RUNTIME_CHANGED')
        return configured
    return _record(path,body)


def _descriptor(cases,configuration):
    bodies={};targets={};specs={}
    for metric,case in cases.items():
        targets[metric]=case['target_period'];specs[metric]={k:v['spec_closure_hash'] for k,v in case['compiled_specs'].items()}
        for proof in case['source_proofs']:
            key=(proof['source_url'],proof['accession'],proof['document_name'])
            _need(key not in bodies or bodies[key]==proof['content_sha256'],'UPDATE_SOURCE_BODY_CONFLICT')
            bodies[key]=proof['content_sha256']
    body={'company_id':configuration['company_id'],'metric_ids':configuration['metric_ids'],
        'requirement_closure_hash':configuration['requirement_closure_hash'],'targets':targets,'specs':specs,
        'source_contents':[{'source_url':k[0],'accession':k[1],'document_name':k[2],'sha256':v} for k,v in sorted(bodies.items())]}
    return {**body,'content_id':content_hash(value=body)}


def _inspect(source_root,configuration):
    ledger=sha256_file(path=source_root/'evidence/requests_log.csv')
    cases={m:normal.prepare_case(data_root=source_root,company_id=configuration['company_id'],metric_id=m)
           for m in configuration['metric_ids']}
    _need(sha256_file(path=source_root/'evidence/requests_log.csv')==ledger,'UPDATE_SOURCE_CHANGED_DURING_INSPECTION')
    return cases,_descriptor(cases,configuration),ledger


def _attempt(root,identity):
    _need(type(identity) is str and len(identity)==32 and all(c in '0123456789abcdef' for c in identity),'UPDATE_ATTEMPT_ID_INVALID')
    path=root/'attempts'/identity
    _need(first_symlink_in_path(path=path) is None,'UPDATE_STATE_PATH_ALIAS')
    return path


def _verify_candidate(root,terminal,configuration):
    _need(terminal['status']=='CANDIDATE_READY' and terminal['configuration_id']==configuration['record_id'],
          'UPDATE_SUCCESS_REFERENCE_INVALID')
    work=_attempt(root,terminal['attempt_id']);data=work/'data';cases={};rows={}
    _need(set(terminal['metrics'])==set(configuration['metric_ids']),'UPDATE_SUCCESS_METRIC_SET_CHANGED')
    for metric in configuration['metric_ids']:
        run=work/'runs'/metric
        manifest,records,_=_mechanically_replay_open_run(run_dir=run,repo_root=data,require_complete_results=True)
        cases[metric]=normal.replay_case(data_root=data,manifest=manifest)
        result=next(r for r in records if r['record_type']=='METRIC_RESULT' and r['metric_id']==metric)
        _need(result['publication']=='PUBLISHED' and result['result_id']==terminal['metrics'][metric]['result_id'],
              'UPDATE_SUCCESS_RESULT_CHANGED')
        rendered=render_ordinary_run(data_root=data,run_dir=run)
        for name,raw in rendered['files'].items():
            path=work/'rows'/metric/name
            _need(path.read_bytes()==raw and sha256_file(path=path)==terminal['metrics'][metric]['files'][name],
                  'UPDATE_SUCCESS_ROW_CHANGED')
        rows[metric]=result
    _need(_descriptor(cases,configuration)==terminal['input'],'UPDATE_SUCCESS_INPUT_CHANGED')
    return rows


def _state(root,configuration):
    path=root/'current.json'
    _need(first_symlink_in_path(path=path) is None,'UPDATE_STATE_PATH_ALIAS')
    if not path.exists():return {'configuration_id':configuration['record_id'],'latest_attempt':None,'successful_attempt':None}
    state=strict_json_file(path=path)
    _need(set(state)=={'configuration_id','latest_attempt','successful_attempt'}
          and state['configuration_id']==configuration['record_id'],'UPDATE_STATE_CONFIGURATION_CHANGED')
    for key in ['latest_attempt','successful_attempt']:
        if state[key] is not None:_attempt(root,state[key])
    if state['latest_attempt'] is None:
        _need(state['successful_attempt'] is None,'UPDATE_STATE_REFERENCE_CHAIN_CHANGED')
    else:
        work=_attempt(root,state['latest_attempt'])
        _need((work/'intent.json').is_file() and (work/'terminal.json').is_file(),'UPDATE_STATE_REFERENCE_MISSING')
        intent=_read(work/'intent.json');terminal=_read(work/'terminal.json')
        _need(intent['configuration_id']==terminal['configuration_id']==configuration['record_id']
              and terminal['intent_id']==intent['record_id'],'UPDATE_STATE_REFERENCE_CHAIN_CHANGED')
        expected=state['latest_attempt'] if terminal['status']=='CANDIDATE_READY' else intent['previous_successful_attempt']
        _need(state['successful_attempt']==expected,'UPDATE_STATE_REFERENCE_CHAIN_CHANGED')
    return state


def _terminal(root,identity):return _read(_attempt(root,identity)/'terminal.json')


def _recover(root,state,configuration):
    """Reconcile the immutable journal before advancing a mutable reference."""
    intents={}
    for work in (root/'attempts').iterdir() if (root/'attempts').exists() else []:
        _attempt(root,work.name)
        if (work/'intent.json').is_file():
            intent=_read(work/'intent.json')
            _need(intent['configuration_id']==configuration['record_id'] and intent['attempt_id']==work.name,
                  'UPDATE_INTENT_CONFIGURATION_CHANGED')
            intents[work.name]=intent
    seen=set()
    successors={}
    for identity,intent in intents.items():
        parent=intent['previous_attempt']
        _need(parent is None or parent in intents and parent!=identity,'UPDATE_JOURNAL_PREDECESSOR_MISSING')
        successors.setdefault(parent,[]).append(identity)
    visited=set();cursor=None
    while True:
        children=successors.get(cursor,[])
        if not children:break
        _need(len(children)==1 and children[0] not in visited,'UPDATE_JOURNAL_BRANCH_OR_CYCLE')
        cursor=children[0];visited.add(cursor)
    _need(visited==set(intents),'UPDATE_JOURNAL_DISCONNECTED')
    while True:
        following=successors.get(state['latest_attempt'],[])
        if not following:break
        _need(len(following)==1 and following[0] not in seen,'UPDATE_JOURNAL_BRANCH_OR_CYCLE')
        identity=following[0];seen.add(identity);intent=intents[identity];work=_attempt(root,identity)
        _need(intent['previous_successful_attempt']==state['successful_attempt'],'UPDATE_INTENT_PREDECESSOR_CHANGED')
        if not (work/'terminal.json').exists():
            _record(work/'terminal.json',{'record_type':'ORDINARY_UPDATE_TERMINAL','attempt_id':identity,
                'configuration_id':configuration['record_id'],'intent_id':intent['record_id'],
                'status':'INTERRUPTED','completed_at':_now(),'input':None,'metrics':{},
                'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False})
        terminal=_terminal(root,identity)
        _need(terminal['intent_id']==intent['record_id'] and terminal['configuration_id']==configuration['record_id'],
              'UPDATE_TERMINAL_INTENT_CHANGED')
        if terminal['status']=='CANDIDATE_READY':
            _verify_candidate(root,terminal,configuration);state['successful_attempt']=identity
        state['latest_attempt']=identity
    atomic_write_json(path=root/'current.json',value=state)
    return state


def run_once(*,state_root,source_root,company_id,metric_ids):
    """Check one company's current input and keep a durable candidate history."""
    root=normal._external(Path(state_root));source=Path(source_root).resolve()
    _need(root!=source and root not in source.parents and source not in root.parents,'UPDATE_SOURCE_STATE_ROOTS_OVERLAP')
    with _locked(root):
        configuration=_config(root,source,company_id,metric_ids);state=_recover(root,_state(root,configuration),configuration)
        previous=None
        if state['successful_attempt'] is not None:
            previous=_terminal(root,state['successful_attempt']);_verify_candidate(root,previous,configuration)
        identity=uuid4().hex;work=_attempt(root,identity)
        intent=_record(work/'intent.json',{'record_type':'ORDINARY_UPDATE_INTENT','attempt_id':identity,
            'configuration_id':configuration['record_id'],'started_at':_now(),'previous_attempt':state['latest_attempt'],
            'previous_successful_attempt':state['successful_attempt']})
        descriptor=None;metrics={};status='INPUT_FAILED';error=None
        try:
            _,descriptor,ledger=_inspect(source,configuration)
            if previous:
                _need(all(descriptor['targets'][m]['period_end']>=previous['input']['targets'][m]['period_end']
                          for m in configuration['metric_ids']),'UPDATE_SOURCE_PERIOD_REGRESSED')
            if previous and descriptor==previous['input']:
                status='NO_SOURCE_CONTENT_CHANGE'
            elif state['latest_attempt'] and (prior:=_terminal(root,state['latest_attempt']))['status'] in {'CANDIDATE_WITHHELD','PREVIOUS_INPUT_WITHHELD'} and prior['input']==descriptor:
                status='PREVIOUS_INPUT_WITHHELD'
            else:
                for metric in configuration['metric_ids']:
                    normal.install_normal_inputs(data_root=work/'data',source_root=None if source==normal.ROOT else source,
                        company_id=company_id,metric_id=metric)
                    created=normal.create_normal_run(data_root=work/'data',run_dir=work/'runs'/metric,company_id=company_id,metric_id=metric)
                    rendered=render_ordinary_run(data_root=work/'data',run_dir=work/'runs'/metric)
                    hashes={}
                    for name,raw in rendered['files'].items():
                        path=work/'rows'/metric/name;normal._write(path,raw);hashes[name]=sha256_file(path=path)
                    metrics[metric]={'result_id':created['result']['result_id'],'publication':created['result']['publication'],
                                     'source_credit':created['input_binding']['source_admission']['source_credit'],'files':hashes}
                _need(sha256_file(path=source/'evidence/requests_log.csv')==ledger,'UPDATE_SOURCE_CHANGED_DURING_EXECUTION')
                status='CANDIDATE_READY' if all(v['publication']=='PUBLISHED' for v in metrics.values()) else 'CANDIDATE_WITHHELD'
                if status=='CANDIDATE_READY':
                    _verify_candidate(root,{'status':status,'configuration_id':configuration['record_id'],
                        'attempt_id':identity,'input':descriptor,'metrics':metrics},configuration)
        except Exception as failure:
            error={'error_type':type(failure).__name__,'reason':str(failure)}
            status='EXECUTION_FAILED' if descriptor is not None else 'INPUT_FAILED'
        terminal=_record(work/'terminal.json',{'record_type':'ORDINARY_UPDATE_TERMINAL','attempt_id':identity,
            'configuration_id':configuration['record_id'],'intent_id':intent['record_id'],'status':status,
            'completed_at':_now(),'input':descriptor,'metrics':metrics,'error':error,
            'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False})
        if status=='CANDIDATE_READY':
            state['successful_attempt']=identity
        state['latest_attempt']=identity;atomic_write_json(path=root/'current.json',value=state)
        return {'status':status,'attempt_id':identity,'latest_attempt':identity,
            'successful_attempt':state['successful_attempt'],'previous_successful_attempt':intent['previous_successful_attempt'],
            'new_candidate_created':bool(metrics),'terminal':terminal,'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
