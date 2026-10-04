"""Source-specific current income input, preserving the original annual guard."""
from pathlib import Path
import re

from .annual_amendment_scope import prepare_saved_amendment_scopes
from .instant_balance_amendment import _part_iii_details, POLICY as AMENDMENT_RULE
from .normal_candidates import _prepare_b06
from .normal_annual_input import annual_period
from .normal_source_authority import ROOT
from .normal_annual_input_v2 import exact_json_value
from .ordinary_source_authority import verify_ordinary_source_proofs
from .canonical import content_hash, sha256_file, strict_json_file, sha256_bytes
from .deterministic_router import parse_accession_xbrl_source
from .text_results_v2 import _ReportedFactMetadata, _verified_context
from .governance_signals import _source_value
from .r5_b06_scope import precision_choice
from .specs import compile_spec_file

POLICY_PATH='config/ordinary_income_input_v1.json'


class IncomeInputError(ValueError):
    category='CURRENT_SOURCE_SCOPE_UNRESOLVED'


def need(condition,reason):
    if not condition:raise IncomeInputError('ORDINARY_INCOME_'+reason)


def inspect_income_amendment(scope,raw,rules):
    need(scope['fiscal_window_unchanged'] and not scope['issues'],'AMENDMENT_IDENTITY_UNRESOLVED')
    if 'ORIGINAL_STATEMENT_VALUES' in scope['unchanged_input_classes']:
        return {'original_scope_id':scope['scope_id'],'inherited_statement_proof':True}
    need(scope['classification']=='PART_III_ADDITION_WITH_EXPLICIT_NO_NEW_FINANCIAL_STATEMENTS',
         'AMENDMENT_KIND_UNSUPPORTED')
    detail=_part_iii_details(scope,raw)
    conflicts=[]
    for block in scope['amendment']['document']['blocks']:
        text=block['text']
        if (re.fullmatch(rules['statement_heading_pattern'],text,re.I)
                or re.search(rules['income_subject_pattern'],text,re.I)
                and re.search(AMENDMENT_RULE['revision_pattern'],text,re.I)):
            conflicts.append(block)
    need(not conflicts,'AMENDMENT_INCOME_CORRECTION_UNRESOLVED:'+','.join(str(b['block_index']) for b in conflicts))
    return {'original_scope_id':scope['scope_id'],'part_iii_details':detail,
            'income_correction_blocks':conflicts,'input_class':rules['input_class']}


def native_income_reports(source,annual,concepts):
    raw=source['raw_bytes'];ref=source['source_reference']
    need(ref['raw_asset_id']=='sha256:'+sha256_bytes(content=raw)
         and ref['accession']==annual['filing']['accessionNumber']
         and ref['company_id']==annual['company_id'],'ORIGINAL_BINDING_CHANGED')
    need(annual_period(raw=raw,cik=annual['entity'],filing=annual['filing'])
         ==annual['table_input']['target_period'],'ORIGINAL_ANNUAL_IDENTITY_CHANGED')
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close()
    need(meta.ordinal==len(parsed.facts),'NATIVE_STREAM_CHANGED')
    names={c.split(':')[-1].casefold() for c in concepts}
    period=annual['table_input']['target_period'];rows=[]
    for fact in parsed.facts:
        info=meta.facts[fact['ordinal']];uri,name=info['concept']
        if name.casefold() not in names:continue
        context=parsed.contexts[fact['context_ref']]
        if (context['period_end']!=period['period_end']
                or not period['period_start']<=context['period_start']<context['period_end']
                or context['dimensions'] or context['typed_dimension_count']):continue
        need(str(int(context['entity_identifier']))==annual['entity'],'NATIVE_ENTITY_CHANGED')
        need(re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri) is not None,'OFFICIAL_CONCEPT_REQUIRED')
        need(meta.units.get(fact['unit_ref'])=={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False},
             'NATIVE_USD_REQUIRED')
        proof=_verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=meta)
        rows.append({'concept':'us-gaap:'+name,'value':_source_value(fact,info),'unit':'USD',
            'period_start':context['period_start'],'period_end':context['period_end'],
            'decimals':info['attrs'].get('decimals'),'ordinal':fact['ordinal'],
            'context_ref':fact['context_ref'],'context':{**context,'dimensions':dict(context['dimensions'])},
            'context_proof':proof,'source_reference':ref})
    return rows


