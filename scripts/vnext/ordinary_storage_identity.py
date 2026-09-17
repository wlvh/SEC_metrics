"""Keep URL document identity separate from immutable attempt storage names."""
import copy
from pathlib import Path
from urllib.parse import urlsplit

from sec_http import validate_official_sec_url
from .canonical import content_hash
from .sources import source_reference_record
from .batch_workflow import validate_request_attempt_binding
from .deterministic_router import source_set_manifest


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
    blobs={r['raw_asset_id']:r for r in view['records'] if r['record_type']=='RAW_BLOB'}
    def logical_reference(old,blob):
        url=old['source_url'];validate_official_sec_url(url=url)
        logical=Path(urlsplit(url).path).name
        if logical==old['document_name']:return old
        proof=validate_request_attempt_binding(repo_root=repo_root,source_url=url,
            content_sha256=blob['raw_asset_id'].split(':',1)[1],accession=old['accession'],
            document_name=logical,request_attempt_id=old['request_attempt_id'],require_immutable=True)
        new=source_reference_record(raw_blob=blob,company_id=old['company_id'],source_url=url,
            accession=old['accession'],document_name=logical,source_role=old['source_role'],
            request_attempt_id=old['request_attempt_id'])
        aliases[old['source_reference_id']]={'original_reference':old,'logical_reference':new,
            'immutable_request_binding':proof,'request_identity_changed':False}
        return new
    groups=[*arguments.get('current_filings',[]),*arguments.get('prior_filings',[])]
    if arguments.get('prior_sources'):groups.append(arguments['prior_sources'])
    for group in groups:
        for source in group:
            source['source_reference']=logical_reference(source['source_reference'],source['raw_blob'])
    manifest_views=[]
    event=arguments.get('event_input')
    for item in [event,*event.get('history_inputs',[])] if event else []:
        old=item['inventory_source_reference'];new=logical_reference(old,blobs[old['raw_asset_id']])
        if new==old:continue
        original_manifest=item['source_set_manifest']
        references=[ref for document in item['filing_documents']
            for ref in [document['hdr_source_reference'],document['primary_source_reference']]]
        manifest=source_set_manifest(company_id=original_manifest['company_id'],
            source_role=original_manifest['source_role'],form_types=original_manifest['form_types'],
            fiscal_or_date_window=original_manifest['fiscal_or_date_window'],
            discovery_policy=original_manifest['discovery_policy'],inventory_source_reference=new,
            inventory_bytes=item['inventory_bytes'],ordered_source_references=references,
            cutoff_timestamp_or_pinned_submissions_attempt=original_manifest['cutoff_timestamp_or_pinned_submissions_attempt'])
        identity_fields={'source_set_manifest_id','inventory_source_reference_id'}
        if ({k:v for k,v in manifest.items() if k not in identity_fields}
                != {k:v for k,v in original_manifest.items() if k not in identity_fields}):
            raise ValueError('DOCUMENT_IDENTITY_SOURCE_SET_CONTENT_CHANGED')
        item['inventory_source_reference']=new;item['source_set_manifest']=manifest
        manifest_views.append({'original_manifest':original_manifest,'logical_inventory_manifest':manifest})
    if not aliases:return view
    known={r.get('source_reference_id') for r in view['records'] if r['record_type']=='SOURCE_REFERENCE'}
    for alias in aliases.values():
        ref=alias['logical_reference']
        if ref['source_reference_id'] not in known:view['records'].append(ref);known.add(ref['source_reference_id'])
    original=view['input_binding'];body={k:v for k,v in original.items() if k!='input_binding_id'}
    body.update(record_type='CURRENT_GOVERNANCE_DOCUMENT_IDENTITY_BINDING',
        original_governance_binding_id=original['input_binding_id'],
        document_identity_views=list(aliases.values()))
    if manifest_views:body['inventory_manifest_views']=manifest_views
    view['input_binding']={**body,'input_binding_id':content_hash(value=body)}
    return view
