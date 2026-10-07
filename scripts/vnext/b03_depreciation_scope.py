"""Bounded source-scope check for a directly selected B03 D&A amount.

Company Facts supplies an approved concept and amount, but its name does not
prove that an inline fact represents all depreciation and amortization. This
check only recognizes an explicit fixed-asset subset or an impairment-related
depreciation component in the selected fact's original annual text. It never
substitutes a competing number or certifies that an unflagged result has
complete EBITDA coverage.
"""
from html.parser import HTMLParser
from pathlib import Path
import re

from .canonical import sha256_bytes
from .composite_scope import index_source_structure
from .constraints import parse_numeric_claim
from .deterministic_router import (
    _numeric_xbrl_value, parse_accession_xbrl_source)
from .financial_structured import _InlineTableIndex, _fact_cells
from .sources import resolve_repository_file
from .text_results_v2 import _ReportedFactMetadata
from .xbrl_namespace_policy import YEAR_ONLY, is_fasb_namespace


_NARROW = re.compile(
    r'\bdepreciation\s+and\s+amortization\s+of\s+'
    r'(?:fixed\s+assets|property\s+and\s+equipment)\b', re.I)
_DA_LABEL = re.compile(r'\bdepreciation\s+and\s+amortization\b', re.I)
_DA_CONCEPTS = {
    'us-gaap:DepreciationDepletionAndAmortization',
    'us-gaap:DepreciationAmortizationAndAccretionNet',
    'us-gaap:DepreciationAndAmortization',
}
_NUMBER = re.compile(r'\(?[0-9][0-9,]*(?:\.[0-9]+)?\)?')
_MARKER = re.compile(r'\(([a-z0-9]{1,2})\)', re.I)
_FOOTNOTE = re.compile(r'^\(([a-z0-9]{1,2})\)\s*(.+)$', re.I)
_IMPAIRMENT_DEPRECIATION = re.compile(
    r'^\([a-z0-9]{1,2}\)\s*includes?\b.{0,180}\bdepreciation\b'
    r'.{0,100}\b(?:related to|due to|associated with|from)\b'
    r'.{0,90}\bimpairment\b', re.I)


def _nearest_da_label(prefix):
    """Scope only the label adjacent to a fact, not an earlier table row."""
    matches = list(_DA_LABEL.finditer(prefix))
    if not matches:
        return None
    label = prefix[matches[-1].start():]
    return {'text': label, 'narrow': bool(_NARROW.match(label))}


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


class _VisibleFactText(HTMLParser):
    """Place parser fact ordinals in the original visible text stream."""

    def __init__(self, ordinals):
        super().__init__(convert_charrefs=True)
        self.ordinals = set(ordinals)
        self.count = 0
        self.parts = []
        self.length = 0
        self.positions = {}

    def _append(self, value):
        if self.parts:
            self.length += 1
        start = self.length
        self.parts.append(value)
        self.length += len(value)
        return start

    def handle_starttag(self, tag, attrs):
        if 'contextref' in dict(attrs):
            self.count += 1
            if self.count in self.ordinals:
                self.positions[self.count] = self._append('')

    def handle_data(self, data):
        if data.strip():
            self._append(data)


def _linked_footnotes(structure, table_order):
    """Read only the numbered block directly following the selected table."""
    table = structure['tables'][table_order]
    next_table = min((row['start_byte'] for row in structure['tables']
        if row['start_byte'] >= table['end_byte']),
        default=structure['source_size'])
    notes = {}
    started = False
    for block in structure['blocks']:
        if block['inside_table'] or block['start_byte'] < table['end_byte']:
            continue
        if block['start_byte'] >= next_table:
            break
        text = ' '.join(block['visible_text'].split())
        if not started and re.fullmatch(r'[_\-—]{3,}', text):
            continue
        match = _FOOTNOTE.match(text)
        if match is None:
            break
        notes.setdefault(match.group(1).casefold(), []).append(block)
        started = True
    return notes


