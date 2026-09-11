"""Carrying-amount reconciliation from native parsed XBRL, not review numbers."""
from decimal import Decimal
import xml.etree.ElementTree as ET
from .canonical import content_hash,sha256_bytes,sha256_file,strict_json_file,decimal_text
from .deterministic_router import parse_accession_xbrl_source,_numeric_xbrl_value
from .calculator import calculate_metric,_result_and_trace


def measurement_inputs(*,raw,source,spec,target,filed,data_root):
    from .r5_b06_structured import need,POLICY_PATH
    policy=strict_json_file(path=data_root/POLICY_PATH)
    path=data_root/policy['measurement_review_file'];need(sha256_file(path=path)==policy['measurement_review_sha256'],'MEASUREMENT_REVIEW_CHANGED')
    reviewed=strict_json_file(path=path)
    matches=[r for r in reviewed['relationships'] if r['source_sha256']==sha256_bytes(content=raw)]
    if not matches:return None
    need(len(matches)==1 and source['raw_asset_id']=='sha256:'+sha256_bytes(content=raw),'MEASUREMENT_SOURCE_AMBIGUOUS')
    review=matches[0];models=spec['compiled']['quality_rule']['carrying_models'];need(review['model_id'] in models,'MEASUREMENT_MODEL_UNKNOWN');model=models[review['model_id']]
    need(source['accession']==target['accession'],'MEASUREMENT_ACCESSION_CHANGED')
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    notes=[f for f in parsed.facts if f['qualified_name'].casefold()==review['note_concept'].casefold() and sha256_bytes(content=f['text'].encode())==review['note_text_sha256']]
    need(len(notes)==1,'MEASUREMENT_REVIEWED_NOTE_CHANGED')
    note_context=parsed.contexts[notes[0]['context_ref']]
    need(str(int(note_context['entity_identifier']))==target['entity'] and note_context['period_end']==target['period_end'] and not note_context['dimensions'] and not note_context['typed_dimension_count'],'MEASUREMENT_NOTE_SCOPE_CHANGED')
    root=ET.fromstring(raw);units={}
    for element in root.iter():
        if element.tag.split('}')[-1]=='unit':
            measures=[(x.text or '').strip() for x in element.iter() if x.tag.split('}')[-1]=='measure']
            if len(measures)==1 and measures[0]=='iso4217:USD':units[element.attrib['id']]='USD'
    def fact(concept):
        candidates=[]
        for f in parsed.facts:
            c=parsed.contexts[f['context_ref']]
            if f['qualified_name'].casefold()!=concept.casefold() or c.get('period_start')!=c['period_end'] or c['period_end']!=target['period_end'] or c['dimensions'] or c['typed_dimension_count']:continue
            need(str(int(c['entity_identifier']))==target['entity'],'MEASUREMENT_ENTITY_CHANGED')
            need(f['unit_ref'] in units,'MEASUREMENT_UNIT_UNKNOWN')
            v=_numeric_xbrl_value(text=f['text'],scale=f['scale'],sign=f['sign'])
            candidates.append((f,v))
        need(bool(candidates) and len({v for _,v in candidates})==1,'MEASUREMENT_FACT_MISSING_OR_CONFLICT:'+concept)
        f,v=sorted(candidates,key=lambda x:x[0]['ordinal'])[0]
        binding={'raw_asset_id':source['raw_asset_id'],'source_reference_id':source['source_reference_id'],'source_role':source['source_role'],'document_name':source['document_name'],'accession':source['accession'],'entity':target['entity'],'xbrl_context_ref':f['context_ref'],'xbrl_fact_ordinal':f['ordinal']}
        return {'accession':source['accession'],'concept':concept,'duration_days':0,'entity':target['entity'],'fact_id':'fact:'+content_hash(value={'binding':binding,'value':v,'parsed_source_id':parsed.parsed_source_id}),'filed':filed,'fiscal_period':'FY','form':'10-K','period_start':target['period_end'],'period_end':target['period_end'],'source_binding':binding,'unit':'USD','value':v}
    gross=fact(model['gross']);deductions=[fact(c) for c in model['deductions']];current=fact(model['current']);noncurrent=fact(model['noncurrent'])
    selected=[gross,*deductions,current,noncurrent]
    need(len({f['source_binding']['xbrl_context_ref'] for f in selected})==1,'MEASUREMENT_CONTEXT_MIXED')
    need(all(Decimal(f['value'])>=0 for f in selected),'MEASUREMENT_ADJUSTMENT_SIGN_INVALID')
    net=Decimal(gross['value'])-sum(Decimal(f['value']) for f in deductions)
    need(net==Decimal(current['value'])+Decimal(noncurrent['value']),'MEASUREMENT_RECONCILIATION_FAILED')
    reported=None
    if model.get('carrying_total'):
        reported=fact(model['carrying_total']);need(Decimal(reported['value'])==net,'MEASUREMENT_CARRYING_TOTAL_CONFLICT')
    return {'model_id':review['model_id'],'basis':'PERIOD_END_CARRYING_AMOUNT','calculation_facts':[gross,*deductions],
            'gross':gross,'deductions':deductions,'current':current,'noncurrent':noncurrent,'reported_carrying':reported,
            'carrying_amount':decimal_text(value=net),'equation':'gross - deductions = current + noncurrent = carrying',
            'source_reference_id':source['source_reference_id'],'reviewed_note':{'concept':review['note_concept'],'sha256':review['note_text_sha256'],'ordinal':notes[0]['ordinal']},
            'relationship_review_id':content_hash(value=review),'reviewer':reviewed['reviewer'],'review_file_sha256':policy['measurement_review_sha256']}


