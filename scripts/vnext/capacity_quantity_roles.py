"""Finite physical quantity roles, independent of annual comparability.

A reported quarterly capability may support a disclosure while remaining
unsuitable for an annual production/capacity ratio. No annualization occurs.
"""
import re
from .capacity_utilization_source import explicit_annual_quantity_statements, need

_NUMBER=r'(?:\d+(?:[,.]\d+)*|one|two|three|four|five|six|seven|eight|nine|ten)'
_AMOUNT=_NUMBER+r'(?:[ -]+(?:thousand|million|billion))?'
_PRODUCT=r'[A-Za-z]+(?:[ -][A-Za-z]+){0,3}'


def _operation_time(antecedent):
    operation=re.search(r'\bwe continued to operate our\b',antecedent,re.I)
    prefix=antecedent[:operation.start()].strip() if operation else antecedent
    leading=re.search(r'(?:^|,)\s*(?:In|During|For(?: the)? fiscal year)\s+(?P<year>\d{4})\s*,?$',prefix,re.I)
    if leading:return {'fiscal_year':int(leading['year'])}
    # An infinitive/cause prefix describes why the footprint was operated;
    # its date does not date the operating assertion itself.
    cause=bool(re.match(r'^(?:To\b|Because of\b|Due to\b)',prefix,re.I))
    remainder=antecedent[operation.start():] if operation else antecedent
    if re.search(r'\b(?:19|20)\d{2}\b',remainder) or (re.search(r'\b(?:19|20)\d{2}\b',prefix) and not cause):
        return {'timing':'UNRESOLVED'}
    if prefix and not cause:return {'timing':'UNRESOLVED'}
    return {'timing':'CURRENT_REPORT'}


def _fact_timing(fact,period):
    return fact.get('timing') or ('CURRENT_REPORT' if fact['fiscal_year']==period.get('fiscal_year') else 'HISTORICAL')


def physical_quantity_role_proofs(text):
    from .regulatory_investigation_candidates import _sentences
    results=explicit_annual_quantity_statements(text=text)
    sentences=list(_sentences(text))
    # Explicit anaphora is limited to a preceding company manufacturing
    # footprint sentence; a supplier/industry mention by itself grants none.
    for index,(start,end,statement) in enumerate(sentences):
        m=re.fullmatch(r'These arrangements maintained a combined manufacturing capacity of (?:approximately )?'
            +r'(?P<amount>'+_AMOUNT+r') (?P<product>'+_PRODUCT+r') per (?P<period>quarter|month|year)\.',statement,re.I)
        if not m or index==0:continue
        previous=sentences[index-1][2]
        if not re.search(r'\bwe continued to operate our (?:domestic |global )?manufacturing footprint\b',previous,re.I):continue
        if re.search(r'\b(?:hypothetical|illustrative|planned|expected|would|could|if)\b',previous,re.I):continue
        results.append({'basis':'AVAILABLE_CAPACITY','statement_text':statement,
            'start_character':start,'end_character':end,'reported_number':m['amount'],
            'reported_product':m['product'],'reported_period':m['period'].lower(),
            'subject':'TARGET_REGISTRANT',**_operation_time(previous),
            'annual_comparability_proven':False,'antecedent_statement':previous})
    for start,end,statement in sentences:
        match=re.fullmatch(r'(?:(?:In|During|For(?: the)? fiscal year)\s+(?P<year>\d{4}),?\s+)?'
            r'Our\s+(?P<facility>(?:[A-Za-z-]+\s+){0,3}(?:plant|plants|factory|factories|facility|facilities))'
            r'\s+can\s+(?:manufacture|produce)\s+(?:approximately\s+)?'
            r'(?P<amount>'+_AMOUNT+r')\s+(?P<product>'+_PRODUCT+r')\s+per\s+(?P<period>quarter|month|year)\.',statement,re.I)
        if match is None:continue
        if re.search(r'\b(?:dollars?|usd|credits?|sales|shipments?|installed|planned)\b',match['product'],re.I):continue
        modifiers=match['facility'].lower().split()[:-1]
        location_or_function={'domestic','global','regional','manufacturing','production'}
        noncurrent={'planned','proposed','future','prospective'}
        if not set(modifiers)<=location_or_function|noncurrent:continue
        role='PLANNED_CAPACITY' if set(modifiers)&noncurrent else 'AVAILABLE_CAPACITY'
        results.append({'basis':role,'statement_text':statement,
            'start_character':start,'end_character':end,'reported_number':match['amount'],
            'reported_product':match['product'],'reported_period':match['period'].lower(),
            'reported_facility':match['facility'],'subject':'TARGET_REGISTRANT',
            **({'fiscal_year':int(match['year'])} if match['year'] else {'timing':'CURRENT_REPORT'}),
            'annual_comparability_proven':False})
    return results


