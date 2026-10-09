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
UNIT_HEADER = (r"\(?(?:dollars in )?(?:millions|thousands)(?:, except (?:per share|per-share) data)?\)?",)

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
        intervals, duration_headers = _annual_interval(table=table, column=column)
        _need({(p['period_start'],p['period_end']) for p in intervals}
              == {(total['period_start'],total['period_end'])}, 'VISIBLE_DURATION_UNRESOLVED')
        unit_headers = [c for r in table['rows'][:column['row_index']+1] for c in r['cells']
                        if c['is_origin'] and any(re.fullmatch(pattern, c['text'].strip(), re.I)
                                                  for pattern in UNIT_HEADER)]
        scales = {6 if 'million' in c['text'].casefold() else 3 for c in unit_headers}
        _need(len(scales)==1, 'VISIBLE_UNIT_UNRESOLVED')
        visible_scale = next(iter(scales))
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
            'total':total, 'parts':parts, 'total_cell':_cell_proof(table=table, cell=cell),
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
