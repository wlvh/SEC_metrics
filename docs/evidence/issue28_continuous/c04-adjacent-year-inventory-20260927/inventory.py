"""Read-only #28 saved annual body inventory; no source admission credit."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATA = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13/source-inputs')
registry = list(csv.DictReader((ROOT/'config/company_registry.csv').open(newline='')))
rows = list(csv.DictReader((DATA/'evidence/requests_log.csv').open(newline='')))
good = [row for row in rows if row['status_code'] == '200' and not row['error']]
latest = {row['source_url']: row for row in good}
summary = []
for company in registry:
    cik = int(company['primary_cik'])
    url = f'https://data.sec.gov/submissions/CIK{cik:010d}.json'
    candidates = [row for row in good if row['source_url'] == url]
    if not candidates:
        summary.append({'company_id': company['company_id'],
                        'submissions_saved': False})
        continue
    current = candidates[-1]
    raw = (DATA/current['repo_relative_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == current['content_sha256']
    submissions = json.loads(raw)
    recent = submissions['filings']['recent']
    annuals = []
    for index, form in enumerate(recent['form']):
        if form != '10-K':
            continue
        accession = recent['accessionNumber'][index]
        document = recent['primaryDocument'][index]
        primary = (f'https://www.sec.gov/Archives/edgar/data/{cik}/'
                   f'{accession.replace("-", "")}/{document}')
        selected = latest.get(primary)
        saved = selected is not None and (DATA/selected['repo_relative_path']).is_file()
        if saved:
            body = (DATA/selected['repo_relative_path']).read_bytes()
            assert hashlib.sha256(body).hexdigest() == selected['content_sha256']
        annuals.append({'accession': accession,
            'filing_date': recent['filingDate'][index],
            'report_date': recent['reportDate'][index],
            'primary_url': primary, 'primary_body_in_log_and_hash_matched': saved})
        if len(annuals) >= 3:
            break
    adjacent = len(annuals) >= 2 and all(
        item['primary_body_in_log_and_hash_matched'] for item in annuals[:2])
    newer_filing = annuals[0]['filing_date'] if annuals else None
    prior_metadata = any(row['timestamp_utc'][:10] < newer_filing
        for row in candidates) if newer_filing else False
    summary.append({'company_id': company['company_id'],
        'submissions_saved': True,
        'saved_submissions_count': len(candidates),
        'adjacent_two_annual_bodies_present': adjacent,
        'pre_newer_filing_submissions_snapshot_in_this_root': prior_metadata,
        'annuals': annuals[:2]})
print(json.dumps({'record_type': 'ISSUE28_SAVED_ANNUAL_ADJACENCY_INVENTORY',
    'source_root': str(DATA), 'read_only': True,
    'all_ten_companies_checked': len(summary) == 10,
    'content_sha256_checked_for_selected_saved_blobs': True,
    'source_admission_or_complete_c04_run_proven': False,
    'new_provider_paid_sec_calls': [0, 0, 0],
    'companies': summary}, ensure_ascii=False, indent=2))
