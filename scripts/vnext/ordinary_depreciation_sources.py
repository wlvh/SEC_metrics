"""Source-only D&A reports from explicitly selected annual originals.

No Company Facts observations, supplied amounts or company/year selection are
inputs. Dimensioned reports remain dimensioned; none certifies complete EBITDA.
Old ordinary income preparation and its namespace policy are unchanged.
"""
from datetime import date, datetime
from decimal import Decimal
import re
from sec_urls import accession_document_url

from .canonical import content_hash, sha256_bytes
from .composite_scope import index_source_structure
from .deterministic_router import parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex
from .governance_signals import _qname, _source_value
from .r5_b06_scope import precision_choice
from .text_results_v2 import _CAPABILITY_POLICY, _ReportedFactMetadata, _verified_context


CONCEPTS = {'Depreciation', 'AmortizationOfIntangibleAssets',
    'DepreciationDepletionAndAmortization', 'DepreciationAndAmortization',
    'DepreciationAmortizationAndAccretionNet'}
USD = {'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')], 'divided': False}
NUMERIC_POLICY = {key: _CAPABILITY_POLICY[key] for key in (
    'numeric_inline_namespaces', 'dot_decimal_supported_lexical_pattern',
    'unformatted_decimal_lexical_pattern')}


def _need(condition, reason):
    if not condition:
        raise ValueError('DEPRECIATION_SOURCE_' + reason)


def _scope(context):
    return (tuple((x['scheme'], str(int(x['value']))) for x in context['identifiers']),
        tuple(sorted((x['kind'], x['value']) for x in context['period_fields'])),
        tuple(sorted((tuple(x['dimension_qname']), tuple(x['member_qname']))
                     for x in context['dimensions'])))


def _numeric_value(fact, info):
    """Check the source representation before the shared amount normalizer."""
    tag_uri, tag_name = _qname(info['tag'], info['namespaces'])
    inline = tag_uri in NUMERIC_POLICY['numeric_inline_namespaces'] and tag_name == 'nonfraction'
    xml = (tag_uri == info['concept'][0]
           and tag_name.casefold() == info['concept'][1].casefold())
    _need(inline or xml, 'NUMERIC_TAG_NOT_SUPPORTED')
    nil = [v for k, v in info['attrs'].items()
           if _qname(k, info['namespaces']) == ('http://www.w3.org/2001/XMLSchema-instance', 'nil')]
    _need(not nil or nil == ['false'] or nil == ['0'], 'NIL_OR_INVALID_SOURCE_VALUE')
    transform = info['attrs'].get('format', '')
    if xml:
        _need(not transform and info['attrs'].get('scale', '0') == '0'
              and not info['attrs'].get('sign'), 'XML_NUMERIC_ATTRIBUTES_NOT_SUPPORTED')
    local = _qname(transform, info['namespaces'])[1] if transform else ''
    if local not in {'fixed-zero', 'numdash'}:
        pattern = NUMERIC_POLICY['dot_decimal_supported_lexical_pattern'] if transform else NUMERIC_POLICY['unformatted_decimal_lexical_pattern']
        _need(re.fullmatch(pattern, str(fact['text']).strip()) is not None, 'NUMERIC_LEXICAL_FORM_NOT_SUPPORTED')
    try:
        return _source_value(fact, info)
    except ValueError as error:
        raise ValueError('DEPRECIATION_SOURCE_NUMERIC_VALUE_NOT_SUPPORTED:' + str(error)) from error


