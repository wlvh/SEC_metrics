"""Compare paid E01 results with pre-call readings and an independent filing census.

The reference judges each candidate item's own text. This reader counts those
judgements, rather than the route's decisions, and checks the opposite direction:
every candidate named by the saved submissions and SEC headers must be in the
request and reference. Missing headers, an undecided item, a changed window or
a different candidate set cannot grant an acceptance. No network or model call.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'scripts'), str(REPO / 'tools')]


def reference_count(request, references, census, paid):
    """A count only when both directions name exactly the same judged items."""
    items = request['items']
    identifiers = [i['item_id'] for i in items]
    if len(set(identifiers)) != len(identifiers) or set(identifiers) != set(references):
        raise ValueError('E01_REFERENCE_DOES_NOT_COVER_REQUEST_EXACTLY')
    keys = [(i['accession'], i['item_code']) for i in items]
    if len(set(keys)) != len(keys):
        raise ValueError('E01_REQUEST_REPEATS_A_FILING_ITEM')
    for item in items:
        if item['text_sha256'] != 'sha256:' + hashlib.sha256(item['text'].encode()).hexdigest():
            raise ValueError('E01_REFERENCE_ITEM_TEXT_CHANGED')
    if paid['contract_check'] != 'PASSED' or not paid['fits_the_output_ceiling']:
        return None, 'PAID_CONTRACT_NOT_PASSED'
    if paid['disagreements']:
        return None, 'PAID_DECISIONS_DIFFER_FROM_PRECALL_READING'
    if any(set(keys) != set(entries) for entries in census.values()):
        return None, 'INDEPENDENT_CENSUS_AND_REQUEST_DIFFER'
    allowed = {'REPORTS_A_TRANSACTION', 'DOES_NOT_REPORT_A_TRANSACTION',
               'CANNOT_TELL_FROM_THE_ITEM_TEXT'}
    if not set(references.values()) <= allowed:
        raise ValueError('E01_REFERENCE_DECISION_UNKNOWN')
    if 'CANNOT_TELL_FROM_THE_ITEM_TEXT' in references.values():
        return None, 'REFERENCE_ITEM_DOES_NOT_SETTLE_IT'
    return sum(v == 'REPORTS_A_TRANSACTION' for v in references.values()), None


def main():
    from bind_acceptance_readings import identity_for
    from read_e01_candidates import candidate_codes, window_candidates
    from read_event_counts import (_case_input, block_filings, filings_in_index,
                                   history_blocks_reached, restored_root_headers, unique_filings)
    from sec_urls import submissions_file_url, submissions_url
    from vnext.annual_update import saved_source
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--requests-dir', type=Path, required=True)
    parser.add_argument('--paid-check', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--runs-root', type=Path, action='append', required=True)
    parser.add_argument('--closure', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    reference = json.loads(args.reference.read_text())['items']
    paid = {r['request']: r for r in json.loads(args.paid_check.read_text())
            ['contracts_and_e01_d02_references'] if r['request'].startswith('E01-')}
    receipts = [r for root in args.runs_root
                for r in collect_run_receipts(runs_root=root)['receipts']]
    index = index_receipts(receipts=receipts)
    request_index = json.loads((args.requests_dir / 'index.json').read_text())
    header = restored_root_headers(args.source_root)
    rows = {}
    for entry in request_index:
        if entry['metric'] != 'E01' or entry['file'] not in paid:
            continue
        name, company, end = entry['file'], entry['company_id'], entry['report_end']
        request_path = args.requests_dir / (name + '.request.json')
        request = json.loads(request_path.read_text())
        period, cik = _case_input(company_id=company, report_end=end, source_root=args.source_root)
        start = period['period_start']
        if request['window'] != {'period_start': start, 'period_end': end}:
            raise ValueError('E01_INDEPENDENT_WINDOW_DIFFERS_FROM_REQUEST')
        source = saved_source(repo_root=args.source_root, url=submissions_url(cik=int(cik)))
        if source is None:
            raise ValueError('E01_READING_SUBMISSIONS_NOT_SAVED')
        submissions = json.loads(source['raw'])
        filings, blocks = filings_in_index(submissions), {}
        for block_name in history_blocks_reached(submissions, start):
            block = saved_source(repo_root=args.source_root,
                                 url=submissions_file_url(file_name=block_name))
            if block is None:
                raise ValueError('E01_READING_HISTORY_BLOCK_NOT_SAVED')
            blocks[block_name] = block['proof']['request_repo_relative_path']
            filings.extend(block_filings(submissions=submissions, name=block_name, raw=block['raw']))
        seen, unreadable = window_candidates(filings=unique_filings(filings), cik=cik,
                                             start=start, end=end, codes=candidate_codes(), header=header)
        census = {basis: [(f['accession'], item) for f in entries for item in f['candidate_items']]
                  for basis, entries in seen.items()}
        refs = {r['item_id']: r['reference'] for r in reference if r['request'] == name}
        value, reason = reference_count(request, refs, census, paid[name])
        if unreadable:
            value, reason = None, 'INDEPENDENT_CENSUS_HEADERS_NOT_SAVED'
        selected = select_receipt(found=index.get((company, 'E01', end), []), closure=args.closure)
        result = selected['result']
        published = None if result is None or result['value'] is None else str(result['value'])
        verdict = ('MATCH' if reason is None and published == str(value)
                   else 'NO_PUBLISHED_VALUE' if published is None else 'NOT_PROVEN' if reason else 'DIFFERS')
        row = {'company_id': company, 'period_end': end, 'window': [start, end],
               'published': published, 'reference_value': value, 'verdict': verdict, 'reason': reason,
               'candidate_items': census, 'filings': seen, 'headers_not_saved': unreadable,
               'filings_in_window': [f['accession'] for f in seen['filing_date']],
               'history_blocks': blocks, 'judged_items': refs, 'ledger_digest': entry['ledger_digest'],
               'request_file_sha256': hashlib.sha256(request_path.read_bytes()).hexdigest(),
               'reading_direction': ['each requested item against pre-call reading',
                                     'all saved window headers back to request and reference']}
        if published is not None:
            identity, refusal = identity_for(position={
                'company_id': company, 'metric_id': 'E01', 'period_end': end, 'published': published,
                'reading_filings': row['filings_in_window'], 'reading_window': [start, end],
                'filings_are_the_whole_set': True}, index=index, closure=args.closure)
            if refusal:
                raise ValueError('E01_PAID_READING_IDENTITY_NOT_RECORDED:' + refusal)
            identity['established_by'] = 'RECORDED_AT_READING_TIME'
            row['checked_identity'] = identity
        rows[name] = row
        print(name, verdict, reason, flush=True)
    body = {'record_type': 'ISSUE_47_E01_PRECALL_REFERENCE_AND_CENSUS_READ',
            'reader': 'tools/read_e01_confirmed.py', 'requirement_closure_hash': args.closure,
            'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
            'paid_check_sha256': hashlib.sha256(args.paid_check.read_bytes()).hexdigest(),
            'per_position': rows, 'calls': [0, 0, 0],
            'limitations': 'Pre-call development judgements, not independent business review; '
                           'only declared candidate item codes; attached exhibits are not read.'}
    args.output.write_text(json.dumps(body, ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
