"""B13 source scope and bounded original-source quantity inputs.

Candidate excerpts never prove absence of a numeric pair. This module keeps
the two required quantity roles and rejects substitution/scope drift; actual
complete semantic coverage, source admission and native Run credit remain
separate from the pure source helpers. Explicit annual quantities can feed
the existing Calculator after the registered native assessment is complete.
"""
from datetime import date
from pathlib import Path
import re

from .canonical import content_hash, strict_json_file, sha256_file
from .continuous_call_policy import delegation_fields
from .normal_annual_input import prepare_saved_annual_input
from .normal_governance_input import _Sources
from .normal_source_authority import ROOT
from .ordinary_source_authority import verify_ordinary_source_proofs
from .specs import compile_spec_file
from .text_coverage import build_text_document
from .text_results import text_claim_from_block
from .deterministic_router import parse_accession_xbrl_source
from .calculator import calculate_metric

POLICY_PATH='config/b13_production_capacity_v1.json'


def need(value,reason):
    if not value:raise ValueError(reason)


def policy():
    rules=strict_json_file(path=ROOT/POLICY_PATH)
    approved=strict_json_file(path=ROOT/rules['approval_policy'])
    comment=strict_json_file(path=ROOT/approved['delegation_record_path'])
    delegation_fields(comment,policy=approved)
    return rules,approved['b13']


def prepare_capacity_sources(*, repo_root:Path, company_id:str):
    rules,approved=policy()
    need(strict_json_file(path=repo_root/POLICY_PATH)==rules,'B13_INSTALLED_RULES_CHANGED')
    need(company_id in approved['applicable_company_ids'],'B13_OUTSIDE_APPROVED_APPLICABILITY')
    annual=prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    reader=_Sources(repo_root,company_id,annual['entity']);original=reader.primary(annual['filing'])
    admission=verify_ordinary_source_proofs(data_root=repo_root,proofs=annual['source_proofs'])
    document=build_text_document(raw_bytes=original['raw_bytes'],raw_blob=original['raw_blob'],
        source_reference=original['source_reference'],expected_company_id=company_id,
        expected_cik=annual['entity'],expected_period_end=annual['filing']['reportDate'])
    need(document['source_state']=='COMPLETE_LOCAL_DOCUMENT','B13_SOURCE_DOCUMENT_INCOMPLETE')
    parsed=parse_accession_xbrl_source(raw_bytes=original['raw_bytes'])
    related=re.compile(rules['related_production_capacity_pattern'],re.I)
    possible=re.compile(rules['possible_actual_production_pattern'],re.I)
    disclosures=[];potential=[]
    for block in document['blocks']:
        if related.search(block['text']):
            disclosures.append(text_claim_from_block(document=document,section_id='CAPACITY_DISCLOSURES',
                block_index=block['block_index'],order=len(disclosures),extent='FULL_BLOCK'))
        if possible.search(block['text']):
            potential.append(text_claim_from_block(document=document,section_id='POSSIBLE_ACTUAL_PRODUCTION',
                block_index=block['block_index'],order=len(potential),extent='FULL_BLOCK'))
    native=[dict(f) for f in parsed.facts if re.search(r'capacity|utilization|actualproduction|productionvolume',
                                                    f['qualified_name'],re.I)]
    body={'record_type':'B13_SOURCE_CANDIDATES','company_id':company_id,'metric_id':'B13',
        'annual':annual,'source_reference':original['source_reference'],'raw_blob':original['raw_blob'],
        'source_proofs':annual['source_proofs'],'source_admission':admission,
        'document_id':document['text_document_id'],'complete_document_block_count':len(document['blocks']),
        'related_disclosures':disclosures,'possible_actual_production':potential,'native_quantity_candidates':native,
        'amendment_scope_proven':not annual['amendments'],
        'source_status':'RELATED_DISCLOSURES_FOUND' if disclosures else 'SOURCE_INTERPRETATION_REQUIRED',
        'numeric_pair_completeness_verified':False,'absence_established':False,
        'candidate_text_status':'TEXT_QUAL' if disclosures else None,
        'native_result_created':False,'review_complete':False,'production_authorized':False,
        'rule_sha256':sha256_file(path=ROOT/POLICY_PATH),'calls':{'provider':0,'paid':0,'sec':0}}
    return {**body,'source_candidate_id':content_hash(value=body)}