def prepare_current_income_input(*,repo_root,company_id):
    rules=strict_json_file(path=repo_root/POLICY_PATH)
    need(rules==strict_json_file(path=ROOT/POLICY_PATH),'INSTALLED_RULES_CHANGED')
    prepared=_prepare_b06(repo_root=repo_root,company_id=company_id)
    annual=prepared['input_binding']['prepared_annual_input']
    amendments=prepare_saved_amendment_scopes(repo_root=repo_root,company_id=company_id)
    blobs={r['raw_asset_id']:r for r in amendments['source_records'] if r['record_type']=='RAW_BLOB'}
    checks=[]
    for scope in amendments['scopes']:
        ref=scope['amendment']['document']['source_reference']
        raw=(repo_root/blobs[ref['raw_asset_id']]['storage_uri']).read_bytes()
        checks.append(inspect_income_amendment(scope,raw,rules))
    from .batch_workflow import _structured_concepts
    b01=compile_spec_file(path=repo_root/'catalog/metrics/B01_revenue.md',dependency_specs={})
    b03=compile_spec_file(path=repo_root/'catalog/metrics/B03_ebitda_margin.md',dependency_specs={'B01':b01})
    concepts=sorted(set(_structured_concepts(compiled_spec=b01))|set(_structured_concepts(compiled_spec=b03)))
    reports={kind:native_income_reports(prepared[kind],annual,concepts) for kind in ['primary','xml']}
    revenue=b01['compiled']['inputs']['revenue']['structured_role']['approved_concepts']
    selected=None
    for concept in revenue:
        candidates={kind:[r for r in rows if r['concept'].casefold()==concept.casefold()] for kind,rows in reports.items()}
        if not any(candidates.values()):continue
        need(all(candidates.values()),'REVENUE_PRIMARY_XML_MISSING')
        periods={kind:{(r['period_start'],r['period_end']) for r in rows} for kind,rows in candidates.items()}
        need(periods['primary']==periods['xml'],'REVENUE_PERIOD_CONFLICT')
        start,end=min(periods['primary'])
        values=[r for rows in candidates.values() for r in rows if (r['period_start'],r['period_end'])==(start,end)]
        amount=precision_choice(values)
        selected={'period_start':start,'period_end':end,'concept':concept,'reported_value':amount['value'],
                  'original_reports':values,'other_current_end_periods':sorted(periods['primary'])}
        break
    need(selected is not None,'CURRENT_REVENUE_PERIOD_UNPROVEN')
    proofs=[*prepared['input_binding']['source_proofs'],*annual['source_proofs'],*amendments['source_proofs']]
    proofs=list({content_hash(value=p):p for p in proofs}.values())
    records=list({content_hash(value=r):r for r in [*prepared['records'],*amendments['source_records']]}.values())
    body=exact_json_value({'record_type':'ORDINARY_CURRENT_INCOME_INPUT','company_id':company_id,'annual_input':annual,
        'statement_period':{'fiscal_year':annual['table_input']['target_period']['fiscal_year'],
                            'period_start':selected['period_start'],'period_end':selected['period_end']},
        'revenue_period_proof':selected,'original_reports':reports,'amendment_input':amendments,
        'amendment_checks':checks,'source_proofs':proofs,'source_records':records,
        'source_admission':verify_ordinary_source_proofs(data_root=repo_root,proofs=proofs),
        'policy_sha256':sha256_file(path=repo_root/POLICY_PATH),'financial_cross_entity_combination_authorized':False,
        'native_result_created':False,'production_authorized':False})
    return {**body,'income_input_id':content_hash(value=body)}


def verify_income_observations(packet,observations):
    annual=packet['annual_input'];period=packet['statement_period'];checks=[]
    for observation in observations:
        b=observation['source_binding']
        need(b['entity']==annual['entity'] and b['accession']==annual['filing']['accessionNumber']
             and observation['unit']=='USD'
             and all(observation[k]==period[k] for k in ['period_start','period_end']),
             'SELECTED_OBSERVATION_SCOPE_CHANGED')
        by_kind={kind:[r for r in rows if r['concept'].casefold()==b['concept'].casefold()
            and all(r[k]==period[k] for k in ['period_start','period_end'])] for kind,rows in packet['original_reports'].items()}
        need(all(by_kind.values()),'SELECTED_ORIGINAL_FACT_MISSING:'+b['concept'])
        chosen=precision_choice([r for rows in by_kind.values() for r in rows])
        need(observation['value']==chosen['value'],'SELECTED_COMPANYFACTS_AMOUNT_DIFFERS:'+b['concept'])
        checks.append({'observation_id':observation['observation_id'],'original_reports':by_kind})
    return checks
