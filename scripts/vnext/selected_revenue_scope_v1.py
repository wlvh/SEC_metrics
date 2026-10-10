"""Explicit revenue-component admission from the selected income statement.

A same-period, same-entity native amount can still be a component. This narrow
successor recognizes an explicitly reported total and its contiguous revenue
parts in a full income statement. It never changes a Spec's concept priority,
adds parts as a calculated revenue, or substitutes a later comparative filing.
No demonstrated split means no new complete-scope credit and no changed choice.
"""
from decimal import Decimal
import re

from .canonical import content_hash
from .selected_income_source_v1 import native_income_reports, IncomeSourceError
from .xbrl_namespace_policy import YEAR_ONLY

EXTRA_REVENUE_CONCEPTS = (
    'us-gaap:RevenueFromCollaborativeArrangementExcludingRevenueFromContractWithCustomer',
    'us-gaap:RoyaltyRevenue', 'us-gaap:Revenues',
)
UNIT_HEADER = (r"\(?(?:dollars in |in )?(?:millions|thousands)(?:, except (?:per share|per-share) data)?\)?",)

STATEMENT_CONCEPTS = ('us-gaap:NetIncomeLoss', 'us-gaap:ProfitLoss',
                      'us-gaap:CostOfRevenue', 'us-gaap:CostOfGoodsAndServicesSold')


def _need(condition, reason):
    if not condition:
        raise IncomeSourceError('SELECTED_REVENUE_' + reason)


def _label(table, cell):
    cells = table['rows'][cell['row_index']]['cells']
    return ' '.join(c['text'] for c in cells if c['is_origin']
                    and c['column_index'] < cell['column_index']
                    and not re.fullmatch(r'[\s$()\d,.−–—-]*', c['text']))


def _label_key(text):
    return re.sub(r'\s+', ' ', re.sub(r'\([a-z0-9]+\)', '', text.casefold())).strip()


