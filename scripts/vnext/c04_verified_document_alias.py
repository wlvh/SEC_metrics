"""Explicit C04 successor for saved SEC URLs with historical local body labels.

The frozen C04 v2 reader requires ``document_name`` to equal the SEC URL
basename. An old capture can instead label the same immutable response
``0002.body``. This module rechecks the actual GET proof and parses the
original SourceReference without changing its identity or historical bytes.
It is called only after frozen v2 rejects that exact alias condition.
"""
from datetime import date
import re

from sec_urls import accession_document_url

from .canonical import content_hash, sha256_bytes
from .deterministic_router import parse_accession_xbrl_source
from .governance_signals import (_FactAttributes, C04_RESOLVER,
                                 C04_V2_RESOLVER)
from .normal_annual_input import dei_namespace_pattern
from .observations import scope_key
from .ordinary_source_authority import verify_ordinary_source_proofs
from .records import validate_record
from .resource_limits import RESOURCE_LIMITS


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _checked_filing(*, sources, company_id, cik, period_end,
                    source_proofs, aliases, dei_release="YEAR_ONLY"):
    """Keep frozen annual fact semantics; change only proven URL-name equality."""
    namespace_pattern = dei_namespace_pattern(dei_release)
    _need(bool(sources), 'C04_FILING_SOURCE_REQUIRED')
    accessions, forms, references, facts, problems = set(), set(), [], [], []
    for source in sources:
        _need(set(source) == {'raw_bytes', 'raw_blob', 'source_reference'},
              'C04_SOURCE_FIELDS_INVALID')
        raw = source['raw_bytes']
        blob = validate_record(record=dict(source['raw_blob']))
        ref = validate_record(record=dict(source['source_reference']))
        _need(type(raw) is bytes and 0 < len(raw) <= RESOURCE_LIMITS.max_html_bytes,
              'C04_SOURCE_SIZE_LIMIT')
        _need(blob['record_type'] == 'RAW_BLOB'
              and ref['record_type'] == 'SOURCE_REFERENCE'
              and blob['raw_asset_id'] == ref['raw_asset_id']
              == 'sha256:' + sha256_bytes(content=raw)
              and blob['byte_length'] == len(raw), 'C04_SOURCE_BYTES_CHANGED')
        _need(ref['company_id'] == company_id, 'C04_COMPANY_MISMATCH')
        expected = accession_document_url(cik=int(cik),
            accession=ref['accession'], document_name=ref['document_name'])
        if ref['source_url'] != expected:
            actual_name = ref['source_url'].rsplit('/', 1)[-1]
            _need(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', actual_name)
                  is not None and ref['source_url'] == accession_document_url(
                      cik=int(cik), accession=ref['accession'],
                      document_name=actual_name),
                  'C04_SAME_CIK_FILING_REQUIRED')
            matching = [proof for proof in source_proofs
                if proof['source_url'] == ref['source_url']
                and proof['accession'] == ref['accession']
                and proof['document_name'] == ref['document_name']
                and proof['request_attempt_id'] == ref['request_attempt_id']
                and proof['content_sha256'] == blob['raw_asset_id'][7:]
                and proof['request_body_sha256'] == blob['raw_asset_id'][7:]]
            _need(len(matching) == 1,
                  'C04_ALIAS_ORIGINAL_REQUEST_PROOF_MISMATCH')
            aliases.append({'source_reference_id': ref['source_reference_id'],
                'request_attempt_id': ref['request_attempt_id'],
                'accession': ref['accession'], 'source_url': ref['source_url'],
                'saved_document_name': ref['document_name'],
                'sec_url_document_name': actual_name})
        accessions.add(ref['accession'])
        references.append(ref)
        parsed = parse_accession_xbrl_source(raw_bytes=raw)
        metadata = _FactAttributes()
        metadata.feed(raw.decode('utf-8'))
        metadata.close()
        _need(metadata.ordinal == len(parsed.facts),
              'C04_ATTRIBUTE_STREAM_INCOMPLETE')
        for fact in parsed.facts:
            uri, local = metadata.facts[fact['ordinal']]['concept']
            if re.fullmatch(namespace_pattern, uri) is None:
                continue
            if local.casefold() == 'documenttype':
                forms.add(fact['text'].upper())
            if local.casefold() != 'auditorname':
                continue
            context = parsed.contexts[fact['context_ref']]
            lexical = ' '.join(fact['text'].split())
            canonical = ''.join(c for c in lexical.casefold() if c.isalnum())
            row = {'source_reference_id': ref['source_reference_id'],
                   'raw_asset_id': blob['raw_asset_id'],
                   'accession': ref['accession'], 'name': lexical,
                   'canonical_name': canonical,
                   'period_start': context['period_start'],
                   'period_end': context['period_end'],
                   'entity_identifier': context['entity_identifier'],
                   'locator': {'qualified_name': fact['qualified_name'],
                               'context_ref': fact['context_ref'],
                               'ordinal': fact['ordinal']}}
            if (context['period_end'] != period_end or context['dimensions']
                    or context['typed_dimension_count']
                    or not str(context['entity_identifier']).isdigit()
                    or str(int(context['entity_identifier'])) != str(int(cik))):
                problems.append({**row,
                    'reason': 'C04_AUDITOR_FACT_SCOPE_CONFLICT'})
            elif canonical:
                facts.append(row)
    _need(len(accessions) == 1 and len(forms) == 1
          and forms <= {'10-K', '10-K/A'},
          'C04_FILING_IDENTITY_OR_FORM_CONFLICT')
    _need(len({ref['source_reference_id'] for ref in references})
          == len(references), 'C04_DUPLICATE_FILING_SOURCE')
    names = sorted({fact['canonical_name'] for fact in facts})
    return {'accession': next(iter(accessions)), 'form': next(iter(forms)),
        'source_references': references, 'facts': facts, 'problems': problems,
        'canonical_names': names,
        'status': ('CONFLICT' if problems or len(names) > 1 else
                   'FOUND' if names else 'MISSING')}


