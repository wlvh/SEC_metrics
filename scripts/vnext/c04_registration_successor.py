"""Explicit C04 successor for complete saved 8-K and 8-K12B form families.

The frozen ordinary governance reader and C04 v2 resolver retain their exact
default behavior. This module adds the registered form family only when the
caller selects it, and keeps a missing same-CIK auditor comparison withheld.
"""
from pathlib import Path
from copy import deepcopy
import re

from sec_urls import (accession_document_url, hdr_sgml_url, submissions_file_url,
                      submissions_url)

from .calculator import calculate_observation_metric, withheld_metric_result
from .canonical import content_hash, strict_json_loads
from .deterministic_router import adapt_8k_item_index, source_set_manifest
from .governance_signals import C04_V2_SPEC_PATH
from .normal_governance_input import (_Sources, _filings, _history_index,
                                      prepare_saved_governance_input)
from .normal_source_authority import ROOT
from .observations import structured_observation
from .ordinary_source_authority import verify_ordinary_source_proofs
from .specs import compile_spec_file


EVENT_FORMS = ['8-K', '8-K/A', '8-K12B', '8-K12B/A']
SPEC_PATH = 'catalog/r5/C04_auditor_changes_v3.md'
RESOLVER = 'auditor_change_registration_filings_v3'


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _unique(items, key):
    seen = {}
    for item in items:
        identity = key(item)
        _need(identity not in seen or seen[identity] == item,
              'C04_REGISTRATION_DUPLICATE_IDENTITY_CONFLICT')
        seen[identity] = item
    return list(seen.values())


def _registration_rows(payload, *, inventory_name):
    """Use the frozen form validator, then restore exact saved form labels."""
    block = payload['filings']['recent'] if 'filings' in payload else payload
    if not any(form in {'8-K12B', '8-K12B/A'} for form in block['form']):
        return _filings(payload, inventory_name=inventory_name)
    temporary = deepcopy(payload)
    replacement = (temporary['filings']['recent'] if 'filings' in temporary
                   else temporary)
    replacement['form'] = ['8-K' if form in {'8-K12B', '8-K12B/A'} else form
                           for form in block['form']]
    checked = _filings(temporary, inventory_name=inventory_name)
    return [{**{key: values[row['metadata_origin']['row_index']]
                 for key, values in block.items()},
             'metadata_origin': row['metadata_origin']} for row in checked]