def _statement_scope(raw, index, parsed, table, *, adjacent_heading=False):
    """Bind the actual consolidated statement title and unassigned prose.

    An unfamiliar local scope statement is unresolved, not silently ignored.
    Native data rows and mechanically proven headers remain handled elsewhere.
    """
    from .composite_scope import index_source_structure
    from .financial_duration import _cell_proof
    structure = index_source_structure(source_bytes=raw)
    span = structure['tables'][table['order']]
    previous = max((t['end_byte'] for t in structure['tables']
                    if t['end_byte'] <= span['start_byte']), default=0)
    intro = [b for b in structure['blocks'] if not b['inside_table']
             and previous <= b['start_byte'] < b['end_byte'] <= span['start_byte']]
    heading_span = None
    if adjacent_heading and not intro:
        # Some filings put the statement title and units in a separate layout
        # table immediately before the amount table. Retain those exact spans;
        # never cross a monetary/native-fact table to borrow another title.
        heading = next((t for t in structure['tables'] if t['end_byte']==previous),None)
        if heading is not None:
            builder = index.tables[heading['table_order']]
            if not any(index.cell_ordinals.get(id(c)) for row in builder.rows for c in row):
                intro = [b for b in structure['blocks']
                         if heading['start_byte'] <= b['start_byte'] < b['end_byte'] <= heading['end_byte']]
                from .financial_structured import _expanded_table, RESOURCE_LIMITS
                heading_grid,_ = _expanded_table(builder=builder,
                    remaining_total_cells=RESOURCE_LIMITS.max_total_cells,
                    remaining_expanded_text_chars=RESOURCE_LIMITS.max_expanded_text_chars)
                all_text=''.join(c['text'] for row in heading_grid['rows'] for c in row['cells'] if c['is_origin'])
                covered=''.join(b['visible_text'] for b in intro)
                _need(re.sub(r'\s+','',all_text)==re.sub(r'\s+','',covered),
                      'STATEMENT_HEADING_TEXT_COVERAGE_UNRESOLVED')
                heading_span = heading
    title_pattern = r'consolidated statements? of (?:income|operations|earnings)'
    titles = [b for b in intro if re.fullmatch(title_pattern, _label_key(b['visible_text']))]
    caption = table.get('caption', '').strip()
    _need(not caption or re.fullmatch(title_pattern, _label_key(caption)), 'STATEMENT_CAPTION_SCOPE_UNRESOLVED')
    _need(bool(titles) or bool(caption), 'CONSOLIDATED_STATEMENT_TITLE_UNPROVEN')
    def company_key(text):
        return re.sub(r'[^a-z0-9]', '', text.casefold())
    registrants = {company_key(f['text']) for f in parsed.facts
                   if f['qualified_name'].split(':')[-1].casefold()=='entityregistrantname'}
    issuer_lines = {name+suffix for name in registrants
                    for suffix in ('','andsubsidiaries','andsubsidiarycompanies')}
    navigation = []
    if adjacent_heading:
        # Pagination and the previous statement's standard note reference may
        # precede this title. Preserve their spans, without allowing arbitrary
        # pre-title scope prose or a note after the title to disappear.
        navigation = [b for b in intro if titles and b['end_byte'] <= titles[-1]['start_byte']
                      and re.fullmatch(r'(?:[0-9]+|table of contents|see accompanying notes\.)',
                                       b['visible_text'].strip(), re.I)]
        _need(all(b in navigation or company_key(b['visible_text']) in issuer_lines
                  or re.fullmatch(title_pattern,_label_key(b['visible_text']))
                  or any(re.fullmatch(p,b['visible_text'].strip(),re.I) for p in UNIT_HEADER)
                  for b in intro), 'STATEMENT_HEADING_SCOPE_UNRESOLVED')
    after_title = [b for b in intro if titles and b['start_byte'] >= titles[-1]['end_byte']]
    _need(all(company_key(b['visible_text']) in issuer_lines
              or adjacent_heading and any(re.fullmatch(p,b['visible_text'].strip(),re.I) for p in UNIT_HEADER)
              for b in after_title),
          'STATEMENT_INTRODUCTION_SCOPE_UNRESOLVED')
    # Capture every nonempty explanatory row, not just a cancellation keyword.
    # An annotation without native data is not given a financial meaning by
    # the native context of a different row in the same table.
    builder = index.tables[table['order']]
    native_rows = {n for n, row in enumerate(builder.rows)
                   if any(index.cell_ordinals.get(id(c)) for c in row)}
    # A native amount authenticates its number, not every assertion sharing
    # its row. Direct limitations to operations/subsidiaries/segments remain
    # unresolved regardless of whether another cell has an XBRL amount.
    for row in table['rows']:
        for c in row['cells']:
            text = c['text'] if c['is_origin'] else ''
            if (re.search(r'\b(?:excludes?|excluded|excluding|only|limited to)\b', text, re.I)
                    and re.search(r'\b(?:operations?|subsidiar(?:y|ies)|segments?|businesses)\b', text, re.I)):
                _need(False, 'STATEMENT_LOCAL_SCOPE_UNRESOLVED:'+table['table_id']
                      +':row='+str(c['row_index'])+':column='+str(c['column_index']))
    unknown = []
    for row in table['rows']:
        if row['row_index'] in native_rows:
            continue
        cells = [c for c in row['cells'] if c['is_origin'] and c['text'].strip()]
        for c in cells:
            text = _label_key(c['text'])
            from .financial_duration import _DATE
            header = (re.fullmatch(r'[0-9]{4}', text)
                      or adjacent_heading and _DATE.fullmatch(text)
                      or re.fullmatch(r'(?:for the )?years? ended [a-z]+ [0-9]{1,2},?', text)
                      or adjacent_heading and re.fullmatch(r'(?:for the )?fiscal years? ended [a-z]+ [0-9]{1,2},?', text)
                      or adjacent_heading and re.fullmatch(r'[0-9]+',text) and any(
                          re.fullmatch(r'(?:for the )?(?:fiscal )?years? ended [a-z]+ [0-9]{1,2},?',
                                       _label_key(other['text'])) for other in cells)
                      or any(re.fullmatch(p, text) for p in UNIT_HEADER)
                      or re.fullmatch(title_pattern, text)
                      or re.fullmatch(r'(?:revenues|costs and expenses|earnings per (?:common )?share[–— -]*(?:basic|diluted)):', text)
                      or adjacent_heading and re.fullmatch(r'(?:cost of revenues|operating expenses)\s*:', text))
            if not header:
                unknown.append(_cell_proof(table=table, cell=c))
    _need(not unknown, 'STATEMENT_LOCAL_SCOPE_UNRESOLVED')
    proof = {'title_sources':titles[-1:] if titles else [], 'caption':caption,
            'table_span':span, 'intervening_sources':intro,
            'unresolved_annotations':unknown}
    if adjacent_heading:
        proof['adjacent_heading_table']=heading_span
        if navigation:
            proof['preceding_navigation_sources']=navigation
    return proof


def _key(row):
    return (row['concept'].casefold(), row['period_start'], row['period_end'],
            Decimal(row['value']))


