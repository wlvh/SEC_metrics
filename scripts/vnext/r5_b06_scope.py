"""Source-bound disjoint financing debt sets on the shared native calculator.

The review proves which reported liability sets overlap. It contains no input
amounts: all numerical roles, precision and equations are rebuilt from raw XBRL.
"""
from decimal import Decimal
import xml.etree.ElementTree as ET
from .canonical import content_hash,sha256_file,sha256_bytes,strict_json_file,decimal_text
from .deterministic_router import parse_accession_xbrl_source,_numeric_xbrl_value
from .constraints import evaluate_expression
from .calculator import calculate_metric,_result_and_trace

RESOLVER='debt_equity_financing_set_v3'


def precision_choice(candidates):
    """Accept coarser reporting only when compatible with the finest amount."""
    from .r5_b06_structured import need
    need(bool(candidates),'DEBT_FACT_MISSING')
    def decimals(c):
        d=c['decimals'];need(d=='INF' or (isinstance(d,str) and d.lstrip('-').isdigit()),'DEBT_PRECISION_UNKNOWN')
        return 10000 if d=='INF' else int(d)
    ranks=[decimals(c) for c in candidates];best=max(ranks)
    finest=[c for c,r in zip(candidates,ranks) if r==best]
    need(len({c['value'] for c in finest})==1,'DEBT_SAME_PRECISION_CONFLICT')
    selected=min(finest,key=lambda c:c['ordinal']);v=Decimal(selected['value'])
    for c,d in zip(candidates,ranks):
        if d==best:continue
        radius=Decimal(10)**(-d)/2
        need(abs(Decimal(c['value'])-v)<=radius,'DEBT_REPORTING_PRECISION_CONFLICT')
    return selected


def validate_partition(model, required, *, complete=True, absent=()):
    """Every target liability class belongs to one group, never two totals."""
    from .r5_b06_structured import need
    need(len(model['inputs'])==len({c.casefold() for c in model['inputs'].values()}),'DEBT_FACT_REUSED_AS_DIFFERENT_ROLES')
    parts=[k for g in model['groups'] for k in g['coverage']]
    need(len(parts)==len(set(parts)),'DEBT_OVERLAPPING_GROUPS')
    need(not set(parts)-set(required) and not set(absent)&set(parts) and not set(absent)-set(required),'DEBT_SCOPE_CLASS_INVALID')
    if complete:need(set(parts)|set(absent)==set(required),'DEBT_SCOPE_INCOMPLETE')
    roles=[r for g in model['groups'] for r in g['roles']]
    need(len(roles)==len(set(roles)) and set(roles)==set(model['inputs']),'DEBT_COMPONENT_REUSED_OR_OMITTED')
    expressions=[g['expression'] for g in model['groups']]
    expected=expressions[0] if len(expressions)==1 else {'op':'add','args':expressions}
    need(model['expression']==expected,'DEBT_GROUP_FORMULA_DIFFERS')
    def refs(e):
        if isinstance(e,str):return [e]
        need(isinstance(e,dict) and set(e)=={'op','args'} and e['op'] in {'add','subtract'} and len(e['args'])>=2,'DEBT_FORMULA_INVALID')
        return [r for a in e['args'] for r in refs(a)]
    for g in model['groups']:
        used=refs(g['expression']);need(len(used)==len(set(used)) and set(used)==set(g['roles']),'DEBT_FORMULA_REPEATS_COMPONENT')


