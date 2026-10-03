"""Bounded offline C04 source reconstruction, not a new accepted Run."""
from pathlib import Path
from unittest.mock import patch
import json
import socket
from vnext.normal_governance_input import prepare_saved_governance_input
from vnext.normal_candidates import _governance_resolution
from vnext.ordinary_storage_identity import auditor_document_views
from vnext.normal_source_authority import ROOT
from vnext.canonical import sha256_bytes
HERE=Path(__file__).resolve().parent
with patch.object(socket.socket,'connect',side_effect=AssertionError('NETWORK_FORBIDDEN')), patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS_FORBIDDEN')):
    p=prepare_saved_governance_input(repo_root=ROOT,company_id='paramount_skydance_paramount_global')
    p=auditor_document_views(repo_root=ROOT,preparation=p)
    spec,resolution=_governance_resolution(data_root=ROOT,preparation=p,metric_id='C04')
    out={'real_calls':[0,0,0],'spec_path':spec,'input_binding':p['input_binding'], 'resolution':resolution,
         'source_index':[r for r in p['records'] if r['record_type'] in ['RAW_BLOB','SOURCE_REFERENCE']],
         'native_run_created':False,'production_authorized':False}
    (HERE/'current.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('selection',json.dumps(p['input_binding']['selection'],ensure_ascii=False))
    print('limitations',p['input_binding']['limitations'])
    print('resolution',json.dumps(resolution['selection'],ensure_ascii=False))
    print('result',json.dumps(resolution['result'],ensure_ascii=False))
