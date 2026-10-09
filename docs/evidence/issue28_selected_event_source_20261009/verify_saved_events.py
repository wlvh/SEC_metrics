"""Read-only selected-event comparison; all writes are isolated test evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from scripts.vnext.normal_annual_input import prepare_saved_annual_input
from scripts.vnext.normal_governance_input import _Sources
from scripts.vnext.selected_event_source_v1 import read_selected_event_sources
from scripts.vnext.canonical import sha256_file
from sec_urls import submissions_url

ROOT = Path(__file__).resolve().parents[3]
BASE = '3d6030b1bc5e1e7b22833a0101fbeb8f88341498'
with tempfile.TemporaryDirectory() as directory:
    workspace = Path(directory)
    original = workspace / 'original_event_module.py'
    original.write_bytes(subprocess.check_output(['git','show',BASE+':scripts/vnext/normal_zero_ai_results.py'],cwd=ROOT))
    spec = importlib.util.spec_from_file_location('scripts.vnext._original_event_module', original)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    company = 'marriott_international'
    started = time.monotonic()
    prepared = prepare_saved_annual_input(repo_root=ROOT,company_id=company)
    reader = _Sources(ROOT,company,prepared['entity'])
    inventory = reader.read(submissions_url(cik=int(prepared['entity'])),role='sec_submissions_inventory',media_type='application/json')
    claims, manifests, filings = module._event_sources(repo_root=ROOT,reader=reader,prepared=prepared,inventory=inventory)
    original_seconds = time.monotonic()-started
    source = workspace / 'source'; source.mkdir()
    paths = {'config/company_registry.csv','evidence/requests_log.csv','evidence/requests_log_manifest.json'}
    for entry in reader.proofs.values():
        proof = entry['proof']
        paths.update((proof['request_repo_relative_path'],proof['request_headers_repo_relative_path']))
    for header in (ROOT/'evidence/accession_materials').glob('*_'+prepared['entity']+'_*/*.hdr.sgml'):
        paths.add(str(header.relative_to(ROOT)))
    for relative in sorted(paths):
        target = source/relative; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,target)
    (source/'evidence/accession_materials').mkdir(parents=True,exist_ok=True)
    before = sha256_file(path=source/'evidence/requests_log.csv')
    started = time.monotonic()
    output = read_selected_event_sources(data_root=source,rules_root=ROOT,prepared=prepared,period=prepared['table_input']['target_period'])
    selected_seconds = time.monotonic()-started
    assert output['claims']==claims
    assert output['source_set_manifests']==manifests
    assert output['filings']==filings
    assert output['source_proofs']==[entry['proof'] for entry in reader.proofs.values()]
    assert sha256_file(path=source/'evidence/requests_log.csv')==before
    assert not (source/'scripts').exists() and not (source/'catalog').exists()
    headers = [p for p in output['source_proofs'] if p['document_name'].endswith('.hdr.sgml')]
    # This is direct source reading, independent of the adapter's claims.
    # Real headers use either plain SGML or closing tags.
    import re
    item_502 = [p['accession'] for p in headers if re.search(r'(?m)^<ITEMS>\s*5\.02\s*(?:</ITEMS>)?\s*$',
                (source/p['request_repo_relative_path']).read_text())]
    assert len(item_502)==3
    summary = {'base_commit':BASE,'company_id':company,'period':output['event_window'],
               'claims_same':True,'manifests_same':True,'filings_same':True,'request_proofs_same':True,
               'event_filing_count':len(filings),'claim_count':len(claims),'proof_count':len(output['source_proofs']),
               'independently_read_item_502_accessions':item_502,
               'original_preparation_and_walk_seconds':original_seconds,'selected_walk_and_proof_seconds':selected_seconds,
               'no_catalog_or_program_in_source':True,'request_ledger_unchanged':True,
               'source_root_kind':'ISOLATED_COPY_OF_SELECTED_SAVED_ORIGINALS',
               'new_calls':output['new_calls'],'native_run_status':output['native_run_status']}
    (Path(__file__).parent/'saved-event-comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
