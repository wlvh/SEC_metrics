"""Read exact saved HTML and replay its explicit development source candidate."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from vnext.canonical import sha256_bytes
from vnext.sources import source_reference_record
from vnext.visible_auditor_source import (inspect_visible_auditor_report,
                                         verify_visible_auditor_report)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--sha256', required=True)
    p.add_argument('--url', required=True)
    p.add_argument('--accession', required=True)
    p.add_argument('--company', required=True)
    p.add_argument('--cik', required=True)
    p.add_argument('--period-end', required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--registrant-binding', default='NATIVE_NAME_ONLY',
                   choices=['NATIVE_NAME_ONLY', 'COVER_CHARTER_NAME'])
    a = p.parse_args()
    raw = a.source.read_bytes()
    if sha256_bytes(content=raw) != a.sha256:
        raise ValueError('SAVED_REPORT_BYTES_DIFFER')
    blob = {'record_type': 'RAW_BLOB', 'raw_asset_id': 'sha256:' + a.sha256,
        'byte_length': len(raw), 'media_type': 'text/html',
        'storage_uri': str(a.source)}
    # New development inspection only, not an old GET/Run re-signature.
    ref = source_reference_record(raw_blob=blob, company_id=a.company,
        source_url=a.url, accession=a.accession,
        document_name=a.url.rsplit('/', 1)[-1], source_role='target_primary',
        request_attempt_id='development-visible-report-inspection')
    args = dict(raw_bytes=raw, raw_blob=blob, source_reference=ref,
        expected_company_id=a.company, expected_cik=a.cik,
        expected_period_end=a.period_end, registrant_binding=a.registrant_binding)
    start = time.perf_counter()
    inspection = inspect_visible_auditor_report(**args)
    elapsed = time.perf_counter() - start
    start = time.perf_counter()
    verify_visible_auditor_report(inspection=inspection, **args)
    rebuild = time.perf_counter() - start
    result = {'source_sha256': a.sha256, 'inspection': inspection,
        'inspection_seconds': elapsed, 'source_rebuild_seconds': rebuild,
        'SEC_calls': 0, 'provider_calls': 0, 'paid_calls': 0,
        'result_created': False}
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(a.output), 'status': inspection['status'],
        'reports': [{'purpose': r['report_purpose'], 'status': r['status'],
                     'signatures': [s['text'] for s in r['signatures']],
                     'reasons': r['reasons']} for r in inspection['reports']],
        'seconds': elapsed, 'rebuild_seconds': rebuild}, ensure_ascii=False))


if __name__ == '__main__':
    main()
