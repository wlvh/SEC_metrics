"""Current carrying-debt table with finance leases explicitly inside its total.

Native balances, every instrument row and the source's current subject column
are reconstructed together. A reported total never grants completeness alone.
"""
from decimal import Decimal
import re

from . import b06_disclosure as disclosure
from .canonical import content_hash,decimal_text,sha256_bytes,strict_json_file
from .constraints import parse_numeric_claim
from .deterministic_router import parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex,_fact_cells
from .fiscal_year_labels import _DefinitionBlocks
from .governance_signals import _source_value,_qname
from .normal_annual_input import annual_period
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT
from .r5_b06_scope import precision_choice
from .text_results_v2 import _ReportedFactMetadata,_verified_context

POLICY_PATH='config/b06_inclusive_table_v1.json'
POLICY=strict_json_file(path=ROOT/POLICY_PATH)


class InclusiveDebtError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise InclusiveDebtError('INCLUSIVE_DEBT_'+reason)


class _InclusiveInlineNotes(disclosure._InlineNotes):
    """Bind numeric facts to their original note and explicit continuations."""
    def __init__(self):
        super().__init__();self.ordinal=0
    def handle_starttag(self,tag,attrs):
        native='contextref' in dict(attrs)
        if native:self.ordinal+=1
        super().handle_starttag(tag,attrs)
        if native and not self.excluded:
            for fragment in self.active:fragment.setdefault('ordinals',[]).append(self.ordinal)
    def ordinals(self,fragment):
        result=[];seen=set()
        while True:
            result.extend(fragment.get('ordinals',[]));link=fragment['attrs'].get('continuedat')
            if not link:return sorted(set(result))
            _need(link not in seen and link in self.fragments,'NUMERIC_NOTE_CONTINUATION_INVALID')
            seen.add(link);fragment=self.fragments[link]


class _InventoryMetadata(_ReportedFactMetadata):
    """Keep the explicit typed RPO date bucket without changing old parsers."""
    def __init__(self):
        super().__init__();self.typed={};self.typed_active=None
    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs);ns=self.stack[-1][1];uri,local=_qname(tag,ns)
        if uri=='http://xbrl.org/2006/xbrldi' and local=='typedmember':
            _need(self.typed_active is None,'NESTED_TYPED_MEMBER')
            self.typed_active={'context_ref':self.context_active['context_ref'],'axis':list(_qname(dict(attrs).get('dimension',''),ns)),
                               'domains':[],'parts':[]}
        elif self.typed_active is not None:
            self.typed_active['domains'].append(list(_qname(tag,ns)))
    def handle_data(self,data):
        super().handle_data(data)
        if self.typed_active is not None:self.typed_active['parts'].append(data)
    def handle_endtag(self,tag):
        ns=self.stack[-1][1] if self.stack else {};uri,local=_qname(tag,ns)
        if uri=='http://xbrl.org/2006/xbrldi' and local=='typedmember':
            item=self.typed_active;item['value']=''.join(item.pop('parts')).strip()
            self.typed.setdefault(item.pop('context_ref'),[]).append(item);self.typed_active=None
        super().handle_endtag(tag)


def _inventory_context(c,meta,name,standard):
    if not c['typed_dimension_count']:
        return _verified_context(native=c,metadata=meta),[]
    from datetime import date
    _need(standard and name=='revenueremainingperformanceobligation' and not c['dimensions']
          and c['typed_dimension_count']==1,'UNSUPPORTED_TYPED_FINANCING_CONTEXT')
    proof=meta.context_proofs[c['context_ref']];typed=meta.typed.get(c['context_ref'],[])
    _need(proof['identifiers']==[{'value':c['entity_identifier'],'scheme':'http://www.sec.gov/CIK'}]
          and proof['period_fields']==[{'kind':'instant','value':c['period_end']}]
          and not proof['dimensions'] and len(typed)==proof['typed_dimension_count']==1,'TYPED_RPO_CONTEXT_CHANGED')
    t=typed[0];axis='RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis'
    _need(re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',t['axis'][0])
          and t['axis'][1].casefold()==axis.casefold() and len(t['domains'])==1
          and t['domains'][0][0]==t['axis'][0] and t['domains'][0][1].casefold()==(axis+'.domain').casefold()
          and date.fromisoformat(t['value'])>date.fromisoformat(c['period_end']),'TYPED_RPO_FUTURE_DATE_UNPROVEN')
    return proof,typed


