"""Bind the shared D&A comparison to current primary facts and existing checks.

The comparison implementation is the unchanged versioned ordinary copy of
Issue47 d7d5938's historical_da_scope_candidate. This adapter checks actual
CIK, namespace, period and units; it does not add a new English classifier or
change the approved EBITDA formula. A KEEP is a limited input check, not an
independent certificate that all business scope is complete.
"""
from decimal import Decimal
import re

from .ordinary_da_scope_v1 import DIRECT, COMPOSITION, WITHHELD_REASON, agree, da_scope_answer
from .deterministic_router import parse_accession_xbrl_source, _numeric_xbrl_value
from .text_results_v2 import _ReportedFactMetadata, _verified_context
from .b03_contract_amortization_scope import _selected_original_facts
from .canonical import sha256_bytes


def inspect_depreciation_input(*, raw_bytes, entity, period, observations):
    parsed = parse_accession_xbrl_source(raw_bytes=raw_bytes)
    metadata = _ReportedFactMetadata()
    metadata.feed(raw_bytes.decode('utf-8-sig')); metadata.close()
    if metadata.ordinal != len(parsed.facts):
        raise ValueError('B03_SCOPE_NATIVE_STREAM_CHANGED')
    candidates = []
    for fact in parsed.facts:
        info = metadata.facts[fact['ordinal']]
        uri, concept = info['concept']
        if concept not in DIRECT + COMPOSITION:
            continue
        context = parsed.contexts[fact['context_ref']]
        if (not re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}', uri)
                or context['period_start'] != period['period_start']
                or context['period_end'] != period['period_end']
                or context['dimensions'] or context['typed_dimension_count']
                or not str(context['entity_identifier']).isdigit()
                or int(context['entity_identifier']) != int(entity)
                or metadata.units.get(fact['unit_ref']) != {
                    'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')],
                    'divided': False}):
            continue
        context_proof = _verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=metadata)
        candidates.append({'concept':concept, 'fact_ordinal':fact['ordinal'],
            'context_ref':fact['context_ref'], 'unit_ref':fact['unit_ref'],
            'value':str(_numeric_xbrl_value(text=fact['text'],scale=fact['scale'],sign=fact['sign'])),
            'decimals':info['attrs'].get('decimals'),'context_proof':context_proof})
    answer = da_scope_answer(facts=candidates)
    direct = [o for o in observations if o['semantic_role']=='depreciation_and_amortization']
    composed = [o for o in observations if o['semantic_role'] in ('depreciation','amortization')]
    chain = ({'concept':direct[0]['source_binding']['concept'].split(':')[-1],
              'value':str(direct[0]['value'])} if len(direct)==1 else
             {'concept':'+'.join(COMPOSITION),
              'value':str(sum(Decimal(str(o['value'])) for o in composed))} if len(composed)==2 else None)
    body = {'filing_answer':answer,'chain_input':chain,'primary_sha256':sha256_bytes(content=raw_bytes),
            'entity':str(entity),'period':dict(period),'source_facts':candidates,
            'complete_business_scope_proven':False}
    if answer['status']=='WITHHOLD':
        return {**body,'status':'WITHHOLD','reason_code':WITHHELD_REASON,'why':answer['why']}
    if answer['status']=='NO_DIRECT_CANDIDATE':
        if direct or len(composed)!=2:
            return {**body,'status':'WITHHOLD','reason_code':WITHHELD_REASON,
                    'why':'CHAIN_DIRECT_OR_COMPOSITION_NOT_SUPPORTED_BY_PRIMARY'}
        originals = _selected_original_facts(parsed=parsed,metadata=metadata,
            roles={o['semantic_role']:o for o in composed},period=period,entity=entity)
        return {**body,'status':'KEEP','composition_originals':originals,'why':answer['why']}
    selected = answer['selected']
    if len(direct)!=1:
        return {**body,'status':'WITHHOLD','reason_code':WITHHELD_REASON,
                'why':'CHAIN_COMPOSED_WHILE_PRIMARY_REPORTS_DIRECT_TOTAL'}
    if chain['concept']!=selected['concept']:
        return {**body,'status':'RETAKE','concept':selected['concept'],'why':answer['why']}
    if not agree({'value':chain['value'],'decimals':'INF'},selected):
        return {**body,'status':'WITHHOLD','reason_code':WITHHELD_REASON,
                'why':'CHAIN_AMOUNT_DIFFERS_FROM_PRIMARY_AT_REPORTED_PRECISION'}
    return {**body,'status':'KEEP','why':answer['why']}
