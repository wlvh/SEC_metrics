"""Independent, authenticated saved processing inputs over the original V14 APIs.

First adapter: complete D04 over byte-matching baseline SEC sources. Acquired
source equivalence and new AI calls remain explicit unsupported entrances.
"""
import json
import base64
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

from .canonical import canonical_json_bytes, content_hash, strict_json_file
from .company_handoff import _atomic_json, binding, external
from .company_source_authority import need


TRUST_VARIABLE = 'SEC_METRICS_PROCESSING_TRUST_ROOT'


def worker(action, program, packet, source, work):
    child = subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('company_processing_read.py')),
        action,str(program),str(packet),str(source),str(work)],capture_output=True,text=True,
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    need(child.returncode==0,'COMPANY_PROCESSING_AUTHENTICATION_FAILED:'+(
        child.stderr.strip().splitlines()[-1] if child.stderr.strip() else 'WORKER_FAILED'))
    return json.loads(child.stdout)


def export_processing(*, installed_root, output_root, runtime_output_root, trust_root, company_id):
    source=external(installed_root); output=external(output_root); runtime=external(runtime_output_root); trust=external(trust_root)
    need(not output.exists() and not runtime.exists(),'COMPANY_PROCESSING_OUTPUT_EXISTS')
    need(all(a!=b and a not in b.parents and b not in a.parents for a,b in
             ((source,output),(source,runtime),(source,trust),(output,runtime),(output,trust),(runtime,trust))),
         'COMPANY_PROCESSING_ROOTS_OVERLAP')
    # Authenticate the complete original record first, with its original code.
    exported=worker('export',source,output,source,runtime)
    record=exported['record']; need(record['company_id']==company_id,'COMPANY_PROCESSING_WRONG_COMPANY')
    # The old installer reads a program-owned catalog/config inventory. This
    # new private Git inventory is read only during compute, never a journal.
    for args in (['init'],['add','.'],['-c','user.name=Company runtime','-c','user.email=company-runtime@localhost',
                                    'commit','-m','Install unchanged saved-processing runtime']):
        subprocess.run(['git',*args],cwd=runtime,check=True,capture_output=True)
    output.mkdir(parents=True); (output/'config').mkdir()
    shutil.copyfile(source/'config/ordinary_going_concern_assessment.json',output/'config/ordinary_going_concern_assessment.json')
    need(strict_json_file(path=output/'config/ordinary_going_concern_assessment.json') == record,
         'COMPANY_PROCESSING_ORIGINAL_RECORD_CHANGED_DURING_EXPORT')
    (output/'processing-source.json').write_bytes(canonical_json_bytes(value=exported['source']))
    metadata={'record_type':'COMPANY_SAVED_PROCESSING_INPUT_V1','company_id':company_id,'metric_id':'D04',
        'input_record_id':record['input_record_id'],'source_id':record['source_id'],'mode':record['mode'],
        'requirement_id':exported['requirement_id'],'requirement_closure_hash':exported['requirement_closure_hash'],
        'new_call_authority':False,'production_authorized':False,
        'files':{p.relative_to(output).as_posix():binding(p) for p in sorted(output.rglob('*')) if p.is_file()},
        'runtime_files':{p.relative_to(runtime).as_posix():binding(p) for p in sorted(runtime.rglob('*')) if p.is_file() and '.git' not in p.parts}}
    metadata['processing_id']=content_hash(value=metadata)
    (output/'processing.json').write_bytes(canonical_json_bytes(value=metadata))
    trust.mkdir(parents=True,exist_ok=True)
    target=trust/(metadata['processing_id'][7:]+'.json')
    if target.exists():
        need(not target.is_symlink() and strict_json_file(path=target)==metadata,
             'COMPANY_PROCESSING_TRUST_CHANGED')
    else:
        from sec_http import write_immutable_bytes
        write_immutable_bytes(path=target,content=canonical_json_bytes(value=metadata))
    return {'status':'SAVED_PROCESSING_EXPORTED','processing_id':metadata['processing_id'],
            'company_id':company_id,'mode':record['mode'],'native_requests':len(record['native_requests']),
            'runtime_root':str(runtime),'output_root':str(output),'new_business_calls':[0,0,0]}