def _annual_identity(parsed, meta, *, filing, entity, period, namespaces):
    """Explicit accepted DEI namespaces include older official quarter editions."""
    def dei(name):
        facts = [f for f in parsed.facts if meta.facts[f['ordinal']]['concept'][0] in namespaces
                 and meta.facts[f['ordinal']]['concept'][1].casefold() == name.casefold()]
        _need(bool(facts), 'DEI_MISSING:' + name)
        values = {f['text'].strip() for f in facts}
        _need(len(values) == 1, 'DEI_CONFLICT:' + name)
        for fact in facts:
            c = parsed.contexts[fact['context_ref']]
            proof = _verified_context(native={**c, 'dimensions': dict(c['dimensions'])}, metadata=meta)
            _need(not proof['dimensions'] and int(c['entity_identifier']) == int(entity)
                  and c['period_start'] == period['period_start']
                  and c['period_end'] == period['period_end'], 'DEI_SCOPE:' + name)
        return next(iter(values))
    end = dei('DocumentPeriodEndDate')
    if end != period['period_end']:
        end = datetime.strptime(end, '%B %d, %Y').date().isoformat()
    _need(dei('DocumentType') == filing['form'] == '10-K'
          and dei('DocumentFiscalPeriodFocus') == 'FY'
          and dei('AmendmentFlag').casefold() == 'false'
          and int(dei('EntityCentralIndexKey')) == int(entity)
          and int(dei('DocumentFiscalYearFocus')) == period['fiscal_year']
          and end == filing['reportDate'] == period['period_end'], 'ANNUAL_IDENTITY')


def _read(source, *, source_kind, company_id, filing, entity, period, namespace_policy):
    raw = source['raw_bytes']; ref = source['source_reference']
    _need(ref['raw_asset_id'] == 'sha256:' + sha256_bytes(content=raw)
          and ref['company_id'] == company_id
          and ref['accession'] == filing['accessionNumber'], 'ORIGINAL_BINDING')
    _need(ref['source_url'] == accession_document_url(cik=int(entity),
          accession=filing['accessionNumber'], document_name=ref['document_name'])
          and (ref['document_name'] == filing['primaryDocument'] if source_kind == 'primary'
               else ref['document_name'].lower().endswith('.xml')), 'SOURCE_LOCATOR')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    meta = _ReportedFactMetadata(); meta.feed(raw.decode('utf-8-sig')); meta.close()
    _need(meta.ordinal == len(parsed.facts), 'NATIVE_STREAM')
    _annual_identity(parsed, meta, filing=filing, entity=entity, period=period,
                     namespaces=namespace_policy['dei_namespaces'])
    reports = []; issues = []
    for f in parsed.facts:
        info = meta.facts[f['ordinal']]; uri, name = info['concept']
        names = {n.casefold(): n for n in CONCEPTS}
        if name.casefold() not in names:
            continue
        name = names[name.casefold()]
        c = parsed.contexts[f['context_ref']]
        if (c['period_start'], c['period_end']) != (period['period_start'], period['period_end']):
            continue
        if int(c['entity_identifier']) != int(entity):
            issues.append({'ordinal': f['ordinal'], 'reason': 'OTHER_ENTITY'}); continue
        if uri not in namespace_policy['concept_namespaces']:
            issues.append({'ordinal': f['ordinal'], 'reason': 'CONCEPT_NAMESPACE_NOT_SELECTED'}); continue
        if c['typed_dimension_count'] or meta.units.get(f['unit_ref']) != USD:
            issues.append({'ordinal': f['ordinal'], 'reason': 'TYPED_SCOPE_OR_NON_USD'}); continue
        try:
            proof = _verified_context(native={**c, 'dimensions': dict(c['dimensions'])}, metadata=meta)
            value = _numeric_value(f, info)
        except ValueError as error:
            issues.append({'ordinal': f['ordinal'], 'reason': str(error)}); continue
        reports.append({'ordinal': f['ordinal'], 'concept': [uri, name],
            'value': value, 'decimals': info['attrs'].get('decimals'),
            'unit': 'USD', 'reported_scale': f['scale'], 'context_proof': proof,
            'source_reference': ref})
    return parsed, reports, issues