def selected_revenue_scope(*, primary, annual, approved_concepts, xml=None,
                           namespace_policy=YEAR_ONLY, annual_period_reader=None):
    """Return source-bound splits; absence is not proof of complete revenue."""
    from .financial_structured import _InlineTableIndex, _fact_cells
    from .financial_duration import _cell_proof, _column_period, _annual_interval
    from .deterministic_router import parse_accession_xbrl_source
    concepts = sorted(set(approved_concepts) | set(EXTRA_REVENUE_CONCEPTS)
                      | set(STATEMENT_CONCEPTS))
    options = {'namespace_policy':namespace_policy, 'annual_period_reader':annual_period_reader}
    reports = {'primary':native_income_reports(primary, annual, concepts, **options)}
    if xml is not None:
        reports['xml'] = native_income_reports(xml, annual, concepts, **options)
    raw = primary['raw_bytes']
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    index = _InlineTableIndex(raw); index.feed(raw.decode('utf-8-sig')); index.close()
    bound = _fact_cells(index, parsed, {r['ordinal'] for r in reports['primary']})
    rows = reports['primary']; splits = []
    approved = {c.casefold() for c in approved_concepts}
    for total in rows:
        if total['concept'].casefold() not in approved or total['ordinal'] not in bound:
            continue
        table, cell = bound[total['ordinal']]
        if _label_key(_label(table, cell)) not in {'total revenues', 'total net revenues', 'total revenue'}:
            continue
        # A dimensional/other-subject fact was excluded by the native reader.
        # Also require this table to contain native full-statement income and
        # costs, after the reported revenue block, in the identical context.
        same = [r for r in rows if r['context_ref'] == total['context_ref']
                and r['ordinal'] in bound and bound[r['ordinal']][0]['table_id'] == table['table_id']]
        later = [r['concept'].casefold() for r in same
                 if bound[r['ordinal']][1]['row_index'] > cell['row_index']]
        if not (any(c in later for c in ('us-gaap:netincomeloss', 'us-gaap:profitloss'))
                and any(c in later for c in ('us-gaap:costofrevenue', 'us-gaap:costofgoodsandservicessold'))):
            continue
        column, headers, reason = _column_period(table=table, selected=cell, extra_header_descriptors=UNIT_HEADER)
        _need(not reason and column['year'] == int(total['period_end'][:4]), 'VISIBLE_YEAR_UNRESOLVED')
        # Keep the whole visible year-column group (e.g. separate $ and amount
        # cells), rather than assuming equal numeric column indices.
        year_group = {(h['origin_row_index'], h['origin_column_index']) for h, _, _ in headers}
        parts = []
        for row_index in range(cell['row_index']-1, -1, -1):
            candidates = [r for r in same if bound[r['ordinal']][1]['row_index'] == row_index]
            if not candidates:
                # Only blank rows may be crossed. A caption or section boundary
                # must not silently combine unrelated revenue sections.
                if any(c['is_origin'] and c['text'].strip() for c in table['rows'][row_index]['cells']):
                    break
                continue
            matches = []
            for r in candidates:
                part_cell = bound[r['ordinal']][1]
                pc, ph, why = _column_period(table=table, selected=part_cell, extra_header_descriptors=UNIT_HEADER)
                if why or pc['year'] != column['year']:
                    continue
                if {(h['origin_row_index'], h['origin_column_index']) for h, _, _ in ph} != year_group:
                    continue
                label = _label_key(_label(table, part_cell))
                if ('revenue' in label and 'total' not in label
                        and 'revenue' in r['concept'].casefold()):
                    matches.append(r)
            if len(matches) != 1:
                break
            parts.insert(0, matches[0])
        if len(parts) < 2:
            if parts:
                _need(Decimal(parts[0]['value']) == Decimal(total['value']), 'INCOMPLETE_REVENUE_BLOCK')
            continue
        intervals, duration_headers = _annual_interval(table=table, column=column)
        _need({(p['period_start'],p['period_end']) for p in intervals}
              == {(total['period_start'],total['period_end'])}, 'VISIBLE_DURATION_UNRESOLVED')
        statement_scope = _statement_scope(raw, index, parsed, table)
        unit_headers = [c for r in table['rows'][:column['row_index']+1] for c in r['cells']
                        if c['is_origin'] and any(re.fullmatch(pattern, c['text'].strip(), re.I)
                                                  for pattern in UNIT_HEADER)]
        scales = {6 if 'million' in c['text'].casefold() else 3 for c in unit_headers}
        _need(len(scales)==1, 'VISIBLE_UNIT_UNRESOLVED')
        visible_scale = next(iter(scales))
        _need(len({_key(p) for p in parts}) == len(parts), 'COMPONENT_REUSED')
        # Existing reported decimals bound rounding; no missing balancing item
        # is invented, and no larger native number is treated as the answer.
        amounts = [*parts, total]
        native_by_ordinal = {f['ordinal']:f for f in parsed.facts}
        _need(all(int(native_by_ordinal[r['ordinal']]['scale'] or 0) == visible_scale
                  for r in amounts), 'VISIBLE_NATIVE_SCALE_CONFLICT')
        for r in amounts:
            d = r['decimals']
            _need(d == 'INF' or isinstance(d, str) and d.lstrip('-').isdigit(), 'PRECISION_UNKNOWN')
        radius = sum((Decimal(0) if r['decimals']=='INF' else Decimal(10)**(-int(r['decimals']))/2)
                     for r in amounts)
        difference = sum(Decimal(p['value']) for p in parts) - Decimal(total['value'])
        _need(abs(difference) <= radius, 'COMPONENT_TOTAL_CONFLICT')
        xml_matches = []
        for r in amounts if xml is not None else []:
            matches = [x for x in reports['xml'] if _key(x) == _key(r)]
            _need(bool(matches), 'PRIMARY_XML_COMPONENT_OR_TOTAL_DIFFERS')
            xml_matches.append({'primary_ordinal':r['ordinal'], 'xml_reports':matches})
        splits.append({'table_id':table['table_id'], 'source_reference':primary['source_reference'],
            'total':total, 'parts':parts, 'statement_scope':statement_scope, 'total_cell':_cell_proof(table=table, cell=cell),
            'part_cells':[_cell_proof(table=table, cell=bound[p['ordinal']][1]) for p in parts],
            'labels':{'total':_label(table, cell), 'parts':[_label(table, bound[p['ordinal']][1]) for p in parts]},
            'year_headers':[_cell_proof(table=table, cell=h) for h, _, _ in headers],
            'duration_headers':duration_headers,
            'unit_headers':[_cell_proof(table=table, cell=h) for h in unit_headers],
            'visible_scale':visible_scale,
            'xml_matches':xml_matches, 'xml_check':'MATCH' if xml is not None else 'NOT_SUPPLIED', 'sum_difference':str(difference), 'rounding_radius':str(radius)})
    # Multiple income tables must agree on what each component is part of.
    totals = {_key(s['total']) for s in splits}
    _need(len(totals) <= 1, 'STATEMENT_TOTAL_CONFLICT')
    body = {'method':'SELECTED_REVENUE_COMPONENT_ADMISSION_V1',
            'annual_input':annual, 'approved_concepts':list(approved_concepts), 'splits':splits,
            'status':'REPORTED_COMPONENTS_AND_TOTAL' if splits else 'NO_DEMONSTRATED_SPLIT',
            'complete_scope_proven':bool(splits),
            'original_reports':reports}
    return {**body, 'scope_id':content_hash(value=body)}