def calculate_comparable_pair(*, target, production, capacity):
    """Development calculation for already source-verified quantity roles.

    This is not a public source-admission API. Its return carries no native Run
    or source credit; the future extractor must independently establish the
    role assignments and source evidence before feeding the shared Calculator.
    """
    rules,approved=policy()
    need(target['company_id'] in approved['applicable_company_ids'],'B13_OUTSIDE_APPROVED_APPLICABILITY')
    need(target['scope'].get('capacity_basis')=='actual_production_over_available_capacity',
         'B13_TARGET_MEANING_CHANGED')
    required={'basis','value','unit','entity','period_start','period_end','product_or_facility_scope','source_binding'}
    need(set(production)==required and set(capacity)==required,'B13_QUANTITY_FIELDS_CHANGED')
    need(production['basis']=='ACTUAL_PRODUCTION' and capacity['basis']=='AVAILABLE_CAPACITY',
         'B13_REQUIRED_QUANTITY_ROLE_MISSING')
    for field in ['unit','entity','period_start','period_end','product_or_facility_scope']:
        need(production[field]==capacity[field] and bool(production[field]),'B13_INCOMPARABLE_'+field.upper())
    need(all(production[k]==target[k] for k in ['entity','period_start','period_end'])
         and target['scope']['product_or_facility_scope']==production['product_or_facility_scope'],
         'B13_TARGET_SCOPE_CHANGED')
    from .canonical import parse_decimal
    need(parse_decimal(value=production['value'])>=0 and parse_decimal(value=capacity['value'])>0,
         'B13_QUANTITY_OR_CAPACITY_NOT_POSITIVE')
    facts=[]
    for role,quantity in [('ActualProduction',production),('AvailableCapacity',capacity)]:
        binding=quantity['source_binding']
        need(binding.get('entity')==target['entity'] and binding.get('accession')==target['accession'],
             'B13_SOURCE_BINDING_CHANGED')
        fact={'concept':'b13:'+role,'value':quantity['value'],'unit':quantity['unit'],
            'entity':quantity['entity'],'period_start':quantity['period_start'],'period_end':quantity['period_end'],
            'accession':target['accession'],'filed':binding['filing_date'],'form':'10-K','fiscal_period':'FY',
            'duration_days':(date.fromisoformat(quantity['period_end'])-date.fromisoformat(quantity['period_start'])).days+1,
            'source_binding':binding}
        facts.append({**fact,'fact_id':content_hash(value=fact)})
    spec=compile_spec_file(path=ROOT/rules['numeric_spec'],dependency_specs={})
    result,trace,observations=calculate_metric(compiled_spec=spec,target=target,company_traits=[],
        structured_facts=facts,verified_observations=[])
    return {'result':result,'trace':trace,'observations':observations,'source_assignments_independently_verified':False,
            'native_result_created':False,'production_authorized':False}


def _quantity_context_qualified(*, quoted, context):
    from .regulatory_investigation_candidates import _PATTERNS
    return quoted or any(_PATTERNS['discourse_qualification'].search(text)
        or _PATTERNS['reported_speech_intro'].search(text)
        or re.fullmatch(r'\s*(?:an?\s+)?(?:hypothetical|illustrative)\s+(?:example|scenario)\s*[:.]?\s*', text, re.I)
        for text in context)