def _industry_scope(texts,finding_timing,period):
    from .regulatory_investigation_candidates import _sentences
    industry=False;target=False;ambiguous=False
    for text in texts:
        for _,_,statement in _sentences(text):
            if not re.search(r'\b(?:capacity|overcapacity|production|manufacturing)\b',statement,re.I):continue
            if re.search(r'\b(?:industry|industrywide)\b',statement,re.I) and (
                re.search(r'\b(?:industry is|industry has|industrywide|across the industry|industry overcapacity)\b',statement,re.I)):
                industry=True
            # Only a company physical-capability assertion overrides an
            # industry assertion. A statement about competitive price effects
            # or the presence of "we" elsewhere is not such an assertion.
            if re.search(r'\bour (?:\w+[ -]){0,4}(?:production|manufacturing) capacity\b',statement,re.I) or re.search(
                r'\bwe (?:operate|maintain|have) (?:\w+[ -]){0,5}(?:manufacturing|production) (?:capacity|facilit(?:y|ies))\b',statement,re.I):
                # A different-period company assertion cannot establish the
                # target subject for this finding's industry assertion.
                years=re.findall(r'\b(?:19|20)\d{2}\b',statement)
                anchored=re.search(r'\b(?:in|during)\s+((?:19|20)\d{2})\s*[.]?$',statement,re.I)
                leading=re.match(r'^(?:In|During)\s+((?:19|20)\d{2}),?\s+',statement,re.I)
                explicit=(anchored or leading)
                if explicit and len(set(years))==1:
                    timing='CURRENT_REPORT' if int(explicit[1])==period.get('fiscal_year') else 'HISTORICAL'
                elif not years and re.search(r'\b(?:capacity (?:is|remains|continues to be)|we (?:operate|maintain|have))\b',statement,re.I):
                    timing='CURRENT_REPORT'
                else:timing='UNRESOLVED'
                if re.search(r'\b(?:if|would|could|hypothetical|illustrative)\b',statement,re.I):timing='UNRESOLVED'
                if timing==finding_timing:target=True
                elif timing=='UNRESOLVED':ambiguous=True
    return ('UNRESOLVED' if ambiguous else 'OTHER_ENTITY') if industry and not target else None