def scope_inputs(*,raw,source,spec,target,filed,data_root):
    from .r5_b06_structured import need,POLICY_PATH
    policy=strict_json_file(path=data_root/POLICY_PATH)
    path=data_root/policy['debt_scope_review_file'];need(sha256_file(path=path)==policy['debt_scope_review_sha256'],'DEBT_SCOPE_REVIEW_CHANGED')
    reviews=strict_json_file(path=path)
    matches=[x for x in reviews['relationships'] if x['source_sha256']==sha256_bytes(content=raw)]
    if not matches:return None
    need(len(matches)==1 and source['raw_asset_id']=='sha256:'+sha256_bytes(content=raw),'DEBT_SCOPE_SOURCE_AMBIGUOUS')
    need(source['accession']==target['accession'],'DEBT_SCOPE_ACCESSION_CHANGED')
    review=matches[0]
    need(type(review['complete']) is bool and isinstance(review['unresolved'],list) and all(isinstance(x,str) and x for x in review['unresolved']) and bool(review['notes']),'DEBT_REVIEW_STATUS_INVALID')
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    notes=[]
    for n in review['notes']:
        found=[f for f in parsed.facts if f['qualified_name'].casefold()==n['concept'].casefold() and sha256_bytes(content=f['text'].encode())==n['text_sha256']]
        need(len(found)==1,'DEBT_SCOPE_NOTE_CHANGED');f=found[0];c=parsed.contexts[f['context_ref']]
        need(str(int(c['entity_identifier']))==target['entity'] and c['period_end']==target['period_end'],'DEBT_SCOPE_NOTE_CONTEXT_CHANGED')
        notes.append({'concept':n['concept'],'text_sha256':n['text_sha256'],'ordinal':f['ordinal'],'context':{**dict(c),'dimensions':dict(c['dimensions'])}})
    proof={'source_sha256':review['source_sha256'],'source_reference_id':source['source_reference_id'],'review_id':content_hash(value=review),'review_file_sha256':policy['debt_scope_review_sha256'],'reviewer':reviews['reviewer'],'scope_class':review['scope_class'],'notes':notes,'findings':review['findings'],'unresolved':review['unresolved'],'complete':review['complete']}
    rule=spec['compiled']['quality_rule'];registry_path=data_root/rule['debt_set_registry']
    need(sha256_file(path=registry_path)==rule['debt_set_registry_sha256'],'DEBT_SET_REGISTRY_CHANGED')
    registry=strict_json_file(path=registry_path);rule={**rule,**registry}
    proof['debt_scope_definition']=rule['debt_scope_definition']
    if not review.get('model_id'):return proof
    model=rule['debt_set_models'][review['model_id']]
    need(not model.get('diagnostic_only') or review['complete'] is False,'DEBT_DIAGNOSTIC_MODEL_NOT_PUBLISHABLE')
    required=rule['required_liability_classes'][review['scope_class']];validate_partition(model,required,complete=review['complete'],absent=review.get('established_absent_classes',[]))
    # Decimal metadata is read from the same exact source. The existing native
    # parser owns each context and ordinal; ET is used only to recover decimals.
    tree=ET.fromstring(raw);nodes=[n for n in tree.iter() if 'contextRef' in n.attrib];units={}
    for e in tree.iter():
        if e.tag.split('}')[-1]=='unit':
            ms=[(x.text or '').strip() for x in e.iter() if x.tag.split('}')[-1]=='measure']
            if len(ms)==1 and ms[0]=='iso4217:USD':units[e.attrib['id']]='USD'
    def fact(concept):
        candidates=[]
        for f in parsed.facts:
            c=parsed.contexts[f['context_ref']]
            if f['qualified_name'].casefold()!=concept.casefold() or c['period_start']!=c['period_end'] or c['period_end']!=target['period_end'] or c['dimensions'] or c['typed_dimension_count']:continue
            need(str(int(c['entity_identifier']))==target['entity'] and f['unit_ref'] in units,'DEBT_FACT_SCOPE_OR_UNIT_CHANGED')
            node=nodes[f['ordinal']-1];need(node.attrib['contextRef']==f['context_ref'] and node.tag.split('}')[-1].casefold()==concept.split(':')[-1].casefold(),'DEBT_PRECISION_LOCATOR_CHANGED')
            value=_numeric_xbrl_value(text=f['text'],scale=f['scale'],sign=f['sign']);need(Decimal(value)>=0 or concept==rule['equity_concept'],'NEGATIVE_DEBT_COMPONENT')
            candidates.append({'value':value,'decimals':node.attrib.get('decimals'),'ordinal':f['ordinal'],'context_ref':f['context_ref']})
        selected=precision_choice(candidates)
        binding={'raw_asset_id':source['raw_asset_id'],'source_reference_id':source['source_reference_id'],'source_role':source['source_role'],'document_name':source['document_name'],'accession':source['accession'],'entity':target['entity'],'xbrl_context_ref':selected['context_ref'],'xbrl_fact_ordinal':selected['ordinal'],'reported_decimals':selected['decimals']}
        record={'accession':source['accession'],'concept':concept,'duration_days':0,'entity':target['entity'],'fact_id':'fact:'+content_hash(value={'binding':binding,'value':selected['value'],'parsed_source_id':parsed.parsed_source_id}),'filed':filed,'fiscal_period':'FY','form':'10-K','period_start':target['period_end'],'period_end':target['period_end'],'source_binding':binding,'unit':'USD','value':selected['value']}
        return record,{'concept':concept,'chosen_ordinal':selected['ordinal'],'all_reports':candidates}
    roles={};precision=[]
    for role,concept in model['inputs'].items():roles[role],p=fact(concept);precision.append(p)
    checks=[]
    for check in model.get('checks',[]):
        values={r:Decimal(f['value']) for r,f in roles.items()}
        extras=[]
        for role,concept in check['inputs'].items():
            f,p=fact(concept);values[role]=Decimal(f['value']);precision.append(p);extras.append(f)
        lhs=evaluate_expression(expression=check['left'],values=values);rhs=evaluate_expression(expression=check['right'],values=values)
        need(lhs==rhs,'DEBT_COMPONENT_RECONCILIATION_FAILED')
        checks.append({'rule':check,'source_facts':extras,'left_value':decimal_text(value=lhs),'right_value':decimal_text(value=rhs)})
    equity,p=fact(rule['equity_concept']);precision.append(p)
    need(len({f['source_binding']['xbrl_context_ref'] for f in [*roles.values(),equity]})==1,'DEBT_COMPONENT_CONTEXT_MIXED')
    debt=evaluate_expression(expression=model['expression'],values={r:Decimal(f['value']) for r,f in roles.items()})
    proof.update(model_id=review['model_id'],model=model,calculation_facts=list(roles.values())+[equity],equity_fact=equity,components=roles,carrying_amount=decimal_text(value=debt),precision=precision,reconciliations=checks)
    return proof


