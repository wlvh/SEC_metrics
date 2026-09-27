"""Limited SEC acquisition over existing HTTP, attempt and source primitives.

This successor owns its count slot and source checkpoint. Recorded transport
retains a separate identity; a checkpoint in a caller directory cannot enroll
itself as an actual acquisition.
"""
from pathlib import Path
import json
import os
from urllib.parse import urlsplit

from sec_http import (SecHttpClient,validate_request_log_manifest,parse_request_log_rows,
                      request_log_attempt_id,validate_official_sec_url,request_log_prefix_bytes)
from .canonical import content_hash,sha256_bytes,sha256_file,strict_json_file,canonical_json_bytes
from .continuous_call_policy import REQUIREMENT_ID,need,load_delegation
from .continuous_call_ledger import live_ledger,recorded_ledger
from .normal_source_authority import ROOT,MANIFEST_PATH,_baseline_file
from .ordinary_source_authority import _prefix,_immutable
from .sources import resolve_repository_file
from .batch_workflow import validate_request_attempt_binding
from .requirements import load_requirement_snapshot
from .invocation_control import _exclusive_write_json,_exclusive_write_bytes

_FACTORY=object()
CHECKPOINT_TYPE='ORDINARY_SEC_ACQUISITION_CHECKPOINT'
# The C04 successor reads original source and an explicit C04 contract, then
# installs current processing rules into a new Run root. These older rule
# copies in a pre-existing acquisition root are never used as C04 authority.
C04_SOURCE_ONLY_STALE_RULE_PATHS=frozenset({
    'config/issue28_normal_results_v2.json',
    'config/ordinary_public_projection_v1.json',
    'catalog/r5/C04_auditor_changes_v3.md',
})


def _seal(body,field):return {**body,field:content_hash(value=body)}


def _check_id(value,field):
    need(value[field]==content_hash(value={k:v for k,v in value.items() if k!=field}),
         'SEC_ACQUISITION_RECORD_CHANGED:'+field)


def _journal():
    from git_workspace import first_symlink_in_path
    path=ROOT/'.git/ordinary-source-authority/acquired'
    need((ROOT/'.git').is_dir() and first_symlink_in_path(path=path) is None,
         'SEC_ACQUISITION_INSTALLED_JOURNAL_REQUIRED')
    return path


def initialize_source_inputs(*,root,requirement,c04_source_only=False):
    """Copy the finite existing source corpus once; never fetch duplicates."""
    need(type(c04_source_only) is bool,'SEC_ACQUISITION_SOURCE_MODE_INVALID')
    baseline=strict_json_file(path=ROOT/MANIFEST_PATH)
    existing=root.exists()
    if root.exists():
        need((root/'source-baseline.json').is_file(),'SEC_ACQUISITION_SOURCE_ROOT_UNOWNED')
        need(strict_json_file(path=root/'source-baseline.json')=={'baseline_manifest_sha256':sha256_file(path=ROOT/MANIFEST_PATH)},
             'SEC_ACQUISITION_BASELINE_CHANGED')
    else:
        root.mkdir(parents=True)
        for relative in baseline['files']:
            _baseline_file(ROOT,relative,baseline)
            raw=resolve_repository_file(repo_root=ROOT,repo_relative_path=relative).read_bytes()
            _exclusive_write_bytes(path=root/relative,content=raw)
        _exclusive_write_json(path=root/'source-baseline.json',value={'baseline_manifest_sha256':sha256_file(path=ROOT/MANIFEST_PATH)})
    # Source discovery also needs its installed fiscal-label policy. It is
    # a rule input, not a downloaded source or a reusable provider response.
    from .normal_annual_input_v2 import POLICY_PATH as fiscal_policy
    _exclusive_write_bytes(path=root/fiscal_policy,content=(ROOT/fiscal_policy).read_bytes())
    # The ordinary source adapters consume the existing catalog/configuration
    # alongside data. Copy the bound rule inputs, not a parallel definition.
    processing_requirement=requirement['parent_snapshot']
    presentation_paths=set(processing_requirement['policy']['presentation_paths'])
    for relative,binding in processing_requirement['execution_authority']['files'].items():
        # Presentation is installed from current bound code in the candidate
        # runtime. It is not an acquisition/source dependency; retain any
        # historical copy instead of overwriting it or blocking new sources.
        if relative in presentation_paths or not relative.startswith(('config/','catalog/')):continue
        if c04_source_only and existing and relative in C04_SOURCE_ONLY_STALE_RULE_PATHS:
            continue
        raw=resolve_repository_file(repo_root=ROOT,repo_relative_path=relative).read_bytes()
        need({'sha256':sha256_bytes(content=raw),'size':len(raw)}==binding,
             'SEC_ACQUISITION_PROCESSING_RULE_CHANGED')
        _exclusive_write_bytes(path=root/relative,content=raw)


