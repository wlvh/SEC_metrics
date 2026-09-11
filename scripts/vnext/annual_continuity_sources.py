"""Saved SEC inputs and explicitly simulated historical list visibility.

The raw SEC body and its request evidence never change. A visibility receipt is
a derived test input, not a new SEC response or a source of table answers.
"""
import copy
from datetime import date
from .annual_adoption import need, record
from .canonical import content_hash, parse_utc_timestamp


def visible_submissions(payload, visibility, source_proof):
    if visibility is None:
        return payload, None
    need(type(visibility) is dict and set(visibility) == {'record_type', 'as_of_utc'}
         and visibility['record_type'] == 'SIMULATED_HISTORICAL_SUBMISSIONS_VISIBILITY',
         'CONTINUITY_VISIBILITY_FIELDS')
    cutoff = parse_utc_timestamp(value=visibility['as_of_utc']).date()
    recent = payload['filings']['recent']
    lengths = {len(values) for values in recent.values()}
    need(len(lengths) == 1, 'CONTINUITY_SUBMISSIONS_COLUMNS_DIFFER')
    dates = []
    for value in recent['filingDate']:
        need(type(value) is str and date.fromisoformat(value).isoformat() == value,
             'CONTINUITY_VISIBILITY_FILING_DATE_UNKNOWN')
        dates.append(date.fromisoformat(value))
    selected = [i for i, value in enumerate(dates) if value <= cutoff]
    transformed = copy.deepcopy(payload)
    transformed['filings']['recent'] = {key: [values[i] for i in selected]
                                          for key, values in recent.items()}
    # Supplemental history is still checked by the unchanged selector; no shard
    # is silently dropped just to make a chosen fiscal year pass.
    receipt = record({'record_type': 'DERIVED_SUBMISSIONS_VISIBILITY',
        'evidence_scope': 'SIMULATED_HISTORICAL_VISIBILITY_NOT_ONLINE_DISCOVERY',
        'visibility': visibility, 'original_source_proof': source_proof,
        'original_payload_id': content_hash(value=payload),
        'visible_payload_id': content_hash(value=transformed),
        'visible_row_count': len(selected), 'raw_sec_bytes_modified': False}, 'visibility_id')
    return transformed, receipt


def select_saved_input(data_root, visibility=None):
    from sec_urls import submissions_url
    from . import annual_input, annual_update as update
    company = update.supported_company(repo_root=data_root)
    source = update.saved_source(repo_root=data_root,
        url=submissions_url(cik=int(company['primary_cik'])))
    need(source is not None, 'SUBMISSIONS_SOURCE_MISSING')
    payload, receipt = visible_submissions(annual_input._json(raw=source['raw']), visibility, source['proof'])
    filing, _ = update._select_filing(company=company, payload=payload)
    prepared = annual_input.prepare_annual_input(repo_root=data_root,
        company_id=company['company_id'], fiscal_year=int(filing['reportDate'][:4]))
    need(prepared['table_input']['accession'] == filing['accessionNumber'], 'CONTINUITY_SELECTED_INPUT_CHANGED')
    return prepared, {'filing': update._identity(company=company, filing=filing),
        'submissions_saved_at_utc': source['saved_at_utc'], 'visibility': receipt}


def frozen_foundation_receipts(head='HEAD'):
    """Read exact historical receipt content, separately from active mirrors.

    The frozen Requirement supplies the content identity. If a root mirror has
    advanced, the committed complete publication still contains that historical
    receipt. No embedded Python is imported and no old Result is selected here.
    """
    import json
    from .annual_adoption import git
    from .canonical import sha256_bytes
    foundation=json.loads(git('show',head+':requirements/issue_15_v1/foundation_verification_receipt.json'))
    package=None;result={}
    for entry in foundation['receipt_bindings']:
        path=entry['path'];raw=git('show',head+':'+path);locator=path
        if len(raw)!=entry['size'] or sha256_bytes(content=raw)!=entry['sha256']:
            if package is None:
                pointer=json.loads(git('show',head+':outputs/active_publication.json'))
                prefix='outputs/publications/'+pointer['publication_id']+'/'
                manifest=json.loads(git('show',head+':'+prefix+'publication_manifest.json'))
                package=(prefix,manifest)
            prefix,manifest=package
            matches=[r for r in manifest['files'] if r['sha256']==entry['sha256'] and r['size']==entry['size']
                     and r['path'].endswith('/'+path)]
            need(bool(matches),'CONTINUITY_FROZEN_FOUNDATION_RECEIPT_MISSING: '+path)
            locator=prefix+sorted(matches,key=lambda r:r['path'])[0]['path']
            raw=git('show',head+':'+locator)
        need(len(raw)==entry['size'] and sha256_bytes(content=raw)==entry['sha256'],
             'CONTINUITY_FROZEN_FOUNDATION_RECEIPT_CHANGED: '+path)
        result[path]={'bytes':raw,'commit':head,'repository_locator':locator,'sha256':entry['sha256'],'size':entry['size']}
    return result
