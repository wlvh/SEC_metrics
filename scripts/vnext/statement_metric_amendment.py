"""Explicit original-statement input properties for B04/B05/B07, not results.

The existing Part III identity/note/cover/correction checks are reused. The
target's approved component roles stay explicit; no old income property or
annual scope is relabelled as proof for all financial metrics.
"""
import re
from decimal import Decimal
from datetime import date

from .canonical import content_hash, sha256_bytes, sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .ordinary_income_input import inspect_income_amendment, need, POLICY_PATH
from .instant_balance_amendment_v2 import _text_units
from .table_grid import build_table_grid

CATALOG_PATH='catalog/deterministic_metrics.json'
_COMPONENT_SUBJECTS={
    'net_income':r'\b(?:(?:net|consolidated) (?:income|loss|earnings|profit)|profit (?:or|and) loss)\b',
    'operating_income':r'\boperating (?:income|loss|profit)\b',
    'interest_expense':r'\b(?:interest (?:expense|cost)|borrowing costs?)\b',
    'pretax_income':r'\b(?:(?:pre-tax|pretax) (?:income|loss|profit)|(?:income|loss|profit) before (?:income )?tax(?:es)?)\b',
    'aggregate_nonoperating':r'\b(?:non-?operating (?:income|expense|loss)|other non-?operating (?:income|expense))\b',
    'operating_cash_flow':r'\b(?:net cash (?:provided by|used in) (?:operating activities|operations)|operating cash flows?|cash flows? from operating activities)\b',
    'capital_expenditures':r'\b(?:capital expenditures?|payments to acquire (?:property,? plant(?:,? and)? equipment|productive assets)|purchases of property,? plant(?:,? and)? equipment)\b',
}
_INPUT_CLASSES={'B04':'ORIGINAL_REPORTED_NET_INCOME_VALUES',
                'B05':'ORIGINAL_REPORTED_FREE_CASH_FLOW_COMPONENT_VALUES',
                'B07':'ORIGINAL_INTEREST_COVERAGE_COMPONENT_VALUES'}
_COMPONENT_ROLES={'B04':{'net_income'},
                  'B05':{'operating_cash_flow','capital_expenditures'},
                  'B07':{'operating_income','interest_expense','pretax_income','aggregate_nonoperating'}}
_INCOME_TAX_SUBJECT=r'\b(?:income taxes?|tax expense|tax benefit)\b'
# Complete row labels differ from references to adjusted compensation targets.
# Parenthetical income/loss is retained as meaning, not stripped globally.
_ROW_LABELS={
    'net_income':r'(?:net (?:income|loss|earnings|profit)(?:\s*\((?:loss|income)\))?|profit (?:or|and) loss)',
    'operating_income':r'operating (?:income|loss|profit)(?:\s*\((?:loss|income)\))?',
    'interest_expense':r'(?:interest (?:expense|cost)(?:,?\s*(?:net|non-operating))?|borrowing costs?)',
    'pretax_income':r'(?:(?:pre-tax|pretax) (?:income|loss|profit)|(?:income|loss|profit) before (?:income )?tax(?:es)?)',
    'aggregate_nonoperating':r'(?:other )?non-?operating (?:income|expense|loss)(?:\s*\((?:expense|income)\))?(?:,?\s*net)?',
    'operating_cash_flow':r'(?:net cash (?:provided by|used in) (?:operating activities|operations)|operating cash flows?|cash flows? from operating activities)',
    'capital_expenditures':r'(?:capital expenditures?|payments to acquire (?:property,? plant(?:,? and)? equipment|productive assets)|purchases of property,? plant(?:,? and)? equipment)',
}
# Amounts in a component-bearing paragraph require an additional relation
# proof. They cannot silently become unchanged merely because no financial
# statement or financial native fact was added. This is a refusal boundary,
# not extraction of a number or an English semantic classification.
_AMOUNT=re.compile(r'(?:[$€£]\s*[-(]?\s*\d|\bUSD\s*[-(]?\s*\d|\d[\d,.]*\s*(?:million|billion|thousand)\b)',re.I)