def _native(source,prepared,kind):
    raw=source['raw_bytes'];ref=source['source_reference'];period=prepared['table_input']['target_period']
    _need(ref['raw_asset_id']=='sha256:'+sha256_bytes(content=raw) and ref['accession']==prepared['filing']['accessionNumber']
          and ref['company_id']==prepared['company_id'],'SOURCE_BINDING_CHANGED')
    _need(annual_period(raw=raw,cik=prepared['entity'],filing=prepared['filing'])==period,'SOURCE_IDENTITY_CHANGED')
    parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_ReportedFactMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close()
    _need(meta.ordinal==len(parsed.facts),'NATIVE_STREAM_CHANGED')
    notes={};reports={role:[] for role in POLICY['monetary_concepts']};members=[]
    for f in parsed.facts:
        c=parsed.contexts[f['context_ref']];m=meta.facts[f['ordinal']];uri,local=m['concept']
        if c['period_end']!=period['period_end']:continue
        note=[n for n in POLICY['note_concepts']+POLICY['extension_note_concepts'] if n.casefold()==local.casefold()]
        roles=[r for r,n in POLICY['monetary_concepts'].items() if n.casefold()==local.casefold()]
        member=local.casefold() in {n.casefold() for n in POLICY['member_concepts']}
        if not note and not roles and not member:continue
        _need(re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri)
              or note and note[0] in POLICY['extension_note_concepts'] and uri and not f['qualified_name'].casefold().startswith('us-gaap:'),
              'CONCEPT_NAMESPACE_CONFLICT')
        _need(str(int(c['entity_identifier']))==prepared['entity'],'CURRENT_ENTITY_CONFLICT')
        context={**c,'dimensions':dict(c['dimensions'])};cp=_verified_context(native=context,metadata=meta)
        if note and not c['dimensions'] and not c['typed_dimension_count']:
            _need(c['period_start']==period['period_start'] and note[0] not in notes,'NOTE_PERIOD_OR_CARDINALITY_CONFLICT')
            notes[note[0]]=f
        if c['period_start']!=c['period_end']:continue
        if roles and (c['dimensions'] or c['typed_dimension_count']):continue
        if not roles and not member:continue
        _need(meta.units.get(f['unit_ref'])=={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False},'NATIVE_UNIT_CONFLICT')
        item={'ordinal':f['ordinal'],'context_ref':f['context_ref'],'context':context,'context_proof':cp,
              'concept_qname':[uri,local],'value':_source_value(f,m),'decimals':m['attrs'].get('decimals')}
        _need('equity' in roles or Decimal(item['value'])>=0,'NEGATIVE_DEBT_AMOUNT')
        for role in roles:reports[role].append(item.copy())
        if member:members.append(item)
    _need(set(notes)==set(POLICY['note_concepts']+POLICY['extension_note_concepts']) and all(reports.values()) and members,'REQUIRED_NOTE_OR_BALANCE_MISSING')
    compact=lambda value:re.sub(r'\s','',disclosure.text(value))
    full_notes=[compact(n['text']) for n in notes.values()]
    for f in parsed.facts:
        c=parsed.contexts[f['context_ref']];name=f['qualified_name'].casefold()
        if c['period_end']!=period['period_end'] or not name.endswith('textblock') or not re.search(r'debt|borrow|loan|lease|credit|financing|promissory|seniornotes|debentures',name):continue
        if kind!='xml' or f in notes.values():continue
        _need(str(int(c['entity_identifier']))==prepared['entity'] and any(compact(f['text']) in n for n in full_notes),
              'ADDITIONAL_FINANCING_NOTE_OUTSIDE_PROVEN_SCOPE:'+kind+':'+name)
    if kind=='primary':
        index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close()
        entries=[r for group in reports.values() for r in group]+members
        cells=_fact_cells(index,parsed,{r['ordinal'] for r in entries})
        for r in entries:
            if r['ordinal'] not in cells:
                r['outside_table_report']=True
                continue
            table,cell=cells[r['ordinal']];f=parsed.facts[r['ordinal']-1]
            amount=parse_numeric_claim(raw_value=cell['text'],reported_unit='USD')*Decimal(10)**int(f['scale'] or '0')
            _need(amount==Decimal(r['value']),'VISIBLE_AMOUNT_SIGN_OR_SCALE_CONFLICT')
            r['source_cell']={'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],
                'row_label':disclosure.label(table['rows'][cell['origin_row_index']]),'cell':cell}
            r['raw_start_byte']=index.fact_positions[r['ordinal']]
        for group in reports.values():
            chosen=precision_choice(group)
            _need(any('source_cell' in r and r['value']==chosen['value'] for r in group),'VISIBLE_NATIVE_CELL_REQUIRED')
    return parsed,notes,reports,members


def _current_column(table,end,prepared):
    col,width,row=disclosure._period_column(table,end,False)
    if prepared['subject_policy']['mode']=='SUCCESSOR_REGISTRANT_ONLY':
        labels=[c for r in table['rows'][:row] for c in disclosure.origins(r)
                if re.fullmatch(POLICY['current_subject_label_pattern'],c['text']) and c['column_index']==col and c['colspan']==width]
        _need(len(labels)==1,'CURRENT_SUCCESSOR_COLUMN_UNPROVEN')
    return col,width,row


