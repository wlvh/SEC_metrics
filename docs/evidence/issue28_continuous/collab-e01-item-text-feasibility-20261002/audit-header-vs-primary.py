"""Bounded diagnostic: compare saved 8-K item headings with header candidates.

This is a source-coverage lead, not an E01 semantic or result acceptance test.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
ACQUIRED = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
source = Path(json.loads((HERE/'current-source.json').read_text())['processing_root'])
companies = ('marriott_international', 'southwest_airlines', 'ford_motor_company',
    'pfizer', 'jpmorgan_chase', 'salesforce', 'lumen_technologies', 'macys',
    'paramount_skydance_paramount_global', 'enphase_energy')
probe_path = ROOT/'docs/evidence/issue28_continuous/ordinary-b01-legacy-exit-20260928/probe.py'
spec = importlib.util.spec_from_file_location('legacy_probe', probe_path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blocked(*args, **kwargs):
    raise AssertionError('NETWORK_FORBIDDEN')


protected = {'claims':ACQUIRED/'claims.jsonl',
    'source_log':ACQUIRED/'source-inputs/evidence/requests_log.csv',
    'active':ROOT/'outputs/active_publication.json'}
before = {key:digest(path) for key,path in protected.items()}
started = time.monotonic()
rows = []
with (patch.object(socket.socket, 'connect', side_effect=blocked),
      patch.object(socket, 'getaddrinfo', side_effect=blocked),
      patch('sec_http.urlopen', side_effect=blocked),
      probe.legacy_disabled() as disabled):
    from vnext.ordinary_e01_item_text_input import prepare_current_e01_item_text
    from vnext.e01_item_text_28_v1 import item_headings
    from vnext.deterministic_router import _visible_text
    from vnext.sources import resolve_repository_file
    for company in companies:
        prepared = prepare_current_e01_item_text(repo_root=source, company_id=company)
        header_items = {(item['accession'],item['item_code']) for item in prepared['items']}
        references = {row['source_reference_id']:row for row in prepared['source_records']
            if row['record_type']=='SOURCE_REFERENCE'}
        blobs = {row['raw_asset_id']:row for row in prepared['source_records']
            if row['record_type']=='RAW_BLOB'}
        filing_rows = []
        for reference in references.values():
            if reference['source_role']!='fy_8k_primary':
                continue
            raw = resolve_repository_file(repo_root=source,
                repo_relative_path=blobs[reference['raw_asset_id']]['storage_uri']).read_bytes()
            found = sorted({code for _,_,code in item_headings(_visible_text(raw_bytes=raw))
                            if code in ('1.01','2.01','8.01')})
            header = sorted(code for accession,code in header_items
                            if accession==reference['accession'])
            filing_rows.append({'accession':reference['accession'],
                'primary_raw_asset_id':reference['raw_asset_id'],
                'primary_detected_candidate_headings':found,
                'header_candidate_codes':header,
                'headings_missing_from_header':sorted(set(found)-set(header))})
        rows.append({'company_id':company,'filings':len(filing_rows),
            'candidate_items':prepared['candidate_count'],
            'headings_missing_from_header':sum(
                len(row['headings_missing_from_header']) for row in filing_rows),
            'filing_rows':sorted(filing_rows,key=lambda row:row['accession'])})
elapsed = time.monotonic()-started
after = {key:digest(path) for key,path in protected.items()}
result = {'record_type':'ISSUE28_E01_HEADER_VS_PRIMARY_DIAGNOSTIC',
    'code_commit':'dcd36df3daf1194b4e74a6fc81779d3dcf07bdb5',
    'source_root':str(source),'rows':rows,
    'companies':len(rows),'candidate_items':sum(row['candidate_items'] for row in rows),
    'potential_header_omissions':sum(row['headings_missing_from_header'] for row in rows),
    'elapsed_seconds':round(elapsed,3),'legacy_exports_disabled':disabled,
    'protected_unchanged':before==after,'new_real_calls':[0,0,0],
    'semantic_or_result_credit':False}
(HERE/'audit-header-vs-primary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({key:result[key] for key in ('companies','candidate_items',
    'potential_header_omissions','elapsed_seconds','protected_unchanged','new_real_calls')}),flush=True)
assert before==after