class SecAcquisitionSession:
    def __init__(self,*,factory,requirement,ledger,recorded_response=None,recorded_status=200):
        need(factory is _FACTORY,'SEC_ACQUISITION_FACTORY_REQUIRED')
        need((ledger.live and recorded_response is None) or
             (not ledger.live and type(recorded_response) is bytes),'SEC_ACQUISITION_TRANSPORT_MODE_CHANGED')
        self._factory=factory;self.requirement=requirement;self.ledger=ledger
        from .invocation_control import prepare_successor_invocation_authority
        self.authority=prepare_successor_invocation_authority(repo_root=ROOT,requirement_id=REQUIREMENT_ID)
        self.response=recorded_response;self.response_status=recorded_status
        self.data_root=ledger.root/'source-inputs'

    def _check(self):
        from .requirement_profile import validate_execution_authority
        need(self._factory is _FACTORY and self.requirement['requirement_id']==REQUIREMENT_ID,
             'SEC_ACQUISITION_SUCCESSOR_REQUIRED')
        binding=self.requirement['execution_authority']['files'].get('scripts/vnext/continuous_sec_acquisition.py')
        need(binding=={'sha256':sha256_file(path=Path(__file__)),'size':Path(__file__).stat().st_size},
             'SEC_ACQUISITION_IMPLEMENTATION_NOT_BOUND')
        validate_execution_authority(repo_root=ROOT,requirement=self.requirement)
        load_delegation(requirement=self.requirement,online=self.ledger.live)
        if self.ledger.live:
            need(self.ledger.root==Path(self.requirement['policy']['budget_root'])
                 and self.data_root==self.ledger.root/'source-inputs'
                 and self.ledger.binding['limits']==[240,240,80]
                 and self.response is None,'SEC_ACQUISITION_FIXED_ALLOWANCE_REQUIRED')
            receipt_path=self.requirement['policy'].get('sec_wiring_receipt_path')
            need(type(receipt_path) is str,'SEC_ACQUISITION_OFFLINE_WIRING_REQUIRED')
            receipt=strict_json_file(path=resolve_repository_file(repo_root=ROOT,repo_relative_path=receipt_path))
            need(receipt['record_type']=='SEC_ACQUISITION_OFFLINE_WIRING'
                 and receipt['execution_authority_hash']==content_hash(value=self.requirement['execution_authority'])
                 and receipt['calls']==[0,0,0] and receipt['actual_http_path_verified'] is True
                 and receipt['checkpoint_import_and_failure_isolation_verified'] is True,
                 'SEC_ACQUISITION_OFFLINE_WIRING_CHANGED')
            for relative,digest in receipt['evidence'].items():
                need(sha256_file(path=resolve_repository_file(repo_root=ROOT,repo_relative_path=relative))==digest,
                     'SEC_ACQUISITION_OFFLINE_EVIDENCE_CHANGED')

    def capture(self,*,company_id,url,refresh_metadata=False,control_id=None,
                source_only_c04=False):
        """Capture one declared dependency; no loop or automatic retry."""
        need(type(source_only_c04) is bool and not (source_only_c04 and control_id is not None),
             'SEC_ACQUISITION_C04_SOURCE_MODE_INVALID')
        from .normal_source_requirements import discover_saved_source_requirements
        self._check();validate_official_sec_url(url=url)
        with self.ledger.locked():
            initialize_source_inputs(root=self.data_root,requirement=self.requirement,
                                     c04_source_only=source_only_c04)
            if control_id is None:
                discovery=discover_saved_source_requirements(repo_root=self.data_root,company_id=company_id)
            else:
                from .r6_historical_controls import discover_control_sources
                need(not refresh_metadata,'SEMANTIC_CONTROL_METADATA_REFRESH_NOT_REQUESTED')
                discovery=discover_control_sources(repo_root=self.data_root,company_id=company_id,control_id=control_id)
            rows=[r for r in discovery['requirements'] if r['source_url']==url]
            need(len(rows)==1,'SEC_ACQUISITION_URL_NOT_A_DECLARED_COMPANY_DEPENDENCY')
            selected=rows[0]
            need(not refresh_metadata or selected['refresh_for_new_discovery'],
                 'SEC_ACQUISITION_ORIGINAL_CANNOT_BE_REFRESHED_AS_METADATA')
            if selected['saved_status']=='VERIFIED_SAVED_SOURCE' and not refresh_metadata:
                return {'status':'EXISTING_VERIFIED_SOURCE_REUSED','source':selected,'calls':[0,0,0]}
            log=self.data_root/'evidence/requests_log.csv';validate_request_log_manifest(log_path=log)
            before=log.read_bytes();old_rows=parse_request_log_rows(text=before.decode())
            client=SecHttpClient(workdir=self.data_root,config_path=ROOT/'config/sec_config.json',log_path=log)
            client.config={**client.config,'max_retries':0}
            request={'url':url,'method':'GET','sec_configuration_sha256':sha256_file(path=ROOT/'config/sec_config.json'),
                'automatic_retry_count':0,'metadata_refresh_parent':sha256_bytes(content=before) if refresh_metadata else None}
            plan={'company_id':company_id,'requirement_id':REQUIREMENT_ID,
                'requirement_closure_hash':self.requirement['requirement_closure_hash'],
                'source_dependency':selected,'discovery_id':discovery['requirements_id'],'request':request,
                'source_ledger_before_sha256':sha256_bytes(content=before),'source_row_count_before':len(old_rows)}
            if source_only_c04:
                plan['source_only_processing_route']='C04_REGISTRATION_FOUR_FORM_UPDATE_V1'
            if control_id is not None:
                plan['historical_semantic_control_id']=control_id
                plan['historical_source_scope']=discovery['scope']
                plan['current_metric_or_publication_credit']=False
            path,intent=self.ledger.claim(channel='SEC',request_digest=content_hash(value=request),
                requirement=self.requirement,plan_id=content_hash(value=plan),purpose='remaining_development_feasibility')
            _exclusive_write_json(path=path/'sec-plan.json',value=plan)
            from .continuous_semantic_calls import preserve_execution_rules
            preserve_execution_rules(self,path)
            document_name=Path(urlsplit(url).path).name
            need(bool(document_name),'SEC_ACQUISITION_DOCUMENT_NAME_MISSING')
            target=self.data_root/'evidence/continuous-acquisition'/('%04d'%intent['ordinal'])/document_name
            if self.ledger.live:
                self._check()
                result=client.fetch(url=url,purpose='ISSUE28_DECLARED_SOURCE_DEPENDENCY',local_path=target)
            else:
                # The recorded path has no opener dispatch and does not patch
                # process-global transport used by another live session.
                result=client._persist_result(url=url,status_code=self.response_status,
                    body=self.response,headers={'Content-Type':selected['media_type']},local_path=target,
                    error='' if self.response_status==200 else 'RECORDED_HTTP_FAILURE')
                client._append_log_row(result=result,purpose='ISSUE28_RECORDED_SOURCE_TEST',attempt=0)
            validate_request_log_manifest(log_path=log)
            after=log.read_bytes();new_rows=parse_request_log_rows(text=after.decode())
            need(after.startswith(before) and len(new_rows)==len(old_rows)+1,
                 'SEC_ACQUISITION_UNOWNED_APPEND_OR_PREFIX_CHANGE')
            row=new_rows[-1]
            need(row['source_url']==url and row['method']=='GET' and row['retry_attempt']=='0',
                 'SEC_ACQUISITION_NATIVE_REQUEST_CHANGED')
            wire={}
            for name,location in [('body',result.local_path),('headers',result.headers_path)]:
                if location:
                    relative=Path(location).relative_to(self.data_root).as_posix()
                    data=resolve_repository_file(repo_root=self.data_root,repo_relative_path=relative).read_bytes()
                    _exclusive_write_bytes(path=path/'sec-wire'/(name+'.bin'),content=data)
                    wire[name]={'source_path':relative,'sha256':sha256_bytes(content=data),'size':len(data)}
            success=row['status_code']=='200' and not row['error'];proof=None
            if success:
                binding=validate_request_attempt_binding(repo_root=self.data_root,source_url=url,
                    content_sha256=row['content_sha256'],accession=selected['accession'],
                    document_name=row['document_name'],request_attempt_id=request_log_attempt_id(row_index=len(old_rows),row=row),
                    require_immutable=True)
                proof={'source_url':url,'accession':selected['accession'],'document_name':row['document_name'],
                       'content_sha256':row['content_sha256'],**binding}
            body={'record_type':'CONTINUOUS_SEC_RECEIPT','intent_id':intent['intent_id'],
                'execution_mode':'LIVE' if self.ledger.live else 'RECORDED_TEST_ONLY',
                'actual_sec_egress_count':int(self.ledger.live),'automatic_retry_count':0,
                'status':'SUCCEEDED' if success else 'FAILED_TERMINAL' if row['status_code']!='0' else 'UNKNOWN_REMOTE_OUTCOME',
                'stop_reason':'UNKNOWN_REMOTE_OUTCOME' if row['status_code']=='0' else 'HTTP_402' if row['status_code']=='402' else '',
                'ledger_before_sha256':sha256_bytes(content=before),'ledger_after_sha256':sha256_bytes(content=after),
                'ledger_row_index':len(old_rows),'ledger_row':row,'proof':proof,
                'wire':wire,
                'company_id':company_id,'delegation_url':self.requirement['policy']['delegation_url'],
                'production_authorized':False}
            receipt=_seal(body,'receipt_id');_exclusive_write_json(path=path/'sec-receipt.json',value=receipt)
            terminal=self.ledger.finish_sec(path=path,intent=intent,receipt=receipt)
            checkpoint=self.register_checkpoint()
            return {'status':receipt['status'],'receipt':receipt,'terminal':terminal,'checkpoint_id':checkpoint['checkpoint_id'],
                    'calls':[0,0,int(self.ledger.live)],'production_authorized':False}

    def register_checkpoint(self):
        """Only the creating process can enroll the complete observed ledger."""
        need(self._factory is _FACTORY and self.ledger._locked,'SEC_ACQUISITION_CREATOR_REQUIRED')
        captures=[]
        for slot in sorted((self.ledger.root/'calls').iterdir()):
            intent=strict_json_file(path=slot/'intent.json')
            if intent['channel']!='SEC':continue
            need((slot/'terminal.json').is_file(),'SEC_ACQUISITION_UNKNOWN_SLOT_NOT_ADMISSIBLE')
            receipt=strict_json_file(path=slot/'sec-receipt.json');terminal=strict_json_file(path=slot/'terminal.json')
            captures.append({'intent':intent,'receipt':receipt,'terminal':terminal})
        body={'record_type':CHECKPOINT_TYPE,'schema_version':1,
            'baseline_manifest_sha256':sha256_file(path=ROOT/MANIFEST_PATH),
            'ledger_sha256':sha256_file(path=self.data_root/'evidence/requests_log.csv'),
            'execution_mode':'LIVE' if self.ledger.live else 'RECORDED_TEST_ONLY',
            'source_credit':'VERIFIED_SEC_ACQUISITION' if self.ledger.live else 'RECORDED_TEST_ONLY',
            'real_sec_credit':self.ledger.live,'captures':captures,'production_authorized':False}
        checkpoint=_seal(body,'checkpoint_id')
        validate_acquisition_checkpoint(self.data_root,checkpoint,strict_json_file(path=ROOT/MANIFEST_PATH))
        _immutable(_journal()/(body['ledger_sha256']+'.json'),checkpoint)
        return checkpoint