def explicit_annual_quantity_statements(*, text, quoted=False, context=()):
    """Extract direct reported annual output/available-capacity relations.

    The product and geographical/facility scope must be stated, not inferred
    from a nearby number or a model's label. Unsupported prose returns no
    quantity proof; the caller must retain an implementation/interpretation
    gap rather than claim disclosure absence.
    """
    from .regulatory_investigation_candidates import _sentences
    from .canonical import parse_decimal, decimal_text
    if _quantity_context_qualified(quoted=quoted, context=context):
        return []
    prefix = r'^(?P<period_basis>For (?:the )?fiscal year|During|In)\s+(?P<year>\d{4}),?\s+'
    amount = r'(?P<amount>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*'
    quantity = amount + r'(?:(?P<scale>thousand|million|billion)\s+)?(?P<product>[A-Za-z]+(?:[ -][A-Za-z]+){0,4}?)\s+'
    scope = r'(?P<scope>worldwide|globally|at our [A-Za-z][A-Za-z -]{0,80} (?:plant|facility))\.?$'
    predicates = {
        'ACTUAL_PRODUCTION': r'we\s+(?:produced|manufactured)\s+',
        'AVAILABLE_CAPACITY': r'our\s+available\s+annual\s+(?:production|manufacturing)\s+capacity\s+was\s+',
    }
    result = []
    for start, end, statement in _sentences(text):
        for role, predicate in predicates.items():
            match = re.fullmatch(prefix + predicate + quantity + scope, statement, re.I)
            if match is None:
                continue
            scale = {None: 1, 'thousand': 1000, 'million': 1000000, 'billion': 1000000000}[match.group('scale').lower() if match.group('scale') else None]
            unit = match.group('product').casefold()
            # Currency, credits, sales and installed/planned amounts are not
            # quantities of a physical manufactured product.
            if unit in {'units', 'items', 'products', 'tons', 'tonnes'} or re.search(
                    r'\b(?:dollars?|usd|credits?|sales|shipments?|installed|planned)\b', unit):
                continue
            geography = match.group('scope').casefold()
            if geography == 'globally':
                geography = 'worldwide'
            result.append({'basis': role, 'value': decimal_text(value=parse_decimal(value=match.group('amount').replace(',', '')) * scale),
                'unit': unit, 'fiscal_year': int(match.group('year')),
                'period_basis': 'FISCAL_YEAR' if match.group('period_basis').casefold().startswith('for') else 'CALENDAR_YEAR',
                'product_or_facility_scope': unit + '; ' + geography,
                'statement_text': statement, 'reported_number': match.group('amount'),
                'reported_scale': match.group('scale'), 'start_character': start, 'end_character': end})
    return result


def calculate_source_comparable_pair(*, source, raw_bytes_by_id):
    """Rebuild both quantities from exact original blocks before Calculator.

    The native caller separately verifies the complete registered assessment
    and acquisition chain. This pure helper cannot confer source admission.
    """
    from .canonical import sha256_bytes
    from .regulatory_investigation_candidates import _quotation_ranges
    need(source['metric_id'] == 'B13' and source['semantic_source_id'] == content_hash(value={
        k:v for k,v in source.items() if k != 'semantic_source_id'}), 'B13_QUANTITY_SOURCE_ID_CHANGED')
    annual = source['prepared_annual_input']; period = annual['table_input']['target_period']
    documents = {d['document_id']: d for d in source['documents']}
    quantities = {'ACTUAL_PRODUCTION': [], 'AVAILABLE_CAPACITY': []}; rebuilt_documents = {}; quotations = {}
    for unit in source['units']:
        if unit['kind'] != 'VISIBLE_TEXT':
            continue
        document = documents[unit['document_id']]; ref = document['source_reference']
        raw = raw_bytes_by_id[document['raw_blob']['raw_asset_id']]
        need('sha256:' + sha256_bytes(content=raw) == ref['raw_asset_id'], 'B13_QUANTITY_ORIGINAL_BYTES_CHANGED')
        if unit['document_id'] not in rebuilt_documents:
            rebuilt = build_text_document(raw_bytes=raw, raw_blob=document['raw_blob'], source_reference=ref,
                expected_company_id=source['company_id'], expected_cik=annual['entity'],
                expected_period_end=document['filing']['reportDate'])
            need(rebuilt['source_state'] == 'COMPLETE_LOCAL_DOCUMENT', 'B13_QUANTITY_DOCUMENT_INCOMPLETE')
            rebuilt_documents[unit['document_id']] = {b['block_index']: b for b in rebuilt['blocks']}
            quotations[unit['document_id']] = _quotation_ranges(raw)
        for block in unit['payload']['blocks']:
            actual = rebuilt_documents[unit['document_id']].get(block['block_index'])
            need(actual is not None and all(actual[k] == block[k] for k in
                ('text','raw_start_byte','raw_end_byte','raw_span_sha256')), 'B13_QUANTITY_SOURCE_BLOCK_CHANGED')
            quoted = any(start < block['raw_end_byte'] and end > block['raw_start_byte']
                         for start, end in quotations[unit['document_id']])
            context = [rebuilt_documents[unit['document_id']][i]['text']
                       for i in range(max(0, block['block_index'] - 2), block['block_index'])]
            facts = explicit_annual_quantity_statements(text=block['text'], quoted=quoted, context=context)
            for fact in facts:
                if fact['fiscal_year'] != period['fiscal_year']:
                    continue
                if fact['period_basis'] == 'CALENDAR_YEAR' and (period['period_start'], period['period_end']) != (
                        str(fact['fiscal_year']) + '-01-01', str(fact['fiscal_year']) + '-12-31'):
                    continue
                need(sha256_bytes(content=raw[block['raw_start_byte']:block['raw_end_byte']]) == block['raw_span_sha256'],
                     'B13_QUANTITY_RAW_SPAN_CHANGED')
                binding = {k: ref[k] for k in ('accession','document_name','raw_asset_id','source_reference_id','source_role')}
                binding.update(entity=annual['entity'], filing_date=document['filing']['filingDate'],
                    quantity_statement={**fact, 'document_id': unit['document_id'], 'block_index': block['block_index'],
                        'raw_start_byte': block['raw_start_byte'], 'raw_end_byte': block['raw_end_byte'],
                        'raw_span_sha256': block['raw_span_sha256']})
                quantities[fact['basis']].append({k: fact[k] for k in ('basis','value','unit','product_or_facility_scope')} | {
                    'entity': annual['entity'], 'period_start': period['period_start'], 'period_end': period['period_end'],
                    'source_binding': binding})
    selected = {}
    for role, values in quantities.items():
        distinct = {content_hash(value={k:v for k,v in q.items() if k != 'source_binding'}) for q in values}
        need(len(distinct) == 1, 'B13_QUANTITY_RELATION_NOT_UNIQUE_OR_UNSUPPORTED:' + role)
        selected[role] = values[0]
    production, capacity = selected['ACTUAL_PRODUCTION'], selected['AVAILABLE_CAPACITY']
    scope = {'capacity_basis': 'actual_production_over_available_capacity',
             'product_or_facility_scope': production['product_or_facility_scope']}
    target = {'company_id': source['company_id'], 'entity': annual['entity'], 'accession': annual['filing']['accessionNumber'],
        'period_start': period['period_start'], 'period_end': period['period_end'], 'scope': scope, 'scope_key': content_hash(value=scope)}
    calculated = calculate_comparable_pair(target=target, production=production, capacity=capacity)
    return {**calculated, 'source_assignments_independently_verified': True,
        'source_quantity_proofs': selected, 'target': target}


