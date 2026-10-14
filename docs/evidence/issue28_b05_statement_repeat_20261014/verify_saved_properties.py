"""Verify the explicit source properties on saved originals; never compute a metric."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
from unittest.mock import patch

from vnext.annual_amendment_scope_v2 import inspect_annual_amendment_scope
from vnext.historical_annual_input import prepare_historical_annual_input
from vnext.normal_governance_input import _Sources
from vnext.normal_period_selection import resolve_period_selection
from vnext.statement_metric_amendment import inspect_statement_metric_amendment
from vnext.ordinary_source_authority import verify_ordinary_source_proofs


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--company',required=True)
    parser.add_argument('--fiscal-year',type=int,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();assert not args.receipt.exists()
    protected=[args.source_root/p for p in ('config/company_registry.csv',
        'evidence/requests_log.csv','evidence/requests_log_manifest.json')]
    before={str(p):sha(p) for p in protected};start=time.perf_counter();results=[]
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
        stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')))
        stack.enter_context(patch('vnext.calculator.calculate_metric',side_effect=AssertionError('NO_CALCULATION')))
        stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',side_effect=AssertionError('NO_CLAIM')))
        selection=resolve_period_selection(repo_root=args.source_root,company_id=args.company,fiscal_year=args.fiscal_year)
        prepared=prepare_historical_annual_input(repo_root=args.source_root,company_id=args.company,
                                                period_selection=selection)
        reader=_Sources(args.source_root,args.company,prepared['entity'])
        original=reader.primary(prepared['filing'])
        convert=lambda item,filing:{'raw':item['raw_bytes'],'blob':item['raw_blob'],
            'reference':item['source_reference'],'filing':filing}
        for filing in prepared['amendments']:
            amendment=reader.primary(filing)
            scope=inspect_annual_amendment_scope(original=convert(original,prepared['filing']),
                amendment=convert(amendment,filing),company_id=args.company,cik=prepared['entity'],
                note_layout='inline-paragraphs-v2')
            saved=json.dumps(scope,ensure_ascii=False,default=dict,sort_keys=True)
            row={'scope_id':scope['scope_id'],'classification':scope['classification'],
                 'scope_further_review_retained':scope['original_statement_admission_requires_further_review'],
                 'unchanged_input_classes':scope['unchanged_input_classes'],'properties':{}}
            for metric in ('B04','B05','B07'):
                value=inspect_statement_metric_amendment(scope,amendment['raw_bytes'],metric_id=metric,
                    **({'original_raw':original['raw_bytes']} if metric=='B05' else {}))
                assert value['metric_id']==metric and value['original_scope_id']==scope['scope_id']
                assert value['metric_result_created'] is False and value['annual_continuity_proven'] is False
                row['properties'][metric]=value
            assert saved==json.dumps(scope,ensure_ascii=False,default=dict,sort_keys=True),'OLD_SCOPE_CHANGED'
            results.append(row)
        proofs=[v['proof'] for v in reader.proofs.values()]
        verify_ordinary_source_proofs(data_root=args.source_root,proofs=proofs)
        for proof in proofs:
            for key,expected in (('request_repo_relative_path','request_body_sha256'),
                                 ('request_headers_repo_relative_path','request_headers_sha256')):
                assert sha(args.source_root/proof[key])==proof[expected],'ORIGINAL_SOURCE_CHANGED'
    assert before=={str(p):sha(p) for p in protected},'SOURCE_LOG_OR_REGISTRY_CHANGED'
    code=Path('scripts/vnext/statement_metric_amendment.py')
    body={'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'code_root':str(Path.cwd()),'source_root':str(args.source_root),
        'working_tree_new_api_sha256':sha(code),'company_id':args.company,
        'fiscal_year':args.fiscal_year,'elapsed_seconds':time.perf_counter()-start,
        'results':results,'original_proofs_verified':len(proofs),'source_proofs':proofs,
        'source_log_and_registry_unchanged':True,'new_calls':{'provider':0,'paid':0,'sec':0},
        'metric_result_created':False,'company_acceptance_completed':False,'production_adopted':False,'tested_tree_committed':False,
        'working_tree_status':subprocess.check_output(['git','status','--short'],text=True),
        'source_property_only':True}
    args.receipt.write_text(json.dumps(body,ensure_ascii=False,indent=2,default=dict)+'\n')
    print(json.dumps({'elapsed_seconds':body['elapsed_seconds'],'scopes':[r['scope_id'] for r in results],
                      'metrics':[list(r['properties']) for r in results],'proofs':len(proofs)}))


if __name__=='__main__':run()