def inspect_depreciation_sources(*, primary, xml, company_id, filing, entity,
                                 period, namespace_policy):
    """Return paired original candidates and bounded scope relationships.

    A context specialization is not a sum or a full-role proof. Visible text is
    retained for content checking; the adapter does not infer inclusion merely
    from dimension names, nor decide current-year impairment from nearby words.
    """
    start = date.fromisoformat(period['period_start']); end = date.fromisoformat(period['period_end'])
    _need((end - start).days + 1 in {364, 365, 366, 371}
          and start.year <= period['fiscal_year'] <= end.year, 'ANNUAL_DURATION_OR_LABEL')
    _need(set(namespace_policy) == {'concept_namespaces', 'dei_namespaces'}
          and all(namespace_policy.values()), 'EXPLICIT_NAMESPACE_POLICY_REQUIRED')
    _need(all(re.fullmatch(r'https?://fasb\.org/us-gaap/\d{4}(?:-\d{2}-\d{2})?', uri)
              for uri in namespace_policy['concept_namespaces'])
          and all(re.fullmatch(r'https?://xbrl\.sec\.gov/dei/\d{4}(?:q[1-4])?', uri)
                  for uri in namespace_policy['dei_namespaces']), 'OFFICIAL_NAMESPACE_POLICY_REQUIRED')
    sources = {'primary': primary, 'xml': xml}
    readings = {kind: _read(source, source_kind=kind, company_id=company_id, filing=filing,
        entity=entity, period=period, namespace_policy=namespace_policy)
        for kind, source in sources.items()}
    grouped = {}
    issues = [{'source_kind': kind, **issue} for kind, (_, _, found) in readings.items() for issue in found]
    for kind, (_, rows, _) in readings.items():
        for row in rows:
            key = (tuple(row['concept']), _scope(row['context_proof']))
            grouped.setdefault(key, {'primary': [], 'xml': []})[kind].append(row)
    index = _InlineTableIndex(primary['raw_bytes'])
    index.feed(primary['raw_bytes'].decode('utf-8-sig')); index.close()
    structure = index_source_structure(source_bytes=primary['raw_bytes'])
    candidates = []
    for reports in grouped.values():
        if not all(reports.values()):
            issues.append({'reason': 'PRIMARY_XML_CANDIDATE_MISSING', 'reports': reports}); continue
        try:
            chosen = precision_choice(reports['primary'] + reports['xml'])
        except ValueError as error:
            issues.append({'reason': 'PRIMARY_XML_AMOUNT_CONFLICT', 'detail': str(error), 'reports': reports}); continue
        blocks = {}
        for report in reports['primary']:
            pos = index.fact_positions[report['ordinal']]
            for block in structure['blocks']:
                if block['start_byte'] <= pos < block['end_byte']:
                    blocks[block['span_sha256']] = block
        body = {'concept': chosen['concept'], 'value': chosen['value'], 'unit': 'USD',
            'context_proof': chosen['context_proof'], 'source_reports': reports,
            'visible_blocks': list(blocks.values()), 'full_da_role_established': False}
        candidates.append({**body, 'candidate_id': content_hash(value=body)})
    relations = []
    for parent in candidates:
        dims = {tuple(d['dimension_qname']): tuple(d['member_qname'])
                for d in parent['context_proof']['dimensions']}
        for child in candidates:
            more = {tuple(d['dimension_qname']): tuple(d['member_qname'])
                    for d in child['context_proof']['dimensions']}
            if (parent['concept'] == child['concept'] and dims.items() < more.items()
                    and Decimal(child['value']) <= Decimal(parent['value'])):
                relations.append({'parent_candidate_id': parent['candidate_id'],
                    'child_candidate_id': child['candidate_id'],
                    'kind': 'CONTEXT_SCOPE_SPECIALIZATION',
                    'additive_relationship_established': False,
                    'reported_inclusion_requires_content_check': True})
    body = {'record_type': 'ORDINARY_DEPRECIATION_SOURCE_CANDIDATES',
        'company_id': company_id, 'filing': filing, 'entity': str(int(entity)),
        'period': period, 'namespace_policy': namespace_policy,
        'numeric_literal_policy': NUMERIC_POLICY, 'candidates': candidates,
        'scope_relations': relations, 'issues': issues,
        'remaining_scope': ['FULL_APPROVED_DA_COVERAGE_NOT_ESTABLISHED',
                            'REPORTED_INCLUSION_AND_IMPAIRMENT_REQUIRE_CONTENT_CHECK'],
        'metric_result_created': False, 'definition_complete': False}
    return {**body, 'source_candidates_id': content_hash(value=body)}