def inspect_inclusive_composition(*,primary,xml,prepared):
    xp,xnotes,xreports,xmembers=_native(xml,prepared,'xml')
    ip,inotes,ireports,imembers=_native(primary,prepared,'primary')
    inline=_InclusiveInlineNotes();inline.feed(primary['raw_bytes'].decode('utf-8-sig'));inline.close()
    _need(not inline.active and not inline.excluded,'INLINE_NOTE_TRUNCATED')
    compact=lambda s:re.sub(r'\s','',s)
    note_proofs=[]
    for name,note in xnotes.items():
        i=inotes[name];found=[f for f in inline.facts if f['attrs'].get('name','').casefold()==i['qualified_name'].casefold()
                             and f['attrs'].get('contextref')==i['context_ref']]
        value=disclosure.text(note['text'])
        _need(len(found)==1 and compact(value)==compact(inline.value(found[0])),'FULL_ORIGINAL_NOTES_DIFFER:'+name)
        note_proofs.append({'concept':name,'xml_ordinal':note['ordinal'],'primary_ordinal':i['ordinal'],'text':value,
                            'primary_fact_ordinals':inline.ordinals(found[0]),'original_xml_html':note['text']})
    # Inline text blocks can end in explicit continuation fragments. Compare
    # their complete native chains, not the parser's first-fragment text.
    complete_notes=[compact(n['text']) for n in note_proofs]
    for f in inline.facts:
        name=f['attrs'].get('name','').casefold();context=ip.contexts.get(f['attrs'].get('contextref'))
        if context is None or context['period_end']!=prepared['filing']['reportDate'] or not name.endswith('textblock') or not re.search(r'debt|borrow|loan|lease|credit|financing|promissory|seniornotes|debentures',name):continue
        _need(str(int(context['entity_identifier']))==prepared['entity'] and any(compact(inline.value(f)) in n for n in complete_notes),
              'ADDITIONAL_FINANCING_NOTE_OUTSIDE_PROVEN_SCOPE:primary:'+name)
    schedule=xnotes['ScheduleOfDebtTableTextBlock'];debt=xnotes['DebtDisclosureTextBlock']
    _need(compact(disclosure.text(schedule['text'])) in compact(disclosure.text(debt['text'])),'SCHEDULE_OUTSIDE_DEBT_NOTE')
    ts=disclosure.tables(schedule['text']);_need(len(ts)==1,'DEBT_TABLE_NOT_UNIQUE');table=ts[0]
    col,width,header=_current_column(table,prepared['filing']['reportDate'],prepared)
    selected={};members=[]
    for row in table['rows'][header+1:]:
        label=disclosure.label(row);cells=[c for c in disclosure.origins(row) if col<=c['column_index']<col+width]
        if not cells:continue
        value=disclosure.amount(row,col,width);entry={'label':label,'value':decimal_text(value=value),'row':row}
        role=next((k for k,v in POLICY['row_labels'].items() if v==label),None)
        if role:
            _need(role not in selected,'DUPLICATE_DEBT_TOTAL_ROLE');selected[role]=entry
        else:
            _need(not selected and re.fullmatch(POLICY['member_label_pattern'],label),'UNRECONCILED_DEBT_ROW:'+label)
            members.append(entry)
    _need(set(selected)==set(POLICY['row_labels']) and members and len({r['label'] for r in members})==len(members),
          'DEBT_COMPOSITION_INCOMPLETE')
    reports={role:{'xml':xreports[role],'primary':ireports[role],'chosen':precision_choice(xreports[role]+ireports[role])} for role in xreports}
    for role,row in selected.items():_need(row['value']==reports[role]['chosen']['value'],'TABLE_NATIVE_AMOUNT_CONFLICT:'+role)
    values={k:Decimal(r['value']) for k,r in selected.items()}
    _need(sum(Decimal(r['value']) for r in members)+values['finance_lease']==values['total']
          and values['total']-values['current']==values['noncurrent'],'INCLUSIVE_CURRENT_TOTAL_RECONCILIATION_CONFLICT')
    expected={r['label']:r['value'] for r in members};groups={}
    for kind,items in [('xml',xmembers),('primary',imembers)]:
        found={}
        for item in items:
            key=content_hash(value={'concept':item['concept_qname'][1].casefold(),'dimensions':item['context']['dimensions']})
            found.setdefault(key,[]).append(item)
            if kind=='primary' and 'source_cell' in item:
                loc=item['source_cell'];_need(loc['row_label'] in expected and expected[loc['row_label']]==item['value'],'NATIVE_MEMBER_OUTSIDE_COMPOSITION')
                _need(loc['cell']['column_index']>=col and loc['cell']['column_index']<col+width,'NATIVE_MEMBER_WRONG_PERIOD_COLUMN')
        groups[kind]=found
    _need(set(groups['xml'])==set(groups['primary']),'NATIVE_MEMBER_DOCUMENT_SETS_DIFFER')
    for key in groups['xml']:
        precision_choice(groups['xml'][key]+groups['primary'][key])
        _need(any('source_cell' in r for r in groups['primary'][key]),'MEMBER_GROUP_TABLE_EVIDENCE_MISSING')
    _need({r['source_cell']['row_label'] for r in imembers if 'source_cell' in r}==set(expected)
          and len(groups['xml'])==len(expected),'NATIVE_MEMBER_ROW_SET_DIFFERS')
    raw=primary['raw_bytes'].decode('utf-8-sig');blocks=_DefinitionBlocks(raw);blocks.feed(raw);blocks.close();blocks._flush()
    declarations=[b for b in blocks.blocks if b['text']==POLICY['scale_declaration'] and not b['quoted_context'] and not b['linked']]
    _need(declarations,'TABULAR_DOLLAR_SCALE_UNPROVEN')
    return exact_json_value({'record_type':'INCLUSIVE_DEBT_COMPOSITION_COMPONENT','policy_hash':content_hash(value=POLICY),
        'source_references':[primary['source_reference'],xml['source_reference']],'notes':note_proofs,'table_id':table['table_id'],
        'grid_sha256':table['grid_sha256'],'members':members,'roles':selected,'reports':reports,'native_members':groups,
        'tabular_scale_declarations':declarations,'carrying_amount':selected['total']['value'],'finance_lease_already_included':True,
        'complete_b06_proven':False,'remaining_checks':['BALANCE_SHEET_SCOPE','OTHER_FINANCING_INVENTORY','DIFFERENT_MEASUREMENTS'],
        'source_acquisition_credit':False,'production_authorized':False})


