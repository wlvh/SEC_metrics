"""Admit an explicitly reported consolidated total; never calculate a new total.

This successor covers a fiscal-year column whose full native context matches
the selected annual input. It keeps V1 component proofs and defaults separate.
An extension-labelled component need not be promoted to an approved concept
when the statement already reports its total with an approved concept.
"""
import re
from datetime import date

from .canonical import content_hash
from .selected_income_source_v1 import native_income_reports, IncomeSourceError
from .selected_revenue_scope_v1 import UNIT_HEADER, STATEMENT_CONCEPTS, _label, _label_key, _statement_scope, _key
from .xbrl_namespace_policy import YEAR_ONLY, is_sec_namespace


# Explicit consumers of the section-closing contract add these dependencies
# to their existing processing identity. No old consumer is opted in here.
STATEMENT_GROUP_PROCESSING_FILES = (
    'scripts/vnext/selected_reported_revenue_v2.py',
    'scripts/vnext/selected_revenue_scope_v1.py',
    'scripts/vnext/going_concern_source.py',
    'scripts/vnext/text_business_candidates.py',
    'scripts/vnext/text_coverage.py',
    'scripts/vnext/normal_annual_input_v2.py',
    'catalog/r6/going_concern_source_rules_v1.json',
    'catalog/r6/text_business_candidates_v1.json',
)


def _need(condition,reason):
    if not condition:raise IncomeSourceError('SELECTED_REPORTED_REVENUE_'+reason)


