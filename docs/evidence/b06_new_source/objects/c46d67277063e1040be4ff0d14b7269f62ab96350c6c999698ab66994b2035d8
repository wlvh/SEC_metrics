"""Bounded debt/lease relationship verification from complete current originals.

Formula candidates have no coverage credit. We verify table membership, balance
sheet classification, current/noncurrent splits and measurement adjustments,
then explain an independently collected disclosure inventory. Unknown patterns
remain gaps. Numerical roles are reread by the native XBRL parser.
"""
from decimal import Decimal
from html.parser import HTMLParser
from datetime import date
import re, xml.etree.ElementTree as ET
from .canonical import content_hash, sha256_bytes, sha256_file, decimal_text, strict_json_file
from .deterministic_router import parse_accession_xbrl_source, _numeric_xbrl_value, _visible_text
from .table_grid import _AllTablesParser, _expanded_table, _semantic_text
from .r5_b06_structured import need
from .r5_b06_scope import precision_choice, validate_partition
from .constraints import evaluate_expression

RESOLVER='debt_equity_new_source_v1'
SPEC_PATH='catalog/r5/B06_new_source.md'
REQUIRED=['current_borrowings','noncurrent_borrowings','finance_leases']
MODES={'INCLUSIVE_RECONCILED_COSTS','BORROWING_PLUS_SEPARATE_FINANCE_LEASE'}


def text(raw):
    return _visible_text(raw_bytes=raw.encode() if isinstance(raw,str) else raw)


def tables(raw):
    parser=_AllTablesParser();parser.feed(raw)
    need(not parser._stack,'DISCLOSURE_TABLE_TRUNCATED')
    parser.close();out=[]
    for b in parser.tables:
        t,_=_expanded_table(builder=b,remaining_total_cells=210000,remaining_expanded_text_chars=20000000)
        out.append(t)
    return out


def origins(row):
    return [c for c in row['cells'] if c['is_origin'] and c['text']]


def label(row):
    cs=origins(row)
    if not cs:return ''
    return cs[0]['text'] if not re.fullmatch(r'[$()\d.,—–\s-]+',cs[0]['text']) else ''


def amount(row, column, width):
    cs=[c for c in origins(row) if column<=c['column_index']<column+width]
    s=''.join(c['text'] for c in cs).replace('$','').replace(',','').strip()
    need(bool(re.fullmatch(r'\(?-?\d+(?:\.\d+)?\)?|[—–-]',s)), 'DISCLOSURE_AMOUNT_UNREADABLE')
    if s in {'—','–','-'}:return Decimal(0)
    return Decimal(s.replace('(','-').replace(')',''))*1000000


def _note(parsed, name, target):
    found=[]
    for f in parsed.facts:
        c=parsed.contexts[f['context_ref']]
        if f['qualified_name'].casefold()==name.casefold() and c['period_end']==target['period_end'] and not c['dimensions'] and not c['typed_dimension_count']:
            need(str(int(c['entity_identifier']))==target['entity'],'DISCLOSURE_NOTE_ENTITY_CHANGED')
            found.append(f)
    need(len(found)==1,'DISCLOSURE_NOTE_MISSING_OR_AMBIGUOUS:'+name)
    return found[0]


def _period_column(table, end, carrying):
    dt=date.fromisoformat(end);date_text=dt.strftime('%B')+' '+str(dt.day)+', '+str(dt.year)
    candidates=[c for row in table['rows'] for c in origins(row) if (c['text'].casefold()==date_text.casefold() if not carrying else c['text'].casefold()=='carrying value as of '+date_text.casefold())]
    need(len(candidates)==1,'DISCLOSURE_PERIOD_COLUMN_AMBIGUOUS')
    c=candidates[0];return c['column_index'],c['colspan'],c['row_index']


