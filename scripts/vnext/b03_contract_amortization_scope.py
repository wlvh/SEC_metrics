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
from .text_results_v2 import _ReportedFactMetadata, _verified_context
from .xbrl_namespace_policy import YEAR_ONLY, is_fasb_namespace


class _RevenueTableIndex(_InlineTableIndex):
    """Do not give explicitly hidden, empty cells a visible column.

    Original bytes and native fact order stay intact. Nonempty cells, hidden
    facts and normal spacers retain the inherited treatment.
    """
    def __init__(self, raw):
        super().__init__(raw)
        self._pending_empty_cell = None

    @staticmethod
    def _hidden_cell(tag, attrs):
        style = dict(attrs).get('style', '') or ''
        if tag not in {'td', 'th'} or '/*' in style or '*/' in style:
            return False
        declarations = [part.strip() for part in style.split(';')]
        displays = [part for part in declarations if re.match(r'display\s*:', part, re.I)]
        # Duplicate declarations require CSS precedence interpretation. Keep
        # the cell rather than guessing that a visible spacer is hidden.
        return len(displays) == 1 and re.fullmatch(
            r'display\s*:\s*none\s*(?:!important\s*)?', displays[0], re.I) is not None

    def _flush_pending(self):
        if self._pending_empty_cell is not None:
            tag, attrs = self._pending_empty_cell
            self._pending_empty_cell = None
            super().handle_starttag(tag, attrs)

    def handle_starttag(self, tag, attrs):
        self._flush_pending()
        if self._hidden_cell(tag, attrs):
            self._pending_empty_cell = (tag, attrs)
        else:
            super().handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._pending_empty_cell is not None and not data.strip():
            return
        self._flush_pending()
        super().handle_data(data)

    def handle_entityref(self, name):
        self._flush_pending()
        super().handle_entityref(name)

    def handle_charref(self, name):
        self._flush_pending()
        super().handle_charref(name)

    def handle_endtag(self, tag):
        if self._pending_empty_cell is not None and tag == self._pending_empty_cell[0]:
            self._pending_empty_cell = None
            return
        self._flush_pending()
        super().handle_endtag(tag)

    def handle_startendtag(self, tag, attrs):
        self._flush_pending()
        if self._hidden_cell(tag, attrs):
            return
        super().handle_startendtag(tag, attrs)


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _selected_original_facts(*, parsed, metadata, roles, period, entity, namespace_policy=YEAR_ONLY):
    """Recheck the chosen Company Facts components against the annual primary."""
    checked = {}
    for role in ('depreciation', 'amortization'):
        selected = roles[role]
        values = []
        for fact in parsed.facts:
            uri, local_name = metadata.facts[fact['ordinal']]['concept']
            if (local_name != selected['source_binding']['concept'].split(':', 1)[1]
                    or not isinstance(uri, str)
                    or not is_fasb_namespace(uri,namespace_policy=namespace_policy)):
                continue
            context = parsed.contexts[fact['context_ref']]
            if (context['period_start'] != period['period_start']
                    or context['period_end'] != period['period_end']
                    or context['dimensions'] or context['typed_dimension_count']
                    or str(int(context['entity_identifier'])) != str(int(entity))):
                continue
            _need(local_name == selected['source_binding']['concept'].split(':', 1)[1]
                  and is_fasb_namespace(uri,namespace_policy=namespace_policy),
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
    def dimensions(row):
        return row.get('resolved_dimensions', row['dimensions'])
    consolidated = [row for row in amounts if set(dimensions(row)) ==
                    {'srt:ProductOrServiceAxis'}]
    if len(consolidated) != 1:
        return None
    base = consolidated[0]
    product = dimensions(base)['srt:ProductOrServiceAxis']
    segments = []
    totals = []
    for row in amounts:
        if row is base:
            continue
        resolved = dimensions(row)
        if (set(resolved) == {'srt:ProductOrServiceAxis', 'srt:ConsolidationItemsAxis'}
                and resolved['srt:ProductOrServiceAxis'] == product
                and resolved['srt:ConsolidationItemsAxis'] == 'us-gaap:OperatingSegmentsMember'):
            totals.append(row)
            continue
        if (set(resolved) != {'srt:ProductOrServiceAxis',
                'srt:ConsolidationItemsAxis',
                'us-gaap:StatementBusinessSegmentsAxis'}
                or resolved['srt:ProductOrServiceAxis'] != product
                or resolved['srt:ConsolidationItemsAxis'] !=
                    'us-gaap:OperatingSegmentsMember'):
            return None
        segments.append(row)
    members = [dimensions(row)['us-gaap:StatementBusinessSegmentsAxis']
               for row in segments]
    if (len(members) != len(set(members))
            or sum(Decimal(row['value_usd']) for row in segments) >
                Decimal(base['value_usd'])):
        return None
    # An operating-segments total overlaps the individual segments. Verify
    # that relationship without adding it a second time or treating it as
    # the consolidated amount (which can differ).
    if totals and (len(totals) != 1 or not segments
            or Decimal(totals[0]['value_usd']) !=
                sum(Decimal(row['value_usd']) for row in segments)):
        return None
    index = _RevenueTableIndex(raw)
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
                               else 'OPERATING_SEGMENTS_TOTAL_REVENUE_DEDUCTION' if amount in totals
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


def _unreconciled_contract_amortization(*, case, data_root, namespace_policy=YEAR_ONLY):
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
        uri, concept = metadata.facts[fact['ordinal']]['concept']
        if concept != 'CapitalizedContractCostAmortization':
            continue
        context = parsed.contexts[fact['context_ref']]
        if (context['period_start'] != period['period_start']
                or context['period_end'] != period['period_end']
                or context['typed_dimension_count']
                or str(int(context['entity_identifier'])) !=
                   str(int(bindings[0]['entity']))):
            continue
        if (concept != 'CapitalizedContractCostAmortization'
                or not is_fasb_namespace(uri,namespace_policy=namespace_policy)
                or metadata.units.get(fact['unit_ref']) != {
                    'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')],
                    'divided': False}):
            continue
        amount = Decimal(str(_numeric_xbrl_value(
            text=fact['text'], scale=fact['scale'], sign=fact['sign'])))
        if amount > 0:
            context_proof = _verified_context(native={**context,'dimensions':dict(context['dimensions'])},metadata=metadata)
            def name(qname):
                uri, local = qname
                for taxonomy in ('us-gaap','srt'):
                    if is_fasb_namespace(uri,taxonomy=taxonomy,namespace_policy=namespace_policy):
                        return taxonomy+':'+local
                return '{'+uri+'}'+local
            amounts.append({'ordinal': fact['ordinal'],
                'context_ref': fact['context_ref'],
                'dimensions': dict(context['dimensions']),
                'resolved_dimensions':{name(d['dimension_qname']):name(d['member_qname']) for d in context_proof['dimensions']},
                'value_usd': str(amount)})
    if not amounts:
        return None
    selected_originals = _selected_original_facts(parsed=parsed,
        metadata=metadata, roles=roles, period=period, entity=bindings[0]['entity'],namespace_policy=namespace_policy)
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


def assess_current_b03_scope(*, case, data_root, namespace_policy=YEAR_ONLY):
    """Keep V13's direct-fact checks; extend only the V14 current path."""
    inherited = assess_direct_depreciation_scope(case=case, data_root=data_root,namespace_policy=namespace_policy)
    if inherited['blocked'] or inherited['status'] != 'NO_DIRECT_DEPRECIATION_SELECTION':
        return inherited
    return _unreconciled_contract_amortization(
        case=case, data_root=data_root,namespace_policy=namespace_policy) or inherited
