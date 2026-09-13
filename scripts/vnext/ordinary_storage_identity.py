"""Keep URL document identity separate from immutable attempt storage names."""
import copy
from pathlib import Path
from urllib.parse import urlsplit

from sec_http import validate_official_sec_url
from .canonical import content_hash
from .sources import source_reference_record
from .batch_workflow import validate_request_attempt_binding


def auditor_document_views(*,repo_root,preparation):
    """Add verified logical references for the frozen auditor business parser.

    Original request rows, proof fields, raw artifacts and references remain
    unchanged. The additional view names the document actually requested in
    the URL and is bound to the same immutable request attempt.
    """
    view=copy.deepcopy(preparation)
    c04=view['resolver_inputs'].get('c04')
    if c04 is None:return view
    arguments=c04['arguments'];aliases={}
    groups=[*arguments.get('current_filings',[]),*arguments.get('prior_filings',[])]
    if arguments.get('prior_sources'):groups.append(arguments['prior_sources'])
    for group in groups:
        for source in group:
            old=source['source_reference'];url=old['source_url']
            validate_official_sec_url(url=url);logical=Path(urlsplit(url).path).name
            if logical==old['document_name']:continue
            proof=validate_request_attempt_binding(repo_root=repo_root,source_url=url,
                content_sha256=source['raw_blob']['raw_asset_id'].split(':',1)[1],
                accession=old['accession'],document_name=logical,request_attempt_id=old['request_attempt_id'],
                require_immutable=True)
            new=source_reference_record(raw_blob=source['raw_blob'],company_id=old['company_id'],
                source_url=url,accession=old['accession'],document_name=logical,
                source_role=old['source_role'],request_attempt_id=old['request_attempt_id'])
            source['source_reference']=new
            aliases[old['source_reference_id']]={'original_reference':old,'logical_reference':new,
                'immutable_request_binding':proof,'request_identity_changed':False}
    if not aliases:return view
    known={r.get('source_reference_id') for r in view['records'] if r['record_type']=='SOURCE_REFERENCE'}
    for alias in aliases.values():
        ref=alias['logical_reference']
        if ref['source_reference_id'] not in known:view['records'].append(ref);known.add(ref['source_reference_id'])
    original=view['input_binding'];body={k:v for k,v in original.items() if k!='input_binding_id'}
    body.update(record_type='CURRENT_GOVERNANCE_DOCUMENT_IDENTITY_BINDING',
        original_governance_binding_id=original['input_binding_id'],
        document_identity_views=list(aliases.values()))
    view['input_binding']={**body,'input_binding_id':content_hash(value=body)}
    return view
