"""Real saved Southwest annual set through the existing input-assessment seam.

No company/result replay or business request. Variants are isolated parser
controls over copies of real bytes and never registered as actual sources.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import time
from unittest.mock import patch

from vnext.canonical import sha256_bytes
from vnext.current_d04_result import _task_input
from vnext.normal_annual_input_v2 import prepare_saved_annual_input
from vnext.ordinary_task_input import parsed_d04_document
from vnext.sources import source_reference_record


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--ledger-root',type=Path,required=True)
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();assert not args.receipt.exists()
    protected=[args.ledger_root/'claims.jsonl',args.ledger_root/'binding.json']
    protected.extend(args.source_root/p for p in ('config/company_registry.csv',
        'evidence/requests_log.csv','evidence/requests_log_manifest.json'))
    for number in range(119,125):
        protected.extend(p for p in (args.ledger_root/'calls'/f'{number:04d}').rglob('*') if p.is_file())
    source=json.loads((args.ledger_root/'calls/0119/source.json').read_text())
    for proof in source['source_proofs']:
        for key in ('request_repo_relative_path','request_headers_repo_relative_path'):
            protected.append(args.source_root/proof[key])
    before={str(p):digest(p) for p in protected}
    results={}
    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket,'connect',side_effect=AssertionError('NO_NETWORK')))
        stack.enter_context(patch.object(socket,'getaddrinfo',side_effect=AssertionError('NO_DNS')))
        stack.enter_context(patch('vnext.continuous_call_ledger.CallLedger.claim',
                                  side_effect=AssertionError('NO_NEW_CLAIM')))
        stack.enter_context(patch('vnext.calculator.calculate_metric',side_effect=AssertionError('NO_CALCULATION')))
        started=time.perf_counter()
        annual=prepare_saved_annual_input(repo_root=args.source_root,company_id='southwest_airlines',ordinary_registered=True)
        results['selection_seconds']=time.perf_counter()-started
        started=time.perf_counter()
        assessment=_task_input(args.source_root,'southwest_airlines',annual)
        results['assessment_seconds']=time.perf_counter()-started
        print('actual input assessment',results['assessment_seconds'],flush=True)
        assert 'd04_task_input_comparison_unavailable' not in assessment,assessment
        actual=assessment['d04_task_input'];assert len(actual['documents'])==2
        assert [d['filing']['form'] for d in actual['documents']]==['10-K','10-K/A']
        results['actual_task_input']=actual
        amendment=next(d for d in source['documents'] if d['source_reference']['source_role']=='annual_amendment')
        original=(args.source_root/amendment['raw_blob']['storage_uri']).read_bytes()
        def parsed(raw):
            blob={**amendment['raw_blob'],'raw_asset_id':'sha256:'+sha256_bytes(content=raw),'byte_length':len(raw)}
            ref=source_reference_record(raw_blob=blob,company_id='southwest_airlines',
                source_url=amendment['source_reference']['source_url'],
                accession=amendment['source_reference']['accession'],
                document_name=amendment['source_reference']['document_name'],
                source_role='annual_amendment',request_attempt_id=amendment['source_reference']['request_attempt_id'])
            return parsed_d04_document(raw_bytes=raw,raw_blob=blob,source_reference=ref,
                expected_company_id='southwest_airlines',expected_cik=annual['entity'],
                expected_period_end=annual['table_input']['target_period']['period_end'],allow_annual_amendment=True)
        started=time.perf_counter();baseline=parsed(original)
        # Actual original remains untouched. These are constructed controls,
        # not new SEC acquisitions or real company/model conclusions.
        variants={
            'empty_external_script':original.replace(b'</body>',b'<script src="/comparison-only.js"></script></body>'),
            'visible_disclosure':original.replace(b'</body>',b'<p>Substantial doubt exists.</p></body>')}
        assert all(raw!=original for raw in variants.values()),'Expected closing body absent'
        results['variant_controls']={}
        for name,raw in variants.items():
            value=parsed(raw);equal=value['parsed_input_sha256']==baseline['parsed_input_sha256']
            assert equal==(name=='empty_external_script'),(name,equal)
            assert value['parsed_input']['identity']['source_state']=='INCOMPLETE'
            for span in value['original_locators']:
                assert sha256_bytes(content=raw[span['raw_start_byte']:span['raw_end_byte']])==span['raw_span_sha256']
            results['variant_controls'][name]={'same_parsed_input':equal,
                'original_reference_spans_checked':len(value['original_locators']),
                'raw_bytes_changed':True,'registered_actual_source':False,
                'source_admission_or_result_credit':value['source_admission_or_result_credit']}
        results['variant_seconds']=time.perf_counter()-started
    assert before=={str(p):digest(p) for p in protected},'ORIGINALS_OR_LEDGER_CHANGED'
    head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
    results.update(code_root=str(Path.cwd()),base_commit=head,
        working_tree_code={p:digest(Path(p)) for p in changed if p.startswith(('scripts/','tests/'))},
        source_root=str(args.source_root),ledger_root=str(args.ledger_root),
        protected_original_files=len(before),originals_unchanged=True,
        new_calls={'provider':0,'paid':0,'sec':0},
        company_result_created=False,model_accuracy_verified=False,production_adopted=False)
    args.receipt.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print('saved-input and isolated variants passed; originals unchanged',flush=True)


if __name__=='__main__':run()