def validate_acquisition_checkpoint(data_root,checkpoint,baseline):
    """Replay source provenance; failed requests remain in the ledger."""
    from .ordinary_source_authority import _proof
    _check_id(checkpoint,'checkpoint_id')
    mode=checkpoint['execution_mode'];live=mode=='LIVE'
    need(checkpoint['record_type']==CHECKPOINT_TYPE and type(checkpoint['schema_version']) is int
         and checkpoint['schema_version']==1 and mode in {'LIVE','RECORDED_TEST_ONLY'}
         and checkpoint['real_sec_credit'] is live and checkpoint['production_authorized'] is False
         and checkpoint['source_credit']==('VERIFIED_SEC_ACQUISITION' if live else 'RECORDED_TEST_ONLY')
         and checkpoint['baseline_manifest_sha256']==sha256_file(path=ROOT/MANIFEST_PATH),
         'SEC_ACQUISITION_CHECKPOINT_MODE_CHANGED')
    raw,rows,old=_prefix(data_root,baseline);captures=checkpoint['captures']
    need(checkpoint['ledger_sha256']==sha256_bytes(content=raw) and len(rows)==len(old)+len(captures),
         'SEC_ACQUISITION_CHECKPOINT_LEDGER_CHANGED')
    old_ids={request_log_attempt_id(row_index=i,row=r) for i,r in enumerate(old)};admitted={}
    for offset,capture in enumerate(captures):
        intent,receipt,terminal=capture['intent'],capture['receipt'],capture['terminal']
        for value,field in [(intent,'intent_id'),(receipt,'receipt_id'),(terminal,'terminal_id')]:_check_id(value,field)
        index=len(old)+offset;row=rows[index]
        need(intent['channel']=='SEC' and receipt['intent_id']==terminal['intent_id']==intent['intent_id']
             and terminal['sec_receipt_id']==receipt['receipt_id'] and terminal['counts']==[0,0,1]
             and receipt['ledger_row_index']==index and receipt['ledger_row']==row
             and receipt['execution_mode']==mode and receipt['actual_sec_egress_count']==int(live)
             and intent['execution_mode']==mode and terminal['status']==receipt['status']
             and receipt['automatic_retry_count']==0 and row['retry_attempt']=='0',
             'SEC_ACQUISITION_CAPTURE_BINDING_CHANGED')
        before=request_log_prefix_bytes(text=raw.decode(),row_count=index)
        after=request_log_prefix_bytes(text=raw.decode(),row_count=index+1)
        need(receipt['ledger_before_sha256']==sha256_bytes(content=before)
             and receipt['ledger_after_sha256']==sha256_bytes(content=after),
             'SEC_ACQUISITION_CAPTURE_PREFIX_CHANGED')
        success=row['status_code']=='200' and not row['error']
        need((receipt['status']=='SUCCEEDED') is success,'SEC_ACQUISITION_CAPTURE_STATUS_CHANGED')
        if success:
            proof=receipt['proof'];_proof(data_root,proof)
            identity=request_log_attempt_id(row_index=index,row=row)
            need(proof['request_attempt_id']==identity and proof['source_url']==row['source_url'],
                 'SEC_ACQUISITION_PROOF_NAMES_ANOTHER_REQUEST')
            admitted[identity]={'binding':proof,'origin':proof}
        else:need(receipt['proof'] is None,'SEC_ACQUISITION_FAILURE_CANNOT_ADMIT_SOURCE')
    return raw,old_ids,admitted


def live_sec_session():
    requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    return SecAcquisitionSession(factory=_FACTORY,requirement=requirement,ledger=live_ledger(requirement=requirement))


def recorded_sec_session(*,root,response,status=200):
    requirement=load_requirement_snapshot(snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    return SecAcquisitionSession(factory=_FACTORY,requirement=requirement,ledger=recorded_ledger(root=root),
                                 recorded_response=response,recorded_status=status)
