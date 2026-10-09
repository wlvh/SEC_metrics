"""Fixed historical producer + owned public runtime, with all sockets denied."""
import importlib.util
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'scripts'))
import vnext
from vnext import ordinary_saved_result as store
from vnext import ordinary_projection as current_projection
from vnext.canonical import sha256_file
from vnext.deterministic_router import shared_xbrl_parses
SOURCE = Path('/Users/lyuhongwang/.codex/worktrees/7e99/SEC_metrics-issue47-company-verified-source-20261006/source-inputs')
PEER_SHA = '8102c3829e64e79d831d28f5c9a3c755b8e164e3'
BASE = 'ae8a13c8'
EVIDENCE = Path(__file__).parent
with tempfile.TemporaryDirectory() as tmp:
    temporary = Path(tmp)
    producer_path = temporary/'historical_event_cases.py'
    producer_path.write_bytes(subprocess.check_output(['git','show',PEER_SHA+':scripts/vnext/historical_event_cases.py'],cwd=ROOT))
    spec = importlib.util.spec_from_file_location('vnext.historical_event_cases',producer_path)
    producer = importlib.util.module_from_spec(spec);sys.modules[spec.name]=producer;spec.loader.exec_module(producer)
    old_path = temporary/'original_projection.py'
    old_path.write_bytes(subprocess.check_output(['git','show',BASE+':scripts/vnext/ordinary_projection.py'],cwd=ROOT))
    spec = importlib.util.spec_from_file_location('vnext._original_projection',old_path)
    old = importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    state_parent = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence')
    state_parent.mkdir(parents=True,exist_ok=True)
    reuse_path = Path(sys.argv[1]) if len(sys.argv)>1 else None
    state = reuse_path.parent if reuse_path is not None else state_parent/('wide-event-window-'+str(time.time_ns()))
    if reuse_path is None: state.mkdir()
    ledger_before = sha256_file(path=SOURCE/'evidence/requests_log.csv')
    started = time.monotonic()
    with patch.object(socket.socket,'connect',side_effect=AssertionError('No business network')), shared_xbrl_parses():
        if reuse_path is None:
            case = producer.prepare_historical_event_year_case(repo_root=SOURCE,
                company_id='paramount_skydance_paramount_global',metric_id='C01',fiscal_year=2025)
            prepared_seconds = time.monotonic()-started
            (state/'case.json').write_text(json.dumps(case,ensure_ascii=False,indent=2)+'\n')
        else:
            case = json.loads(reuse_path.read_text()); prepared_seconds = None
        annual_before = json.dumps(case['prepared_annual_input'],sort_keys=True)
        # Both sides use the same unchanged calculated case and real writer.
        # Only the before side selects the fixed original renderer, not a mock
        # that fabricates success or replaces extraction/installation.
        before_reason = None
        with patch.object(current_projection,'render_ordinary_records',old.render_ordinary_records):
            try:
                store.save_calculated_case(source_root=SOURCE,output_root=state/'before',
                    company_id=case['prepared_annual_input']['company_id'],metric_id='C01',case=case)
            except ValueError as error:before_reason=str(error)
        assert before_reason=='ORDINARY_PROJECTION_PREPARED_PERIOD_CHANGED',before_reason
        started = time.monotonic()
        saved = store.save_calculated_case(source_root=SOURCE,output_root=state/'after',
            company_id=case['prepared_annual_input']['company_id'],metric_id='C01',case=case)
        save_seconds = time.monotonic()-started
        started = time.monotonic();read = store.read_saved_result(output_root=state/'after')
        read_seconds = time.monotonic()-started
    assert saved['result']==read['result']==case['results']['C01']
    assert saved['result']['value']=='12' and saved['result']['unit']=='count'
    assert json.dumps(case['prepared_annual_input'],sort_keys=True)==annual_before
    expected = {'fiscal_year':2025,'period_start':'2024-01-01','period_end':'2025-12-31'}
    assert saved['manifest']['target_period']==expected
    accessions = set(case['selection']['source_event_accessions'])
    matched = []
    for proof in case['source_proofs']:
        if proof['document_name'].endswith('.hdr.sgml') and proof['accession'] in accessions:
            raw = (SOURCE/proof['request_repo_relative_path']).read_text()
            if re.search(r'(?m)^<ITEMS>\s*5\.02\s*(?:</ITEMS>)?\s*$',raw):matched.append(proof['accession'])
    assert len(set(matched))==12,matched
    assert sha256_file(path=SOURCE/'evidence/requests_log.csv')==ledger_before
    result = {'tested_tree_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'has_uncommitted_product_changes':bool(subprocess.check_output(['git','diff','--name-only','HEAD','--','scripts','config','catalog'],cwd=ROOT).strip()),'code_root':str(ROOT),'source_root':str(SOURCE),
        'historical_producer_sha':PEER_SHA,'historical_producer_path':'scripts/vnext/historical_event_cases.py',
        'historical_producer_file_sha256':sha256_file(path=producer_path),'state_root':str(state),
        'before_reason':before_reason,'result_id':saved['result']['result_id'],'value':saved['result']['value'],
        'unit':saved['result']['unit'],'measurement_period':saved['manifest']['target_period'],
        'annual_container':case['prepared_annual_input']['table_input']['target_period'],
        'direct_header_item_502_accessions':sorted(set(matched)),
        'filing_count':len(accessions),'proof_count':len(case['source_proofs']),
        'reused_case_from_first_driver_failure':reuse_path is not None,'prepared_case_seconds':prepared_seconds,'save_seconds':save_seconds,'independent_read_seconds':read_seconds,
        'csv_files':['metrics_matrix.csv','metric_evidence.csv'],'request_ledger_unchanged':True,
        'new_calls':{'provider':0,'paid':0,'sec':0},'credit':'PUBLIC_INTERFACE_INTEGRATION_ONLY_NOT_ISSUE28_BUSINESS_ACCEPTANCE'}
    for name in result['csv_files']:assert (state/'after'/name).is_file()
    (EVIDENCE/'saved-wide-window.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
