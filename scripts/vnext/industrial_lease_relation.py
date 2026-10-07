"""A reported finance-lease component is not another additive debt balance.

This reads a specific inclusive table assertion, not a debt-completeness rule.
The caller has already checked each original's subject, period, USD, dimensions,
amount and visible industrial column. Missing evidence stays unresolved.
"""
from decimal import Decimal
from html.parser import HTMLParser
import re

from .b06_disclosure import label
from .b06_inclusive_table import _InclusiveInlineNotes
from .financial_structured import _fact_cells
from .governance_signals import _source_value
from .r5_b06_scope import precision_choice
from .text_results_v2 import _verified_context
from .composite_scope import index_source_structure
from .constraints import parse_numeric_claim
from .canonical import sha256_bytes


def _scope_matches(context, parent, metadata, parent_proof):
    if (context['period_start'], context['period_end'], context['entity_identifier']) != (
            parent['period_start'], parent['period_end'], parent['entity_identifier']):
        return False
    if context['typed_dimension_count']:
        return False
    proof = _verified_context(native={**context, 'dimensions': dict(context['dimensions'])}, metadata=metadata)
    dims = {tuple(d['dimension_qname']): tuple(d['member_qname']) for d in proof['dimensions']}
    inherited = {tuple(d['dimension_qname']): tuple(d['member_qname']) for d in parent_proof['dimensions']}
    if any(dims.get(k) != v for k, v in inherited.items()):
        return False
    extra = set(dims) - set(inherited)
    return all(re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}', axis[0])
               and axis[1].casefold() == 'longtermdebttypeaxis'
               and dims[axis][0] == axis[0] for axis in extra)


def _context_key(context):
    return (tuple((x['scheme'], x['value']) for x in context['identifiers']),
            tuple(sorted((x['kind'], x['value']) for x in context['period_fields'])),
            tuple(sorted((tuple(x['dimension_qname']), tuple(x['member_qname']))
                         for x in context['dimensions'])))


def carrier_reports(*, native_sources, index, table_id, row_index, column, span, parent, parent_proof, sources):
    """Read the carrier cell's own facts; no multiplier is borrowed."""
    parsed, meta = native_sources['primary']
    eligible = [f for f in parsed.facts if f['unit_ref']
                and _scope_matches(parsed.contexts[f['context_ref']], parent, meta, parent_proof)]
    cells = _fact_cells(index, parsed, {f['ordinal'] for f in eligible})
    selected = []
    for fact in eligible:
        found = cells.get(fact['ordinal'])
        if not found:
            continue
        table, cell = found
        if (table['table_id'], cell['origin_row_index'], cell['column_index'], cell['colspan']) != (
                table_id, row_index, column, span):
            continue
        if meta.units.get(fact['unit_ref']) != {
                'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')], 'divided': False}:
            continue
        context = parsed.contexts[fact['context_ref']]
        proof = _verified_context(native={**context, 'dimensions': dict(context['dimensions'])}, metadata=meta)
        concept = meta.facts[fact['ordinal']]['concept']
        row = {'ordinal': fact['ordinal'], 'value': _source_value(fact, meta.facts[fact['ordinal']]),
               'decimals': meta.facts[fact['ordinal']]['attrs'].get('decimals'),
               'context_proof': proof, 'concept': concept, 'unit': 'USD',
               'reported_scale': fact['scale'], 'source_reference': sources['primary']['source_reference'],
               'cell': cell}
        other_parsed, other_meta = native_sources['xml']
        peers = []
        for other in other_parsed.facts:
            qname = other_meta.facts[other['ordinal']]['concept']
            if (qname[0], qname[1].casefold()) != (concept[0], concept[1].casefold()):
                continue
            c = other_parsed.contexts[other['context_ref']]
            if not _scope_matches(c, parent, other_meta, parent_proof) or other_meta.units.get(other['unit_ref']) != {
                    'measures': [('http://www.xbrl.org/2003/iso4217', 'USD')], 'divided': False}:
                continue
            p = _verified_context(native={**c, 'dimensions': dict(c['dimensions'])}, metadata=other_meta)
            if _context_key(p) != _context_key(proof):
                continue
            peers.append({'ordinal': other['ordinal'],
                'value': _source_value(other, other_meta.facts[other['ordinal']]),
                'decimals': other_meta.facts[other['ordinal']]['attrs'].get('decimals'),
                'context_proof': p, 'concept': qname, 'unit': 'USD',
                'source_reference': sources['xml']['source_reference']})
        if peers:
            choice = precision_choice([row, *peers])
            selected.append({'value': choice['value'], 'primary': row, 'xml': peers})
    return selected[0] if len(selected) == 1 else None