def unsupported_quantity_constructions(text):
    """Turn source candidate families with possible physical amounts into obligations.

    This does not assign a quantity from a keyword. It prevents an unsupported
    amount relation from becoming absence merely because a model omitted it.
    Only separately proved roles or clear nonphysical number uses discharge it.
    """
    from .regulatory_investigation_candidates import _sentences
    from .capacity_utilization_source import ROOT,POLICY_PATH
    from .canonical import strict_json_file
    rules=strict_json_file(path=ROOT/POLICY_PATH)
    families={'ACTUAL_PRODUCTION':rules['possible_actual_production_pattern'],
              'AVAILABLE_CAPACITY':rules['related_production_capacity_pattern']}
    proved={(f['basis'],f['start_character'],f['end_character']) for f in physical_quantity_role_proofs(text)}
    proved.update(('AVAILABLE_CAPACITY',f['start_character'],f['end_character']) for f in physical_quantity_role_proofs(text) if f['basis']=='PLANNED_CAPACITY')
    families['AVAILABLE_CAPACITY']+='|'+r'\bour\s+(?:[A-Za-z-]+\s+){0,8}(?:plant|plants|factory|factories|facility|facilities)\s+can\s+(?:manufacture|produce)\b'
    constructions=[]
    for start,end,statement in _sentences(text):
        amounts=[]
        for match in re.finditer(r'\b'+_AMOUNT+r'\b',statement,re.I):
            before=statement[:match.start()];after=statement[match.end():]
            following=re.match(r'\s*([A-Za-z]+)',after)
            word=following[1].lower() if following else ''
            # Calendar labels, percentages, money and counts of periods do
            # not by themselves create a physical output/capability amount.
            if re.search(r'(?:[$€£]|\bUSD)\s*$',before,re.I) or re.match(r'\s*%',after):continue
            if re.search(r'\b[A-Za-z][A-Za-z0-9]*-$',before):continue
            if re.search(r'\bcancel(?:ling|ing|led|ed)\s*$',before,re.I) and re.match(
                r'\s+(?:previously\s+)?planned\b',after,re.I):continue
            if word in {'percent','percentage','dollars','dollar','credits','credit','tax','years','year',
                        'months','month','quarters','quarter','days','day'}:continue
            if re.fullmatch(r'(?:19|20)\d{2}',match.group()) and (re.search(
                r'\b(?:in|during|for|since|through|from|to|on|fiscal year|year ended|January|February|March|April|May|June|July|August|September|October|November|December)\s*$',before,re.I)):continue
            amounts.append(match)
        if not amounts:continue
        for role,pattern in families.items():
            if re.search(pattern,statement,re.I) and (role,start,end) not in proved:
                constructions.append({'basis':role,'start_character':start,'end_character':end})
    return constructions


