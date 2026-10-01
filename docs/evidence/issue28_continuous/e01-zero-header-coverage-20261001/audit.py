"""Bound four E01 zero rows to saved 8-K metadata and original header items."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import socket
import sys
from unittest.mock import patch

CODE = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
LEDGER = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
sys.path[:0] = [str(CODE), str(CODE/'scripts')]

from vnext.continuous_call_policy import REQUIREMENT_ID
from vnext.normal_run_v3 import prepare_case
from vnext.ordinary_processing_source import verify_processing_source
from vnext.requirements import load_requirement_snapshot


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def metadata_rows(root, proofs, start, end):
    rows = []
    boundaries = []
    for proof in proofs:
        if ('data.sec.gov/submissions/' not in proof['source_url']
                or proof.get('accession')):
            continue
        raw = json.loads((root/proof['request_repo_relative_path']).read_text())
        recent = raw.get('filings', {}).get('recent', raw)
        for i, form in enumerate(recent['form']):
            if form.startswith('8-K') and start <= recent['filingDate'][i] <= end:
                rows.append({'accession': recent['accessionNumber'][i],
                    'form': form, 'filing_date': recent['filingDate'][i],
                    'metadata_source_sha256': proof['content_sha256']})
        for entry in raw.get('filings', {}).get('files', []):
            if not any(p['document_name'] == entry['name'] for p in proofs):
                continue
            matched = next(p for p in proofs if p['document_name'] == entry['name'])
            shard = json.loads((root/matched['request_repo_relative_path']).read_text())
            values = shard.get('filings', {}).get('recent', shard)['filingDate']
            boundaries.append({'name': entry['name'],
                'declared_from': entry['filingFrom'],
                'declared_to': entry['filingTo'],
                'declared_count': entry['filingCount'],
                'saved_from': min(values), 'saved_to': max(values),
                'saved_count': len(values),
                'source_sha256': matched['content_sha256']})
    return rows, boundaries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--processing-root', required=True, type=Path)
    args = parser.parse_args()
    root = args.processing_root.resolve()
    requirement = load_requirement_snapshot(
        snapshot_dir=CODE/'requirements'/REQUIREMENT_ID)
    originals = {'claims': LEDGER/'claims.jsonl',
        'source_log': LEDGER/'source-inputs/evidence/requests_log.csv',
        'active': CODE/'outputs/active_publication.json'}
    before = {key: digest(path) for key, path in originals.items()}
    with patch.object(socket.socket, 'connect',
            side_effect=AssertionError('NETWORK_FORBIDDEN')), \
         patch.object(socket, 'getaddrinfo',
            side_effect=AssertionError('DNS_FORBIDDEN')):
        verified = verify_processing_source(
            acquisition_root=LEDGER/'source-inputs',
            processing_root=root, requirement=requirement)
        companies = []
        for company in ('marriott_international', 'pfizer',
                        'enphase_energy', 'jpmorgan_chase'):
            case = prepare_case(data_root=root, company_id=company,
                                metric_id='E01')
            result = case['results']['E01']
            assert result['value'] == '0'
            start, end = result['period_start'], result['period_end']
            metadata, boundaries = metadata_rows(
                root, case['source_proofs'], start, end)
            headers = []
            for proof in case['source_proofs']:
                # The immutable storage name may be e.g. 0013.body. The
                # authenticated source URL, not its local name, is the header.
                if not proof['source_url'].endswith('.hdr.sgml'):
                    continue
                raw = (root/proof['request_repo_relative_path']).read_text()
                items = re.findall(r'^<ITEMS>([^\n]+)', raw, re.M)
                headers.append({'accession': proof['accession'],
                    'items': items, 'source_sha256': proof['content_sha256'],
                    'storage_name': proof['document_name']})
            metadata_ids = [row['accession'] for row in metadata]
            header_ids = [row['accession'] for row in headers]
            assert len(metadata_ids) == len(set(metadata_ids))
            assert len(header_ids) == len(set(header_ids))
            assert set(metadata_ids) == set(header_ids)
            assert not [row for row in headers
                if set(row['items']) & {'1.01', '2.01'}]
            companies.append({'company_id': company,
                'period_start': start, 'period_end': end,
                'current_prepared_result_id': result['result_id'],
                'metadata_8k_count': len(metadata),
                'selected_header_count': len(headers),
                'metadata_forms': dict(Counter(row['form'] for row in metadata)),
                'metadata_8k': metadata, 'selected_headers': headers,
                'history_descriptor_comparisons': boundaries,
                'all_saved_metadata_8k_headers_selected': True,
                'selected_item_1_01_or_2_01_count': 0})
    after = {key: digest(path) for key, path in originals.items()}
    assert before == after
    body = {'record_type': 'ISSUE28_E01_FOUR_ZERO_HEADER_COVERAGE_AUDIT',
        'tested_product_head': '3d7adf920125a588a3c19f8f14baf23e421cdba2',
        'source_snapshot_id': verified['snapshot_id'],
        'requirement_closure_hash': requirement['requirement_closure_hash'],
        'companies': companies, 'new_real_calls': [0, 0, 0],
        'originals_unchanged': before == after,
        'business_meaning_decided': False,
        'formal_adoption': False, 'all390_acceptance': False}
    (HERE/'audit.json').write_text(json.dumps(body, indent=2,
        ensure_ascii=False)+'\n')
    for row in companies:
        print(row['company_id'], row['metadata_8k_count'],
            row['selected_header_count'],
            row['selected_item_1_01_or_2_01_count'], flush=True)


if __name__ == '__main__':
    main()
