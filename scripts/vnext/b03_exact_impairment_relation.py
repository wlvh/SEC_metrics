"""Prove an exact impairment-depreciation split in a saved B03 primary.

This is a source proof, not a replacement MetricResult or an enabled Run route.
The current B03 result stays withheld until an explicit successor consumes the
proof through an approved Spec and the native result/replay chain.
"""
from decimal import Decimal
from pathlib import Path
import re

from .b03_depreciation_scope import assess_direct_depreciation_scope
from .canonical import content_hash, sha256_bytes
from .deterministic_router import _numeric_xbrl_value, parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex, _fact_cells
from .sources import resolve_repository_file


_DEPRECIATION_ROW = re.compile(
    r'\bdepreciation\b.{0,60}\bamortization\b', re.I)
_IMPAIRMENT_COMPONENT = re.compile(
    r'\basset impairment\b.{0,160}\bincluding depreciation of\s*\$?\s*'
    r'(?P<amount>[0-9][0-9,]*)', re.I)


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def prove_exact_impairment_relation(*, case, data_root):
    """Return only an exact, same-context source relation; never grant credit.

    The selected D&A total must already have the original segment-table
    impairment-inclusion proof. A separate cash-flow table must identify its
    depreciation-and-amortization line and explicitly tag the impairment's
    depreciation component inside the impairment line. Same-context values
    must satisfy selected D&A = ordinary D&A + impairment depreciation.
    """
    scoped = assess_direct_depreciation_scope(case=case, data_root=data_root)
    _need(scoped['status'] == 'SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT'
          and scoped['blocked'], 'B03_EXACT_SELECTED_IMPAIRMENT_NOT_PROVEN')
    inclusion = scoped['impairment_inclusion_proof']
    selected = inclusion['selected_fact']
    da_observations = [row for row in case['observations']
        if row['semantic_role'] == 'depreciation_and_amortization']
    _need(len(da_observations) == 1,
          'B03_EXACT_SELECTED_OBSERVATION_NOT_UNIQUE')
    accession = da_observations[0]['source_binding']['accession']
    proofs = [proof for proof in case['source_proofs']
        if proof.get('content_sha256') == scoped['primary_source_sha256']
        and proof.get('accession') == accession
        and proof.get('document_name', '').lower().endswith(('.htm', '.html'))]
    _need(len(proofs) == 1, 'B03_EXACT_PRIMARY_SOURCE_NOT_UNIQUE')
    proof = proofs[0]
    raw = resolve_repository_file(repo_root=Path(data_root),
        repo_relative_path=proof['request_repo_relative_path']).read_bytes()
    _need(sha256_bytes(content=raw) == proof['content_sha256'],
          'B03_EXACT_PRIMARY_BYTES_CHANGED')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    by_ordinal = {fact['ordinal']: fact for fact in parsed.facts}
    original = by_ordinal.get(selected['ordinal'])
    _need(original is not None and
          original['qualified_name'] == selected['concept'],
          'B03_EXACT_SELECTED_INLINE_FACT_CHANGED')
    context = parsed.contexts[original['context_ref']]
    period = case['target_period']
    _need(context['period_start'] == period['period_start']
          and context['period_end'] == period['period_end']
          and not context['dimensions'] and not context['typed_dimension_count']
          and original['unit_ref'].casefold() == 'usd',
          'B03_EXACT_SELECTED_CONTEXT_CHANGED')

    names = {
        'ordinary': 'us-gaap:Depreciation',
        'impairment': 'us-gaap:ProductionRelatedImpairmentsOrCharges',
    }
    matched = {}
    for role, concept in names.items():
        rows = [fact for fact in parsed.facts
            if fact['qualified_name'] == concept
            and fact['context_ref'] == original['context_ref']
            and fact['unit_ref'] == original['unit_ref']]
        _need(len(rows) == 1, 'B03_EXACT_COMPONENT_NOT_UNIQUE:' + role)
        matched[role] = rows[0]

    def amount(fact):
        return Decimal(str(_numeric_xbrl_value(text=fact['text'],
            scale=fact['scale'], sign=fact['sign'])))

    total = amount(original)
    ordinary = amount(matched['ordinary'])
    impairment = amount(matched['impairment'])
    _need(total > 0 and ordinary > 0 and impairment > 0
          and total == ordinary + impairment
          and total == Decimal(selected['value']),
          'B03_EXACT_COMPONENT_ARITHMETIC_FAILED')

    index = _InlineTableIndex(raw)
    index.feed(raw.decode('utf-8'))
    index.close()
    cells = _fact_cells(index, parsed,
        {matched['ordinary']['ordinal'], matched['impairment']['ordinal']})
    _need(len(cells) == 2, 'B03_EXACT_COMPONENT_NOT_VISIBLE_IN_TABLE')
    ordinary_table, ordinary_cell = cells[matched['ordinary']['ordinal']]
    impairment_table, impairment_cell = cells[matched['impairment']['ordinal']]
    _need(ordinary_table['table_id'] == impairment_table['table_id']
          and ordinary_cell['row_index'] != impairment_cell['row_index'],
          'B03_EXACT_CASH_FLOW_ROWS_UNRELATED')
    ordinary_row = ordinary_table['rows'][ordinary_cell['row_index']]
    impairment_row = impairment_table['rows'][impairment_cell['row_index']]
    ordinary_label = ' '.join(cell['text'] for cell in ordinary_row['cells']
        if cell['is_origin'] and cell['column_index'] < ordinary_cell['column_index'])
    impairment_label = ' '.join(cell['text'] for cell in impairment_row['cells']
        if cell['is_origin'] and cell['column_index'] <= impairment_cell['column_index'])
    match = _IMPAIRMENT_COMPONENT.search(' '.join(impairment_label.split()))
    _need(_DEPRECIATION_ROW.search(' '.join(ordinary_label.split()))
          and match is not None
          and match.group('amount').replace(',', '') ==
              matched['impairment']['text'].replace(',', '')
          and impairment_cell['column_index'] < ordinary_table['column_count'] - 1,
          'B03_EXACT_CASH_FLOW_LABELS_NOT_PROVEN')
    body = {'record_type': 'B03_EXACT_IMPAIRMENT_RELATION_V1',
        'primary_source_sha256': proof['content_sha256'],
        'primary_source_path': proof['request_repo_relative_path'],
        'selected_da_fact_ordinal': original['ordinal'],
        'ordinary_da_fact_ordinal': matched['ordinary']['ordinal'],
        'impairment_depreciation_fact_ordinal': matched['impairment']['ordinal'],
        'shared_context_ref': original['context_ref'],
        'cash_flow_table_id': ordinary_table['table_id'],
        'cash_flow_table_grid_sha256': ordinary_table['grid_sha256'],
        'selected_total_usd': str(total),
        'exact_impairment_depreciation_usd': str(impairment),
        'arithmetically_remaining_da_usd': str(ordinary),
        'segment_inclusion_footnote_sha256': inclusion['footnote']['span_sha256'],
        'native_result_created': False, 'current_business_credit': False}
    return {**body, 'proof_id': content_hash(value=body)}