def validate_quantity_role_findings(*,units,findings,period,quantity_scope=None):
    from .capacity_quantity_scope import quantity_qualification,local_context_blocks
    from .capacity_utilization_source import _quantity_context_qualified
    blocks={(u['unit_id'],b['block_index']):(u,b) for u in units if u['kind']=='VISIBLE_TEXT'
        for b in u['payload']['blocks']}
    unresolved=[]
    for finding in findings:
        evidence=finding['resolved_evidence'];texts=[e['text'] for e in evidence]
        if finding['kind'] in {'AVAILABLE_CAPACITY','CAPACITY_QUALITATIVE'} and finding['subject']=='TARGET_REGISTRANT':
            industry=_industry_scope(texts,finding['timing'],period)
            need(industry!='OTHER_ENTITY','B13_INDUSTRY_CAPACITY_IS_NOT_TARGET_CAPACITY')
            if industry=='UNRESOLVED':
                unresolved.append({'unit_id':finding['unit_id'],'reason':'B13_TARGET_INDUSTRY_ASSERTION_TIMING_UNSUPPORTED',
                    'source_indices':[e['source_index'] for e in evidence]})
        if finding['kind'] not in {'ACTUAL_PRODUCTION','AVAILABLE_CAPACITY'}:continue
        matched=False;unsupported=False
        for evidence_item in evidence:
            if evidence_item['kind']!='VISIBLE_BLOCK':unsupported=True;continue
            unit,block=blocks[(finding['unit_id'],evidence_item['source_index'])]
            candidates=physical_quantity_role_proofs(block['text'])
            for fact in candidates:
                if fact['basis']!=finding['kind']:continue
                timing=_fact_timing(fact,period)
                if timing=='UNRESOLVED':unsupported=True;continue
                if finding['subject']!='TARGET_REGISTRANT' or finding['timing']!=timing:unsupported=True;continue
                reason=quantity_qualification(block=block,document_id=unit['document_id'],scope=quantity_scope,statement=fact)
                context=local_context_blocks(blocks=[b for (uid,_),(u,b) in blocks.items() if u['document_id']==unit['document_id']],
                    block=block,document_id=unit['document_id'],scope=quantity_scope)
                if reason or _quantity_context_qualified(quoted=block['html_quotation_context'],context=context):
                    unsupported=True;continue
                matched=True
            # A year, cost ratio or industry-demand number is not enough.
            # A direct but unsupported quantity construction stays unfinished.
            if any(f['basis']==finding['kind'] for f in unsupported_quantity_constructions(block['text'])):unsupported=True
        if matched:continue
        if unsupported:
            unresolved.append({'unit_id':finding['unit_id'],'reason':'B13_PHYSICAL_QUANTITY_ROLE_SYNTAX_OR_SCOPE_UNSUPPORTED',
                'source_indices':[e['source_index'] for e in evidence],'quantity_role':finding['kind']})
        else:need(False,'B13_PHYSICAL_QUANTITY_ROLE_NOT_ESTABLISHED')
    for (unit_id,index),(unit,block) in blocks.items():
        for construction in unsupported_quantity_constructions(block['text']):
            reason=quantity_qualification(block=block,document_id=unit['document_id'],scope=quantity_scope,statement=construction)
            context=local_context_blocks(blocks=[b for (uid,_),(u,b) in blocks.items() if u['document_id']==unit['document_id']],
                block=block,document_id=unit['document_id'],scope=quantity_scope)
            if reason in {'EXPLICIT_PRECEDING_NONACTUAL_QUANTITIES','HYPOTHETICAL_HTML_HEADING_SCOPE'} or _quantity_context_qualified(
                quoted=block['html_quotation_context'],context=context):
                continue
            unresolved.append({'unit_id':unit_id,'source_index':index,
                'reason':'B13_PHYSICAL_QUANTITY_ROLE_SYNTAX_OR_SCOPE_UNSUPPORTED',
                'quantity_role':construction['basis'],'statement_start_character':construction['start_character'],
                'statement_end_character':construction['end_character']})
        for fact in physical_quantity_role_proofs(block['text']):
            if fact.get('annual_comparability_proven') is not False:continue
            reason=quantity_qualification(block=block,document_id=unit['document_id'],scope=quantity_scope,statement=fact)
            context=local_context_blocks(blocks=[b for (uid,_),(u,b) in blocks.items() if u['document_id']==unit['document_id']],
                block=block,document_id=unit['document_id'],scope=quantity_scope)
            if reason in {'EXPLICIT_PRECEDING_NONACTUAL_QUANTITIES','HYPOTHETICAL_HTML_HEADING_SCOPE'}:
                current_roles={other['basis'] for other in physical_quantity_role_proofs(block['text'])
                    if _fact_timing(other,period)=='CURRENT_REPORT' and not quantity_qualification(
                        block=block,document_id=unit['document_id'],scope=quantity_scope,statement=other)}
                if current_roles:current_roles.add('CAPACITY_QUALITATIVE')
                positive={'ACTUAL_PRODUCTION','AVAILABLE_CAPACITY','CAPACITY_QUALITATIVE','PLANNED_CAPACITY'}
                need(not any(f['unit_id']==unit_id and f['kind'] in positive-current_roles
                    and f['subject']=='TARGET_REGISTRANT' and f['timing']=='CURRENT_REPORT'
                    and any(e['kind']=='VISIBLE_BLOCK' and e['source_index']==index for e in f['resolved_evidence'])
                    for f in findings),'B13_QUALIFIED_QUANTITY_CANNOT_ESTABLISH_CURRENT_SOURCE')
                continue
            if _fact_timing(fact,period)=='UNRESOLVED' or reason or _quantity_context_qualified(quoted=block['html_quotation_context'],context=context):
                unresolved.append({'unit_id':unit_id,'source_index':index,
                    'reason':'B13_PHYSICAL_QUANTITY_ROLE_SCOPE_UNSUPPORTED'})
                continue
            need(any(f['unit_id']==unit_id and f['subject']==fact['subject']
                and f['kind']==fact['basis'] and f['timing']==_fact_timing(fact,period)
                and any(e['kind']=='VISIBLE_BLOCK' and e['source_index']==index
                    for e in f['resolved_evidence']) for f in findings),'B13_SOURCE_PHYSICAL_QUANTITY_CLASSIFICATION_CONFLICT')
    return unresolved