def _balance_scope(primary,prepared,composition):
    reports=composition['reports'];tables={t['table_id']:t for t in disclosure.tables(primary['raw_bytes'].decode('utf-8-sig'))}
    common=None
    for role in ['current','noncurrent','equity']:
        found={r['source_cell']['table_id'] for r in reports[role]['primary'] if 'source_cell' in r}
        common=found if common is None else common&found
    _need(len(common)==1,'CURRENT_CONSOLIDATED_BALANCE_TABLE_AMBIGUOUS')
    table=tables[next(iter(common))];col,width,_=_current_column(table,prepared['filing']['reportDate'],prepared)
    selected={}
    for role in ['current','noncurrent','equity']:
        choices=[r for r in reports[role]['primary'] if r.get('source_cell',{}).get('table_id')==table['table_id']
                 and col<=r['source_cell']['cell']['column_index']<col+width]
        _need(choices,'CURRENT_BALANCE_COLUMN_AMOUNT_MISSING')
        selected[role]=choices
    equity_labels={r['source_cell']['row_label'] for r in selected['equity']}
    _need(equity_labels=={'Total Parent stockholders’ equity'},'PARENT_EQUITY_SCOPE_UNPROVEN')
    return {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],'selected_reports':selected,
            'entity':prepared['entity'],'period_end':prepared['filing']['reportDate'],
            'predecessor_combined':False,'finance_lease_counted_once':True}


def _other_disclosures(primary,prepared,composition):
    from datetime import date,timedelta
    from .b06_disclosure_v2 import _date_text
    notes={n['concept']:n['text'] for n in composition['notes']};debt=notes['DebtDisclosureTextBlock'];commit=notes['CommitmentsAndContingenciesDisclosureTextBlock']
    end=_date_text(prepared['filing']['reportDate'])
    previous=(date.fromisoformat(prepared['table_input']['target_period']['period_start'])-timedelta(days=1)).isoformat()
    pair=re.escape(end)+r' \(Successor\) and '+re.escape(_date_text(previous))+r' \(Predecessor\)'
    commercial=re.search(r'At both '+pair+r', we had no outstanding commercial paper borrowings\.',debt)
    revolver=re.search(r'At '+re.escape(end)+r', we had no borrowings outstanding under the Credit Facility and the availability under the Credit Facility was \$([0-9.]+) billion\.',debt)
    bank=re.search(r'At both '+pair+r', there were no outstanding bank borrowings under ([^.]+?)\$([0-9]+) million credit facility that matures in [A-Za-z]+ [0-9]{4}\.',debt)
    _need(commercial and revolver and bank,'COMPLETE_CURRENT_ZERO_BORROWING_STATEMENTS_MISSING')
    letters=re.search(r'At '+re.escape(end)+r', we had outstanding letters of credit and surety bonds of \$([0-9]+) million that were not recorded on the Consolidated Balance Sheet, as well as a \$([0-9.]+) billion standby letter of credit facility\.',commit)
    _need(letters,'LETTERS_OFF_BALANCE_SCOPE_UNPROVEN')
    standby=re.search(r'The amount outstanding was zero at '+re.escape(end)+r' and \$([0-9.]+) billion in [A-Za-z]+ [0-9]{4}\.',commit)
    _need(standby,'STANDBY_CURRENT_ZERO_UNPROVEN')
    purchase='Our long-term commitments not recorded on the balance sheet primarily consist of programming and talent commitments and purchase obligations for goods and services resulting from our normal course of business.'
    programming='At '+end+', we also had long-term contractual obligations for programming liabilities, participations, and residuals.'
    _need(purchase in commit and programming in commit,'PROGRAMMING_PURCHASE_NATURE_UNPROVEN')
    raw=primary['raw_bytes'].decode('utf-8-sig');blocks=_DefinitionBlocks(raw);blocks.feed(raw);blocks.close();blocks._flush()
    assertions=[commercial[0],revolver[0],bank[0],letters[0],standby[0],purchase,programming]
    for assertion in assertions:
        matching=[b for b in blocks.blocks if assertion in b['text']]
        _need(matching and any(not b['quoted_context'] and not b['linked'] for b in matching),'FINANCING_ASSERTION_ONLY_QUOTED_OR_MISSING')
    return {'current_zero_statements':[commercial[0],revolver[0],bank[0],standby[0]],
        'unused_revolver_capacity':decimal_text(value=Decimal(revolver[1])*1000000000),
        'other_facility_limit':decimal_text(value=Decimal(bank[2])*1000000),
        'letters_of_credit':decimal_text(value=Decimal(letters[1])*1000000),
        'standby_capacity':decimal_text(value=Decimal(letters[2])*1000000000),
        'letters_off_balance_statement':letters[0],'purchase_statement':purchase,'programming_statement':programming}


