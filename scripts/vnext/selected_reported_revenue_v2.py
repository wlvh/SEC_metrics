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
from .xbrl_namespace_policy import YEAR_ONLY


def _need(condition,reason):
    if not condition:raise IncomeSourceError('SELECTED_REPORTED_REVENUE_'+reason)


def reported_revenue_scope(*,primary,annual,approved_concepts,xml=None,
                           namespace_policy=YEAR_ONLY,annual_period_reader=None,
                           fiscal_label_resolution=None):
    from .financial_structured import _InlineTableIndex,_fact_cells
    from .financial_duration import _column_period,_cell_proof,_MONTH,_DATE,_date
    from .deterministic_router import parse_accession_xbrl_source
    concepts=sorted(set(approved_concepts)|set(STATEMENT_CONCEPTS))
    options={'namespace_policy':namespace_policy,'annual_period_reader':annual_period_reader}
    rows=native_income_reports(primary,annual,concepts,**options)
    raw=primary['raw_bytes'];parsed=parse_accession_xbrl_source(raw_bytes=raw)
    index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close()
    bound=_fact_cells(index,parsed,{r['ordinal'] for r in rows})
    period=annual['table_input']['target_period'];approved={c.casefold() for c in approved_concepts}
    column_year=period['fiscal_year']
    if fiscal_label_resolution is not None:
        from .canonical import sha256_bytes
        from .normal_annual_input_v2 import _choose_fiscal_year
        from .historical_fiscal_labels import require_actual_definition_scope
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
    for row in rows:
        if row['concept'].casefold() not in approved or row['ordinal'] not in bound:continue
        table,cell=bound[row['ordinal']]
        if _label_key(_label(table,cell)) not in {'total revenue','total revenues','total net revenues'}:continue
        if (row['period_start'],row['period_end'])!=(period['period_start'],period['period_end']):continue
        same=[r for r in rows if r['context_ref']==row['context_ref'] and r['ordinal'] in bound
              and bound[r['ordinal']][0]['table_id']==table['table_id']
              and bound[r['ordinal']][1]['row_index']>cell['row_index']]
        names={r['concept'].casefold() for r in same}
        if not(names & {'us-gaap:netincomeloss','us-gaap:profitloss'}
               and names & {'us-gaap:costofrevenue','us-gaap:costofgoodsandservicessold'}):continue
        column,headers,reason=_column_period(table=table,selected=cell,extra_header_descriptors=UNIT_HEADER)
        _need(not reason and column['year']==column_year,'FISCAL_COLUMN_UNRESOLVED')
        column_end=column.get('date')
        _need(column_end is None or column_end.isoformat()==period['period_end'],'VISIBLE_DATE_CONFLICT')
        actual_end=date.fromisoformat(period['period_end']);end_headers=[]
        end_pattern=re.compile(r'\byears?\s+ended\s+('+_MONTH+r')\s+([0-9]{1,2})',re.I)
        for header_row in table['rows'][:column['row_index']+1]:
            origins=[c for c in header_row['cells'] if c['is_origin'] and c['text'].strip()]
            for c in origins:
                matches=list(end_pattern.finditer(c['text']))
                if not matches:continue
                common=(c['column_index']<cell['column_index'] and all(
                    other is c or re.fullmatch(r'[0-9]{4}',other['text'].strip())
                    or _DATE.fullmatch(other['text'].strip())
                    or any(re.fullmatch(p,other['text'].strip(),re.I) for p in UNIT_HEADER)
                    for other in origins))
                covers=c['column_index']<=cell['column_index']<c['column_index']+c['colspan']
                if not (covers or common):continue
                for match in matches:
                    try:described_end=_date(year=actual_end.year,month=match[1],day=int(match[2]))
                    except ValueError:raise IncomeSourceError('SELECTED_REPORTED_REVENUE_VISIBLE_END_DAY_INVALID')
                    _need(described_end==actual_end,'VISIBLE_END_DAY_CONFLICT')
                end_headers.append(_cell_proof(table=table,cell=c))
        statement=_statement_scope(raw,index,parsed,table,adjacent_heading=True)
        units=[{'kind':'visible_cell','proof':_cell_proof(table=table,cell=c),'text':c['text']}
               for r in table['rows'][:column['row_index']+1] for c in r['cells']
               if c['is_origin'] and any(re.fullmatch(p,c['text'].strip(),re.I) for p in UNIT_HEADER)]
        units.extend({'kind':'heading_block','proof':b,'text':b['visible_text']}
                     for b in statement['intervening_sources']
                     if any(re.fullmatch(p,b['visible_text'].strip(),re.I) for p in UNIT_HEADER))
        scales={6 if 'million' in u['text'].casefold() else 3 for u in units}
        _need(len(scales)==1 and int(parsed.facts[row['ordinal']]['scale'] or 0)==next(iter(scales)),
              'VISIBLE_NATIVE_UNIT_UNRESOLVED')
        matches=[r for r in xml_rows if _key(r)==_key(row)] if xml_rows is not None else []
        _need(xml_rows is None or matches,'PRIMARY_XML_TOTAL_DIFFERS')
        selected.append({'total':row,'total_cell':_cell_proof(table=table,cell=cell),
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
    return {**body,'scope_id':content_hash(value=body)}


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
