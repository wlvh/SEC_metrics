"""Explicit E01 V2 input: reconcile each saved 8-K body with its header.

This does not decide whether an item reports M&A or count announcements. It
reuses the current source-discovery and SEC-proof path, then binds every 1.01,
2.01 and 8.01 item's own text. No old E01 Result enters this input.
"""
from pathlib import Path

from sec_urls import submissions_url
from .annual_amendment_scope import prepare_saved_amendment_input
from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file
from .deterministic_router import load_event_route_catalog, _hdr_item_codes
from .e01_item_text_28_v1 import item_text, PEER_SOURCE_SHA
from .e01_header_document_guard_28_v1 import (
    check_document_header_items, PEER_PATCH_SHA, POLICY)
from .normal_annual_input_v2 import prepare_saved_annual_input, exact_json_value
from .normal_governance_input import _Sources
from .normal_zero_ai_results import _event_sources, _registered_event_sources
from .ordinary_source_authority import verify_ordinary_source_proofs
from .public_projection import event_target_period
from .sources import resolve_repository_file


CANDIDATE_CODES = frozenset(('1.01', '2.01', '8.01'))
RECORD_TYPE = 'ORDINARY_E01_SOURCE_BOUND_ITEM_TEXT_V2'


def _need(condition, reason):
    if not condition:
        raise ValueError('ORDINARY_E01_ITEM_TEXT_' + reason)


def prepare_current_e01_item_text(*, repo_root: Path, company_id: str):
    """Rebuild all saved candidate items; grant no semantic or Result credit."""
    root = Path(repo_root)
    prepared = prepare_saved_annual_input(repo_root=root, company_id=company_id)
    verify_ordinary_source_proofs(data_root=root, proofs=prepared['source_proofs'])
    catalog = load_event_route_catalog(repo_root=root)
    route = catalog['routes']['E01']
    codes = set(route['direct_item_codes']) | {
        rule['item_code'] for rule in route['keyword_item_rules']}
    _need(codes == CANDIDATE_CODES, 'APPROVED_ITEM_CODE_SET_CHANGED')
    period = prepared['table_input']['target_period']
    registered = prepared['subject_policy']['mode'] == 'SUCCESSOR_REGISTRANT_ONLY'
    if registered:
        projection = strict_json_file(path=root/'catalog/zero_ai_public_projection.json')
        period = event_target_period(target_period=period,
            continuity_status='successor_predecessor', catalog=projection)
    else:
        _need(prepared['subject_policy']['mode'] == 'CONTINUOUS_PRIMARY',
              'SUBJECT_SCOPE_UNSUPPORTED')
    reader = _Sources(root, company_id, prepared['entity'])
    inventory = reader.read(submissions_url(cik=int(prepared['entity'])),
        role='sec_submissions_inventory',media_type='application/json')
    reader.primary(prepared['filing'])
    amendment = None
    if prepared['amendments']:
        amendment = prepare_saved_amendment_input(repo_root=root,
            company_id=company_id,input_class='FISCAL_EVENT_WINDOW')
        _need(amendment['prepared_input'] == prepared.get('original_input', prepared)
              and amendment['decision'] == 'INPUT_PROPERTY_PROVEN',
              'AMENDMENT_EVENT_WINDOW_UNPROVEN')
    if registered:
        claims, sets, filings, registered_scope = _registered_event_sources(
            repo_root=root, reader=reader, prepared=prepared,
            inventory=inventory, period=period)
    else:
        claims, sets, filings = _event_sources(
            repo_root=root, reader=reader, prepared=prepared,
            inventory=inventory)
        registered_scope = None
    references = {row['source_reference_id']:row for row in reader.records.values()
                  if row['record_type'] == 'SOURCE_REFERENCE'}
    blobs = {row['raw_asset_id']:row for row in reader.records.values()
             if row['record_type'] == 'RAW_BLOB'}
    # All discovered filings are checked, including those with no header claims.
    raw_by_reference = {}
    checks = []
    for filing in sorted(filings, key=lambda row: row['accessionNumber']):
        accession = filing['accessionNumber']
        pair = {}
        for role in ('fy_8k_primary', 'fy_8k_header'):
            matches = [reference for reference in references.values()
                if reference['source_role'] == role
                and reference['accession'] == accession
                and reference['company_id'] == company_id]
            _need(len(matches) == 1, 'FILING_SOURCE_ROLE_NOT_UNIQUE:' + accession + ':' + role)
            reference = matches[0]
            blob = blobs[reference['raw_asset_id']]
            raw = resolve_repository_file(repo_root=root,
                repo_relative_path=blob['storage_uri']).read_bytes()
            _need(len(raw) == blob['byte_length'] and
                  'sha256:' + sha256_bytes(content=raw) == reference['raw_asset_id'],
                  'FILING_ORIGINAL_BYTES_CHANGED:' + accession + ':' + role)
            pair[role] = (reference, raw)
            raw_by_reference[reference['source_reference_id']] = raw
        primary, raw = pair['fy_8k_primary']
        header, header_raw = pair['fy_8k_header']
        listed = _hdr_item_codes(raw_bytes=header_raw)
        filing_claims = [claim for claim in claims
                        if claim['attributes']['accession'] == accession]
        _need({claim['attributes']['item_code'] for claim in filing_claims} == set(listed)
              and all(claim['attributes']['primary_source_reference_id']
                      == primary['source_reference_id'] for claim in filing_claims),
              'HEADER_CLAIM_SET_CHANGED:' + accession)
        headed = check_document_header_items(raw_bytes=raw,
            listed_item_codes=listed, candidate_item_codes=CANDIDATE_CODES,
            accession=accession)
        checks.append({'accession':accession,
            'primary_source_reference_id':primary['source_reference_id'],
            'primary_raw_asset_id':primary['raw_asset_id'],
            'header_source_reference_id':header['source_reference_id'],
            'header_raw_asset_id':header['raw_asset_id'],
            'listed_item_codes':sorted(listed), 'headed_item_codes':headed})
    items = []
    for claim in sorted(claims, key=lambda row: (
            row['attributes']['accession'], row['attributes']['item_code'],
            row['verified_claim_id'])):
        attributes = claim['attributes']
        if attributes['item_code'] not in CANDIDATE_CODES:
            continue
        reference = references[attributes['primary_source_reference_id']]
        blob = blobs[reference['raw_asset_id']]
        _need(reference['source_role'] == 'fy_8k_primary'
              and reference['company_id'] == company_id
              and reference['accession'] == attributes['accession'],
              'PRIMARY_CLAIM_SOURCE_CHANGED')
        _need(reference['source_reference_id'] in raw_by_reference,
              'CLAIM_OUTSIDE_DISCOVERED_FILINGS')
        raw = raw_by_reference[reference['source_reference_id']]
        text = item_text(raw_bytes=raw,item_code=attributes['item_code'])
        body = {'accession':attributes['accession'],
                'item_code':attributes['item_code'],
                'verified_claim_id':claim['verified_claim_id'],
                'primary_source_reference_id':reference['source_reference_id'],
                'primary_raw_asset_id':reference['raw_asset_id'],
                'item_text':text}
        items.append({**body,'item_input_id':content_hash(value=body)})
    ids = [(item['accession'],item['item_code']) for item in items]
    _need(len(set(ids)) == len(ids), 'DUPLICATE_CANDIDATE_ITEM')
    proofs = list({content_hash(value=proof):proof
        for proof in [*prepared['source_proofs'],
                      *(entry['proof'] for entry in reader.proofs.values()),
                      *(amendment['source_proofs'] if amendment else [])]}.values())
    admission = verify_ordinary_source_proofs(data_root=root, proofs=proofs)
    source_records = list(reader.records.values())
    if amendment:
        source_records = list({content_hash(value=row):row for row in
            [*source_records,*amendment['source_records']]}.values())
    body = {'record_type':RECORD_TYPE,'company_id':company_id,
        'target_period':period,'prepared_input':prepared,
        'amendment_input':amendment,'registered_event_scope':registered_scope,
        'candidate_item_codes':sorted(CANDIDATE_CODES),
        'complete_event_source_sets':sets,'event_filings':filings,
        'all_header_claim_ids':[claim['verified_claim_id'] for claim in claims],
        'source_records':source_records,'source_proofs':proofs,
        'source_admission':admission,'items':items,
        'item_reader_source_commit':PEER_SOURCE_SHA,
        'item_reader_sha256':sha256_file(path=Path(__file__).with_name(
            'e01_item_text_28_v1.py')),
        'source_adapter_sha256':sha256_file(path=Path(__file__)),
        'header_document_checks':checks,
        'header_document_guard':{'policy':POLICY,'source_patch_commit':PEER_PATCH_SHA,
            'module_sha256':sha256_file(path=Path(__file__).with_name(
                'e01_header_document_guard_28_v1.py'))},
        'semantic_confirmation_status':'NOT_PERFORMED',
        'candidate_count':len(items),'metric_result_created':False,
        'native_run_status':'NOT_CREATED','production_authorized':False,
        'calls':{'provider':0,'paid':0,'sec':0}}
    body = exact_json_value(body)
    return {**body,'input_id':content_hash(value=body)}