def inspect_inclusive_balance_scope(*,primary,xml,prepared):
    component=inspect_inclusive_composition(primary=primary,xml=xml,prepared=prepared)
    return {**component,'balance_scope':_balance_scope(primary,prepared,component),
            'other_financing_disclosures':_other_disclosures(primary,prepared,component)}


def _measurements(primary,prepared,component):
    """Retain original measurement bases, including their different precision."""
    from datetime import datetime,date
    from .b06_disclosure_v2 import _date_text
    notes={n['concept']:n for n in component['notes']};debt=notes['DebtDisclosureTextBlock']['text']
    end=_date_text(prepared['filing']['reportDate']);money=r'([0-9]+(?:\.[0-9]+)?)'
    acquisition=re.search(r'our debt, which was recorded at its fair value on the closing date of the Transactions and the NAI Transaction on ([A-Za-z]+ [0-9]{1,2}, [0-9]{4}) \(see Note 2\)',debt)
    _need(acquisition,'ACQUISITION_DATE_BASIS_UNPROVEN')
    acquisition_date=datetime.strptime(acquisition[1],'%B %d, %Y').date()
    _need(acquisition_date<date.fromisoformat(prepared['filing']['reportDate']),'ACQUISITION_IS_NOT_EARLIER_MEASUREMENT')
    business=notes['BusinessCombinationDisclosureTextBlock']
    basis=re.search(r'The table below details the preliminary estimated fair values of [^.]+? assets, liabilities and noncontrolling interests at the Ultimate Parent\x27s basis as of '+re.escape(acquisition[1])+r', including measurement period adjustments recorded during the fourth quarter of [0-9]{4}\.',business['text'])
    _need(basis,'ACQUISITION_TABLE_DATE_BASIS_UNPROVEN')
    acq_tables=[t for t in disclosure.tables(business['original_xml_html']) if any(c['text']=='Allocation of Ultimate Parent’s Basis' for r in t['rows'] for c in disclosure.origins(r))]
    _need(len(acq_tables)==1,'ACQUISITION_TABLE_AMBIGUOUS');at=acq_tables[0]
    headers=[c for r in at['rows'] for c in disclosure.origins(r) if c['text']=='Preliminary, Revised']
    _need(len(headers)==1 and any(re.search(r' basis at '+re.escape(acquisition[1])+r'$',disclosure.label(r)) for r in at['rows']),
          'ACQUISITION_REVISED_COLUMN_OR_DATE_UNPROVEN')
    ah=headers[0];acq_rows={}
    for concept,label in POLICY['acquisition_row_labels'].items():
        rows=[r for r in at['rows'] if disclosure.label(r)==label];_need(len(rows)==1,'ACQUISITION_ROW_MISSING')
        acq_rows[concept.casefold()]={'label':label,'value':decimal_text(value=disclosure.amount(rows[0],ah['column_index'],ah['colspan']))}
    adjustment=re.search(r'At '+re.escape(end)+r' \(Successor\), our senior and junior debt balances were net of unamortized fair value adjustments totaling \$'+money+r' billion\.',debt)
    face=re.search(r'The face value of our total debt at both '+re.escape(end)+r' \(Successor\) and [A-Za-z]+ [0-9]{1,2}, [0-9]{4} \(Predecessor\) was \$'+money+r' billion\.',debt)
    fair=notes['FinancialInstrumentsAndFairValueDisclosureTextBlock']['text']
    market=re.search(r'At '+re.escape(end)+r' \(Successor\) and [A-Za-z]+ [0-9]{1,2}, [0-9]{4} \(Predecessor\), the carrying value of our outstanding notes and debentures was \$'+money+r' billion and \$'+money+r' billion, respectively, and the fair value, which is determined based on quoted prices in active markets \(Level 1 in the fair value hierarchy\), was \$'+money+r' billion and \$'+money+r' billion, respectively\.',fair)
    _need(adjustment and face and market,'CURRENT_OTHER_MEASUREMENT_BASIS_UNPROVEN')
    billion=lambda v:Decimal(v)*1000000000
    reported=lambda v:{'value':decimal_text(value=billion(v)),
        'visible_rounding_radius':decimal_text(value=Decimal(10)**Decimal(v).as_tuple().exponent*1000000000/2)}
    carrying=reported(market[1]);instruments=sum(Decimal(m['value']) for m in component['members'])
    _need(abs(instruments-Decimal(carrying['value']))<=Decimal(carrying['visible_rounding_radius']),
          'ROUNDED_NOTES_CARRYING_CONFLICT')
    maturity=notes['ScheduleOfMaturitiesOfLongTermDebtTableTextBlock']
    prefix='At '+end+', our scheduled maturities of long-term debt at face value, which excludes payments for the related interest and finance leases, were as follows:'
    _need(maturity['text'].startswith(prefix),'MATURITY_FACE_EXCLUDES_LEASE_SCOPE_UNPROVEN')
    mt=disclosure.tables(maturity['original_xml_html']);_need(len(mt)==1,'MATURITY_TABLE_AMBIGUOUS')
    rows=[r for r in mt[0]['rows'] if disclosure.label(r)=='Long-term debt'];_need(len(rows)==1,'MATURITY_PRINCIPAL_ROW_MISSING')
    headings=[c for r in mt[0]['rows'] for c in disclosure.origins(r) if re.fullmatch(r'[0-9]{4}(?: and Thereafter)?',c['text'])]
    expected=[str(int(prepared['filing']['reportDate'][:4])+i) for i in range(1,7)];expected[-1]+=' and Thereafter'
    _need(sorted(c['text'] for c in headings)==expected,'MATURITY_FUTURE_YEAR_SET_UNPROVEN')
    maturities=[{'period':c['text'],'value':decimal_text(value=disclosure.amount(rows[0],c['column_index'],c['colspan']))} for c in headings]
    maturity_total=sum(Decimal(m['value']) for m in maturities);face_report=reported(face[1]);adjustment_report=reported(adjustment[1])
    _need(abs(maturity_total-Decimal(face_report['value']))<=Decimal(face_report['visible_rounding_radius']),
          'MATURITY_FACE_VISIBLE_PRECISION_CONFLICT')
    _need(abs(maturity_total-Decimal(adjustment_report['value'])-instruments)<=Decimal(adjustment_report['visible_rounding_radius']),
          'FACE_ADJUSTMENT_CARRYING_VISIBLE_PRECISION_CONFLICT')
    raw=primary['raw_bytes'].decode('utf-8-sig');blocks=_DefinitionBlocks(raw);blocks.feed(raw);blocks.close();blocks._flush()
    assertions=[acquisition[0],basis[0],adjustment[0],face[0],market[0],prefix]
    for assertion in assertions:
        _need(any(assertion in b['text'] and not b['quoted_context'] and not b['linked'] for b in blocks.blocks),
              'MEASUREMENT_ASSERTION_ONLY_QUOTED_OR_MISSING')
    return {'acquisition_date':acquisition_date.isoformat(),'acquisition_basis_statement':basis[0],
        'acquisition_grid_sha256':at['grid_sha256'],'acquisition_rows':acq_rows,'acquisition_revised_column':ah,
        'face_statement':face[0],'adjustment_statement':adjustment[0],'market_statement':market[0],
        'face':face_report,'adjustment':adjustment_report,'market':reported(market[3]),'rounded_notes_carrying':carrying,
        'exact_notes_carrying':decimal_text(value=instruments),'future_maturities':maturities,
        'maturity_face_total':decimal_text(value=maturity_total),
        'native_decimals_preserved':True,'coarse_measurements_are_not_calculation_operands':True}