def _original_cash_flow_total(scope, raw, components):
    """Read an original full-year total; a same-valued subtotal is insufficient."""
    from .deterministic_router import parse_accession_xbrl_source
    from .text_results_v2 import _ReportedFactMetadata, _verified_context
    from .governance_signals import _source_value
    from .financial_structured import _InlineTableIndex, _fact_cells
    from .financial_duration import _cell_proof, _column_period
    from .selected_revenue_scope_v1 import _label
    from .composite_scope import index_source_structure
    from .annual_amendment_scope import _words
    old=scope['original'];doc=old['document']
    need(doc['raw_asset_id']=='sha256:'+sha256_bytes(content=raw)
         and doc['byte_length']==len(raw),'STATEMENT_ORIGINAL_RAW_BINDING_CHANGED')
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close()
    need(meta.ordinal==len(parsed.facts),'STATEMENT_ORIGINAL_NATIVE_STREAM_CHANGED')
    approved={name.casefold() for c in components if c['role']=='operating_cash_flow'
              for name in c['approved_concepts']}
    period=old['period'];facts=[]
    for fact in parsed.facts:
        info=meta.facts[fact['ordinal']];uri,name=info['concept']
        if name.casefold() not in approved or not re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri):continue
        context=parsed.contexts[fact['context_ref']]
        if (any(context[k]!=period[k] for k in period) or context['dimensions']
                or context['typed_dimension_count']):continue
        if (str(int(context['entity_identifier']))!=str(int(doc['cik']))
                or meta.units.get(fact['unit_ref'])!={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}):continue
        facts.append((fact,info,context,_source_value(fact,info)))
    if not facts or len({f[3] for f in facts})!=1:return None
    index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close()
    cells=_fact_cells(index,parsed,{f[0]['ordinal'] for f in facts})
    structure=index_source_structure(source_bytes=raw)
    end=date.fromisoformat(period['period_end']);proofs=[]
    for fact,info,context,value in facts:
        bound=cells.get(fact['ordinal'])
        if bound is None:continue
        table,cell=bound;label=_label(table,cell)
        if not re.fullmatch(r'Net cash(?: flow)? (?:provided by|used in) operating activities',label,re.I):continue
        column,headers,reason=_column_period(table=table,selected=cell)
        if reason or column['year']!=end.year:continue
        header_text=[c['text'] for r in table['rows'][:cell['row_index']] for c in r['cells'] if c['is_origin']]
        if not any(re.fullmatch(r'Year Ended '+end.strftime('%B')+' '+str(end.day)+r',?',t,re.I) for t in header_text):continue
        span=structure['tables'][table['order']]
        previous=max((t['end_byte'] for t in structure['tables'] if t['end_byte']<=span['start_byte']),default=0)
        intro=[b for b in structure['blocks'] if not b['inside_table']
               and previous<=b['start_byte']<b['end_byte']<=span['start_byte']]
        title=[b for b in intro if re.fullmatch(r'CONSOLIDATED STATEMENTS? OF CASH FLOWS',b['visible_text'],re.I)]
        issuer=[b for b in intro if any(_words(b['visible_text'])==_words(n+' AND SUBSIDIARIES')
                   for n in doc['registrant_names'])]
        scale=[b for b in intro if re.fullmatch(r'\(In (millions|thousands)\)',b['visible_text'],re.I)]
        if len(title)!=1 or len(issuer)!=1 or len(scale)!=1:continue
        factor={'millions':Decimal(1000000),'thousands':Decimal(1000)}[
            re.fullmatch(r'\(In (millions|thousands)\)',scale[0]['visible_text'],re.I)[1].casefold()]
        try:visible=Decimal(cell['text'].replace(',','').replace('(','-').replace(')',''))*factor
        except ArithmeticError:continue
        if visible!=Decimal(value):continue
        proofs.append({'ordinal':fact['ordinal'],'concept':'us-gaap:'+info['concept'][1],
            'reported_value':value,'unit':'USD','period':dict(period),
            'context':_verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=meta),
            'statement_title':title[0],'issuer_title':issuer[0],'unit_header':scale[0],
            'row_label':label,'amount_cell':_cell_proof(table=table,cell=cell),
            'period_headers':[_cell_proof(table=table,cell=h) for h,_,_ in headers],
            'source_reference':doc['source_reference']})
    return proofs[0] if len(proofs)==1 else None


