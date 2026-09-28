"""Bounded source-scope check for a directly selected B03 D&A amount.

Company Facts supplies an approved concept and amount, but its name does not
prove that an inline fact represents all depreciation and amortization. This
check only recognizes an explicit fixed-asset subset in the selected fact's
original annual text. It never substitutes a competing number or certifies
that an unflagged result has complete EBITDA coverage.
"""
from html.parser import HTMLParser
from pathlib import Path
import re

from .canonical import sha256_bytes
from .deterministic_router import (
    _numeric_xbrl_value, parse_accession_xbrl_source)
from .sources import resolve_repository_file


_NARROW = re.compile(
    r'\bdepreciation\s+and\s+amortization\s+of\s+'
    r'(?:fixed\s+assets|property\s+and\s+equipment)\b', re.I)
_DA_LABEL = re.compile(r'\bdepreciation\s+and\s+amortization\b', re.I)
_DA_CONCEPTS = {
    'us-gaap:DepreciationDepletionAndAmortization',
    'us-gaap:DepreciationAmortizationAndAccretionNet',
    'us-gaap:DepreciationAndAmortization',
}


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


def assess_direct_depreciation_scope(*, case, data_root):
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
    period = case['target_period']
    facts = []
    for fact in parsed.facts:
        if fact['qualified_name'] not in _DA_CONCEPTS:
            continue
        context = parsed.contexts[fact['context_ref']]
        if (context['period_start'] != period['period_start']
                or context['period_end'] != period['period_end']
                or context['typed_dimension_count']
                or context['dimensions']
                or str(int(context['entity_identifier'])) !=
                   str(int(binding['entity']))):
            continue
        try:
            value = str(_numeric_xbrl_value(text=fact['text'],
                scale=fact['scale'], sign=fact['sign']))
        except (ValueError, TypeError):
            continue
        facts.append({'ordinal': fact['ordinal'],
            'concept': fact['qualified_name'], 'value': value,
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
    return {'status': 'NO_EXPLICIT_NARROW_SCOPE_FOUND', 'blocked': False,
        'primary_source_sha256': proof['content_sha256'],
        'selected_fact_ordinals': sorted(selected_ordinals),
        'complete_depreciation_scope_proven': False}