def visible_scale(*, structure, table, raw):
    """The selected table's explicit unit, including its preceding introduction."""
    span = structure['tables'][table['order']]
    previous = max((s['end_byte'] for s in structure['tables']
                    if s['end_byte'] <= span['start_byte']), default=0)
    declarations = [{'text': c['text'], 'proof': c} for r in table['rows'][:4]
                    for c in r['cells'] if c['is_origin'] and c['text']]
    if table.get('caption_raw_text'):
        declarations.append({'text': table['caption_raw_text'], 'proof': {'table_id': table['table_id']}})
    # A filing can put the introduction inside the same div as its table.
    # The existing block index then has no separate introduction block. Read
    # the bounded original gap between tables instead of guessing a distance.
    intro = raw[previous:span['start_byte']]
    declarations.append({'text': introductory_text(intro), 'proof': {
        'start_byte': previous, 'end_byte': span['start_byte'],
        'span_sha256': sha256_bytes(content=intro)}})
    found = []
    for d in declarations:
        # A debt's original currency is not the reporting unit of this table.
        # Only an explicit unit declaration can contradict the native USD.
        for match in re.finditer(r'\bin (dollars|thousands|millions|billions|euros?|pounds?|yen|USD|EUR|GBP|JPY)(?: of (dollars|euros?|pounds?|yen|USD|EUR|GBP|JPY))?(?=\s*(?:,|\)|$))', d['text'], re.I):
            currency = (match[2] or match[1]).casefold()
            if currency in {'euro', 'euros', 'pound', 'pounds', 'yen', 'eur', 'gbp', 'jpy'}:
                return None
            unit = match[1].casefold()
            if unit == 'usd':
                unit = 'dollars'
            found.append({'factor': {'dollars':'1','thousands':'1000','millions':'1000000','billions':'1000000000'}[unit], 'proof':d['proof']})
    return found if len({x['factor'] for x in found}) == 1 else None


def introductory_text(raw):
    """Find a table introduction, excluding unrelated earlier discussion."""
    class Intro(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True); self.skipped=[]; self.parts=[]; self.blocks=[]
        def boundary(self):
            text = ' '.join(' '.join(self.parts).split())
            if text:
                self.blocks.append(text)
            self.parts=[]
        def handle_starttag(self,tag,attrs):
            if tag in {'script','style','ix:header','ix:hidden','ix:resources'} or tag.split(':')[-1] in {'context','unit'}:
                self.skipped.append(tag)
            elif not self.skipped and tag in {'p', 'div', 'br'}:
                self.boundary()
        def handle_endtag(self,tag):
            if self.skipped and self.skipped[-1]==tag:self.skipped.pop()
            elif not self.skipped and tag in {'p', 'div'}:
                self.boundary()
        def handle_data(self,data):
            if not self.skipped:self.parts.append(data)
    p=Intro();p.feed(raw.decode('utf-8-sig'));p.close()
    p.boundary()
    for text in reversed(p.blocks):
        # An explicit table lead-in or a standalone unit line can provide
        # the table's unit. Earlier issuance prose cannot supply that scope.
        if (re.search(r'\bas follows\s*\(in [^)]+\)\s*[:.]?$', text, re.I)
                or re.fullmatch(r'\(?in [^)]+\)?\s*[:.]?', text, re.I)):
            return text
    return ''