class _InlineNotes(HTMLParser):
    """Read nonnumeric facts and their explicit continuations, excluding ix:exclude.

    Page headers are excluded by the filing itself. Continuation IDs are followed
    exactly; missing, cyclic or ambiguous chains fail instead of dropping text.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True);self.active=[];self.fragments={};self.facts=[];self.excluded=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='ix:exclude':self.excluded+=1
        if tag in {'ix:nonnumeric','ix:continuation'}:
            f={'tag':tag,'attrs':a,'parts':[]};self.active.append(f)
            if tag=='ix:nonnumeric':self.facts.append(f)
            if a.get('id'):
                need(a['id'] not in self.fragments,'INLINE_FRAGMENT_DUPLICATE');self.fragments[a['id']]=f
    def handle_data(self,data):
        if not self.excluded:
            for f in self.active:f['parts'].append(data)
    def handle_endtag(self,tag):
        if tag=='ix:exclude':self.excluded-=1
        if tag in {'ix:nonnumeric','ix:continuation'}:
            need(self.active and self.active[-1]['tag']==tag,'INLINE_NOTE_MARKUP_INVALID');self.active.pop()
    def value(self,f):
        parts=[];seen=set()
        while True:
            parts.extend(f['parts']);link=f['attrs'].get('continuedat')
            if not link:return ' '.join(parts)
            need(link not in seen and link in self.fragments,'INLINE_CONTINUATION_MISSING_OR_CYCLIC');seen.add(link);f=self.fragments[link]


def discover_scope(*, raw, primary, target):
    """No model or calculation allowlist is an input to this inventory."""
    need(primary.strip().lower().endswith(b'</html>'),'DISCLOSURE_PRIMARY_TRUNCATED')
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    debt=_note(parsed,'us-gaap:DebtDisclosureTextBlock',target)
    schedule=_note(parsed,'us-gaap:ScheduleOfDebtInstrumentsTextBlock',target)
    leases=_note(parsed,'us-gaap:LesseeLeasesPolicyTextBlock',target)
    notes=[]
    for f in parsed.facts:
        c=parsed.contexts[f['context_ref']]
        if c['period_end']==target['period_end'] and not c['dimensions'] and 'textblock' in f['qualified_name'].casefold() and re.search(r'debt|borrow|loan|lease|credit',f['qualified_name'],re.I):
            notes.append({'concept':f['qualified_name'],'ordinal':f['ordinal'],'text':text(f['text']),'tables':tables(f['text'])})
    debt_tables=tables(schedule['text']);need(len(debt_tables)==1,'DEBT_COMPOSITION_TABLE_AMBIGUOUS')
    inline=_InlineNotes();inline.feed(primary.decode('utf-8'));inline.close()
    need(not inline.active and not inline.excluded,'INLINE_NOTE_TRUNCATED')
    all_tables=tables(primary.decode('utf-8'))
    balance=[]
    for t in all_tables:
        labels=[label(r).casefold() for r in t['rows']]
        joined=' '.join(labels)
        if ('total current assets' in joined and 'total current liabilities' in joined and ('stockholders' in joined or 'shareholders' in joined) and 'cash and cash equivalents' in joined):balance.append(t)
    need(len(balance)==1,'COMPLETE_BALANCE_SHEET_MISSING_OR_AMBIGUOUS')
    # All selected source text is retained; parser limits raise rather than cut.
    return {'parsed':parsed,'debt':debt,'schedule':schedule,'leases':leases,'notes':notes,'balance':balance[0],
            'debt_table':debt_tables[0],'inline':inline,'primary_tables':all_tables,'primary_text':text(primary),
            'scope_id':content_hash(value={'source':sha256_bytes(content=raw),'primary':sha256_bytes(content=primary),'target':target,'notes':[(n['concept'],n['ordinal']) for n in notes],'balance':balance[0]['table_id']})}


def propose(*, raw, primary, target):
    scope=discover_scope(raw=raw,primary=primary,target=target)
    # Proposes a formula, without claims of semantic acceptance or completeness.
    inclusive=any(re.fullmatch(r'finance leases',label(r),re.I) for r in scope['debt_table']['rows'])
    return {'method':'DETERMINISTIC_DISCLOSURE_V1','model_id':'INCLUSIVE_RECONCILED_COSTS' if inclusive else 'BORROWING_PLUS_SEPARATE_FINANCE_LEASE',
            'source_sha256':sha256_bytes(content=raw),'primary_sha256':sha256_bytes(content=primary),'scope_id':scope['scope_id']}


def _facts(raw,source,target,filed):
    parsed=parse_accession_xbrl_source(raw_bytes=raw);tree=ET.fromstring(raw)
    nodes=[n for n in tree.iter() if 'contextRef' in n.attrib];units={}
    for n in tree.iter():
        if n.tag.split('}')[-1]=='unit':
            ms=[(e.text or '').strip() for e in n.iter() if e.tag.split('}')[-1]=='measure']
            if ms==['iso4217:USD']:units[n.attrib['id']]='USD'
    def get(concept):
        candidates=[]
        for f in parsed.facts:
            c=parsed.contexts[f['context_ref']]
            if f['qualified_name'].casefold()!=concept.casefold() or c['period_start']!=c['period_end'] or c['period_end']!=target['period_end'] or c['dimensions'] or c['typed_dimension_count']:continue
            need(str(int(c['entity_identifier']))==target['entity'] and f['unit_ref'] in units,'DEBT_FACT_SCOPE_OR_UNIT_CHANGED')
            node=nodes[f['ordinal']-1]
            need(node.attrib['contextRef']==f['context_ref'] and node.tag.split('}')[-1].casefold()==concept.split(':')[-1].casefold(),'DEBT_PRECISION_LOCATOR_CHANGED')
            v=_numeric_xbrl_value(text=f['text'],scale=f['scale'],sign=f['sign'])
            need(Decimal(v)>=0 or concept=='us-gaap:StockholdersEquity','NEGATIVE_DEBT_COMPONENT')
            candidates.append({'value':v,'decimals':node.attrib.get('decimals'),'ordinal':f['ordinal'],'context_ref':f['context_ref']})
        s=precision_choice(candidates)
        binding={'raw_asset_id':source['raw_asset_id'],'source_reference_id':source['source_reference_id'],'source_role':source['source_role'],'document_name':source['document_name'],'accession':source['accession'],'entity':target['entity'],'xbrl_context_ref':s['context_ref'],'xbrl_fact_ordinal':s['ordinal'],'reported_decimals':s['decimals']}
        record={'accession':source['accession'],'concept':concept,'duration_days':0,'entity':target['entity'],'fact_id':'fact:'+content_hash(value={'binding':binding,'value':s['value'],'parsed_source_id':parsed.parsed_source_id}),'filed':filed,'fiscal_period':'FY','form':'10-K','period_start':target['period_end'],'period_end':target['period_end'],'source_binding':binding,'unit':'USD','value':s['value']}
        return record,{'concept':concept,'chosen_ordinal':s['ordinal'],'all_reports':candidates}
    return get


def verify(*, raw, primary, source, spec, target, filed, data_root, proposal):
    need(source['raw_asset_id']=='sha256:'+sha256_bytes(content=raw) and source['accession']==target['accession'],'RELATIONSHIP_SOURCE_IDENTITY_CHANGED')
    need(proposal.get('method')=='DETERMINISTIC_DISCLOSURE_V1','PROPOSAL_METHOD_UNSUPPORTED')
    need(set(proposal)=={'method','model_id','source_sha256','primary_sha256','scope_id'},'PROPOSAL_CANNOT_ASSERT_APPROVAL_OR_AMOUNTS')
    need(target['scope']=={'entity_scope':'consolidated'} and target['period_start']==target['period_end'],'FIXED_DEBT_SCOPE_REQUIRED')
    need(proposal['model_id'] in MODES,'UNSUPPORTED_RELATIONSHIP_MODEL')
    scope=discover_scope(raw=raw,primary=primary,target=target)
    need(proposal['source_sha256']==sha256_bytes(content=raw) and proposal['primary_sha256']==sha256_bytes(content=primary) and proposal['scope_id']==scope['scope_id'],'PROPOSAL_SOURCE_BINDING_CHANGED')
    rule=spec['compiled']['quality_rule']
    need(sha256_file(path=data_root/rule['debt_set_registry'])==rule['debt_set_registry_sha256'],'DEBT_SET_REGISTRY_CHANGED')
    registry=strict_json_file(path=data_root/rule['debt_set_registry'])
    model=registry['debt_set_models'][proposal['model_id']]
    validate_partition(model,REQUIRED)
    get=_facts(raw,source,target,filed);roles={};precision=[];checks=[]
    for r,concept in model['inputs'].items():roles[r],p=get(concept);precision.append(p)
    values={r:Decimal(f['value']) for r,f in roles.items()}
    for check in model['checks']:
        more=[]
        for r,concept in check['inputs'].items():
            f,p=get(concept);values[r]=Decimal(f['value']);more.append(f);precision.append(p)
        lhs=evaluate_expression(expression=check['left'],values=values);rhs=evaluate_expression(expression=check['right'],values=values)
        need(lhs==rhs,'DEBT_COMPONENT_RECONCILIATION_FAILED')
        checks.append({'rule':check,'source_facts':more,'left_value':decimal_text(value=lhs),'right_value':decimal_text(value=rhs)})
    equity,p=get('us-gaap:StockholdersEquity');precision.append(p)
    lease,p=get('us-gaap:FinanceLeaseLiability');precision.append(p)
    lc,_=get('us-gaap:FinanceLeaseLiabilityCurrent');ln,_=get('us-gaap:FinanceLeaseLiabilityNoncurrent')
    need(Decimal(lc['value'])+Decimal(ln['value'])==Decimal(lease['value']),'LEASE_CURRENT_NONCURRENT_RECONCILIATION_FAILED')
    maturity=_note(scope['parsed'],'us-gaap:FinanceLeaseLiabilityMaturityTableTextBlock',target)
    mts=tables(maturity['text']);need(len(mts)==1,'LEASE_MATURITY_TABLE_MISSING')
    mt=mts[0];hc=[c for r in mt['rows'] for c in origins(r) if c['text'].casefold()=='finance leases']
    need(len(hc)==1 and 'in millions' in text(maturity['text']).casefold(),'LEASE_COLUMN_OR_UNIT_UNPROVEN')
    h=hc[0];mr=[]
    for r in mt['rows'][h['row_index']+1:]:
        if not any(h['column_index']<=c['column_index']<h['column_index']+h['colspan'] for c in origins(r)):continue
        mr.append((label(r).casefold(),amount(r,h['column_index'],h['colspan'])))
    payments=[v for l,v in mr if l in {'total lease payments','total minimum lease payments'}]
    interest=[abs(v) for l,v in mr if l in {'less imputed interest','less: imputed interest'}]
    total=[v for l,v in mr if l in {'total','total lease obligations'}]
    need(len(payments)==len(interest)==len(total)==1 and payments[0]-interest[0]==total[0]==Decimal(lease['value']),'LEASE_PRESENT_VALUE_RECONCILIATION_FAILED')
    payment_fact,_=get('us-gaap:FinanceLeaseLiabilityPaymentsDue');interest_fact,_=get('us-gaap:FinanceLeaseLiabilityUndiscountedExcessAmount')
    need(Decimal(payment_fact['value'])==payments[0] and Decimal(interest_fact['value'])==interest[0],'LEASE_PAYMENT_MEASUREMENT_CONFLICT')
    need(len({f['source_binding']['xbrl_context_ref'] for f in [*roles.values(),equity,lease,lc,ln]})==1,'DEBT_COMPONENT_CONTEXT_MIXED')
    inclusive=proposal['model_id']=='INCLUSIVE_RECONCILED_COSTS'
    policy_text=text(scope['leases']['text']); debt_text=text(scope['debt']['text'])
    # Negation/qualification is checked in both directions, including totals
    # as grammatical subject. Unrecognized limiting language leaves a gap.
    relation_text=policy_text+' '+debt_text
    for sentence in re.split(r'(?<=[.!?])\s+',relation_text):
        sentence=re.sub(r'\(not including amounts associated with interest on finance leases\)','',sentence,flags=re.I)
        if re.search(r'finance leas',sentence,re.I) and re.search(r'borrow|debt|maturities',sentence,re.I) and re.search(r'\b(?:not|never|exclude\w*|except|only|neither|outside|omit\w*)\b',sentence,re.I):
            need(False,'FINANCE_LEASE_RELATIONSHIP_CONFLICT')
    if inclusive:
        pattern=r'Finance leases are included in Property and equipment, Current maturities of long-term debt, and Long-term debt less current maturities in the Consolidated Balance Sheet\.'
        need(re.search(pattern,policy_text,re.I) is not None,'FINANCE_LEASE_INCLUSION_NOT_PROVEN')
        need(not re.search(r'finance leases?[^.]{0,160}\b(?:not|exclud\w*|except|only)\b[^.]*\b(?:debt|maturities|included)\b',policy_text+' '+debt_text,re.I),'FINANCE_LEASE_RELATIONSHIP_CONFLICT')
    else:
        for sentence in re.split(r'(?<=[.!?])\s+',relation_text):
            if re.search(r'finance leas',sentence,re.I) and re.search(r'borrow|debt',sentence,re.I) and re.search(r'\b(?:include\w*|contain\w*|compris\w*|part of)\b',sentence,re.I):
                need(False,'SEPARATE_LEASE_RELATIONSHIP_CONFLICT')
        pattern=r'Assets \(also referred to as ROU assets\) and liabilities recognized from finance leases are included in property and equipment, accrued expenses and other liabilities and other noncurrent liabilities, respectively, on the Company[’\']s consolidated balance sheets\.'
        need(re.search(pattern,policy_text,re.I) is not None,'SEPARATE_LEASE_CLASSIFICATION_NOT_PROVEN')
        need(re.search(r'The components of the Company[’\']s borrowings were as follows',text(scope['schedule']['text']),re.I) is not None,'BORROWING_TABLE_SCOPE_NOT_PROVEN')
        need(not re.search(r'finance leases?[^.]{0,100}\b(?:included in|part of)\b[^.]*\b(?:borrowings|debt)\b',policy_text+' '+debt_text,re.I),'SEPARATE_LEASE_RELATIONSHIP_CONFLICT')
    # Membership and arithmetic apply to the table actually named by the policy.
    t=scope['debt_table'];col,width,header=_period_column(t,target['period_end'],not inclusive)
    need('in millions' in text(scope['schedule']['text']).casefold(),'DISCLOSURE_UNITS_NOT_PROVEN')
    inventory=[];components=[];totals=[];deductions=[]
    for row in t['rows'][header+1:]:
        cs=[c for c in origins(row) if col<=c['column_index']<col+width]
        if not cs:continue
        v=amount(row,col,width);lab=label(row);low=lab.casefold()
        item={'origin':'debt_composition','row':row['row_index'],'label':lab,'value':str(v)}
        if not lab or low.startswith('total'):
            totals.append((row['row_index'],v,lab));item['disposition']='RECONCILED_TOTAL'
        elif low.startswith('less'):
            deductions.append((low,abs(v)));item['disposition']='RECONCILED_ADJUSTMENT'
        elif re.fullmatch(r'finance leases',lab,re.I):
            need(inclusive and v==Decimal(lease['value']),'FINANCE_LEASE_MEMBERSHIP_CONFLICT');components.append((lab,v));item['disposition']='INCLUDED_IN_SELECTED_SET'
        elif re.search(r'\b(?:notes|debentures|loan|credit agreement)\b',lab,re.I):
            need(not re.search(r'\b(?:exclud\w*|not|except)\b',lab,re.I),'DEBT_MEMBERSHIP_NEGATED')
            components.append((lab,v));item['disposition']='INCLUDED_IN_SELECTED_SET'
        else:item['disposition']='UNRESOLVED'
        inventory.append(item)
    need(components and len(totals)==2 and totals[0][0]<totals[1][0],'DEBT_COMPOSITION_STRUCTURE_UNSUPPORTED')
    need(sum(v for _,v in components)==totals[0][1],'DEBT_MEMBERSHIP_SUM_CONFLICT')
    need(all(i['row']<totals[0][0] for i in inventory if i['disposition']=='INCLUDED_IN_SELECTED_SET'),'DEBT_MEMBERSHIP_OUTSIDE_TOTAL')
    if inclusive:
        need(any(lab.casefold()=='finance leases' for lab,v in components),'FINANCE_LEASE_NOT_IN_COMPOSITION')
        need(totals[0][1]==values['gross'],'DEBT_GROSS_TABLE_BINDING_CONFLICT')
        need(dict(deductions)=={'less current maturities':values['current'],'less debt discount and issuance costs':values['cost']},'DEBT_ADJUSTMENT_TARGET_NOT_PROVEN')
    else:
        need(not any('lease' in lab.casefold() for lab,v in components),'SEPARATE_LEASE_ALREADY_INCLUDED')
        need(totals[0][1]==values['borrowing'] and dict(deductions)=={'less current portion of debt':values['current']},'BORROWING_TOTAL_TABLE_BINDING_CONFLICT')
    need(totals[0][1]-sum(v for _,v in deductions)==totals[1][1]==values['noncurrent'],'DEBT_CURRENT_OR_COST_RECONCILIATION_FAILED')
    # Independent financial statement scan includes every row, not model roles.
    bs=scope['balance'];in_liabilities=False
    bcol,bwidth,_=_period_column(bs,target['period_end'],False)
    current_labels={'current maturities of long-term debt','current portion of debt','debt, current'}
    noncurrent_labels={'long-term debt less current maturities','noncurrent debt','debt, noncurrent'}
    known_finance_labels=current_labels|noncurrent_labels
    seen_roles=set()
    ordinary_labels={'accounts payable','accrued liabilities','accounts payable, accrued expenses and other liabilities','current operating lease liabilities','operating lease liabilities, current','noncurrent operating lease liabilities','air traffic liability','air traffic liability - noncurrent','deferred income taxes','other noncurrent liabilities','unearned revenue','total current liabilities','total liabilities'}
    for row in bs['rows']:
        lab=label(row);low=lab.casefold().rstrip(':')
        if low in {'stockholders’ equity',"stockholders' equity",'shareholders’ equity',"shareholders' equity"}:break
        if 'liabilities' in low:in_liabilities=True
        if not in_liabilities or not lab:continue
        cs=[c for c in origins(row) if bcol<=c['column_index']<bcol+bwidth]
        if not cs:continue
        v=amount(row,bcol,bwidth)
        if low in known_finance_labels:
            role='current' if low in current_labels else 'noncurrent'
            need(role not in seen_roles,'BALANCE_SHEET_DEBT_LINE_DUPLICATED');seen_roles.add(role)
            need(v==values[role],'BALANCE_SHEET_DEBT_AMOUNT_CONFLICT')
            disposition='INCLUDED_IN_SELECTED_SET'
        elif low in ordinary_labels:disposition='EXCLUDED_ORDINARY_OR_OPERATING_OR_AGGREGATE'
        else:disposition='UNRESOLVED'
        inventory.append({'origin':'balance_sheet','row':row['row_index'],'label':lab,'value':str(v),'disposition':disposition})
    need('noncurrent' in seen_roles and ('current' in seen_roles or values['current']==0),'BALANCE_SHEET_DEBT_CLASSIFICATION_MISSING')
    # Unfiltered standard/custom instant facts: keep potential financing claims
    # that the formula registry never saw. Exclusions have explicit nature.
    unit_measures={n.attrib['id']:[(m.text or '').strip() for m in n.iter() if m.tag.split('}')[-1]=='measure'] for n in ET.fromstring(raw).iter() if n.tag.split('}')[-1]=='unit'}
    recognized={p['concept'].casefold() for p in precision}|{'us-gaap:longtermdebt','us-gaap:debtinstrumentcarryingamount'}
    for f in scope['parsed'].facts:
        c=scope['parsed'].contexts[f['context_ref']];name=f['qualified_name'].casefold();short=name.split(':')[-1]
        if c['period_start']!=c['period_end'] or c['period_end']!=target['period_end'] or c['dimensions'] or not f['unit_ref'] or not re.search('debt|borrow|loan|lease|credit|facility|financing|funding|obligation|promissory',name):continue
        if _numeric_xbrl_value(text=f['text'],scale=f['scale'],sign=f['sign'])=='0':disposition='EXPLICIT_ZERO_IN_CURRENT_ORIGINAL'
        elif unit_measures.get(f['unit_ref']) in [['xbrli:pure'],['pure']] or (len(unit_measures.get(f['unit_ref'],[]))==1 and unit_measures[f['unit_ref']][0].split(':')[-1].casefold()=='performanceobligation'):disposition='EXCLUDED_NONMONETARY_COUNT_OR_RATE'
        elif name=='us-gaap:lettersofcreditoutstandingamount':
            need('letters of credit are an off-balance sheet item' in debt_text.casefold(),'LETTER_OF_CREDIT_RECOGNITION_UNRESOLVED');disposition='EXCLUDED_DOCUMENTED_OFF_BALANCE_SHEET_STANDBY'
        elif name in recognized or short in {'financeleaseliabilitycurrent','financeleaseliabilitynoncurrent'}:disposition='INCLUDED_OR_RECONCILED'
        elif name.startswith('us-gaap:') and re.search('asset|tax|receivables|availableforsale|operatinglease|lessor|rightofuse|weightedaverage|maturit|paymentsdue|undiscounted|collateral|revenueremainingperformanceobligation',short):disposition='EXCLUDED_STANDARD_DIFFERENT_MEASUREMENT_OR_NATURE'
        elif not name.startswith('us-gaap:') and (short.startswith(('deferredtaxassets','deferredtaxliabilities')) or short in {'revenueremainingperformanceobligationcurrent','revenueremainingperformanceobligationnoncurrent','leaserightofuseasset','lessoroperatingleasepaymentstobereceivednextfiveyears','lesseeoperatingleasecommitmentincludingleasenotyetcommencedamount'}):disposition='EXCLUDED_EXPLICIT_CUSTOM_TAX_ASSET_OR_OPERATING_NATURE'
        elif short=='convertibledebtcurrent':
            need(Decimal(f['text'])==values['current'],'BALANCE_SHEET_CURRENT_DEBT_CONFLICT');disposition='RECONCILED_CURRENT_BALANCE_SHEET_LINE'
        elif short=='leaseliability':
            op,_=get('us-gaap:OperatingLeaseLiability')
            need(Decimal(f['text'])==Decimal(op['value'])+Decimal(lease['value']),'COMBINED_LEASE_TOTAL_CONFLICT');disposition='RECONCILED_FINANCE_AND_OPERATING_TOTAL'
        else:disposition='UNRESOLVED'
        inventory.append({'origin':'all_instant_xbrl','concept':name,'ordinal':f['ordinal'],'value':f['text'],'disposition':disposition})
    # Any additional financing row within debt/lease notes must be explained.
    # A custom concept or row cannot disappear through Company Facts filtering.
    known_labels={label(r).casefold() for r in t['rows']}|known_finance_labels
    for n in scope['notes']:
        for table in n['tables']:
            for row in table['rows']:
                lab=label(row);low=lab.casefold()
                if not re.search(r'borrow|loan|financing|commercial paper|facility|credit agreement|funding|promissory',low):continue
                if not any(re.fullmatch(r'[$()0-9, .—–-]+',c['text']) and re.search(r'\d|[—–]',c['text']) for c in origins(row)[1:]):continue
                disposition='INCLUDED_IN_SELECTED_SET' if low in known_labels else 'EXCLUDED_LEASE_CASH_FLOW' if low in {'financing cash flows for finance leases','financing cash outflows for finance leases'} and re.search('lease.*textblock$',n['concept'],re.I) else 'UNRESOLVED'
                inventory.append({'origin':'related_disclosure','concept':n['concept'],'row':row['row_index'],'label':lab,'disposition':disposition})
    unresolved=[i for i in inventory if i['disposition']=='UNRESOLVED']
    need(not unresolved,'UNRESOLVED_FINANCING_ITEM:'+str(unresolved[:3]))
    # Complete note blocks must be present in the actual primary document;
    # XML facts cannot stand in for missing HTML pages or unreadable footnotes.
    compact=lambda s:re.sub(r'\s','',s).casefold()
    for f in [scope['debt'],scope['leases'],maturity]:
        matches=[z for z in scope['inline'].facts if z['attrs'].get('name','').casefold()==f['qualified_name'].casefold()]
        need(len(matches)==1 and compact(text(f['text']))==compact(scope['inline'].value(matches[0])),'PRIMARY_NOTE_SOURCE_CONFLICT_OR_MISSING')
    debt=evaluate_expression(expression=model['expression'],values=values)
    relations=[{'premise':'lease_balance_sheet_classification','status':'VERIFIED','evidence':re.search(pattern,policy_text,re.I).group()},
               {'premise':'debt_composition_membership','status':'VERIFIED','members':[(l,str(v)) for l,v in components]},
               {'premise':'current_and_adjustments_target','status':'VERIFIED','deductions':[(l,str(v)) for l,v in deductions]},
               {'premise':'finance_lease_current_noncurrent','status':'VERIFIED','current':lc['value'],'noncurrent':ln['value'],'total':lease['value']}]
    return {'model_id':proposal['model_id'],'model':model,'scope_class':'consolidated_nonbank','complete':True,'unresolved':[],
            'source_credit':'NOT_EVALUATED_AT_SEMANTIC_LAYER','coverage':REQUIRED,'scope_id':scope['scope_id'],'relations':relations,'disclosure_inventory':inventory,'proposal':proposal,
            'calculation_facts':list(roles.values())+[equity],'equity_fact':equity,'components':roles,'carrying_amount':decimal_text(value=debt),
            'precision':precision,'reconciliations':checks,'debt_scope_definition':registry['debt_scope_definition']}
