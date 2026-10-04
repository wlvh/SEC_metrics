"""Keep a bond's current and noncurrent schedule occurrences distinct.

Only the historical reader changes. A label may occur once in each reported
section; the native fact must still match its concept, dimensions, section,
exact note row, current column and amount. Zero occurrences are retained.
The frozen reader remains the path for globally unique labels, preserving its
proof bytes. This is a composition repair, not financing completeness credit.
"""
from . import b06_bond_leases as frozen
from .canonical import content_hash
from .historical_dei import release_aware, release_aware_with
from .historical_financial_wording import successor


SCHEDULE_FORMS = ((
    "len({p['label'] for group in parts.values() for p in group}) == sum(len(v) for v in parts.values())",
    "all(len({p['label'] for p in group}) == len(group) for group in parts.values())",
),)

MEMBER_FORMS = (
    ("    expected = {row['label']:row['value'] for group in bonds['members'].values() for row in group}",
     "    expected = {(section,row['label']):row['value'] for section,group in bonds['members'].items() for row in group}\n"
     "    positions = {row['row']['row_index']:(section,row['label'])\n"
     "                 for section,group in bonds['members'].items() for row in group}\n"
     "    _need(len(expected) == len(positions) == sum(len(group) for group in bonds['members'].values()),\n"
     "          'BOND_SECTION_MEMBER_DUPLICATED')"),
    ("            found.append({'ordinal':f['ordinal']",
     "            classification = 'current' if local.casefold() == 'debtcurrent' else 'noncurrent'\n"
     "            found.append({'classification':classification,'ordinal':f['ordinal']"),
    ("                _need(label in expected and expected[label] == r['value'] and col <= cell['column_index'] < col+width,",
     "                member = (r['classification'],label)\n"
     "                _need(member in expected and expected[member] == r['value']\n"
     "                      and positions.get(row['row_index']) == member\n"
     "                      and _same_schedule_grid(table,bonds)\n"
     "                      and col <= cell['column_index'] < col+width,"),
    ("{r['source_row']['label'] for r in found} == set(expected)",
     "{(r['classification'],r['source_row']['label']) for r in found} == set(expected)"),
    ("content_hash(value=r['dimensions'])",
     "content_hash(value={'classification':r['classification'],'dimensions':r['dimensions']})"),
    ("result.append({'dimensions':left[0]['dimensions'],'value':chosen['value'],",
     "result.append({'classification':left[0]['classification'],'dimensions':left[0]['dimensions'],'value':chosen['value'],"),
)

_section_bond_schedule = release_aware(successor(frozen._bond_schedule, SCHEDULE_FORMS))
_frozen_native_members = release_aware(frozen._native_bond_members)


def table_shape_hash(table):
    # Entity spellings can differ between an XML text block and its inline
    # counterpart. The decoded text is already supplied by the shared parser.
    # Preserve every expanded cell and all geometry, including both periods.
    shape = {k: v for k, v in table.items() if k not in {
        'table_id', 'order', 'grid_sha256', 'caption_raw_text', 'rows'}}
    shape['rows'] = [dict(row, cells=[{k: v for k, v in cell.items() if k != 'raw_text'}
        for cell in row['cells']]) for row in table['rows']]
    return content_hash(value=shape)


def bond_schedule(note, end, reports):
    bonds = _section_bond_schedule(note, end, reports)
    labels = [row['label'] for group in bonds['members'].values() for row in group]
    if len(set(labels)) != len(labels):
        bonds['section_grid_shape_hash'] = table_shape_hash(frozen.disclosure.tables(note['text'])[0])
    return bonds


def same_schedule_grid(table, bonds):
    return table_shape_hash(table) == bonds['section_grid_shape_hash']


_section_native_members = release_aware_with(
    successor(frozen._native_bond_members, MEMBER_FORMS),
    _same_schedule_grid=same_schedule_grid)


def native_bond_members(primary, xml, prepared, bonds):
    labels = [row['label'] for group in bonds['members'].values() for row in group]
    if len(set(labels)) == len(labels):
        return _frozen_native_members(primary, xml, prepared, bonds)
    return _section_native_members(primary, xml, prepared, bonds)


inspect_bond_lease_composition = release_aware_with(
    frozen.inspect_bond_lease_composition, _bond_schedule=bond_schedule)
inspect_bond_debt_scope = release_aware_with(
    frozen.inspect_bond_debt_scope,
    inspect_bond_lease_composition=inspect_bond_lease_composition,
    _native_bond_members=native_bond_members)