def inspect_inclusion(*, primary, parsed, reported_components, lease_reports,
                      native_sources, index, sources):
    notes = _InclusiveInlineNotes()
    notes.feed(primary['raw_bytes'].decode('utf-8-sig')); notes.close()
    if notes.active or notes.excluded:
        raise ValueError('INDUSTRIAL_LEASE_NOTE_TRUNCATED')
    debt_notes = [f for f in notes.facts
                  if f['attrs'].get('name', '').split(':')[-1] == 'DebtDisclosureTextBlock']
    unresolved = {'status': 'UNRESOLVED', 'additional_debt_amount': None,
                  'reason': 'REPORTED_LEASE_INCLUSION_NOT_ESTABLISHED', 'relationships': []}
    relationships = []
    structure = index_source_structure(source_bytes=primary['raw_bytes'])
    for role, concept in [('current_debt', 'financeleaseliabilitycurrent'),
                          ('noncurrent_debt', 'financeleaseliabilitynoncurrent')]:
        parent = reported_components.get(role)
        component = {kind: rows.get(concept, []) for kind, rows in lease_reports.items()}
        if not parent or not component.get('primary') or not component.get('xml'):
            return unresolved
        choice = precision_choice(component['primary'] + component['xml'])
        value = Decimal(choice['value'])
        if value < 0 or value > Decimal(parent['value']):
            return unresolved
        supported = []
        for evidence in parent['visible_table_evidence']:
            table, cell = evidence['table'], evidence['cell']
            start = min((c['row_index'] for c in evidence['column_headers']), default=0)
            end = cell['origin_row_index']
            previous_totals = [e['cell']['origin_row_index']
                for other_role, other in reported_components.items() if other_role != role
                for e in other['visible_table_evidence']
                if e['table']['table_id'] == table['table_id']
                and start <= e['cell']['origin_row_index'] < end]
            if previous_totals:
                start = max(previous_totals) + 1
            rows = [(i, r) for i, r in enumerate(table['rows'][start:end], start)
                    if re.fullmatch(r'Other debt \(including finance leases\)\s*\([a-z]\)',
                                    label(r), re.I)]
            if not rows:
                continue
            row_index, row = rows[-1]
            parent_context = parent['source_reports']['primary'][0]['context']
            parent_proof = _verified_context(native={**parent_context, 'dimensions': dict(parent_context['dimensions'])},
                metadata=native_sources['primary'][1])
            carrier = carrier_reports(native_sources=native_sources, index=index,
                table_id=table['table_id'], row_index=row_index, column=cell['column_index'],
                span=cell['colspan'], parent=parent_context, parent_proof=parent_proof, sources=sources)
            if carrier is None or value > Decimal(carrier['value']):
                continue
            scale = visible_scale(structure=structure, table=table, raw=primary['raw_bytes'])
            if scale is None:
                continue
            visible = parse_numeric_claim(raw_value=carrier['primary']['cell']['text'], reported_unit='USD')
            visible *= Decimal(scale[0]['factor'])
            if visible != Decimal(carrier['primary']['value']):
                continue
            # The same original note must contain the proved parent and the
            # lease facts. A similarly named balance elsewhere is insufficient.
            lease_ordinals = {r['ordinal'] for r in component['primary']}
            matching = [n for n in debt_notes
                        if evidence['ordinal'] in notes.ordinals(n)
                        and carrier['primary']['ordinal'] in notes.ordinals(n)
                        and lease_ordinals.intersection(notes.ordinals(n))
                        and n['attrs'].get('contextref') in parsed.contexts
                        and parsed.contexts[n['attrs']['contextref']]['period_end'] == parent_context['period_end']
                        and parsed.contexts[n['attrs']['contextref']]['entity_identifier'] == parent_context['entity_identifier']]
            if len(matching) != 1:
                continue
            supported.append({'parent_role': role, 'parent_amount': parent['value'],
                'component_amount': choice['value'], 'unit': 'USD',
                'table_id': table['table_id'], 'inclusive_row_index': row_index,
                'inclusive_label': label(row), 'total_cell': cell,
                'inclusive_amount': carrier['value'], 'carrier_reports': carrier,
                'visible_reporting_unit': scale,
                'source_reference': primary['source_reference'],
                'parent_ordinal': evidence['ordinal'],
                'component_reports': {**component, 'primary': [r for r in component['primary']
                    if r['ordinal'] in notes.ordinals(matching[0])]},
                'note_attributes': matching[0]['attrs']})
        if not supported:
            return unresolved
        relationships.append({'role': role, 'amount': choice['value'],
                              'status': 'ALREADY_INCLUDED', 'evidence': supported})
    return {'status': 'REPORTED_INCLUDED', 'additional_debt_amount': '0',
            'reason': 'INCLUSIVE_REPORTED_DEBT_TABLE', 'relationships': relationships,
            'component_total': str(sum(Decimal(r['amount']) for r in relationships)),
            'complete_B06': False}
