"""Income facts for an explicitly selected filing, without current-year discovery.

This explicit successor reuses the current native fact and visible-column
checks. It reads no registry, latest filing, ledger, saved answer or Result, and
creates no Candidate/Run. Callers still verify source requests, amendments,
statement scope and calculation. The optional annual reader is program code
selected by the consumer, not an unchecked period supplied as an answer.
"""
import re
from decimal import Decimal
from .canonical import sha256_bytes
from .deterministic_router import parse_accession_xbrl_source
from .text_results_v2 import _ReportedFactMetadata, _verified_context
from .governance_signals import _source_value, GovernanceSignalError
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
    return _native_income_reports(source,annual,concepts,
        check_visible_short_period=check_visible_short_period,
        namespace_policy=namespace_policy,annual_period_reader=annual_period_reader)


def single_segment_revenue_reports(source,annual,concepts,*,namespace_policy=YEAR_ONLY,
                                   annual_period_reader=None):
    """Original revenue candidates with one declared operating/reportable segment.

    This is not complete-revenue admission. The caller must still prove the
    complete consolidated statement, sole top line, column and separate XML.
    All existing nondimensional readers retain their default behavior.
    """
    names={c.split(':')[-1].casefold() for c in concepts}
    names &= {'revenues','salesrevenuenet',
        'revenuefromcontractwithcustomerexcludingassessedtax',
        'revenuefromcontractwithcustomerincludingassessedtax'}
    rows=_native_income_reports(source,annual,concepts,namespace_policy=namespace_policy,
        annual_period_reader=annual_period_reader,single_segment_concepts=names)
    return [row for row in rows if 'single_segment_scope' in row]


def _single_segment_scope(parsed,meta,annual,namespace_policy):
    """Bind official current count facts and the unique declared segment member."""
    period=annual['table_input']['target_period'];entity=annual['entity']
    def current(context):
        return (str(context['entity_identifier']).isdigit()
            and str(int(context['entity_identifier']))==entity
            and context['period_start']==period['period_start']
            and context['period_end']==period['period_end'])
    counts={name:[] for name in ('NumberOfOperatingSegments','NumberOfReportableSegments')}
    count_names={name.casefold():name for name in counts}
    for fact in parsed.facts:
        info=meta.facts[fact['ordinal']];uri,name=info['concept']
        context=parsed.contexts[fact['context_ref']]
        count_name=count_names.get(name.casefold())
        if (count_name is None or not current(context) or context['dimensions']
                or context['typed_dimension_count']):continue
        if not is_fasb_namespace(uri,namespace_policy=namespace_policy):continue
        unit=meta.units.get(fact['unit_ref'])
        if (unit is None or unit['divided'] or len(unit['measures'])!=1):return None
        unit_uri,unit_name=unit['measures'][0]
        if not ((unit_uri,unit_name)==('http://www.xbrl.org/2003/instance','pure')
                or unit_name=='segment' and bool(unit_uri)):return None
        try:
            value=_source_value(fact,info)
        except GovernanceSignalError as error:
            if str(error) not in {'C03_UNSUPPORTED_TRANSFORM_NAMESPACE',
                    'C03_UNSUPPORTED_NUMERIC_TRANSFORM'}:
                raise
            # Optional segment qualification cannot assign an unsupported
            # scalar count a value. It grants no dimensional scope credit.
            return None
        if Decimal(value)!=1:return None
        proof=_verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=meta)
        counts[count_name].append({'fact':dict(fact),'namespace':uri,'value':value,
            'unit':unit,'context_proof':proof})
    if not all(counts.values()):return None
    units={tuple(row['unit']['measures'][0]) for rows in counts.values() for row in rows}
    if len(units)!=1:return None
    members=set()
    for context in parsed.contexts.values():
        if not current(context):continue
        for dimension in meta.context_proofs.get(context['context_ref'],{}).get('dimensions',[]):
            uri,name=dimension['dimension_qname']
            if name=='StatementBusinessSegmentsAxis' and is_fasb_namespace(uri,namespace_policy=namespace_policy):
                members.add(tuple(dimension['member_qname']))
    if len(members)!=1:return None
    member=next(iter(members))
    if not all(member) or member[1]!='ReportableSegmentMember':return None
    unit=next(iter(units))
    if unit[1]=='segment' and unit[0]!=member[0]:return None
    return {'status':'ONE_OPERATING_AND_REPORTABLE_SEGMENT',
        'segment_member_qname':list(member),'counts':counts}


def _native_income_reports(source,annual,concepts,*,check_visible_short_period=False,
                          namespace_policy=YEAR_ONLY,annual_period_reader=None,
                          single_segment_concepts=()):
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
    segment_scope=None;segment_scope_checked=False
    for fact in parsed.facts:
        info=meta.facts[fact['ordinal']];uri,name=info['concept']
        if name.casefold() not in names:continue
        context=parsed.contexts[fact['context_ref']]
        if (context['period_end']!=period['period_end']
                or not period['period_start']<=context['period_start']<context['period_end']
                or context['typed_dimension_count']):continue
        qualified_segment=None
        if context['dimensions']:
            if (name.casefold() not in single_segment_concepts
                    or context['period_start']!=period['period_start']
                    or len(context['dimensions'])!=1):continue
            proof=_verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=meta)
            dimension=proof['dimensions'][0];axis_uri,axis_name=dimension['dimension_qname']
            if (axis_name!='StatementBusinessSegmentsAxis'
                    or not is_fasb_namespace(axis_uri,namespace_policy=namespace_policy)
                    or dimension['member_qname'][1]!='ReportableSegmentMember'):continue
            if not segment_scope_checked:
                segment_scope=_single_segment_scope(parsed,meta,annual,namespace_policy)
                segment_scope_checked=True
            if segment_scope is None or dimension['member_qname']!=segment_scope['segment_member_qname']:continue
            qualified_segment=segment_scope
        need(str(int(context['entity_identifier']))==annual['entity'],'NATIVE_ENTITY_CHANGED')
        need(is_fasb_namespace(uri,namespace_policy=namespace_policy),'OFFICIAL_CONCEPT_REQUIRED')
        need(meta.units.get(fact['unit_ref'])=={'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False},
             'NATIVE_USD_REQUIRED')
        proof=_verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=meta)
        rows.append({'concept':'us-gaap:'+name,'value':_source_value(fact,info),'unit':'USD',
            'period_start':context['period_start'],'period_end':context['period_end'],
            'decimals':info['attrs'].get('decimals'),'ordinal':fact['ordinal'],
            'context_ref':fact['context_ref'],'context':{**context,'dimensions':dict(context['dimensions'])},
            **({'single_segment_scope':qualified_segment} if qualified_segment is not None else {}),
            'context_proof':proof,'source_reference':ref})
    if check_visible_short_period:
        short=[row for row in rows if row['period_start']!=period['period_start']]
        visible=visible_income_periods(raw,parsed,short) if short else {}
        for row in short:row['visible_period_check']=visible[row['ordinal']]
    return rows
