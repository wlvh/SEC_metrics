"""Finite local trigger adapter; every event invokes the same run-once CLI."""
import json
import re
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
from . import annual_continuity as continuity
from .annual_adoption import ROOT, need
from .canonical import atomic_write_json


def _paths(approval_url):
    binding=continuity.verify_stage(approval_url=approval_url,execution=False)
    root=Path(binding['stage']['stage_root'])/'trigger'
    return binding,root,root/'current.json'


def _state(current,stage):
    state=continuity._json(current)
    need(state['stage_id']==stage['stage_id'] and type(state['trigger_id']) is str
         and re.fullmatch('[0-9a-f]{32}',state['trigger_id']) is not None
         and type(state['running']) is bool and type(state['process_id']) is int and state['process_id']>0,
         'CONTINUITY_TRIGGER_STATE_CHANGED')
    continuity._external(current.parent/state['trigger_id'])
    return state


def status(*,approval_url):
    binding,root,current=_paths(approval_url)
    if not current.exists():return {'status':'TRIGGER_DISABLED','running':False}
    state=_state(current,binding['stage'])
    from .invocation_control import _process_is_alive
    alive=state['running'] and _process_is_alive(process_id=state.get('process_id'))
    return {**state,'status':'TRIGGER_RUNNING' if alive else 'TRIGGER_INTERRUPTED' if state['running'] else 'TRIGGER_DISABLED','running':alive}


def stop(*,approval_url):
    binding,root,current=_paths(approval_url)
    if not current.exists():return {'status':'TRIGGER_DISABLED','running':False}
    state=_state(current,binding['stage']);path=root/state['trigger_id']/'stop.json'
    from .invocation_control import _process_is_alive
    if state['running'] and not _process_is_alive(process_id=state.get('process_id')):
        state.update(running=False,stopped_at_utc=continuity.now().isoformat(),stop_reason='TRIGGER_OWNER_EXITED_INSPECT_STAGE_BUDGET_BEFORE_RESTART')
        atomic_write_json(path=current,value=state)
    if state['running'] and not path.exists():
        continuity._write_once(path,{'stage_id':binding['stage']['stage_id'],'requested_at_utc':continuity.now().isoformat()})
    return {'status':'STOP_REQUESTED_AFTER_CURRENT_INVOCATION' if state['running'] else 'TRIGGER_DISABLED',
            'trigger_id':state['trigger_id'],'running':state['running']}


def run(*,approval_url,max_invocations,interval_seconds):
    binding,root,current=_paths(approval_url);stage=binding['stage'];continuity.validate_stage(stage,execution=True)
    need(type(max_invocations) is int and 1<=max_invocations<=3 and 0<=interval_seconds<=60,'CONTINUITY_FINITE_TRIGGER_BOUNDS')
    root.mkdir(parents=True,exist_ok=True)
    lock=root/'trigger.lock';need(not lock.is_symlink(),'CONTINUITY_TRIGGER_LOCK_ALIAS')
    handle=lock.open('a+b')
    try: fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:
        handle.close();raise
    if current.exists():need(not _state(current,stage)['running'],'CONTINUITY_TRIGGER_ALREADY_RUNNING_OR_UNKNOWN')
    identity=uuid4().hex;work=root/identity;work.mkdir(parents=True)
    state={'trigger_id':identity,'stage_id':stage['stage_id'],'process_id':os.getpid(),'running':True,'started_at_utc':continuity.now().isoformat(),
        'maximum_invocations':max_invocations,'invocations':[],'production_scheduler_installed':False}
    atomic_write_json(path=current,value=state)
    try:
        for ordinal in range(1,max_invocations+1):
            if (work/'stop.json').exists():break
            continuity.validate_stage(stage,execution=True)
            output=work/('run-'+str(ordinal)+'.json');log=work/('run-'+str(ordinal)+'.log')
            argv=[sys.executable,str(ROOT/'tools/vnext_annual_continuity.py'),'run-once','--approval-url',approval_url,'--output-json',str(output)]
            with log.open('xb') as stream:
                process=subprocess.run(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=False)
            result=continuity._json(output) if output.exists() else {'status':'PROCESS_RESULT_UNKNOWN'}
            state['invocations'].append({'ordinal':ordinal,'argv':argv,'returncode':process.returncode,'status':result.get('status'),
                'output':str(output),'log':str(log)})
            atomic_write_json(path=current,value=state)
            if process.returncode!=0:break
            if ordinal<max_invocations:time.sleep(interval_seconds)
    finally:
        state.update(running=False,stopped_at_utc=continuity.now().isoformat())
        atomic_write_json(path=current,value=state)
        continuity._write_once(work/'terminal.json',state)
        handle.close()
    return {'status':'FINITE_TRIGGER_STOPPED',**state}
