"""Read the completed offline bridge evidence before the first real request."""
from .canonical import content_hash, strict_json_file, sha256_file
from .continuous_call_policy import need
from .normal_source_authority import ROOT
from .sources import resolve_repository_file

def validate_wiring_receipt(*, requirement):
    value = strict_json_file(path=resolve_repository_file(repo_root=ROOT,
        repo_relative_path=requirement['policy']['offline_wiring_receipt_path']))
    need(value['record_type']=='CONTINUOUS_OFFLINE_WIRING_RECEIPT'
         and value['requirement_id']==requirement['requirement_id']
         and value['execution_authority_hash']==content_hash(value=requirement['execution_authority'])
         and value['delegation_url']==requirement['policy']['delegation_url']
         and value['calls']=={'provider':0,'paid':0,'sec':0}
         and value['network_disabled'] is True
         and value['legacy_default_forbidden'] is True
         and value['real_request_factory_to_controller_verified'] is True
         and value['count_control_tests_passed'] is True,
         'CONTINUOUS_OFFLINE_WIRING_MISSING_OR_CHANGED')
    for relative,digest in value['evidence'].items():
        need(sha256_file(path=resolve_repository_file(repo_root=ROOT,repo_relative_path=relative))==digest,
             'CONTINUOUS_OFFLINE_WIRING_EVIDENCE_CHANGED')
    return value