def resolve_financing(*,spec,target,traits,facts,scope_reasons=(),measurement=None):
    from .r5_b06_structured import need
    rule=spec['compiled']['quality_rule'];need(target['scope']=={'entity_scope':rule['scope']} and target['period_start']==target['period_end'],'STRUCTURED_INSTANT_SCOPE_REQUIRED')
    reasons=list(scope_reasons);selected=[];equity=None;debt=None
    if measurement is None:reasons.append('DEBT_SET_RELATIONSHIP_NOT_ESTABLISHED')
    else:
        reasons.extend(measurement['unresolved'])
        if measurement['complete'] is not True:reasons.append('DEBT_SET_COMPLETENESS_UNPROVEN')
        if 'calculation_facts' in measurement:
            selected=measurement['calculation_facts'];equity=measurement['equity_fact'];debt=measurement['carrying_amount']
            # Any present same-filing CF report must be a compatible actual XML
            # report; a reconciled gross must not erase another basis conflict.
            for p in measurement['precision']:
                values={x['value'] for x in p['all_reports']}
                cf=[f for f in facts if f['concept']==p['concept'] and f['entity']==target['entity'] and f['accession']==target['accession'] and f['period_start']==f['period_end']==target['period_end']]
                if any(f['unit']!='USD' or f['value'] not in values for f in cf):reasons.append('DEBT_COMPANYFACTS_XBRL_CONFLICT:'+p['concept'])
            model=measurement['model'];inputs=spec['compiled']['inputs']['debt']['choose_first']
            # The exact model must be a declared Spec branch. Supplying an
            # arbitrary runtime model cannot replace reviewed calculation rules.
            def matches(b):
                expression=model['expression']
                if isinstance(expression,str):
                    return b.get('extraction_role',{}).get('approved_concepts')==[model['inputs'][expression]]
                d=b.get('derived_role',{})
                return (d.get('op'),d.get('args'),{k:v['approved_concepts'][0] for k,v in d.get('inputs',{}).items()})==(expression['op'],expression['args'],model['inputs'])
            if measurement['complete']:need(any(matches(b) for b in inputs),'DEBT_MODEL_NOT_IN_SPEC')
    if not reasons and selected:
        result,trace,observations=calculate_metric(compiled_spec=spec,target=target,company_traits=traits,structured_facts=selected,verified_observations=[])
        if result['publication']=='WITHHELD':reasons.append(result['reason_code'])
    if reasons or not selected:
        result,trace=_result_and_trace(compiled_spec=spec,target=target,applicability='APPLICABLE',quality='NONE',publication='WITHHELD',reason_code='STRUCTURED_SOURCE_AMBIGUOUS',value=None,result_unit=None,trace_steps=[{'event':'WITHHELD','reason_code':'STRUCTURED_SOURCE_AMBIGUOUS'}],input_ids=[]);observations=[]
    exact=[f for f in facts if f['accession']==target['accession'] and f['period_start']==f['period_end']==target['period_end'] and f['entity']==target['entity']]
    audit={'record_type':'STRUCTURED_PRIMARY_SELECTION','resolver':RESOLVER,'target':target,'branch':None if measurement is None else measurement.get('model_id'),'debt_candidates':exact+[f for f in selected if f not in exact],'chosen_debt_fact_ids':[f['fact_id'] for f in selected if f is not equity],'equity_fact_id':None if equity is None else equity['fact_id'],'debt':debt if measurement and measurement['complete'] else None,'proven_debt_subtotal':debt,'equity':None if equity is None else equity['value'],'reasons':sorted(set(reasons)),'nonpositive_equity':equity is not None and Decimal(equity['value'])<=0,'fallback_executed':False,'provider_paid_sec_calls':[0,0,0],'measurement_basis':rule['measurement_basis'],'measurement_reconciliation':measurement,'debt_scope_definition':None if measurement is None else measurement.get('debt_scope_definition'),'result_id':result['result_id']}
    audit['selection_id']=content_hash(value=audit)
    return result,trace,observations,audit