def validate_visible_source_label_roles(*, findings):
    """Require a source relation for positive narrative roles, not a model reason.

    These are necessary bounded checks, not a general semantic proof. Unknown
    formulations stay unresolved; no alternate label or successful result is
    inferred. Numeric/native roles keep their separate existing validators.
    """
    from .regulatory_investigation_candidates import _sentences
    physical = r'\b(?:manufacturing|production)\s+(?:capacity|capabilities)\b'
    utilization = r'\butili[sz]ation\s+(?:of|at)\s+(?:(?:our|the|its|their|company[’\x27]s)\s+)?(?:[A-Za-z-]+\s+){0,4}manufacturing\s+(?:facility|facilities|plant|plants)\b'
    restriction = r'\b(?:restrict\w*|limit\w*|constrain\w*)\s+(?:[A-Za-z-]+\s+){0,4}(?:production|manufacturing)\b'
    product = (r'\b(?:energy|battery)\s+storage\s+capacity\b|'
               r'\binstalled\s+(?:solar|wind|generating|generation)\s+capacity\b|'
               r'\b(?:battery|batteries|storage\s+system|inverter|solar\s+panel)\b[^.;!?]{0,64}'
               r'\b(?:capacity|rated)\b[^.;!?]{0,48}\b(?:kWh|MWh|GWh|kW|MW|GW)\b')
    qualifiers = r'(?:(?:our|the|its|their|combined|annual|total|domestic|global|existing)\s+)*'
    planning = (r'\b(?:plan(?:s|ned)?|intend(?:s|ed)?|expect(?:s|ed)?)\s+to\s+'
                r'(?:expand|increase|reduce|add)\s+' + qualifiers + r'(?:manufacturing|production)\s+capacity\b|'
                r'\b(?:planned|proposed|future|expected)\s+' + qualifiers + r'(?:manufacturing|production)\s+capacity\b')
    uncertain = r'\b(?:not|never|no|hypothetical|illustrative|abandoned|scrapped|dropped|rejected|cancelled|canceled|if|unless|would|could|might)\b'
    unresolved = []
    for finding in findings:
        kind = finding['kind']
        if kind not in {'CAPACITY_QUALITATIVE', 'PLANNED_CAPACITY', 'PRODUCT_STORAGE_OR_INSTALLED_CAPACITY'}:
            continue
        evidence = finding['resolved_evidence']
        if not evidence or any(e['kind'] != 'VISIBLE_BLOCK' for e in evidence):
            continue
        supported = False
        for ref in evidence:
            for _, _, sentence in _sentences(ref['text']):
                has_physical = re.search(physical, sentence, re.I) is not None
                if kind == 'CAPACITY_QUALITATIVE':
                    supported |= has_physical or re.search(utilization+'|'+restriction, sentence, re.I) is not None
                elif kind == 'PLANNED_CAPACITY':
                    for plan in re.finditer(planning, sentence, re.I):
                        prefix, suffix = sentence[:plan.start()], sentence[plan.end():]
                        # A coordinated debt denial does not negate the plan.
                        # Preserve conditional framing and local cancellation.
                        local_prefix = re.split(r';|\b(?:and|but)\b', prefix, flags=re.I)[-1]
                        local_suffix = re.split(r';|\b(?:and|but)\b', suffix, flags=re.I)[0]
                        conditional = re.search(r'\b(?:if|unless|hypothetical|illustrative)\b', prefix, re.I)
                        cancelled_later = re.search(r'\b(?:scrapped|cancelled|canceled|abandoned|dropped|rejected)\s+'
                            r'(?:(?:the|our|these|those)\s+)?(?:plans?|expansion|it|them)\b', suffix, re.I)
                        supported |= (has_physical and not conditional and not cancelled_later
                                      and re.search(uncertain, local_prefix + ' ' + local_suffix, re.I) is None)
                else:
                    supported |= re.search(product, sentence, re.I) is not None
        if not supported:
            unresolved.append({'unit_id': finding['unit_id'],
                'source_indices': [e['source_index'] for e in evidence],
                'claimed_kind': kind, 'reason': 'B13_VISIBLE_SOURCE_ROLE_NOT_ESTABLISHED',
                'scope': 'Necessary source relation missing; not a relabeling or disclosure-absence conclusion'})
    return unresolved