def _cash_flow_repeat(scope, units, unit, original):
    """Bind one first-person annual highlight to the original total.

    This finite relation does not infer a missing period/subject, interpret an
    adjusted target, or substitute the repeated amount into a Calculator.
    """
    if original is None:return None
    text=unit['text']
    if not text.startswith('We '):return None
    match=re.search(r'\b(?:generated|generating|reported) net operating cash flow of '
                    r'\$(?P<amount>[0-9][0-9,.]*) (?P<scale>million|billion|thousand)\b',text,re.I)
    if match is None:return None
    if _AMOUNT.search(text[:match.start()]) or _AMOUNT.search(text[match.end():]):return None
    # Do not borrow the issuer scope for another subject or a qualified measure.
    prefix=text[:match.start()];suffix=text[match.end():]
    if prefix!='We ' and not re.fullmatch(r'We [a-z ,]+including ',prefix):return None
    # Do not discard arbitrary text after a dash. Only a closed comparative
    # aside to an earlier year is supported; other local scope remains unknown.
    if not re.fullmatch(r'\s*\.?\s*',suffix):
        comparison=re.fullmatch(r'\s*[—–]\s*(?:an? )?(?:[a-z]+ )*'
            r'(?:improvement|increase|decrease) (?:from|over) (?P<year>[0-9]{4})'
            r'\s*[—–]\s+and (?P<activity>.+)',suffix,re.I)
        fiscal=[f['value'] for f in scope['original']['identity'] if f['name']=='documentfiscalyearfocus']
        if comparison is None or len(fiscal)!=1 or int(comparison['year'])>=int(fiscal[0]):return None
        # A separate activity cannot quietly qualify the CFO, its period or
        # entity. Unrecognized measure/amount/scope text stays unresolved.
        if re.search(r'\b(?:cash|flow|amount|measure|value|result|exclu\w*|adjusted|'
                     r'continuing|discontinued|subsidiar\w*|segment\w*|[0-9]{4})\b',
                     comparison['activity'],re.I):return None
    indices=unit.get('block_indices',[unit.get('block_index')])
    if set(indices)&set(scope['amendment']['quoted_block_indices']):return None
    if (re.search(r'\b(?:subsidiar\w*|segment\w*|they|their)\b',prefix,re.I)
            or re.search(r'\b(?:adjusted|continuing|discontinued|excluding|only|limited to)\b',suffix,re.I)):
        return None
    amount=Decimal(match['amount'].replace(',',''))*{
        'million':Decimal(1000000),'billion':Decimal(1000000000),'thousand':Decimal(1000)}[match['scale'].casefold()]
    if amount!=Decimal(original['reported_value']):return None
    position=units.index(unit)
    # Bullet list entries remain separate source units. Its immediate lead-in
    # binds the Company's fiscal year; arbitrary earlier headings are not used.
    lead=position-1
    while lead>=1 and units[lead]['text']=='•':
        lead-=1
        if units[lead]['text'].endswith(':'):break
        lead-=1
    if lead<0:return None
    introduction=units[lead]
    pattern=r".+?\bthe Company[’']s (?P<year>[0-9]{4}) qualitative performance goals, which included the following highlights:"
    context=re.fullmatch(pattern,introduction['text'],re.I)
    fy=[f['value'] for f in scope['original']['identity'] if f['name']=='documentfiscalyearfocus']
    context_indices=introduction.get('block_indices',[introduction.get('block_index')])
    if (context is None or fy!=[context['year']]
            or set(context_indices)&set(scope['amendment']['quoted_block_indices'])):return None
    return {'role':'operating_cash_flow','reported_value':original['reported_value'],
        'source_unit':unit,'period_and_subject_introduction':introduction,
        'original_fact':original,'relation':'DUPLICATE_ORIGINAL_FULL_YEAR_REPORTED_TOTAL',
        'quantity_substitution_permitted':False}