def prepare_c04_registration_case(*, repo_root: Path, company_id: str,
                                  event_forms):
    """Rebuild one explicit native C04 case from already saved, proven sources."""
    _need(event_forms == EVENT_FORMS, 'C04_REGISTRATION_EVENT_FORM_SCOPE_REQUIRED')
    base = prepare_saved_governance_input(repo_root=repo_root,
                                          company_id=company_id)
    binding = base['input_binding']
    _need(binding['metric_input_status']['C04'] == 'PREPARED'
          and not binding['history_alignment_conflicts']
          and 'c04' in base['resolver_inputs'],
          'C04_REGISTRATION_BASE_INPUT_UNRESOLVED')
    selected = binding['selection']
    annual = binding['prepared_annual_input']['table_input']['target_period']
    cik = binding['prepared_annual_input']['entity']
    reader = _Sources(repo_root, company_id, cik)
    current = reader.read(submissions_url(cik=int(cik)),
        role='sec_submissions_inventory', media_type='application/json')
    current_payload = strict_json_loads(text=current['raw_bytes'].decode('utf-8'))
    history = _history_index(current_payload, cik)
    indexed = {item['name']: item for item in history}
    _need(set(selected['history_loaded']) <= set(indexed),
          'C04_REGISTRATION_HISTORY_SELECTION_CHANGED')
    inventories = [(current, current_payload)]
    for name in selected['history_loaded']:
        item = reader.read(submissions_file_url(file_name=name),
            role='sec_submissions_history', media_type='application/json')
        payload = strict_json_loads(text=item['raw_bytes'].decode('utf-8'))
        _need('cik' not in payload or str(payload['cik']).isdigit()
              and int(payload['cik']) == int(cik),
              'C04_REGISTRATION_HISTORY_ENTITY_CHANGED')
        inventories.append((item, payload))
    rows = []
    for inventory, payload in inventories:
        rows.extend(_registration_rows(payload,
            inventory_name=inventory['source_reference']['document_name']))
    accessions = [row['accessionNumber'] for row in rows]
    _need(len(accessions) == len(set(accessions)),
          'C04_REGISTRATION_METADATA_ACCESSIONS_OVERLAP')
    window = {'period_start': annual['period_start'],
              'period_end': annual['period_end']}
    events = sorted((row for row in rows if row['form'] in EVENT_FORMS
                     and window['period_start'] <= row['filingDate'] <= window['period_end']),
                    key=lambda row: (row['filingDate'], row['accessionNumber']))
    old_events = [row for row in events if row['form'] in {'8-K', '8-K/A'}]
    _need(old_events == selected['events'],
          'C04_REGISTRATION_OLD_EVENT_SELECTION_CHANGED')
    needed_history = {item['name'] for item in history
        if item['filingFrom'] <= window['period_end']
        and item['filingTo'] >= window['period_start']}
    _need(needed_history <= set(selected['history_loaded']),
          'C04_REGISTRATION_RELEVANT_HISTORY_NOT_LOADED')

    event_inputs, event_references, event_claims = [], [], []
    for inventory, _ in inventories:
        name = inventory['source_reference']['document_name']
        if inventory is not current and name not in needed_history:
            continue
        documents, references = [], []
        for filing in events:
            if filing['metadata_origin']['inventory_name'] != name:
                continue
            accession = filing['accessionNumber']
            registration = filing['form'] in {'8-K12B', '8-K12B/A'}
            primary = reader.read(accession_document_url(cik=int(cik),
                accession=accession, document_name=filing['primaryDocument']),
                accession=accession,
                role='registration_event_primary' if registration else 'fy_8k_primary',
                media_type='text/html')
            header = reader.read(hdr_sgml_url(cik=int(cik), accession=accession),
                accession=accession,
                role='registration_event_header' if registration else 'fy_8k_header',
                media_type='text/plain')
            declared = re.search(rb'<TYPE>\s*([^\r\n]+)', header['raw_bytes'], re.I)
            _need(declared is not None and
                  declared.group(1).decode('ascii').strip() == filing['form'],
                  'C04_REGISTRATION_HEADER_FORM_CHANGED')
            documents.append({'hdr_bytes': header['raw_bytes'],
                'hdr_source_reference': header['source_reference'],
                'primary_document_bytes': primary['raw_bytes'],
                'primary_source_reference': primary['source_reference']})
            references.extend([header['source_reference'],
                               primary['source_reference']])
        manifest = source_set_manifest(company_id=company_id,
            source_role='fy_8k_item_inventory', form_types=EVENT_FORMS,
            fiscal_or_date_window=window, discovery_policy='PINNED_SUBMISSIONS',
            inventory_source_reference=inventory['source_reference'],
            inventory_bytes=inventory['raw_bytes'],
            ordered_source_references=references,
            cutoff_timestamp_or_pinned_submissions_attempt=
                inventory['source_reference']['request_attempt_id'])
        event_input = {'filing_documents': documents,
            'source_set_manifest': manifest,
            'inventory_source_reference': inventory['source_reference'],
            'inventory_bytes': inventory['raw_bytes']}
        event_claims.extend(adapt_8k_item_index(**event_input))
        event_inputs.append(event_input)
        event_references.extend([inventory['source_reference'], *references])
    _need(bool(event_inputs), 'C04_REGISTRATION_CURRENT_INVENTORY_MISSING')

    from .governance_signals import resolve_c04
    old_spec = compile_spec_file(path=ROOT / C04_V2_SPEC_PATH,
                                 dependency_specs={})
    old_arguments = dict(base['resolver_inputs']['c04']['arguments'])
    old_arguments.update(compiled_spec=old_spec, event_input=None)
    annual_check = resolve_c04(**old_arguments)['selection']
    spec_file = (repo_root / SPEC_PATH if (repo_root / SPEC_PATH).is_file()
                 else ROOT / SPEC_PATH)
    spec = compile_spec_file(path=spec_file, dependency_specs={})
    _need(spec == compile_spec_file(path=ROOT / SPEC_PATH, dependency_specs={})
          and spec['compiled']['quality_rule']['resolver'] == RESOLVER,
          'C04_REGISTRATION_INSTALLED_SPEC_CHANGED')
    matching = [claim for claim in event_claims
                if claim['attributes']['item_code'] == '4.01']
    comparison = annual_check['names_differ']
    prior = annual_check['prior_filing_check']
    if annual_check['reason_code'] == 'C04_AUDITOR_SOURCE_CONFLICT':
        reason, value = 'C04_AUDITOR_SOURCE_CONFLICT', None
    elif matching or comparison is True:
        reason, value = 'PASS', '1'
    elif comparison is False:
        reason, value = 'PASS', '0'
    else:
        reason, value = 'C04_COMPARABLE_AUDITOR_FACTS_MISSING', None
    selection = {key: annual_check[key] for key in (
        'target', 'current_filing_checks', 'selected_current_accession',
        'prior_filing_check', 'prior_filing_checks', 'names_differ')}
    selection.update(resolver=RESOLVER, event_forms=EVENT_FORMS,
        event_source_set_manifest=event_inputs[0]['source_set_manifest'],
        event_source_sets=[{'manifest': item['source_set_manifest'],
            'inventory_source_reference': item['inventory_source_reference']}
            for item in event_inputs],
        event_item_claims=event_claims,
        matched_item_4_01_claim_ids=[claim['verified_claim_id'] for claim in matching],
        same_cik_prior_status=selected['prior_status'], reason_code=reason)
    selection['selection_id'] = content_hash(value=selection)
    target = old_arguments['target']
    observations = []
    if value is None:
        result, trace = withheld_metric_result(compiled_spec=spec,
            target=target, reason_code=reason)
    else:
        annual_refs = [reference for check in
            [*annual_check['current_filing_checks'],
             *annual_check['prior_filing_checks']]
            for reference in check['source_references']]
        all_refs = [*annual_refs, *event_references]
        selected_current = next(check for check in
            annual_check['current_filing_checks']
            if check['accession'] == annual_check['selected_current_accession'])
        anchor = (next(ref for ref in event_references
            if ref['source_reference_id'] == matching[0]['source_reference_id'])
            if matching else selected_current['source_references'][0])
        observation = structured_observation(metric_id='C04',
            semantic_role='auditor_change_flag', company_id=company_id,
            period_start=target['period_start'], period_end=target['period_end'],
            scope=target['scope'], value=value, unit='flag', quality='EXACT',
            source_binding={'raw_asset_id': anchor['raw_asset_id'],
                'source_reference_id': anchor['source_reference_id'],
                'accession': anchor['accession'],
                'document_name': anchor['document_name'],
                'source_role': anchor['source_role'],
                'selection_id': selection['selection_id'],
                'source_reference_ids': [r['source_reference_id'] for r in all_refs],
                'current_accession': annual_check['selected_current_accession'],
                'prior_accession': prior['accession'] if prior else None,
                'matched_item_4_01_claim_ids': selection['matched_item_4_01_claim_ids'],
                'event_source_set_manifest_ids': [item['source_set_manifest']['source_set_manifest_id']
                    for item in event_inputs]})
        result, trace = calculate_observation_metric(compiled_spec=spec,
            target=target, company_traits=[], observation=observation)
        observations.append(observation)

    proofs = _unique([*binding['source_proofs'],
        *binding['prepared_annual_input']['source_proofs'],
        *(entry['proof'] for entry in reader.proofs.values())],
        lambda row: row['request_attempt_id'])
    admission = verify_ordinary_source_proofs(data_root=repo_root,
                                               proofs=proofs)
    records = _unique([*base['records'], *reader.records.values()],
                      lambda row: content_hash(value=row))
    references = [row for row in records if row['record_type'] == 'SOURCE_REFERENCE']
    input_body = {'record_type': 'C04_REGISTRATION_INPUT_BINDING',
        'base_governance_input_binding_id': binding['input_binding_id'],
        'event_forms': EVENT_FORMS, 'event_accessions': [row['accessionNumber'] for row in events],
        'registration_accessions': [row['accessionNumber'] for row in events
            if row['form'] in {'8-K12B', '8-K12B/A'}],
        'event_source_set_manifest_ids': [item['source_set_manifest']['source_set_manifest_id']
            for item in event_inputs],
        'source_proofs': proofs, 'same_cik_prior_status': selected['prior_status'],
        'source_admission': admission, 'production_authorized': False}
    input_binding = {**input_body,
        'input_binding_id': content_hash(value=input_body)}
    period = {'fiscal_year': annual['fiscal_year'],
        'period_start': result['period_start'], 'period_end': result['period_end']}
    return {'kind': 'STRUCTURED', 'primary_metric_id': 'C04',
        'input_binding': {'c04_registration_successor': input_binding},
        'source_records': records, 'references': references,
        'source_proofs': proofs, 'admission': admission,
        'spec_paths': {'C04': SPEC_PATH}, 'compiled_specs': {'C04': spec},
        'target_period': period,
        'expected_records': [*records, *event_claims, *observations, trace, result],
        'results': {'C04': result}, 'traces': {'C04': trace},
        'observations': observations, 'selection': selection}