def authenticate_processing(*, packet_root, program_root, company_id):
    packet=external(packet_root); program=external(program_root)
    location=os.environ.get(TRUST_VARIABLE)
    need(location,'COMPANY_PROCESSING_TRUST_ROOT_REQUIRED')
    trust=external(location)
    need(all(a!=trust and a not in trust.parents and trust not in a.parents for a in (packet,program)),
         'COMPANY_PROCESSING_TRUST_ROOT_OVERLAP')
    metadata=strict_json_file(path=packet/'processing.json')
    need(metadata['processing_id']==content_hash(value={k:v for k,v in metadata.items() if k!='processing_id'}),
         'COMPANY_PROCESSING_ID_CHANGED')
    need(strict_json_file(path=trust/(metadata['processing_id'][7:]+'.json'))==metadata,
         'COMPANY_PROCESSING_NOT_TRUSTED')
    need(metadata['company_id']==company_id and metadata['metric_id']=='D04'
         and metadata['new_call_authority'] is False and metadata['production_authorized'] is False,
         'COMPANY_PROCESSING_WRONG_COMPANY_OR_AUTHORITY')
    for directory, files in ((packet,metadata['files']),(program,metadata['runtime_files'])):
        from git_workspace import first_symlink_in_path
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file() and '.git' not in p.relative_to(directory).parts}
        need(actual == set(files) | ({'processing.json'} if directory == packet else set()),
             'COMPANY_PROCESSING_MEMBER_SET_CHANGED')
        for relative, expected in files.items():
            path=Path(relative)
            need(not path.is_absolute() and '..' not in path.parts and first_symlink_in_path(path=directory/path) is None,
                 'COMPANY_PROCESSING_FILE_ALIAS')
            need(binding(directory/path)==expected,'COMPANY_PROCESSING_BOUND_FILE_CHANGED:'+relative)
    need(not (program/'.git/objects/info/alternates').exists() and not (program/'evidence').exists()
         and not (program/'config/ordinary_going_concern_assessment.json').exists(),
         'COMPANY_PROCESSING_PROGRAM_STATE_NOT_SEPARATE')
    return metadata


def compute_saved_processing(*, root, source, admission, company_id, packet_root, program_root):
    location=os.environ.get(TRUST_VARIABLE)
    need(location,'COMPANY_PROCESSING_TRUST_ROOT_REQUIRED')
    trust=external(location)
    need(trust!=root and root not in trust.parents and trust not in root.parents,
         'COMPANY_PROCESSING_STATE_TRUST_OVERLAP')
    metadata=authenticate_processing(packet_root=packet_root,program_root=program_root,company_id=company_id)
    need(admission['original_checkpoint'] is None,'COMPANY_PROCESSING_ACQUIRED_SOURCE_ADAPTER_REQUIRED')
    target=root/'updates/processing/D04'/metadata['requirement_closure_hash'][7:]
    target.mkdir(parents=True,exist_ok=True); pointer=target/'current.json'
    previous=strict_json_file(path=pointer) if pointer.is_file() else None
    fingerprint=content_hash(value={k:metadata[k] for k in
        ('input_record_id','source_id','mode','requirement_closure_hash')} | {'checkpoint_id':admission['checkpoint_id']})
    reusable = previous and previous['input_fingerprint']==fingerprint
    if previous and not reusable:
        # An older envelope fingerprint must not recreate a byte-identical
        # native assessment merely because its container was repacked.
        work=Path(previous['candidate']['rows_root']).parent
        receipt=strict_json_file(path=work/'processing-receipt.json')
        registered=strict_json_file(path=work/'data/config/ordinary_going_concern_assessment.json')
        reusable=(receipt['source_checkpoint_id']==admission['checkpoint_id'] and
            all(registered[k]==metadata[k] for k in ('input_record_id','source_id','mode','requirement_closure_hash')))
    if reusable:
        candidate=previous['candidate']; work=Path(candidate['rows_root']).parent
        files=worker('replay',program_root,packet_root,source,work)
        for name,raw in files.items():
            need((work/'rows/D04'/name).read_bytes()==base64.b64decode(raw,validate=True),
                 'COMPANY_PROCESSING_ROWS_CHANGED')
        if previous['input_fingerprint']!=fingerprint:
            _atomic_json(pointer,{**previous,'input_fingerprint':fingerprint})
        return {'metric_id':'D04','status':'NO_SOURCE_CONTENT_CHANGE','last_verified_candidate':candidate,
                'saved_processing_mode':metadata['mode'],'new_candidate_created':False,
                'business_metric_completed':False}
    identity=uuid4().hex; work=target/'attempts'/identity;work.mkdir(parents=True)
    try:
        completed=worker('compute',program_root,packet_root,source,work)
        need(completed['native_assessment_completed'] is True,'COMPANY_PROCESSING_RESULT_WITHHELD')
        # Preserve authenticated processing bytes beside (not inside) SEC data.
        shutil.copytree(packet_root,work/'processing')
        receipt={'processing_id':metadata['processing_id'],'company_id':company_id,
            'source_checkpoint_id':admission['checkpoint_id'],'runtime_root':str(program_root),**completed}
        _atomic_json(work/'processing-receipt.json',receipt)
        candidate={'attempt_id':identity,'rows_root':str(work/'rows'),'current_input_matches':True,
                   'processing_id':metadata['processing_id'],'runtime_root':str(program_root)}
        _atomic_json(pointer,{'attempt_id':identity,'input_fingerprint':fingerprint,'candidate':candidate})
        return {'metric_id':'D04','status':'CANDIDATE_READY','last_verified_candidate':candidate,
                'saved_processing_mode':metadata['mode'],'new_candidate_created':True,
                'native_assessment_completed':True, 'business_metric_completed':False}
    except Exception as error:
        failure={'metric_id':'D04','status':'PROCESSING_INPUT_REJECTED','reason':str(error),
                 'business_metric_completed':False,'last_verified_candidate':(
                     {**previous['candidate'],'current_input_matches':False} if previous else None)}
        _atomic_json(target/'latest_failure.json',failure)
        return failure