def annual_selection_with_verified_aliases(*, arguments, source_proofs,
                                           data_root, dei_release="YEAR_ONLY",
                                           allow_exact_document_names=False):
    """Compare current/prior auditor facts after rechecking original GETs."""
    dei_namespace_pattern(dei_release)
    _need(type(allow_exact_document_names) is bool,
          "C04_EXACT_DOCUMENT_SELECTION_INVALID")
    verify_ordinary_source_proofs(data_root=data_root, proofs=source_proofs)
    _need(type(arguments) is dict and arguments.get('event_input') is None,
          'C04_ALIAS_ANNUAL_ONLY_REQUIRED')
    semantic = arguments['compiled_spec']['compiled']
    _need(semantic['metric_id'] == 'C04'
          and semantic['kind'] == 'direct_numeric'
          and semantic['canonical_unit'] == 'flag'
          and semantic['quality_rule'].get('resolver') in
              {C04_RESOLVER, C04_V2_RESOLVER},
          'C04_SPEC_REQUIRED')
    target = arguments['target']
    _need(set(target) == {'company_id', 'period_start', 'period_end',
                          'scope', 'scope_key'}
          and target['scope'] == {'entity_scope': 'registrant'}
          and target['scope_key'] == scope_key(scope=target['scope']),
          'C04_TARGET_SCOPE_INVALID')
    cik = arguments['expected_cik']
    aliases = []
    def check(sources, period_end):
        return _checked_filing(sources=sources,
            company_id=target['company_id'], cik=cik,
            period_end=period_end, source_proofs=source_proofs,
            aliases=aliases, dei_release=dei_release)
    current = [check(sources, target['period_end'])
               for sources in arguments['current_filings']]
    _need(1 <= len(current) <= 64
          and current[0]['accession'] == arguments['target_accession'],
          'C04_FILED_TARGET_MUST_BE_FIRST')
    if len(current) > 1:
        _need(all(f['form'] == '10-K/A' for f in current[:-1])
              and current[-1]['form'] == '10-K'
              and len({f['accession'] for f in current}) == len(current),
              'C04_ORIGINAL_FALLBACK_INVALID')
    selected = next((f for f in current if f['status'] != 'MISSING'),
                    current[-1])
    prior_sources = arguments.get('prior_sources') or []
    prior_filings = arguments.get('prior_filings') or []
    _need(not (prior_sources and prior_filings),
          'C04_PRIOR_CHAIN_REQUIRES_V2')
    prior_checks = []
    if prior_sources or prior_filings:
        _need(date.fromisoformat(arguments['prior_period_end'])
              < date.fromisoformat(target['period_start']),
              'C04_PRIOR_PERIOD_INVALID')
        prior_checks = ([check(sources, arguments['prior_period_end'])
                         for sources in prior_filings] if prior_filings else
                        [check(prior_sources, arguments['prior_period_end'])])
    if prior_filings:
        _need(len(prior_checks) <= 64 and prior_checks[-1]['form'] == '10-K'
              and all(f['form'] == '10-K/A' for f in prior_checks[:-1])
              and len({f['accession'] for f in prior_checks})
              == len(prior_checks), 'C04_PRIOR_CHAIN_INVALID')
    prior = (next((f for f in prior_checks if f['status'] != 'MISSING'),
                  prior_checks[-1]) if prior_checks else None)
    names_differ = (selected['canonical_names'] != prior['canonical_names']
        if selected['status'] == 'FOUND' and prior is not None
        and prior['status'] == 'FOUND' else None)
    conflict = selected['status'] == 'CONFLICT' or (prior is not None
        and prior['status'] == 'CONFLICT')
    reason = ('C04_AUDITOR_SOURCE_CONFLICT' if conflict else
        'PASS' if names_differ is True else
        'C04_EVENT_COVERAGE_REQUIRED' if names_differ is False else
        'C04_COMPARABLE_AUDITOR_FACTS_MISSING')
    _need(bool(aliases) or allow_exact_document_names,
          'C04_ALIAS_FALLBACK_WITHOUT_REAL_ALIAS')
    selection = {'target': dict(target), 'current_filing_checks': current,
        'selected_current_accession': selected['accession'],
        'prior_filing_check': prior, 'prior_filing_checks': prior_checks,
        'names_differ': names_differ, 'reason_code': reason,
        'verified_document_aliases': aliases}
    return {'selection': {**selection,
        'selection_id': content_hash(value=selection)}, 'aliases': aliases}