def admit_revenue_facts(*, facts, scope):
    """Filter existing facts before Calculator; retain their original identity."""
    if not scope['splits']:
        return list(facts)
    annual = scope['annual_input']; approved = {c.casefold() for c in scope['approved_concepts']}
    allowed = {_key(s['total']) for s in scope['splits']}
    eligible = []
    for fact in facts:
        is_target = (fact['concept'].casefold() in approved
                     and (fact['period_start'],fact['period_end']) in {(k[1],k[2]) for k in allowed})
        if is_target:
            _need(fact['unit'] == 'USD', 'COMPANYFACTS_UNIT_DIFFERS')
            if (fact['entity'] != annual['entity']
                    or fact['accession'] != annual['filing']['accessionNumber']
                    or _key(fact) not in allowed):
                continue
        eligible.append(fact)
    _need(any(_key(f) in allowed and f['entity']==annual['entity']
              and f['accession']==annual['filing']['accessionNumber'] for f in eligible),
          'REPORTED_TOTAL_NOT_IN_COMPANYFACTS')
    return eligible


def verify_revenue_observations(*, observations, scope):
    if not scope['splits']:
        return
    allowed = {_key(s['total']) for s in scope['splits']}
    for observation in observations:
        if observation['semantic_role'] == 'revenue':
            row = {**observation, 'concept':observation['source_binding']['concept']}
            _need(_key(row) in allowed, 'SELECTED_COMPONENT_NOT_TOTAL')