def verify_current_e01_item_text(*, candidate, repo_root: Path, company_id: str):
    rebuilt = prepare_current_e01_item_text(repo_root=repo_root,
                                            company_id=company_id)
    _need(candidate == rebuilt, 'SOURCE_REPLAY_CHANGED')
    return rebuilt


def install_current_e01_item_text(*, source_root: Path, data_root: Path,
                                  company_id: str):
    """Install the exact source and current runtime for independent cold read.

    This reuses the ordinary Run installer, but creates no Run, result or
    answer. The destination must be a new external directory.
    """
    from .normal_run_v3 import (_external, _install_case_inputs,
                                REQUIREMENT_ID)
    from .normal_source_authority import ROOT
    from .requirements import load_requirement_snapshot

    source = Path(source_root).resolve()
    output = _external(Path(data_root))
    _need(not output.exists() and output != source
          and output not in source.parents and source not in output.parents,
          'OUTPUT_ROOT_OVERLAP_OR_EXISTS')
    prepared = prepare_current_e01_item_text(repo_root=source,
                                              company_id=company_id)
    requirement = load_requirement_snapshot(
        snapshot_dir=ROOT/'requirements'/REQUIREMENT_ID)
    _install_case_inputs(data_root=output, source_root=source,
        company_id=company_id,
        case={'source_proofs':prepared['source_proofs'],
              'primary_metric_id':'E01'},requirement=requirement)
    rebuilt = prepare_current_e01_item_text(repo_root=output,
                                             company_id=company_id)
    _need(prepared['input_id'] == rebuilt['input_id'],
          'INSTALLED_SOURCE_OR_CODE_CHANGED')
    return rebuilt