def _selected_impairment_inclusion(raw, parsed, selected_rows):
    """Prove that a selected visible total sums a footnoted impairment item.

    A nearby impairment mention is insufficient: the marker must belong to a
    numeric component of the selected row, the visible components must sum to
    its selected total, and the adjacent original footnote must explicitly say
    that impairment-related depreciation is included.
    """
    ordinals = {row['ordinal'] for row in selected_rows}
    index = _InlineTableIndex(raw)
    index.feed(raw.decode('utf-8'))
    index.close()
    cells = _fact_cells(index, parsed, ordinals)
    structure = index_source_structure(source_bytes=raw)
    for selected in selected_rows:
        pair = cells.get(selected['ordinal'])
        if pair is None:
            continue
        table, selected_cell = pair
        order = table['order']
        source_table = structure['tables'][order]
        position = index.fact_positions[selected['ordinal']]
        if not (source_table['start_byte'] <= position < source_table['end_byte']):
            continue
        row = [cell for cell in table['rows'][selected_cell['row_index']]
               ['cells'] if cell['is_origin']]
        numbers = [(cell, parse_numeric_claim(raw_value=cell['text'],
                    reported_unit='USD')) for cell in row
                   if _NUMBER.fullmatch(cell['text'].strip())]
        if not numbers or numbers[-1][0] != selected_cell:
            continue
        components = numbers[:-1]
        if len(components) < 2 or sum(value for _, value in components) != numbers[-1][1]:
            continue
        if not any(re.search(r'\bdepreciation\b.*\bamortization\b',
                             cell['text'], re.I)
                   for cell in row if cell['column_index'] < components[0][0]['column_index']):
            continue
        footnotes = _linked_footnotes(structure, order)
        for marker_cell in row:
            match = _MARKER.fullmatch(marker_cell['text'].strip())
            if match is None or marker_cell['column_index'] >= selected_cell['column_index']:
                continue
            earlier = [(cell, value) for cell, value in components
                       if cell['column_index'] < marker_cell['column_index']]
            if not earlier:
                continue
            component, amount = earlier[-1]
            later = [cell for cell, _ in components
                     if component['column_index'] < cell['column_index']
                     < marker_cell['column_index']]
            if later:
                continue
            notes = footnotes.get(match.group(1).casefold(), [])
            if len(notes) != 1:
                continue
            note = notes[0]
            text = ' '.join(note['visible_text'].split())
            if (not _IMPAIRMENT_DEPRECIATION.search(text)
                    or sha256_bytes(content=raw[note['start_byte']:
                        note['end_byte']]) != note['span_sha256']):
                continue
            return {'selected_fact': selected,
                'table_id': table['table_id'],
                'table_grid_sha256': table['grid_sha256'],
                'selected_visible_total': selected_cell['text'],
                'visible_component_sum': str(sum(value for _, value in components)),
                'included_component': {'visible_value': component['text'],
                    'column_index': component['column_index'],
                    'marker': match.group(1).casefold()},
                'footnote': {'text': note['visible_text'],
                    'start_byte': note['start_byte'],
                    'end_byte': note['end_byte'],
                    'span_sha256': note['span_sha256']}}
    return None