def _narrative(component,prepared):
    from .b06_disclosure_v2 import _Narrative,_BORROWING,_BALANCE,_MONETARY_CUE,_date_text
    class Paragraphs(_Narrative):
        def handle_starttag(self,tag,attrs):
            if tag=='table' and not self.depth:self.parts.append('\n')
            super().handle_starttag(tag,attrs)
        def handle_endtag(self,tag):
            super().handle_endtag(tag)
            if tag=='table' and not self.depth:self.parts.append('\n')
    result=[];other=component['other_financing_disclosures'];measurements=component['measurements']
    statements=other['current_zero_statements']+[other['letters_off_balance_statement']]
    end=_date_text(prepared['filing']['reportDate']);members={m['label'].casefold():m['value'] for m in component['members']}
    for note in component['notes']:
        if note['concept'] not in {'DebtDisclosureTextBlock','LesseeLeasesPolicyTextBlock','LesseeOperatingLeasesTextBlock',
                                   'CommitmentsAndContingenciesDisclosureTextBlock','FinancialInstrumentsAndFairValueDisclosureTextBlock'}:continue
        parser=Paragraphs();parser.feed(note['original_xml_html']);parser.close();_need(not parser.depth,'NARRATIVE_TABLE_TRUNCATED')
        paragraphs=[' '.join(p.split()) for p in ' '.join(parser.parts).split('\n')]
        for sentence in [s for p in paragraphs for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])',p)]:
            if not _BORROWING.search(sentence):continue
            if any(sentence.endswith(s) for s in statements):disposition='SOURCE_BOUND_CURRENT_ZERO_OR_OFF_BALANCE_SECURITY'
            elif any(sentence.endswith(measurements[k]) for k in ['face_statement','adjustment_statement','market_statement']):
                disposition='SOURCE_BOUND_OTHER_MEASUREMENT'
            elif re.search(r'\b(?:additional (?:borrowings?|debt|loans?|notes|finance leases?)|other borrowings?|other loans?|outside|not included|excluded from)\b',sentence,re.I) and not re.search(r'\b(?:may|could|would|option)\b',sentence,re.I):
                raise InclusiveDebtError('INCLUSIVE_DEBT_UNRESOLVED_ADDITIONAL_BORROWING:'+sentence)
            elif not _BALANCE.search(sentence) or not _MONETARY_CUE.search(sentence):
                disposition='NO_MONETARY_BALANCE_ASSERTION'
            elif re.fullmatch(r'\(a\) In connection with the pushdown of the Ultimate Parent’s basis, our debt was recorded at fair value, which resulted in a decrease to our total debt balance of \$[0-9,.]+ million, reflecting the reversal of a net unamortized discount of \$[0-9,.]+ million and unamortized deferred financing fees of \$[0-9,.]+ million, and a reduction of \$[0-9.]+ billion to adjust our debt to its fair value\.',sentence):
                disposition='EARLIER_ACQUISITION_BASIS_ADJUSTMENT'
            elif re.fullmatch(r'During (?:the fourth quarter of )?([0-9]{4}) \(Predecessor\), we (?:redeemed|repurchased) [^.]+(?:\.[0-9]+[^.]+)*\.',sentence) and int(re.search(r'\b[0-9]{4}\b',sentence)[0])<int(prepared['filing']['reportDate'][:4]):
                _need(not re.search(r'\b(?:remain|remains|are|is) outstanding\b',sentence,re.I),'HISTORICAL_REPAYMENT_CURRENT_CONTRADICTION')
                disposition='EXPLICIT_HISTORICAL_REDEMPTION_OR_REPURCHASE'
            elif sentence.startswith('Junior Debt At '+end+' (Successor), our junior debt was comprised of '):
                tail=sentence.split('was comprised of ',1)[1]
                pattern=r'\$([0-9,]+) million ([0-9.]+% junior subordinated debentures due [0-9]{4})'
                matches=re.findall(pattern,tail);_need(matches and re.sub(pattern,'AMOUNT',tail)=='AMOUNT and AMOUNT.',
                                                     'JUNIOR_NARRATIVE_COMPOSITION_UNPROVEN')
                _need(all(members.get(label.casefold())==decimal_text(value=Decimal(v.replace(',',''))*1000000) for v,label in matches),
                      'JUNIOR_NARRATIVE_TABLE_AMOUNT_CONFLICT')
                disposition='RECONCILED_NAMED_JUNIOR_TABLE_MEMBERS'
            else:raise InclusiveDebtError('INCLUSIVE_DEBT_CURRENT_BORROWING_ASSERTION_UNRESOLVED:'+sentence)
            result.append({'concept':note['concept'],'sentence':sentence,'disposition':disposition})
    return result