def validate_explicit_quantity_classifications(*, units, findings, period):
    """Known physical quantities cannot be erased by a different model label."""
    blocks = {(u['document_id'], b['block_index']): b for u in units if u['kind'] == 'VISIBLE_TEXT'
              for b in u['payload']['blocks']}
    for unit in units:
        if unit['kind'] != 'VISIBLE_TEXT':
            continue
        for block in unit['payload']['blocks']:
            index = block['block_index']
            if index and (unit['document_id'], index - 1) not in blocks:
                # A per-request boundary may omit an introducing qualifier.
                # The full-source consumer rechecks this block with context.
                continue
            context = [blocks[(unit['document_id'], i)]['text'] for i in range(max(0, index - 2), index)
                       if (unit['document_id'], i) in blocks]
            qualified = _quantity_context_qualified(quoted=block['html_quotation_context'], context=context)
            facts = explicit_annual_quantity_statements(text=block['text'])
            selected = [f for f in findings if f['unit_id'] == unit['unit_id'] and any(
                e['kind'] == 'VISIBLE_BLOCK' and e['source_index'] == index for e in f['resolved_evidence'])]
            if facts and qualified:
                need(not any(f['kind'] in {'ACTUAL_PRODUCTION','AVAILABLE_CAPACITY'}
                    and f['subject'] == 'TARGET_REGISTRANT' and f['timing'] == 'CURRENT_REPORT'
                    for f in selected), 'B13_QUALIFIED_QUANTITY_CANNOT_ESTABLISH_CURRENT_SOURCE')
                continue
            for fact in facts:
                timing = 'CURRENT_REPORT' if fact['fiscal_year'] == period.get('fiscal_year') else 'HISTORICAL'
                need(any(f['kind'] == fact['basis'] and f['subject'] == 'TARGET_REGISTRANT'
                    and f['timing'] == timing and f['unit_id'] == unit['unit_id'] and any(
                        e['kind'] == 'VISIBLE_BLOCK' and e['source_index'] == block['block_index']
                        for e in f['resolved_evidence']) for f in findings),
                    'B13_SOURCE_QUANTITY_CLASSIFICATION_CONFLICT')
