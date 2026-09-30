"""Explicit V14 B03 treatment of separately reported contract amortization.

The historical B03 Spec and V13 source check retain their original bytes.
Contract-cost amortization can be excluded from the composed D&A role only
when its original income-statement row is proved to reduce gross revenue.
An unproved relation still blocks current credit; no amount is added back.
"""
from decimal import Decimal
from pathlib import Path
import re

from .b03_depreciation_scope import assess_direct_depreciation_scope
from .canonical import sha256_bytes
from .constraints import parse_numeric_claim
from .deterministic_router import _numeric_xbrl_value, parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex, _fact_cells
from .b06_disclosure import label as row_label
from .sources import resolve_repository_file
from .text_results_v2 import _ReportedFactMetadata


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _selected_original_facts(*, parsed, metadata, roles, period, entity):
    """Recheck the chosen Company Facts components against the annual primary."""
    checked = {}
    for role in ('depreciation', 'amortization'):
        selected = roles[role]
        values = []
        for fact in parsed.facts:
            if fact['qualified_name'] != selected['source_binding']['concept']:
                continue
            context = parsed.contexts[fact['context_ref']]
            if (context['period_start'] != period['period_start']
                    or context['period_end'] != period['period_end']
                    or context['dimensions'] or context['typed_dimension_count']
                    or str(int(context['entity_identifier'])) != str(int(entity))):
                continue
            uri, local_name = metadata.facts[fact['ordinal']]['concept']
            _need(local_name == selected['source_binding']['concept'].split(':', 1)[1]
                  and re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}', uri),
                  'B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NAMESPACE_MISMATCH:' + role)
            if metadata.units.get(fact['unit_ref']) != {
                    'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')],
                    'divided': False}:
                continue
            values.append((fact['ordinal'], str(_numeric_xbrl_value(
                text=fact['text'], scale=fact['scale'], sign=fact['sign']))))
        _need(values and {value for _, value in values} == {str(selected['value'])},
              'B03_CONTRACT_SCOPE_SELECTED_COMPONENT_NOT_IN_ORIGINAL:' + role)
        checked[role] = {'concept': selected['source_binding']['concept'],
                         'value_usd': str(selected['value']),
                         'primary_fact_ordinals': [ordinal for ordinal, _ in values]}
    return checked


def _visible_revenue_deductions(*, raw, parsed, amounts, period):
    """Prove each separate amortization line is a gross-to-net revenue deduction."""
    consolidated = [row for row in amounts if set(row['dimensions']) ==
                    {'srt:ProductOrServiceAxis'}]
    if len(consolidated) != 1:
        return None
    base = consolidated[0]
    product = base['dimensions']['srt:ProductOrServiceAxis']
    segments = []
    for row in amounts:
        if row is base:
            continue
        dimensions = row['dimensions']
        if (set(dimensions) != {'srt:ProductOrServiceAxis',
                'srt:ConsolidationItemsAxis',
                'us-gaap:StatementBusinessSegmentsAxis'}
                or dimensions['srt:ProductOrServiceAxis'] != product
                or dimensions['srt:ConsolidationItemsAxis'] !=
                    'us-gaap:OperatingSegmentsMember'):
            return None
        segments.append(row)
    members = [row['dimensions']['us-gaap:StatementBusinessSegmentsAxis']
               for row in segments]
    if (len(members) != len(set(members))
            or sum(Decimal(row['value_usd']) for row in segments) >
                Decimal(base['value_usd'])):
        return None
    index = _InlineTableIndex(raw)
    index.feed(raw.decode('utf-8-sig'))
    index.close()
    mapped = _fact_cells(index, parsed, {row['ordinal'] for row in amounts})
    proofs = []
    for amount in amounts:
        pair = mapped.get(amount['ordinal'])
        if pair is None:
            return None
        table, cell = pair
        rows = table['rows']
        line = cell['origin_row_index']
        if not (0 < line < len(rows) - 1):
            return None
        gross, deduction, net = rows[line-1:line+2]
        if not (re.fullmatch(r'Gross\b.*\brevenues?', row_label(gross), re.I)
                and re.fullmatch(r'Contract\b.*\bamortization',
                                 row_label(deduction), re.I)
                and re.fullmatch(r'Net\b.*\brevenues?', row_label(net), re.I)):
            return None
        if amount is base and not any(
                row_label(row).strip().casefold() == 'revenues'
                for row in rows[:line]):
            return None
        column = cell['column_index']
        if not any(c['is_origin'] and c['text'].strip() ==
                   period['period_end'][:4]
                   and c['column_index'] <= column <
                       c['column_index'] + c['colspan']
                   for row in rows[:line] for c in row['cells']):
            return None
        def displayed(row):
            # The original numeric fact spans the amount plus an adjacent
            # display cell. Some tables put a dollar marker in that cell.
            cells = [c for c in row['cells'] if c['is_origin']
                and column <= c['column_index'] <
                    column + cell['colspan'] + 1]
            if not cells:
                return None
            text = ''.join(c['text'] for c in cells).replace('$', '').strip()
            return parse_numeric_claim(raw_value=text,
                                       reported_unit='USD')
        gross_value, deduction_value, net_value = (
            displayed(row) for row in (gross, deduction, net))
        fact = parsed.facts[amount['ordinal']-1]
        scale = Decimal(10) ** int(fact['scale'] or '0')
        if (None in (gross_value, deduction_value, net_value)
                or deduction_value >= 0
                or -deduction_value * scale != Decimal(amount['value_usd'])
                or gross_value + deduction_value != net_value):
            return None
        proofs.append({'fact_ordinal': amount['ordinal'],
            'relation_class': ('CONSOLIDATED_REVENUE_DEDUCTION' if amount is base
                               else 'OPERATING_SEGMENT_REVENUE_DEDUCTION'),
            'dimensions': amount['dimensions'],
            'table_id': table['table_id'],
            'table_grid_sha256': table['grid_sha256'],
            'gross_row': gross['row_index'],
            'deduction_row': deduction['row_index'],
            'net_row': net['row_index'],
            'reported_labels': [row_label(row) for row in
                                (gross, deduction, net)],
            'displayed_amounts': [str(value) for value in
                                  (gross_value, deduction_value, net_value)]})
    return proofs