def _independent_inventory(primary,xml,prepared,component):
    from .governance_signals import _qname
    inventory={}
    for kind,source in [('xml',xml),('primary',primary)]:
        raw=source['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw);meta=_InventoryMetadata();meta.feed(raw.decode('utf-8-sig'));meta.close()
        consumed={r['ordinal'] for group in component['reports'].values() for r in group[kind]}
        consumed.update(r['ordinal'] for group in component['native_members'][kind].values() for r in group)
        rows=[]
        for f in parsed.facts:
            c=parsed.contexts[f['context_ref']];m=meta.facts[f['ordinal']];uri,local=m['concept'];name=local.casefold()
            if c['period_start']!=c['period_end'] or c['period_end']!=prepared['filing']['reportDate'] or not f['unit_ref']:continue
            if not re.search(r'debt|borrow|loan|lease|credit|facility|financing|funding|obligation|promissory|seniornotes|subordinatednotes|debentures',name):continue
            _need(str(int(c['entity_identifier']))==prepared['entity'],'INVENTORY_SUBJECT_CONFLICT')
            standard=re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri) is not None
            context={**c,'dimensions':dict(c['dimensions'])};context_proof,typed=_inventory_context(context,meta,name,standard)
            unit=meta.units.get(f['unit_ref']);usd=unit=={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}
            pure=unit=={'measures':[('http://www.xbrl.org/2003/instance','pure')],'divided':False}
            if f['text'].strip().casefold() in {'no','zero'} and name in {'lineofcredit','lettersofcreditoutstandingamount'}:
                tu,tl=_qname(m['attrs'].get('format',''),m['namespaces'])
                _need(standard and usd and tl=='fixed-zero' and re.fullmatch(r'https?://www\.xbrl\.org/inlineXBRL/transformation/\d{4}-\d{2}-\d{2}',tu)
                      and m['attrs'].get('sign','') in {'','-'},'NATIVE_CURRENT_ZERO_UNPROVEN')
                value=Decimal(0)
            else:value=Decimal(_source_value(f,m))
            disposition=None
            if f['ordinal'] in consumed:
                _need(usd,'CONSUMED_AMOUNT_UNIT_CONFLICT');disposition='RECONCILED_IN_CURRENT_INCLUSIVE_DEBT'
            elif usd and value==0:disposition='EXPLICIT_CURRENT_ZERO'
            elif pure and (standard and (name.startswith('definedbenefitplanassumptions') or name in {'debtinstrumentinterestratestatedpercentage','operatingleaseweightedaveragediscountratepercent'})
                          or not standard and name in {'lineofcreditfacilitycovenantmaximumconsolidatedleverageratio','definedbenefitplanexpectedfutureemployercontributionsfundingthresholdpercentage'}):
                disposition='REPORTED_RATE_OR_COVENANT_NOT_MONETARY_DEBT'
            elif usd and standard and name=='lettersofcreditoutstandingamount':
                _need(value==Decimal(component['other_financing_disclosures']['letters_of_credit']),'LETTERS_AMOUNT_UNRECONCILED')
                disposition='REPORTED_OFF_BALANCE_SECURITY_NOT_CURRENT_DEBT'
            elif usd and standard and name=='lineofcreditfacilityremainingborrowingcapacity':
                _need(value==Decimal(component['other_financing_disclosures']['unused_revolver_capacity']),'REMAINING_CREDIT_CAPACITY_CONFLICT')
                disposition='UNUSED_FACILITY_CAPACITY_WITH_CURRENT_ZERO_BORROWING'
            elif usd and standard and name=='lineofcreditfacilitymaximumborrowingcapacity':
                _need(value in {Decimal(component['other_financing_disclosures'][k]) for k in ['unused_revolver_capacity','other_facility_limit','standby_capacity']},
                      'FACILITY_LIMIT_SOURCE_AMOUNT_CONFLICT')
                disposition='COMMITTED_FACILITY_LIMIT_NOT_DRAWN_BALANCE'
            elif usd and standard and name in {'debtinstrumentfaceamount','debtinstrumentfairvalue','debtinstrumentunamortizeddiscountpremiumnet'}:
                role={'debtinstrumentfaceamount':'face','debtinstrumentfairvalue':'market','debtinstrumentunamortizeddiscountpremiumnet':'adjustment'}[name]
                _need(not c['dimensions'] and value==Decimal(component['measurements'][role]['value']),'OTHER_MEASUREMENT_SOURCE_AMOUNT_CONFLICT')
                disposition='REPORTED_DIFFERENT_MEASUREMENT_NOT_USED_TO_REPLACE_CARRYING'
            elif usd and standard and name.startswith('longtermdebtmaturitiesrepaymentsofprincipal'):
                disposition='FUTURE_FACE_PRINCIPAL_NOT_ADDED_TO_CARRYING'
            elif usd and (standard and name.startswith(('operatinglease','lesseeoperatinglease'))):
                disposition='OPERATING_LEASE_EXCLUDED_BY_DEBT_DEFINITION'
            elif usd and standard and name.startswith(('programrightsobligations','recordedunconditionalpurchaseobligation','unrecordedunconditionalpurchaseobligation')):
                disposition='REPORTED_PROGRAMMING_OR_PURCHASE_OBLIGATION_NOT_BORROWING'
            elif usd and standard and name.startswith(('definedbenefitplan','deferredtax','taxcredit','revenueremainingperformanceobligation','filmmonetized')):
                disposition='REPORTED_BENEFIT_TAX_REVENUE_OR_CONTENT_ASSET_NOT_BORROWING'
            elif usd and not standard and name=='deferredtaxassetsleaseliability':
                disposition='REPORTED_TAX_ASSET_NOT_BORROWING'
            elif usd and 'businesscombinationrecognized' in name:
                acquisition_rows=component['measurements']['acquisition_rows']
                _need(name in acquisition_rows and value==Decimal(acquisition_rows[name]['value']) and len(c['dimensions'])==1
                      and next(iter(c['dimensions'])).casefold()=='us-gaap:businessacquisitionaxis','ACQUISITION_MEASUREMENT_SCOPE_MISSING')
                if kind=='primary':
                    note=next(n for n in component['notes'] if n['concept']=='BusinessCombinationDisclosureTextBlock')
                    _need(f['ordinal'] in note['primary_fact_ordinals'],'ACQUISITION_FACT_OUTSIDE_SOURCE_NOTE')
                disposition='ACQUISITION_MEASUREMENT_NOT_PERIOD_END_BORROWING'
            _need(disposition is not None,'UNRESOLVED_ADDITIONAL_FINANCING_FACT:'+local)
            rows.append({'ordinal':f['ordinal'],'concept_qname':[uri,local],'context':context,'value':decimal_text(value=value),
                         'context_proof':context_proof,'typed_dimensions':typed,
                         'decimals':m['attrs'].get('decimals'),'unit_definition':unit,'disposition':disposition})
        inventory[kind]=rows
    groups={}
    for kind,rows in inventory.items():
        groups[kind]={}
        for row in rows:
            key=content_hash(value={'concept':[row['concept_qname'][0],row['concept_qname'][1].casefold()],
                'dimensions':row['context']['dimensions'],'typed_dimensions':row['typed_dimensions'],'unit':row['unit_definition']})
            groups[kind].setdefault(key,[]).append(row)
    _need(set(groups['xml'])==set(groups['primary']),'FINANCING_INVENTORY_DOCUMENT_SETS_DIFFER')
    for key in groups['xml']:precision_choice(groups['xml'][key]+groups['primary'][key])
    return inventory


def inspect_inclusive_debt_scope(*,primary,xml,prepared):
    component=inspect_inclusive_balance_scope(primary=primary,xml=xml,prepared=prepared)
    component['measurements']=_measurements(primary,prepared,component)
    component['narrative_inventory']=_narrative(component,prepared)
    inventory=_independent_inventory(primary,xml,prepared,component)
    return {**component,'record_type':'INCLUSIVE_DEBT_SCOPE_COMPONENT','independent_financing_inventory':inventory,
            'complete_b06_proven':True,'proven_composition_amount':component['carrying_amount'],'remaining_checks':[]}