def inspect_statement_metric_amendment(scope,raw,*,metric_id,original_raw=None):
    """Return a bound, metric-specific property or a concrete unresolved cause.

    Original quantity selection, unit/period/subject, continuity, scope,
    coverage and Calculator checks remain the consumer's responsibilities.
    Default income and instant-balance callers do not consume this API.
    """
    need(metric_id in _INPUT_CLASSES,'STATEMENT_METRIC_NOT_SUPPORTED')
    doc=scope['amendment']['document']
    need(doc['raw_asset_id']=='sha256:'+sha256_bytes(content=raw)
         and doc['byte_length']==len(raw),'STATEMENT_AMENDMENT_RAW_BINDING_CHANGED')
    definition=strict_json_file(path=ROOT/CATALOG_PATH)['metrics'][metric_id]
    components=[c for branch in definition['branches'] for c in branch['components']]
    roles=sorted({c['role'] for c in components})
    expected=_COMPONENT_ROLES[metric_id]
    need(set(roles)==expected and all(c['unit']=='USD' and c['period_role']=='current_annual'
        and c['accession_role']=='current' and c['dimension_policy']=='NONE' for c in components),
        'STATEMENT_COMPONENT_DEFINITION_CHANGED')
    subjects='(?:'+'|'.join(_COMPONENT_SUBJECTS[role] for role in roles)+')'
    rules=strict_json_file(path=ROOT/POLICY_PATH)
    typed_rules={**rules,'input_class':_INPUT_CLASSES[metric_id],
        'income_subject_pattern':'(?:'+rules['income_subject_pattern']+'|'+subjects+'|'+_INCOME_TAX_SUBJECT+')'}
    checked=inspect_income_amendment(scope,raw,typed_rules)
    reported=[];duplicates=[]
    original_total=None
    if metric_id=='B05' and original_raw is not None:
        original_total=_original_cash_flow_total(scope,original_raw,components)
    # An already proved identical-original link correction has no additional
    # statement content. Part III needs this further whole-document check.
    if not checked.get('inherited_statement_proof'):
        units=_text_units(doc['blocks'],raw,scope.get('note_layout','blocks-v1'))
        for unit in units:
            matched=[role for role in roles if re.search(_COMPONENT_SUBJECTS[role],unit['text'],re.I)]
            if matched and _AMOUNT.search(unit['text']):
                relation=(_cash_flow_repeat(scope,units,unit,original_total)
                          if matched==['operating_cash_flow'] and metric_id=='B05' else None)
                if relation is None:reported.append({'component_roles':matched,'source_unit':unit})
                else:duplicates.append(relation)
        grid=build_table_grid(html_bytes=raw,parent_raw_asset_ids=[doc['raw_asset_id']],
                             storage_uri='derived/statement-amendment-tables.json')
        for table in grid['tables']:
            for row in table['rows']:
                cells=[c for c in row['cells'] if c['is_origin']]
                matched=[role for role in roles if any(re.fullmatch(
                    _ROW_LABELS[role]+r'(?:\s*,?\s+(?:attributable to|net of)\s+.+)?'
                    +r'(?:\s*\([0-9]+\)|\s*\*)?',
                    ' '.join(c['text'].split()),re.I) for c in cells)]
                numeric=[c for c in cells if re.fullmatch(
                    r'(?:USD\s*|[$€£]\s*)?[-(]?\s*\d[\d,.]*\s*\)?',c['text'].strip(),re.I)
                    or c['text'].strip() in {'-','–','—'}]
                if matched and numeric:
                    reported.append({'component_roles':matched,'table_id':table['table_id'],
                        'row':row,'source_reference':doc['source_reference']})
    need(not reported,'STATEMENT_COMPONENT_DISCLOSURE_RELATION_UNRESOLVED',details=reported)
    body={'record_type':'ORIGINAL_STATEMENT_METRIC_INPUT_PROPERTY','schema_version':1,
        'metric_id':metric_id,'input_class':_INPUT_CLASSES[metric_id],
        'original_scope_id':scope['scope_id'],'covered_component_roles':roles,
        'metric_definition_sha256':sha256_file(path=ROOT/CATALOG_PATH),
        'amendment_raw_sha256':sha256_bytes(content=raw),
        'original_source_reference':scope['original']['document']['source_reference'],
        'amendment_source_reference':doc['source_reference'],'source_property':checked,
        'additional_component_disclosures':reported,
        'original_scope_reclassified':False,'annual_continuity_proven':False,
        'debt_completeness_proven':False,'metric_result_created':False,
        'source_acquisition_credit':False,'production_authorized':False}
    if duplicates:body['duplicate_component_disclosures']=duplicates
    return {**body,'property_id':content_hash(value=body)}