def _unreconciled_contract_amortization(*, case, data_root):
    selected = [row for row in case['observations'] if row['metric_id'] == 'B03'
                and row['semantic_role'] in {'depreciation', 'amortization'}]
    if not selected:
        return None
    roles = {row['semantic_role']: row for row in selected}
    _need(len(selected) == 2 and set(roles) == {'depreciation', 'amortization'}
          and roles['depreciation']['source_binding']['concept'] == 'us-gaap:Depreciation'
          and roles['amortization']['source_binding']['concept'] ==
              'us-gaap:AmortizationOfIntangibleAssets',
          'B03_CONTRACT_SCOPE_COMPOSED_SELECTION_CHANGED')
    bindings = [row['source_binding'] for row in selected]
    _need(bindings[0]['accession'] == bindings[1]['accession']
          and bindings[0]['entity'] == bindings[1]['entity'],
          'B03_CONTRACT_SCOPE_COMPOSED_SOURCE_MISMATCH')
    period = case['target_period']
    _need(all(row['period_start'] == period['period_start']
              and row['period_end'] == period['period_end'] for row in selected),
          'B03_CONTRACT_SCOPE_COMPOSED_PERIOD_CHANGED')
    primary = [proof for proof in case['source_proofs']
        if proof.get('accession') == bindings[0]['accession']
        and proof.get('document_name', '').lower().endswith(('.htm', '.html'))]
    _need(len(primary) == 1, 'B03_CONTRACT_SCOPE_PRIMARY_NOT_UNIQUE')
    proof = primary[0]
    raw = resolve_repository_file(repo_root=Path(data_root),
        repo_relative_path=proof['request_repo_relative_path']).read_bytes()
    _need(sha256_bytes(content=raw) == proof['content_sha256'],
          'B03_CONTRACT_SCOPE_PRIMARY_BYTES_CHANGED')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    metadata = _ReportedFactMetadata()
    metadata.feed(raw.decode('utf-8-sig'))
    metadata.close()
    _need(metadata.ordinal == len(parsed.facts),
          'B03_CONTRACT_SCOPE_NATIVE_STREAM_CHANGED')
    amounts = []
    for fact in parsed.facts:
        if fact['qualified_name'] != 'us-gaap:CapitalizedContractCostAmortization':
            continue
        context = parsed.contexts[fact['context_ref']]
        if (context['period_start'] != period['period_start']
                or context['period_end'] != period['period_end']
                or context['typed_dimension_count']
                or str(int(context['entity_identifier'])) !=
                   str(int(bindings[0]['entity']))):
            continue
        uri, concept = metadata.facts[fact['ordinal']]['concept']
        if (concept != 'CapitalizedContractCostAmortization'
                or not re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}', uri)
                or metadata.units.get(fact['unit_ref']) != {
                    'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')],
                    'divided': False}):
            continue
        amount = Decimal(str(_numeric_xbrl_value(
            text=fact['text'], scale=fact['scale'], sign=fact['sign'])))
        if amount > 0:
            amounts.append({'ordinal': fact['ordinal'],
                'context_ref': fact['context_ref'],
                'dimensions': dict(context['dimensions']),
                'value_usd': str(amount)})
    if not amounts:
        return None
    selected_originals = _selected_original_facts(parsed=parsed,
        metadata=metadata, roles=roles, period=period, entity=bindings[0]['entity'])
    revenue_deductions = _visible_revenue_deductions(raw=raw, parsed=parsed,
        amounts=amounts, period=period)
    if revenue_deductions is not None:
        return {'status': 'COMPOSED_DA_CONTRACT_REVENUE_DEDUCTION_EXCLUDED',
            'blocked': False, 'primary_source_sha256': proof['content_sha256'],
            'selected_components': {role: roles[role]['value']
                for role in ('depreciation', 'amortization')},
            'selected_original_facts': selected_originals,
            'excluded_facts': amounts,
            'revenue_deduction_proofs': revenue_deductions,
            'amount_added_or_result_recomputed': False}
    return {'status': 'COMPOSED_DA_ADDITIONAL_AMORTIZATION_UNRECONCILED',
        'blocked': True, 'primary_source_sha256': proof['content_sha256'],
        'selected_components': {role: roles[role]['value']
                                for role in ('depreciation', 'amortization')},
        'additional_fact_concept': 'us-gaap:CapitalizedContractCostAmortization',
        'additional_facts': amounts,
        'selected_original_facts': selected_originals,
        'revenue_deduction_proofs': [],
        'amount_added_or_result_recomputed': False}


def assess_current_b03_scope(*, case, data_root):
    """Keep V13's direct-fact checks; extend only the V14 current path."""
    inherited = assess_direct_depreciation_scope(case=case, data_root=data_root)
    if inherited['blocked'] or inherited['status'] != 'NO_DIRECT_DEPRECIATION_SELECTION':
        return inherited
    return _unreconciled_contract_amortization(
        case=case, data_root=data_root) or inherited