def resolve_carrying(*,spec,target,traits,facts,scope_reasons=(),measurement=None):
    from .r5_b06_structured import _resolve_primary_v1
    result,trace,observations,audit=_resolve_primary_v1(spec=spec,target=target,traits=traits,facts=facts,scope_reasons=scope_reasons)
    reasons=list(audit['reasons']);rule=spec['compiled']['quality_rule']
    if measurement:
        # Reconciliation never expands the debt set or removes scope issues.
        reasons=[r for r in reasons if r!='DIRECT_TOTAL_CONFLICT']
        comparison_roles=[measurement['gross'],*measurement['deductions'],measurement['current'],measurement['noncurrent']]
        if measurement['reported_carrying']:comparison_roles.append(measurement['reported_carrying'])
        for source_fact in comparison_roles:
            cf=[f for f in facts if f['concept']==source_fact['concept'] and f['accession']==target['accession'] and f['period_end']==target['period_end'] and f['period_start']==target['period_start'] and f['entity']==target['entity']]
            if (source_fact is measurement['gross'] and not cf) or (cf and {(f['value'],f['unit']) for f in cf}!={(source_fact['value'],source_fact['unit'])}):
                reasons.append('MEASUREMENT_COMPANYFACTS_XBRL_DIFFER:'+source_fact['concept'])
        equity=[f for f in facts if f['fact_id']==audit['equity_fact_id']]
        if not reasons and len(equity)==1:
            result,trace,observations=calculate_metric(compiled_spec=spec,target=target,company_traits=traits,structured_facts=measurement['calculation_facts']+equity,verified_observations=[])
            if result['publication']=='WITHHELD':reasons.append(result['reason_code'])
        audit['debt']=measurement['carrying_amount'];audit['branch']='RECONCILED_CARRYING_AMOUNT'
        audit['historical_priority_candidate_fact_ids']=audit['chosen_debt_fact_ids']
        audit['chosen_debt_fact_ids']=[f['fact_id'] for f in measurement['calculation_facts']]
        audit['debt_candidates']+=measurement['calculation_facts']
    elif audit['branch']=='DIRECT_TOTAL_NO_ADDERS' and any(f['fact_id'] in audit['chosen_debt_fact_ids'] and f['concept'].endswith(':LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities') for f in facts):
        reasons.append('CARRYING_MEASUREMENT_NOT_ESTABLISHED')
    if reasons:
        result,trace=_result_and_trace(compiled_spec=spec,target=target,applicability='APPLICABLE',quality='NONE',publication='WITHHELD',reason_code='STRUCTURED_SOURCE_AMBIGUOUS',value=None,result_unit=None,trace_steps=[{'event':'WITHHELD','reason_code':'STRUCTURED_SOURCE_AMBIGUOUS'}],input_ids=[]);observations=[]
    audit.update(resolver=rule['resolver'],measurement_basis=rule['measurement_basis'],measurement_reconciliation=measurement,reasons=sorted(set(reasons)),result_id=result['result_id'])
    audit.pop('selection_id');audit['selection_id']=content_hash(value=audit)
    return result,trace,observations,audit