def reported_revenue_scope(*,primary,annual,approved_concepts,xml=None,
                           namespace_policy=YEAR_ONLY,annual_period_reader=None,
                           fiscal_label_resolution=None,allow_single_revenue_line=False,
                           allow_statement_group_totals=False,dei_release=YEAR_ONLY):
    from .financial_structured import _InlineTableIndex,_fact_cells
    from .financial_duration import _column_period,_cell_proof,_MONTH,_DATE,_date
    from .deterministic_router import parse_accession_xbrl_source
    _need(type(allow_single_revenue_line) is bool,'SINGLE_REVENUE_OPTION_INVALID')
    _need(type(allow_statement_group_totals) is bool,'STATEMENT_GROUP_OPTION_INVALID')
    is_sec_namespace('',taxonomy='dei',namespace_policy=dei_release)
    concepts=sorted(set(approved_concepts)|set(STATEMENT_CONCEPTS))
    options={'namespace_policy':namespace_policy,'annual_period_reader':annual_period_reader}
    rows=native_income_reports(primary,annual,concepts,**options)
    raw=primary['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw)
    native_by_ordinal={f['ordinal']:f for f in parsed.facts}
    index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close()
    bound=_fact_cells(index,parsed,{r['ordinal'] for r in rows})
    period=annual['table_input']['target_period'];approved={c.casefold() for c in approved_concepts}
    column_year=period['fiscal_year']
    if fiscal_label_resolution is not None:
        from .canonical import sha256_bytes
        from .normal_annual_input_v2 import _choose_fiscal_year
        from .selected_fiscal_definition_scope_v1 import require_actual_definition_scope
        label=fiscal_label_resolution;inspected=label.get('source_inspection',{})
        _need(label.get('record_type') in {'SELECTED_HISTORICAL_FISCAL_LABEL','ORDINARY_FISCAL_YEAR_LABEL_RESOLUTION'}
              and inspected.get('primary_sha256')==sha256_bytes(content=raw)
              and inspected.get('entity')==annual['entity']
              and inspected.get('accession')==annual['filing']['accessionNumber']
              and inspected.get('actual_period')=={k:period[k] for k in ('period_start','period_end')}
              and label.get('original_dei_fiscal_year')==period['fiscal_year'],
              'FISCAL_LABEL_SOURCE_CHANGED')
        inspected=require_actual_definition_scope(inspected)
        column_year,_=_choose_fiscal_year(inspected)
        _need(column_year==label.get('selected_fiscal_year'),'FISCAL_LABEL_SELECTION_CHANGED')
    xml_rows=native_income_reports(xml,annual,concepts,**options) if xml is not None else None
    selected=[]
    complete_expense_rejections=[]
    for row in rows:
        if row['concept'].casefold() not in approved or row['ordinal'] not in bound:continue
        table,cell=bound[row['ordinal']]
        label=_label_key(_label(table,cell))
        single_operating = allow_single_revenue_line and ' '.join(
            _label(table,cell).casefold().split()) == 'operating revenue'
        single=allow_single_revenue_line and (label in {'revenue','revenues'} or single_operating)
        operating = ' '.join(_label(table,cell).casefold().split()) == 'total operating revenues'
        group_total=allow_statement_group_totals and label==''
        if group_total and xml is None:continue
        if label not in {'total revenue','total revenues','total net revenues'} and not (single or operating or group_total):continue
        if (row['period_start'],row['period_end'])!=(period['period_start'],period['period_end']):continue
        same=[r for r in rows if r['context_ref']==row['context_ref'] and r['ordinal'] in bound
              and bound[r['ordinal']][0]['table_id']==table['table_id']
              and bound[r['ordinal']][1]['row_index']>cell['row_index']]
        operating_costs=[]
        if operating:
            # The income statement's complete operating-expense total can
            # prove the expense side without inventing a cost-of-sales tag.
            cost_rows=native_income_reports(primary,annual,['us-gaap:OperatingCostsAndExpenses'],**options)
            cost_bound=_fact_cells(index,parsed,{r['ordinal'] for r in cost_rows})
            operating_costs=[r for r in cost_rows if r['context_ref']==row['context_ref']
                and r['ordinal'] in cost_bound and cost_bound[r['ordinal']][0]['table_id']==table['table_id']
                and cost_bound[r['ordinal']][1]['row_index']>cell['row_index']
                and ' '.join(_label(*cost_bound[r['ordinal']]).casefold().split())
                    in {'total operating expenses', 'total operating expenses, net'}]
        names={r['concept'].casefold() for r in same}
        complete_expenses=None
        if group_total or (single and not (names & {'us-gaap:costofrevenue','us-gaap:costofgoodsandservicessold'})):
            try:
                complete_expenses=_complete_expense_statement(primary,xml,annual,options,
                    index,parsed,table,cell,row,same,column_year=column_year,
                    **({'section_closed':True} if group_total else {}))
            except IncomeSourceError as error:
                # Failure of this added proof is not failure of the source or
                # permission to replace the caller's existing fallback. Only
                # this route's bounded proof reasons are withheld here.
                if not str(error).startswith('SELECTED_REPORTED_REVENUE_COMPLETE_EXPENSE_'):
                    raise
                complete_expense_rejections.append({'ordinal':row['ordinal'],
                    'source_reference':row['source_reference'], 'reason':str(error)})
                complete_expenses=None
        if not(names & {'us-gaap:netincomeloss','us-gaap:profitloss'}
               and (names & {'us-gaap:costofrevenue','us-gaap:costofgoodsandservicessold'}
                    or operating_costs or complete_expenses)):continue
        if group_total and complete_expenses is None:continue
        extra_units=(r'\(?(?:in |dollars in )?(?:millions|thousands), except per share amounts\)?',) if operating else ()
        if group_total:
            extra_units=(r'\(?(?:in |\$ in )?(?:millions|thousands), except per share amounts\)?',)
        if single_operating:
            extra_units = (r'\(?dollars in (?:millions|thousands), except per share amounts, and shares in thousands\)?',)
        unit_headers=UNIT_HEADER+extra_units
        column,headers,reason=_column_period(table=table,selected=cell,extra_header_descriptors=unit_headers)
        _need(not reason and column['year']==column_year,'FISCAL_COLUMN_UNRESOLVED')
        if single:
            _single_revenue_line(index,parsed,table,cell,row,column,same,
                                 extra_unit_headers=extra_units,
                                 **({'first_cost_row':complete_expenses['expense_group_row']}
                                    if complete_expenses else {}))
        column_end=column.get('date')
        _need(column_end is None or column_end.isoformat()==period['period_end'],'VISIBLE_DATE_CONFLICT')
        actual_end=date.fromisoformat(period['period_end']);end_headers=[]
        end_pattern=re.compile(r'\byears?\s+ended\s+('+_MONTH+r')\s+([0-9]{1,2})',re.I)
        for header_row in table['rows'][:cell['row_index']]:
            origins=[c for c in header_row['cells'] if c['is_origin'] and c['text'].strip()]
            for c in origins:
                matches=list(end_pattern.finditer(c['text']))
                full_dates=list(_DATE.finditer(c['text']))
                if not matches and not full_dates:continue
                common=(c['column_index']<cell['column_index'] and all(
                    other is c or re.fullmatch(r'[0-9]{4}',other['text'].strip())
                    or bool(matches) and re.fullmatch(r'[0-9]+',other['text'].strip())
                    or _DATE.fullmatch(other['text'].strip())
                    or any(re.fullmatch(p,other['text'].strip(),re.I) for p in unit_headers)
                    for other in origins))
                covers=c['column_index']<=cell['column_index']<c['column_index']+c['colspan']
                if not (covers or common):continue
                for match in full_dates:
                    try:described_end=_date(year=int(match[3]),month=match[1],day=int(match[2]))
                    except ValueError:raise IncomeSourceError('SELECTED_REPORTED_REVENUE_VISIBLE_END_DAY_INVALID')
                    _need(described_end==actual_end,'VISIBLE_DATE_CONFLICT')
                for match in matches:
                    try:described_end=_date(year=actual_end.year,month=match[1],day=int(match[2]))
                    except ValueError:raise IncomeSourceError('SELECTED_REPORTED_REVENUE_VISIBLE_END_DAY_INVALID')
                    _need(described_end==actual_end,'VISIBLE_END_DAY_CONFLICT')
                end_headers.append(_cell_proof(table=table,cell=c))
        sections = (r'operating revenues:',r'operating expenses(?:, net)?:',
                    r'(?:non-operating|other) expenses \(income\):') if operating else ()
        if single_operating:
            sections = (r'operating expenses:?', r'other expense:?',
                        r'other \(expense\) income:?',
                        r'basic and diluted earnings \(loss\) per common share',
                        r'basic and diluted \(loss\) earnings per common share',
                        r'basic and diluted loss per common share',
                        r'basic and diluted loss per share of common stock',
                        r'weighted average common shares outstanding',
                        r'weighted average common stock outstanding')
        issuer_headers=None
        if complete_expenses:
            issuer_headers=_defined_income_headers(primary,parsed,annual,
                dei_release=dei_release,
                **({'include_cover':True} if group_total else {}))
            sections=(*sections,*issuer_headers['patterns'])
        if group_total:
            sections=(*sections,r'operating costs and expenses:?',r'earnings(?: \(loss\))? per share')
        statement=_statement_scope(raw,index,parsed,table,adjacent_heading=True,
            extra_unit_headers=extra_units,
            extra_section_headers=sections, bind_statement_page=True,
            **({'extra_heading_headers':(*issuer_headers['heading_patterns'],
                r'fiscal years '+str(column_year)+r', '+str(column_year-1)+
                r', and '+str(column_year-2))} if group_total else {}))
        unit_stop = cell['row_index'] if single_operating else column['row_index']+1
        units=[{'kind':'visible_cell','proof':_cell_proof(table=table,cell=c),'text':c['text']}
               for r in table['rows'][:unit_stop] for c in r['cells']
               if c['is_origin'] and any(re.fullmatch(p,c['text'].strip(),re.I) for p in unit_headers)]
        units.extend({'kind':'heading_block','proof':b,'text':b['visible_text']}
                     for b in statement['intervening_sources']
                     if any(re.fullmatch(p,b['visible_text'].strip(),re.I) for p in unit_headers))
        scales={6 if 'million' in u['text'].casefold() else 3 for u in units}
        _need(len(scales)==1 and int(native_by_ordinal[row['ordinal']]['scale'] or 0)==next(iter(scales)),
              'VISIBLE_NATIVE_UNIT_UNRESOLVED')
        matches=[r for r in xml_rows if _key(r)==_key(row)] if xml_rows is not None else []
        _need(xml_rows is None or matches,'PRIMARY_XML_TOTAL_DIFFERS')
        selected.append({**({'operating_expense_reports':operating_costs} if operating else {}),'total':row,'total_cell':_cell_proof(table=table,cell=cell),
                         **({'complete_expense_statement':complete_expenses} if complete_expenses else {}),
                         **({'statement_group_total':True} if group_total else {}),
                         **({'issuer_header_definition':issuer_headers['definitions']} if issuer_headers else {}),
                         'statement_scope':statement,'unit_sources':units,
                         'year_headers':[_cell_proof(table=table,cell=h) for h,_,_ in headers],
                         'end_headers':end_headers,
                         'annual_period':period,'xml_matches':matches,
                         'xml_check':'MATCH' if xml_rows is not None else 'NOT_SUPPLIED'})
    _need(len({_key(s['total']) for s in selected})<=1,'STATEMENT_TOTAL_CONFLICT')
    body={'method':'SELECTED_REPORTED_CONSOLIDATED_REVENUE_V2','annual_input':annual,
          'approved_concepts':list(approved_concepts),'reported_totals':selected,
          'selected_fiscal_column_year':column_year,'fiscal_label_resolution':fiscal_label_resolution,
          'status':'REPORTED_CONSOLIDATED_TOTAL' if selected else 'NO_REPORTED_TOTAL_PROVEN',
          'complete_scope_proven':bool(selected),'original_reports':rows}
    if complete_expense_rejections:
        body['complete_expense_rejections']=complete_expense_rejections
    if allow_statement_group_totals:
        body['statement_group_totals_allowed']=True
    if dei_release!=YEAR_ONLY:
        body['dei_release']=dei_release
    if allow_single_revenue_line:
        body.update(method='SELECTED_REPORTED_SINGLE_REVENUE_LINE_V1',
                    single_revenue_line_allowed=True)
    return {**body,'scope_id':content_hash(value=body)}


def _defined_income_headers(primary,parsed,annual,*,include_cover=False,dei_release=YEAR_ONLY):
    """Exact issuer headings from its explicit consolidated alias definition."""
    from .fiscal_year_labels import _DefinitionBlocks
    from .text_results_v2 import _ReportedFactMetadata
    from .xbrl_namespace_policy import is_sec_namespace,YEAR_QUARTER_OR_DATE
    from .canonical import sha256_bytes
    is_sec_namespace('',taxonomy='dei',namespace_policy=dei_release)
    raw=primary['raw_bytes'];text=raw.decode('utf-8-sig');meta=_ReportedFactMetadata()
    meta.feed(text);meta.close()
    names={f['text'].strip() for f in parsed.facts
        if meta.facts[f['ordinal']]['concept'][1].casefold()=='entityregistrantname'
        and is_sec_namespace(meta.facts[f['ordinal']]['concept'][0],taxonomy='dei',
                             namespace_policy=YEAR_QUARTER_OR_DATE)
        and str(int(parsed.contexts[f['context_ref']]['entity_identifier']))==annual['entity']
        and not parsed.contexts[f['context_ref']]['dimensions']
        and not parsed.contexts[f['context_ref']]['typed_dimension_count']
        and parsed.contexts[f['context_ref']]['period_start']==annual['table_input']['target_period']['period_start']
        and parsed.contexts[f['context_ref']]['period_end']==annual['table_input']['target_period']['period_end']}
    aliases=set(names);definitions=[]
    if include_cover and any(re.search(r'\s+/[A-Za-z]{2}/\s*$',name) for name in names):
        from .text_coverage import build_text_document
        from .going_concern_source import _registrant_name_binding
        document=build_text_document(raw_bytes=raw,raw_blob=primary['raw_blob'],
            source_reference=primary['source_reference'],expected_company_id=annual['company_id'],
            expected_cik=annual['entity'],expected_period_end=annual['filing']['reportDate'],
            namespace_policy=dei_release)
        binding=_registrant_name_binding(document,parsed,meta,namespace_policy=dei_release)
        from .normal_annual_input_v2 import exact_json_value
        binding=exact_json_value(binding)
        _need(binding['status']=='SAME_SOURCE_COVER_AND_CURRENT_DEI_NAME_BOUND',
              'COMPLETE_EXPENSE_COVER_NAME_NOT_BOUND')
        aliases.update(binding['accepted_source_names'])
        definitions.append({'same_source_cover_name_binding':binding})
    blocks=_DefinitionBlocks(text);blocks.feed(text);blocks.close();blocks._flush()
    for block in blocks.blocks:
        if block['quoted_context'] or block['linked']:continue
        match=re.search(r'Unless the context requires otherwise, references in this document to '
            r'(?P<aliases>[^.;]{1,200}) mean (?P<name>[^,;]{1,100}) and its consolidated subsidiaries(?=,|\.)',block['text'])
        if not match or match['name'] not in names:continue
        prefix=block['text'][:match.start()]
        if prefix and re.search(r'\b(?:not|except|excluded|only|subsidiary)\b',prefix,re.I):continue
        tokens=re.findall(r'“([^”]+)”',match['aliases'])
        residual=re.sub(r'“[^”]+”','',match['aliases'])
        if not tokens or re.fullmatch(r'[\s,]*(?:and[\s,]*)?',residual) is None:continue
        defined={a.rstrip(',') for a in tokens if a.rstrip(',') not in {'the Company','we','us','our'}}
        aliases.update(defined)
        start=len(text[:block['start']].encode('utf-8'))+(3 if raw.startswith(b'\xef\xbb\xbf') else 0)
        end=len(text[:block['end']].encode('utf-8'))+(3 if raw.startswith(b'\xef\xbb\xbf') else 0)
        definitions.append({'raw_start_byte':start,'raw_end_byte':end,'raw_span_sha256':sha256_bytes(content=raw[start:end]),
            'text':block['text'],'registrant_name':match['name'],'aliases':sorted(defined)})
    patterns=[r'weighted average number of common shares outstanding:']
    for name in sorted(aliases):
        escaped=re.escape(name.casefold())
        patterns.extend([r'amounts attributable to '+escaped+r':',
            r'(?:basic|diluted) net earnings \(loss\) per common share attributable to '+escaped+r':'])
    return {'patterns':patterns,'definitions':definitions,
            **({'dei_release':dei_release} if dei_release!=YEAR_ONLY else {}),
            **({'heading_patterns':tuple(re.escape(name.casefold()) for name in sorted(aliases))}
               if include_cover else {})}


def _complete_expense_statement(primary,xml,annual,options,index,parsed,table,cell,revenue,following,*,column_year=None,section_closed=False):
    """The full expense group and its reported operating result in one column."""
    if column_year is None:column_year=annual['table_input']['target_period']['fiscal_year']
    from decimal import Decimal
    from .financial_structured import _fact_cells
    from .financial_duration import _cell_proof,_column_period
    costs=native_income_reports(primary,annual,['us-gaap:CostsAndExpenses'],**options)
    bound=_fact_cells(index,parsed,{r['ordinal'] for r in costs})
    candidates=[r for r in costs if r['context_ref']==revenue['context_ref']
        and r['ordinal'] in bound and bound[r['ordinal']][0]['table_id']==table['table_id']
        and bound[r['ordinal']][1]['row_index']>cell['row_index']]
    if not candidates:return None
    _need(len(candidates)==1,'COMPLETE_EXPENSE_TOTAL_AMBIGUOUS')
    expense=candidates[0];expense_cell=bound[expense['ordinal']][1]
    _need((_label(table,expense_cell).strip()=='' if section_closed else
           ' '.join(_label(table,expense_cell).casefold().split())=='total costs and expenses'),
          'COMPLETE_EXPENSE_TOTAL_LABEL_UNPROVEN')
    closed_sections=[]
    if section_closed:
        for amount,header in ((cell,r'revenues:?'),(expense_cell,r'operating costs and expenses:?')):
            closed_sections.append(_closed_section_total(table,amount,header=header))
    group=[]
    for gridrow in table['rows'][cell['row_index']+1:expense_cell['row_index']]:
        origins=[c for c in gridrow['cells'] if c['is_origin'] and c['text'].strip()]
        if len(origins)==1 and (re.fullmatch(r'operating costs and expenses:?',origins[0]['text'].strip(),re.I)
                if section_closed else origins[0]['text'].strip().casefold()=='costs and expenses:'):
            group.append(origins[0])
    _need(len(group)==1,'COMPLETE_EXPENSE_GROUP_UNPROVEN')
    operating=native_income_reports(primary,annual,['us-gaap:OperatingIncomeLoss'],**options)
    obound=_fact_cells(index,parsed,{r['ordinal'] for r in operating})
    operating=[r for r in operating if r['context_ref']==revenue['context_ref']
        and r['ordinal'] in obound and obound[r['ordinal']][0]['table_id']==table['table_id']
        and obound[r['ordinal']][1]['row_index']>expense_cell['row_index']]
    _need(len(operating)==1,'COMPLETE_EXPENSE_OPERATING_RESULT_UNPROVEN')
    income=operating[0];income_cell=obound[income['ordinal']][1]
    _need(' '.join(_label(table,income_cell).casefold().split()) in
          {'operating income','operating loss','operating income (loss)'},
          'COMPLETE_EXPENSE_OPERATING_LABEL_UNPROVEN')
    for report,amount_cell in ((expense,expense_cell),(income,income_cell)):
        covers=amount_cell['column_index']<=cell['column_index']<amount_cell['column_index']+amount_cell['colspan']
        _need(covers,'COMPLETE_EXPENSE_COLUMN_CONFLICT')
        column,_,reason=_column_period(table=table,selected=amount_cell,extra_header_descriptors=UNIT_HEADER)
        _need(not reason and column['year']==column_year,
              'COMPLETE_EXPENSE_COLUMN_PERIOD_UNPROVEN')
        native=next(f for f in parsed.facts if f['ordinal']==report['ordinal'])
        visible=''.join(amount_cell['text'].split()).lstrip('$').strip('()')
        _need(visible==''.join(native['text'].split()).strip('()'),
              'COMPLETE_EXPENSE_CELL_TEXT_CONFLICT')
        _need(native.get('scale')==next(f for f in parsed.facts if f['ordinal']==revenue['ordinal']).get('scale'),
              'COMPLETE_EXPENSE_SCALE_CONFLICT')
    # Do not silently omit disposition gains or another intervening amount.
    numeric=_fact_cells(index,parsed,{f['ordinal'] for f in parsed.facts if f.get('unit_ref')})
    intermediate=[ordinal for ordinal,(t,c) in numeric.items() if t['table_id']==table['table_id']
        and expense_cell['row_index']<c['row_index']<income_cell['row_index']
        and c['column_index']<=cell['column_index']<c['column_index']+c['colspan']]
    from .text_results_v2 import _ReportedFactMetadata
    from .governance_signals import _source_value
    metadata=_ReportedFactMetadata();metadata.feed(primary['raw_bytes'].decode('utf-8-sig'));metadata.close()
    neutral=[]
    for ordinal in intermediate:
        fact=next(f for f in parsed.facts if f['ordinal']==ordinal);_,intermediate_cell=numeric[ordinal]
        _need(fact['context_ref']==revenue['context_ref']
              and fact['unit_ref']==next(f for f in parsed.facts if f['ordinal']==revenue['ordinal'])['unit_ref']
              and _source_value(fact,metadata.facts[ordinal])=='0'
              and intermediate_cell['text'].strip() in {'0','—','–','-'}
              and ' '.join(_label(table,intermediate_cell).casefold().split())in {'gains on dispositions','net gains on dispositions'},
              'COMPLETE_EXPENSE_INTERVENING_AMOUNT_UNPROVEN')
        neutral.append({'ordinal':ordinal,'concept':list(metadata.facts[ordinal]['concept']),
            'value':'0','context_ref':fact['context_ref'],'unit_ref':fact['unit_ref'],
            'cell':_cell_proof(table=table,cell=intermediate_cell)})
    neutral_rows={numeric[ordinal][1]['row_index'] for ordinal in intermediate}
    for gridrow in table['rows'][expense_cell['row_index']+1:income_cell['row_index']]:
        amounts=[c for c in gridrow['cells'] if c['is_origin']
            and c['column_index']<=cell['column_index']<c['column_index']+c['colspan']
            and c['text'].strip()]
        _need(not amounts or gridrow['row_index'] in neutral_rows,
              'COMPLETE_EXPENSE_UNTAGGED_INTERVENING_AMOUNT')
    _need(Decimal(revenue['value'])-Decimal(expense['value'])==Decimal(income['value']),
          'COMPLETE_EXPENSE_OPERATING_RELATION_CONFLICT')
    matches=[]
    if xml is not None:
        xmlreports=native_income_reports(xml,annual,['us-gaap:CostsAndExpenses','us-gaap:OperatingIncomeLoss'],**options)
        for chosen in (expense,income):
            found=[r for r in xmlreports if _key(r)==_key(chosen)]
            _need(bool(found),'COMPLETE_EXPENSE_PRIMARY_XML_DIFFERS')
            matches.extend(found)
    return {'expense':expense,'expense_cell':_cell_proof(table=table,cell=expense_cell),
            'expense_group':_cell_proof(table=table,cell=group[0]),'expense_group_row':group[0]['row_index'],
            'operating_income':income,'operating_cell':_cell_proof(table=table,cell=income_cell),
            'neutral_intermediate_reports':neutral,
            'annual_period':annual['table_input']['target_period'],'xml_matches':matches,
            'xml_check':'MATCH' if xml is not None else 'NOT_SUPPLIED',
            **({'closed_sections':closed_sections} if section_closed else {})}


def _closed_section_total(table,cell,*,header):
    """A blank reported total must close its explicitly named section."""
    before=[]
    for row in table['rows'][:cell['row_index']]:
        cells=[c for c in row['cells'] if c['is_origin'] and c['text'].strip()]
        if len(cells)==1 and re.fullmatch(header,cells[0]['text'].strip(),re.I):
            before.append(cells[0])
    _need(len(before)==1,'COMPLETE_EXPENSE_SECTION_HEADER_UNPROVEN')
    _need(any(c['is_origin'] and c['text'].strip()
        and c['column_index']<=cell['column_index']<c['column_index']+c['colspan']
        for row in table['rows'][before[0]['row_index']+1:cell['row_index']] for c in row['cells']),
        'COMPLETE_EXPENSE_SECTION_COMPONENTS_MISSING')
    _need(not _label(table,cell).strip(),'COMPLETE_EXPENSE_SECTION_TOTAL_NOT_BLANK')
    following=[row for row in table['rows'][cell['row_index']+1:]
               if any(c['is_origin'] and c['text'].strip() for c in row['cells'])]
    _need(bool(following),'COMPLETE_EXPENSE_SECTION_END_MISSING')
    next_label=' '.join(' '.join(c['text'] for c in following[0]['cells']
        if c['is_origin'] and c['column_index']<cell['column_index']).casefold().split())
    expected=(r'operating costs and expenses:?' if header==r'revenues:?'
              else r'operating (?:income|loss)(?: \(loss\))?')
    _need(re.fullmatch(expected,next_label,re.I) is not None,
          'COMPLETE_EXPENSE_SECTION_END_UNPROVEN')
    from .financial_duration import _cell_proof
    return {'section_header':_cell_proof(table=table,cell=before[0]),
            'total_row':cell['row_index'],'next_section_row':following[0]['row_index']}


def _single_revenue_line(index,parsed,table,cell,row,column,following,*,extra_unit_headers=(),first_cost_row=None):
    """A sole top-line amount in this column, not a component or note subtotal.

    The caller still proves the complete consolidated income statement,
    native entity/annual context, column, units and any supplied XML match.
    Check all numeric tags, including company extensions, and visible amounts
    between the year header and the first actual cost row; do not just search
    a list of approved revenue concepts.
    """
    from .financial_structured import _fact_cells
    from .financial_duration import _column_period,_MONTH,_date
    costs=[r for r in following if r['concept'].casefold() in
           {'us-gaap:costofrevenue','us-gaap:costofgoodsandservicessold'}]
    numeric=_fact_cells(index,parsed,{f['ordinal'] for f in parsed.facts if f.get('unit_ref')})
    first_cost=(first_cost_row if first_cost_row is not None
                else min(numeric[c['ordinal']][1]['row_index'] for c in costs))
    selected_column=cell['column_index']
    _need(column['row_index']<cell['row_index']<first_cost,'SINGLE_REVENUE_POSITION_UNPROVEN')
    visible=''.join(cell['text'].split())
    native=''.join(next(f for f in parsed.facts if f['ordinal']==row['ordinal'])['text'].split())
    if visible.startswith('$') and not native.startswith('$'):visible=visible[1:]
    _need(visible==native,'SINGLE_REVENUE_SELECTED_CELL_TEXT_CONFLICT')
    # A later/repeated year header cannot erase amounts earlier in this
    # same statement column. Recognize actual header rows with the existing
    # parser, then inspect all rows before the first cost, not just those
    # after whichever header was nearest the selected revenue.
    header_rows=set()
    for before in table['rows'][:first_cost]:
        probe={**cell,'row_index':before['row_index']+1}
        period,_,reason=_column_period(table=table,selected=probe,
            extra_header_descriptors=UNIT_HEADER+extra_unit_headers)
        if not reason and period['row_index']==before['row_index']:
            _need(period['year']==column['year'],'SINGLE_REVENUE_HEADER_CONFLICT')
            header_rows.add(before['row_index'])
    for ordinal,(other_table,other_cell) in numeric.items():
        in_column=other_cell['column_index']<=selected_column<other_cell['column_index']+other_cell['colspan']
        if other_table['table_id']==table['table_id'] and in_column and other_cell['row_index']<first_cost:
            _need(ordinal==row['ordinal'],'SINGLE_REVENUE_OTHER_AMOUNT')
    for other_row in table['rows']:
        if not other_row['row_index']<first_cost or other_row['row_index'] in header_rows or other_row['row_index']==cell['row_index']:continue
        for other_cell in other_row['cells']:
            in_column=other_cell['column_index']<=selected_column<other_cell['column_index']+other_cell['colspan']
            if other_cell['is_origin'] and in_column:
                descriptor=re.fullmatch(r'(?:for the )?(?:fiscal )?years? ended ('+_MONTH+r')\s+([0-9]{1,2}),?',
                                        other_cell['text'].strip(),re.I)
                if descriptor:
                    end=date.fromisoformat(row['period_end'])
                    _need(_date(year=end.year,month=descriptor[1],day=int(descriptor[2]))==end,
                          'SINGLE_REVENUE_HEADER_DATE_CONFLICT')
                    continue
                _need(not re.search(r'[0-9]',other_cell['text']),
                      'SINGLE_REVENUE_UNTAGGED_AMOUNT:row='+str(other_row['row_index'])+':'+other_cell['text'][:120])


def admit_reported_revenue_facts(*,facts,scope):
    if not scope['reported_totals']:return list(facts)
    from .selected_revenue_scope_v1 import admit_revenue_facts
    # Only reuse the mechanical native-fact filter. This private adapter does
    # not assert a component sum and is not saved as a V1 component proof.
    return admit_revenue_facts(facts=facts,scope={
        'annual_input':scope['annual_input'],'approved_concepts':scope['approved_concepts'],
        'splits':[{'total':s['total']} for s in scope['reported_totals']]})


def verify_reported_revenue_observations(*,observations,scope):
    if not scope['reported_totals']:return
    from .selected_revenue_scope_v1 import verify_revenue_observations
    verify_revenue_observations(observations=observations,scope={
        'splits':[{'total':s['total']} for s in scope['reported_totals']]})