def assess_direct_depreciation_scope(*, case, data_root, namespace_policy=YEAR_ONLY):
    """Return a source-bound conflict, never an inferred replacement amount."""
    _need(case['primary_metric_id'] == 'B03',
          'B03_SCOPE_WRONG_METRIC')
    result = case['results']['B03']
    if result['publication'] != 'PUBLISHED' or result['reason_code'] != 'PASS':
        return {'status': 'NO_PUBLISHED_B03_VALUE', 'blocked': False}
    direct = [row for row in case['observations']
              if row['semantic_role'] == 'depreciation_and_amortization']
    if not direct:
        return {'status': 'NO_DIRECT_DEPRECIATION_SELECTION', 'blocked': False}
    _need(len(direct) == 1 and direct[0]['source_binding']['concept'] in _DA_CONCEPTS,
          'B03_SCOPE_SELECTED_FACT_AMBIGUOUS')
    selected = direct[0]
    binding = selected['source_binding']
    accession = binding['accession']
    primary = [proof for proof in case['source_proofs']
        if proof.get('accession') == accession
        and proof.get('document_name', '').lower().endswith(('.htm', '.html'))]
    _need(len(primary) == 1, 'B03_SCOPE_PRIMARY_NOT_UNIQUE')
    proof = primary[0]
    root = Path(data_root)
    path = resolve_repository_file(repo_root=root,
        repo_relative_path=proof['request_repo_relative_path'])
    raw = path.read_bytes()
    _need(sha256_bytes(content=raw) == proof['content_sha256'],
          'B03_SCOPE_PRIMARY_BYTES_CHANGED')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    metadata = _ReportedFactMetadata()
    metadata.feed(raw.decode('utf-8-sig')); metadata.close()
    _need(metadata.ordinal == len(parsed.facts), 'B03_SCOPE_NATIVE_STREAM_CHANGED')
    period = case['target_period']
    facts = []
    for fact in parsed.facts:
        uri, local_name = metadata.facts[fact['ordinal']]['concept']
        concept = 'us-gaap:' + local_name
        if concept not in _DA_CONCEPTS:
            continue
        if not is_fasb_namespace(uri,namespace_policy=namespace_policy):
            continue
        context = parsed.contexts[fact['context_ref']]
        if (context['period_start'] != period['period_start']
                or context['period_end'] != period['period_end']
                or context['typed_dimension_count']
                or context['dimensions']
                or str(int(context['entity_identifier'])) !=
                   str(int(binding['entity']))):
            continue
        if metadata.units.get(fact['unit_ref']) != {
                'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')],
                'divided': False}:
            continue
        try:
            value = str(_numeric_xbrl_value(text=fact['text'],
                scale=fact['scale'], sign=fact['sign']))
        except (ValueError, TypeError):
            continue
        facts.append({'ordinal': fact['ordinal'],
            'concept': concept, 'value': value,
            'context_ref': fact['context_ref']})
    selected_rows = [fact for fact in facts
        if fact['concept'] == binding['concept']
        and fact['value'] == str(selected['value'])]
    _need(bool(selected_rows), 'B03_SCOPE_SELECTED_INLINE_FACT_NOT_FOUND')
    selected_ordinals = {fact['ordinal'] for fact in selected_rows}
    parser = _VisibleFactText(fact['ordinal'] for fact in facts)
    parser.feed(raw.decode('utf-8'))
    parser.close()
    _need(parser.count == len(parsed.facts),
          'B03_SCOPE_INLINE_FACT_ORDER_CHANGED')
    visible = ' '.join(parser.parts)
    labels = {}
    for fact in facts:
        position = parser.positions.get(fact['ordinal'])
        _need(position is not None, 'B03_SCOPE_FACT_TEXT_NOT_FOUND')
        labels[fact['ordinal']] = ' '.join(
            visible[max(0, position - 190):position].split())
    scoped = {fact['ordinal']: _nearest_da_label(labels[fact['ordinal']])
              for fact in facts}
    narrow = [fact for fact in selected_rows
              if scoped[fact['ordinal']] is not None
              and scoped[fact['ordinal']]['narrow']]
    competitors = [fact for fact in facts
        if fact['ordinal'] not in selected_ordinals
        and fact['value'] != str(selected['value'])
        and scoped[fact['ordinal']] is not None
        and not scoped[fact['ordinal']]['narrow']]
    if narrow:
        return {'status': ('NARROW_SELECTED_AND_COMPETING_SCOPE'
                if competitors else 'NARROW_SELECTED_SCOPE_NOT_PROVEN'),
            'blocked': True, 'primary_source_sha256': proof['content_sha256'],
            'selected_fact': narrow[0],
            'selected_label': labels[narrow[0]['ordinal']][-190:],
            'competing_facts': [{**fact,
                'label': labels[fact['ordinal']][-190:]}
                for fact in competitors]}
    impairment = _selected_impairment_inclusion(raw, parsed, selected_rows)
    if impairment is not None:
        return {'status': 'SELECTED_DEPRECIATION_INCLUDES_IMPAIRMENT',
            'blocked': True, 'primary_source_sha256': proof['content_sha256'],
            'impairment_inclusion_proof': impairment}
    return {'status': 'NO_EXPLICIT_NARROW_SCOPE_FOUND', 'blocked': False,
        'primary_source_sha256': proof['content_sha256'],
        'selected_fact_ordinals': sorted(selected_ordinals),
        'complete_depreciation_scope_proven': False}
