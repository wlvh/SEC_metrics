"""Income facts for an explicitly selected filing, without current-year discovery.

This explicit successor reuses the current native fact and visible-column
checks. It reads no registry, latest filing, ledger, saved answer or Result, and
creates no Candidate/Run. Callers still verify source requests, amendments,
statement scope and calculation. The optional annual reader is program code
selected by the consumer, not an unchecked period supplied as an answer.
"""
import re
from .canonical import sha256_bytes
from .deterministic_router import parse_accession_xbrl_source
from .text_results_v2 import _ReportedFactMetadata, _verified_context
from .governance_signals import _source_value
from .xbrl_namespace_policy import YEAR_ONLY, is_fasb_namespace


class IncomeSourceError(ValueError):
    category='SELECTED_SOURCE_SCOPE_UNRESOLVED'


def need(condition,reason):
    if not condition:raise IncomeSourceError('SELECTED_INCOME_'+reason)


def visible_income_periods(raw, parsed, rows):
    """Compare an inline fact's own column date range, never a nearby column."""
    from .financial_structured import _InlineTableIndex, _fact_cells
    from .financial_duration import _column_period, _cell_proof, _MONTH, _date
    index=_InlineTableIndex(raw);index.feed(raw.decode('utf-8-sig'));index.close()
    cells=_fact_cells(index,parsed,{row['ordinal'] for row in rows})
    pattern=re.compile(r'\bperiod\s+from\s+('+_MONTH+r')\s+([0-9]{1,2})\s*[-–—]\s*('
                       +_MONTH+r')\s+([0-9]{1,2}),?\s*$',re.I)
    checks={}
    for row in rows:
        bound=cells.get(row['ordinal']);evidence=[];intervals=set()
        if bound:
            table,cell=bound
            column,year_headers,reason=_column_period(table=table,selected=cell)
            if not reason:
                for table_row in table['rows'][:cell['row_index']]:
                    for header in table_row['cells']:
                        if not header['is_origin'] or not (header['column_index']<=cell['column_index']
                                <header['column_index']+header['colspan']):continue
                        match=pattern.search(' '.join(header['text'].split()))
                        if match:
                            try:
                                end=_date(year=column['year'],month=match[3],day=int(match[4]))
                                start=_date(year=end.year,month=match[1],day=int(match[2]))
                                if start>end:start=start.replace(year=start.year-1)
                            except ValueError:continue
                            intervals.add((start.isoformat(),end.isoformat()))
                            evidence.append({'range_header':_cell_proof(table=table,cell=header),
                                'year_headers':[_cell_proof(table=table,cell=h) for h,_,_ in year_headers]})
        expected=(row['period_start'],row['period_end'])
        checks[row['ordinal']]={'native_period':list(expected),'visible_periods':[list(p) for p in sorted(intervals)],
            'status':'MATCH' if intervals=={expected} else 'CONFLICT' if intervals else 'UNRESOLVED',
            'headers':evidence,'source_reference':row['source_reference']}
    return checks

def native_income_reports(source,annual,concepts,*,check_visible_short_period=False,
                          namespace_policy=YEAR_ONLY, annual_period_reader=None):
    # The explicit reader lets an already selected historical filing use its
    # existing DEI implementation; it must inspect these exact source bytes.
    if annual_period_reader is None:
        from .normal_annual_input import annual_period as annual_period_reader
    need(callable(annual_period_reader),'ANNUAL_PERIOD_READER_REQUIRED')
    is_fasb_namespace('',namespace_policy=namespace_policy)  # reject unknown policies
    raw=source['raw_bytes'];ref=source['source_reference']
    need(ref['raw_asset_id']=='sha256:'+sha256_bytes(content=raw)
         and ref['accession']==annual['filing']['accessionNumber']
         and ref['company_id']==annual['company_id'],'ORIGINAL_BINDING_CHANGED')
    need(annual_period_reader(raw=raw,cik=annual['entity'],filing=annual['filing'])
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
        need(is_fasb_namespace(uri,namespace_policy=namespace_policy),'OFFICIAL_CONCEPT_REQUIRED')
        need(meta.units.get(fact['unit_ref'])=={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False},
             'NATIVE_USD_REQUIRED')
        proof=_verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=meta)
        rows.append({'concept':'us-gaap:'+name,'value':_source_value(fact,info),'unit':'USD',
            'period_start':context['period_start'],'period_end':context['period_end'],
            'decimals':info['attrs'].get('decimals'),'ordinal':fact['ordinal'],
            'context_ref':fact['context_ref'],'context':{**context,'dimensions':dict(context['dimensions'])},
            'context_proof':proof,'source_reference':ref})
    if check_visible_short_period:
        short=[row for row in rows if row['period_start']!=period['period_start']]
        visible=visible_income_periods(raw,parsed,short) if short else {}
        for row in short:row['visible_period_check']=visible[row['ordinal']]
    return rows
