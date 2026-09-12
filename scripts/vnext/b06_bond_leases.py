"""Reconcile reported bonds, separate leases and the full financing inventory.

Individual source components do not establish complete debt. The combined
scope proof checks current totals, instrument dimensions, other disclosures
and independent potential financing facts before ordinary native calculation.
Source acquisition, qualification and production permissions remain separate.
"""
from decimal import Decimal
from datetime import date
import re

from . import b06_disclosure as disclosure
from .b06_financing_inventory import inspect_financing_inventory
from .canonical import content_hash, decimal_text, strict_json_file
from .deterministic_router import parse_accession_xbrl_source
from .normal_source_authority import ROOT
from .r5_b06_scope import precision_choice


POLICY_PATH = 'config/b06_bond_leases_v1.json'
POLICY = strict_json_file(path=ROOT/POLICY_PATH)


class BondLeaseError(ValueError):
    pass


def _need(condition, reason):
    if not condition: raise BondLeaseError('BOND_LEASE_'+reason)


def _notes(primary, xml, prepared, concepts=None):
    end = prepared['filing']['reportDate']; notes = {}
    parsed = parse_accession_xbrl_source(raw_bytes=xml['raw_bytes'])
    inline = disclosure._InlineNotes(); inline.feed(primary['raw_bytes'].decode('utf-8-sig')); inline.close()
    _need(not inline.active and not inline.excluded, 'PRIMARY_NOTES_TRUNCATED')
    compact = lambda value:re.sub(r'\s','',value)
    for role,local in (concepts or POLICY['note_concepts']).items():
        found = []
        for f in parsed.facts:
            c = parsed.contexts[f['context_ref']]
            if f['qualified_name'].split(':')[-1].casefold() == local.casefold() and c['period_end'] == end and not c['dimensions'] and not c['typed_dimension_count']:
                _need(str(int(c['entity_identifier'])) == prepared['entity']
                      and c['period_start'] == prepared['table_input']['target_period']['period_start'], 'NOTE_SCOPE_CONFLICT')
                found.append(f)
        _need(len(found) == 1,'NOTE_NOT_UNIQUE:'+role); fact = found[0]
        matches = [f for f in inline.facts if f['attrs'].get('name','').casefold() == fact['qualified_name'].casefold()
                   and f['attrs'].get('contextref') == fact['context_ref']]
        _need(len(matches) == 1 and compact(disclosure.text(fact['text'])) == compact(inline.value(matches[0])),
              'FULL_PRIMARY_XML_NOTE_CONFLICT:'+role)
        notes[role] = fact
    return notes


def _finance_reports(inventory, end):
    reports = {}
    for role,concept in POLICY['finance_concepts'].items():
        by_kind = {}
        for kind in ['xml','primary']:
            rows = [r for r in inventory['native_fact_inventory'][kind]
                    if r['concept_qname'][1].casefold() == concept.casefold()
                    and r['context']['period_start'] == r['context']['period_end'] == end]
            _need(rows and all(r['official_us_gaap_concept'] and r['unit_class'] == 'USD' for r in rows),
                  'FINANCE_FACT_CONCEPT_OR_UNIT_UNPROVEN:'+role)
            by_kind[kind] = rows
        chosen = precision_choice(by_kind['xml']+by_kind['primary'])
        _need(Decimal(chosen['value']) >= 0,'NEGATIVE_FINANCE_LIABILITY')
        reports[role] = {**by_kind,'chosen':chosen}
    return reports


def _lease_classification(note, end, reports):
    text = disclosure.text(note['text'])
    _need(text.startswith(POLICY['classification_introduction']) and POLICY['scale_text'] in text,
          'CLASSIFICATION_SCOPE_OR_SCALE_UNPROVEN')
    tables = disclosure.tables(note['text'])
    choices = [t for t in tables if any(re.fullmatch(POLICY['finance_row_pattern'],disclosure.label(r)) for r in t['rows'])]
    _need(len(choices) == 1,'CLASSIFICATION_TABLE_NOT_UNIQUE'); table = choices[0]
    column,width,header = disclosure._period_column(table,end,False)
    state = None; within_liabilities = False; selected = {}; rows = []
    for row in table['rows'][header+1:]:
        label = disclosure.label(row)
        if label == 'Liabilities': within_liabilities = True
        if not within_liabilities: continue
        if label in {'Current','Noncurrent'}:
            state = label.casefold(); continue
        if not re.fullmatch(POLICY['finance_row_pattern'],label): continue
        _need(state in {'current','noncurrent'} and state not in selected,'FINANCE_CLASSIFICATION_AMBIGUOUS')
        classification = [c for c in disclosure.origins(row) if c['text'] == POLICY['classification_labels'][state]]
        _need(len(classification) == 1 and classification[0]['column_index'] < column,
              'FINANCE_STATEMENT_CLASS_UNPROVEN')
        value = disclosure.amount(row,column,width)
        _need(value == Decimal(reports[state]['chosen']['value']),'FINANCE_CLASSIFICATION_AMOUNT_CONFLICT')
        selected[state] = {'value':decimal_text(value=value),'row_index':row['row_index'],'row':row,
                           'statement_class':classification[0]['text']}
        rows.append(label)
    _need(set(selected) == {'current','noncurrent'},'FINANCE_CURRENT_NONCURRENT_MISSING')
    _need(sum(Decimal(v['value']) for v in selected.values()) == Decimal(reports['total']['chosen']['value']),
          'FINANCE_CURRENT_NONCURRENT_RECONCILIATION')
    return {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],
            'table_count_in_note':len(tables),'selected':selected}


def _lease_maturity(note, reports, prepared):
    from .b06_disclosure_v2 import _date_text
    text = disclosure.text(note['text']); _need(POLICY['scale_text'] in text,'MATURITY_SCALE_UNPROVEN')
    _need(text.startswith('As of '+_date_text(prepared['filing']['reportDate'])+', the maturity of lease liabilities is as follows:'),
          'MATURITY_AS_OF_UNPROVEN')
    tables = disclosure.tables(note['text'])
    choices = [t for t in tables if any(c['text'] == 'Finance Leases' for row in t['rows'] for c in disclosure.origins(row))]
    _need(len(choices) == 1,'MATURITY_TABLE_NOT_UNIQUE'); table = choices[0]
    headers = [c for row in table['rows'] for c in disclosure.origins(row) if c['text'] == 'Finance Leases']
    _need(len(headers) == 1,'FINANCE_MATURITY_COLUMN_AMBIGUOUS'); h = headers[0]
    columns = {'finance':h}
    for kind,pattern in [('operating',r'Operating Leases(?: \([a-z](?: and [a-z])?\))?'),('combined',r'Total')]:
        matches = [c for row in table['rows'] for c in disclosure.origins(row) if re.fullmatch(pattern,c['text'])]
        _need(len(matches) == 1,'MATURITY_OTHER_COLUMN_AMBIGUOUS'); columns[kind] = matches[0]
    values = {}; members = []
    for row in table['rows'][h['row_index']+1:]:
        label = disclosure.label(row)
        cells = [c for c in disclosure.origins(row) if h['column_index'] <= c['column_index'] < h['column_index']+h['colspan']]
        if not cells: continue
        if all(c['text'] == POLICY['scale_text'] for c in cells): continue
        value = disclosure.amount(row,h['column_index'],h['colspan'])
        role = next((k for k,v in POLICY['maturity_labels'].items() if v == label),None)
        if role:
            _need(role not in values and value == Decimal(reports[role]['chosen']['value']),'MATURITY_TOTAL_CONFLICT')
            values[role] = {'value':decimal_text(value=value),'row':row}
        else:
            # A displayed year can occupy its own label cell after Fiscal year.
            all_labels = [c['text'] for c in disclosure.origins(row) if c['column_index'] < h['column_index']]
            _need(not values and any(re.fullmatch(r'(?:After )?[0-9]{4}',v) for v in all_labels),
                  'MATURITY_MEMBER_PERIOD_UNPROVEN')
            members.append({'labels':all_labels,'value':decimal_text(value=value),'row':row})
    _need(set(values) == {'payments','interest','total'} and members,'MATURITY_COMPONENTS_MISSING')
    years = [next(v for v in m['labels'] if re.fullmatch(r'(?:After )?[0-9]{4}',v)) for m in members]
    first = int(prepared['table_input']['target_period']['fiscal_year'])+1
    _need(years == [str(first+n) for n in range(5)]+['After '+str(first+4)], 'MATURITY_FISCAL_YEAR_SEQUENCE_CONFLICT')
    _need(sum(Decimal(m['value']) for m in members) == Decimal(values['payments']['value'])
          and Decimal(values['payments']['value'])-Decimal(values['interest']['value']) == Decimal(values['total']['value']),
          'MATURITY_RECONCILIATION_FAILED')
    for item in [*members,*values.values()]:
        amounts = {kind:disclosure.amount(item['row'],c['column_index'],c['colspan']) for kind,c in columns.items()}
        _need(amounts['finance']+amounts['operating'] == amounts['combined'],'MATURITY_CLASS_SUM_CONFLICT')
        item['reported_values'] = {k:decimal_text(value=v) for k,v in amounts.items()}
    for kind in columns:
        _need(sum(Decimal(m['reported_values'][kind]) for m in members) == Decimal(values['payments']['reported_values'][kind])
              and Decimal(values['payments']['reported_values'][kind])-Decimal(values['interest']['reported_values'][kind])
              == Decimal(values['total']['reported_values'][kind]),'MATURITY_COLUMN_RECONCILIATION_CONFLICT')
    return {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],'table_count_in_note':len(tables),
            'members':members,'totals':values,'columns':columns}


def inspect_separate_finance_leases(*, primary, xml, prepared):
    """A source component only, pending complete debt-set composition."""
    inventory = inspect_financing_inventory(primary=primary,xml=xml,prepared=prepared)
    notes = _notes(primary,xml,prepared); end = prepared['filing']['reportDate']
    reports = _finance_reports(inventory,end)
    classification = _lease_classification(notes['lease_classification'],end,reports)
    maturity = _lease_maturity(notes['lease_maturity'],reports,prepared)
    return {'record_type':'SEPARATE_FINANCE_LEASE_SOURCE_COMPONENT','source_references':inventory['source_references'],
        'policy_hash':content_hash(value=POLICY),'finance_reports':reports,'classification':classification,
        'maturity':maturity,'recognized_finance_lease':reports['total']['chosen']['value'],
        'unit':'USD','separate_from_bond_debt_proven':False,'complete_b06_proven':False,
        'source_acquisition_credit':False,'production_authorized':False}


def inspect_supplier_payment_terms(*, primary, xml, prepared):
    """Recognize the reported unchanged trade-payable arrangement, not its name."""
    from .b06_disclosure_v2 import _Narrative
    from .fiscal_year_labels import _DefinitionBlocks
    inventory = inspect_financing_inventory(primary=primary,xml=xml,prepared=prepared)
    notes = _notes(primary,xml,prepared,concepts=POLICY['supplier_note_concepts'])
    names = []
    for source in [primary,xml]:
        parsed = parse_accession_xbrl_source(raw_bytes=source['raw_bytes'])
        found = {disclosure.text(f['text']) for f in parsed.facts
                 if f['qualified_name'].casefold() == 'dei:entityregistrantname'
                 and str(int(parsed.contexts[f['context_ref']]['entity_identifier'])) == prepared['entity']}
        _need(len(found) == 1,'SUPPLIER_REGISTRANT_NAME_AMBIGUOUS'); names.append(next(iter(found)))
    normalize = lambda value:' '.join(value.replace('’',"'").split()).casefold()
    _need(normalize(names[0]) == normalize(names[1]),'SUPPLIER_REGISTRANT_NAME_CONFLICT')
    parser = _Narrative(); parser.feed(notes['program']['text']); parser.close()
    _need(parser.depth == 0,'SUPPLIER_PROGRAM_TABLE_TRUNCATED')
    narrative = ' '.join(' '.join(parser.parts).split())
    expected = POLICY['supplier_narrative'].format(registrant=names[0])
    _need(normalize(narrative) == normalize(expected),'SUPPLIER_PAYMENT_TERMS_UNPROVEN_OR_CHANGED')
    blocks = _DefinitionBlocks(primary['raw_bytes'].decode('utf-8-sig'))
    blocks.feed(primary['raw_bytes'].decode('utf-8-sig')); blocks.close(); blocks._flush()
    clause = "The Company's obligations to its suppliers, including amounts due and scheduled payment terms, are not impacted by a supplier's participation in the SCF programs."
    locations = [b for b in blocks.blocks if normalize(clause) in normalize(b['text'])]
    _need(len(locations) == 1 and not locations[0]['quoted_context'] and not locations[0]['linked'],
          'SUPPLIER_TERMS_ASSERTION_NOT_CURRENT_ISSUER')
    compact = lambda value:re.sub(r'\s','',value)
    _need(compact(disclosure.text(notes['table']['text'])) in compact(disclosure.text(notes['program']['text'])),
          'SUPPLIER_TABLE_OUTSIDE_PROGRAM_NOTE')
    tables = disclosure.tables(notes['table']['text']); _need(len(tables) == 1,'SUPPLIER_TABLE_NOT_UNIQUE')
    table = tables[0]; end = prepared['filing']['reportDate']
    col,width,header = disclosure._period_column(table,end,False)
    _need(any(c['text'] == POLICY['scale_text'] for row in table['rows'][:header+3] for c in disclosure.origins(row)),
          'SUPPLIER_TABLE_SCALE_UNPROVEN')
    rows = {}
    for row in table['rows'][header+1:]:
        label = disclosure.label(row)
        cells = [c for c in disclosure.origins(row) if col <= c['column_index'] < col+width]
        if not cells: continue
        if all(c['text'] == POLICY['scale_text'] for c in cells): continue
        role = next((k for k,v in POLICY['supplier_table_labels'].items() if v == label),None)
        _need(role is not None and role not in rows,'SUPPLIER_TABLE_ROW_UNRESOLVED:'+label)
        rows[role] = {'value':decimal_text(value=disclosure.amount(row,col,width)),'row':row}
    _need(set(rows) == set(POLICY['supplier_table_labels']),'SUPPLIER_TABLE_ROLE_MISSING')
    values = {k:Decimal(v['value']) for k,v in rows.items()}
    _need(values['opening'] >= 0 and values['confirmed'] >= 0 and values['paid'] <= 0
          and values['opening']+values['confirmed']+values['paid'] == values['closing'],
          'SUPPLIER_BALANCE_ROLLFORWARD_CONFLICT')
    reports = {}
    for role,concept in POLICY['supplier_concepts'].items():
        selected = {}
        for kind in ['xml','primary']:
            matches = [r for r in inventory['native_fact_inventory'][kind]
                       if r['concept_qname'][1].casefold() == concept.casefold()]
            _need(matches and all(r['official_us_gaap_concept'] and r['unit_class'] == 'USD' for r in matches),
                  'SUPPLIER_AMOUNT_SCOPE_OR_UNIT_UNPROVEN')
            start = end if role == 'closing' else prepared['table_input']['target_period']['period_start']
            _need(all(r['context']['period_start'] == start for r in matches),'SUPPLIER_AMOUNT_PERIOD_CONFLICT')
            selected[kind] = matches
        chosen = precision_choice(selected['xml']+selected['primary'])
        _need(Decimal(chosen['value']) == abs(values[role]),'SUPPLIER_TABLE_NATIVE_AMOUNT_CONFLICT')
        reports[role] = {**selected,'chosen':chosen}
    return {'record_type':'SUPPLIER_UNCHANGED_TRADE_PAYABLE_PROOF','policy_hash':content_hash(value=POLICY),
        'source_references':inventory['source_references'],'program_note_ordinal':notes['program']['ordinal'],
        'narrative':narrative,'terms_source_block':locations[0],'table_id':table['table_id'],
        'grid_sha256':table['grid_sha256'],'table_rows':rows,'native_reports':reports,
        'reported_outstanding':decimal_text(value=values['closing']),'unit':'USD',
        'debt_set_disposition':'EXCLUDED_REPORTED_ORDINARY_TRADE_PAYABLE_WITH_UNCHANGED_COMPANY_TERMS',
        'whole_b06_proven':False,'source_acquisition_credit':False,'production_authorized':False}


def _balance_reports(primary, xml, prepared):
    from .text_results_v2 import _ReportedFactMetadata, _verified_context
    from .governance_signals import _source_value
    from .financial_structured import _InlineTableIndex, _fact_cells
    from .constraints import parse_numeric_claim
    by_kind = {}
    for kind,source in [('xml',xml),('primary',primary)]:
        raw = source['raw_bytes']; parsed = parse_accession_xbrl_source(raw_bytes=raw)
        meta = _ReportedFactMetadata(); meta.feed(raw.decode('utf-8-sig')); meta.close()
        _need(meta.ordinal == len(parsed.facts),'BALANCE_NATIVE_STREAM_CONFLICT')
        reports = {role:[] for role in POLICY['balance_concepts']}
        for f in parsed.facts:
            c = parsed.contexts[f['context_ref']]
            if c['period_start'] != c['period_end'] or c['period_end'] != prepared['filing']['reportDate'] or c['dimensions'] or c['typed_dimension_count']:
                continue
            m = meta.facts[f['ordinal']]; uri,local = m['concept']
            roles = [role for role,name in POLICY['balance_concepts'].items() if name.split(':')[-1].casefold() == local.casefold()]
            if not roles: continue
            _need(str(int(c['entity_identifier'])) == prepared['entity'],'BALANCE_ENTITY_CONFLICT')
            context = {**c,'dimensions':dict(c['dimensions'])}; context_proof = _verified_context(native=context,metadata=meta)
            _need(meta.units.get(f['unit_ref']) == {'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False},
                  'BALANCE_UNIT_CONFLICT')
            standard = re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri) is not None
            value = _source_value(f,m)
            for role in roles:
                _need(standard == POLICY['balance_concepts'][role].startswith('us-gaap:') and uri.startswith(('http://','https://')),
                      'BALANCE_CONCEPT_NAMESPACE_CONFLICT')
                _need(role == 'equity' or Decimal(value) >= 0,'NEGATIVE_REPORTED_BALANCE')
                reports[role].append({'value':value,'decimals':m['attrs'].get('decimals'),'ordinal':f['ordinal'],
                    'context_ref':f['context_ref'],'context_proof':context_proof,'concept_qname':[uri,local]})
        _need(all(reports.values()),'BALANCE_ROLE_MISSING:'+','.join(k for k,v in reports.items() if not v))
        if kind == 'primary':
            index = _InlineTableIndex(raw); index.feed(raw.decode('utf-8-sig')); index.close()
            cells = _fact_cells(index,parsed,{r['ordinal'] for group in reports.values() for r in group})
            for role,group in reports.items():
                chosen = precision_choice(group); visible = False
                for r in group:
                    if r['ordinal'] not in cells: continue
                    table,cell = cells[r['ordinal']]; f = parsed.facts[r['ordinal']-1]
                    explicit_zero = cell['text'] in {'—','–','-'} and r['value'] == '0'
                    amount = (Decimal(0) if explicit_zero else
                              parse_numeric_claim(raw_value=cell['text'],reported_unit='USD')*Decimal(10)**int(f['scale'] or '0'))
                    row_label = disclosure.label(table['rows'][cell['origin_row_index']])
                    deduction = role == 'cost' and row_label == POLICY['bond_cost_label']
                    _need(amount == Decimal(r['value'])*(-1 if deduction else 1),'BALANCE_VISIBLE_SCALE_OR_SIGN_CONFLICT')
                    r['cell'] = {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],'row_label':row_label,
                        **{k:cell[k] for k in ['row_index','column_index','rowspan','colspan','raw_text','text']}}
                    visible |= r['value'] == chosen['value'] and r['decimals'] == chosen['decimals']
                _need(visible,'BALANCE_SELECTED_VISIBLE_AMOUNT_MISSING')
        by_kind[kind] = reports
    result = {}
    for role in POLICY['balance_concepts']:
        left,right = by_kind['xml'][role],by_kind['primary'][role]
        names = lambda rows:{(r['concept_qname'][0],r['concept_qname'][1].casefold()) for r in rows}
        _need(names(left) == names(right),'BALANCE_CROSS_DOCUMENT_NAMESPACE_CONFLICT')
        result[role] = {'xml':left,'primary':right,'chosen':precision_choice(left+right)}
    return result


def _bond_schedule(note, end, reports):
    _need(disclosure.text(note['text']).startswith("The Company's debt is as follows:"),'BOND_SCHEDULE_SCOPE_UNPROVEN')
    tables = disclosure.tables(note['text']); _need(len(tables) == 1,'BOND_SCHEDULE_NOT_UNIQUE')
    table = tables[0]; col,width,header = disclosure._period_column(table,end,False)
    _need(any(c['text'] == POLICY['scale_text'] for r in table['rows'][:header+3] for c in disclosure.origins(r)),
          'BOND_SCHEDULE_SCALE_UNPROVEN')
    state = None; parts = {'current':[],'noncurrent':[]}; totals = {}; adjustments = {}
    for row in table['rows'][header+1:]:
        label = disclosure.label(row)
        if label in {'Short-term debt:','Long-term debt:'}:
            new = 'current' if label == 'Short-term debt:' else 'noncurrent'
            _need(state is None and new == 'current' or state == 'current' and new == 'noncurrent' and 'current' in totals,
                  'BOND_SCHEDULE_SECTION_ORDER_CONFLICT'); state = new; continue
        cells = [c for c in disclosure.origins(row) if col <= c['column_index'] < col+width]
        if not cells: continue
        if all(c['text'] == POLICY['scale_text'] for c in cells): continue
        _need(state is not None and state not in totals,'BOND_AMOUNT_OUTSIDE_SECTION')
        amount = disclosure.amount(row,col,width); record = {'label':label,'value':decimal_text(value=amount),'row':row}
        if not label:
            totals[state] = record
        elif re.fullmatch(POLICY['bond_member_pattern'],label):
            _need(not adjustments and amount >= 0,'BOND_MEMBER_AFTER_ADJUSTMENT_OR_NEGATIVE')
            parts[state].append(record)
        elif label == POLICY['bond_cost_label']:
            _need(state == 'noncurrent' and 'cost' not in adjustments and amount <= 0,'BOND_COST_SCOPE_CONFLICT')
            adjustments['cost'] = record
        elif re.fullmatch(POLICY['bond_premium_pattern'],label):
            _need(state == 'noncurrent' and 'premium' not in adjustments and amount >= 0,'BOND_PREMIUM_SCOPE_CONFLICT')
            adjustments['premium'] = record
        else:
            raise BondLeaseError('BOND_LEASE_UNKNOWN_BOND_ROW:'+label)
    _need(set(totals) == {'current','noncurrent'} and all(parts.values()) and set(adjustments) == {'cost','premium'},
          'BOND_COMPONENTS_INCOMPLETE')
    _need(len({p['label'] for group in parts.values() for p in group}) == sum(len(v) for v in parts.values()),
          'BOND_MEMBER_DUPLICATED')
    current = sum(Decimal(p['value']) for p in parts['current'])
    gross_long = sum(Decimal(p['value']) for p in parts['noncurrent'])
    v = {k:Decimal(r['chosen']['value']) for k,r in reports.items()}
    _need(current == Decimal(totals['current']['value']) == v['current'],'BOND_CURRENT_RECONCILIATION_CONFLICT')
    _need(gross_long+current == v['gross'] and -Decimal(adjustments['cost']['value']) == v['cost']
          and Decimal(adjustments['premium']['value']) == v['premium'],'BOND_GROSS_ADJUSTMENT_CONFLICT')
    _need(gross_long-v['cost']+v['premium'] == Decimal(totals['noncurrent']['value']) == v['carrying']
          and v['carrying']+v['current'] == v['total_borrowing'],'BOND_CARRYING_RECONCILIATION_CONFLICT')
    return {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],'members':parts,
            'adjustments':adjustments,'totals':totals,'reported_borrowing':decimal_text(value=v['total_borrowing'])}


def _fair_value_scope(notes, end, reports):
    text = disclosure.text(notes['fair_value']['text'])
    assertion = 'The fair values of long-term debt, excluding capitalized leases, are generally estimated based on quoted market prices for identical or similar instruments'
    _need(assertion in text,'BOND_FAIR_VALUE_LEASE_SCOPE_UNPROVEN')
    compact = lambda s:re.sub(r'\s','',s)
    _need(compact(disclosure.text(notes['fair_value_table']['text'])) in compact(text),'BOND_FAIR_VALUE_TABLE_OUTSIDE_NOTE')
    tables = disclosure.tables(notes['fair_value_table']['text']); _need(len(tables) == 1,'BOND_FAIR_VALUE_TABLE_NOT_UNIQUE')
    table = tables[0]; day = date.fromisoformat(end)
    date_text = day.strftime('%B')+' '+str(day.day)+', '+str(day.year)
    rows = [r for r in table['rows'] if disclosure.label(r) == date_text]
    _need(len(rows) == 1,'BOND_FAIR_VALUE_DATE_UNPROVEN')
    columns = {}
    for role,label in [('gross','Notional Amount'),('total_borrowing','Carrying Amount'),('fair_value','Fair Value')]:
        headers = [c for r in table['rows'] for c in disclosure.origins(r) if c['text'] == label]
        _need(len(headers) == 1,'BOND_FAIR_VALUE_BASIS_COLUMN_AMBIGUOUS'); h = headers[0]
        value = disclosure.amount(rows[0],h['column_index'],h['colspan'])
        _need(value == Decimal(reports[role]['chosen']['value']),'BOND_FAIR_VALUE_RECONCILIATION_CONFLICT')
        columns[role] = {'value':decimal_text(value=value),'header':h}
    _need(any(c['text'] == POLICY['scale_text'] for r in table['rows'] for c in disclosure.origins(r)),
          'BOND_FAIR_VALUE_SCALE_UNPROVEN')
    return {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],'source_assertion':assertion,
            'target_row':rows[0],'columns':columns}


def _balance_separation(primary, end, reports, lease, supplier):
    tables = disclosure.tables(primary['raw_bytes'].decode('utf-8-sig'))
    choices = [t for t in tables if all(s in ' '.join(disclosure.label(r).casefold() for r in t['rows'])
               for s in ['total current assets','total current liabilities','cash and cash equivalents'])]
    _need(len(choices) == 1,'COMPLETE_BALANCE_SHEET_NOT_UNIQUE'); table = choices[0]
    col,width,_ = disclosure._period_column(table,end,False); selected = {}
    for role,label in POLICY['balance_sheet_labels'].items():
        rows = [r for r in table['rows'] if disclosure.label(r) == label]
        _need(len(rows) == 1,'BALANCE_CLASSIFICATION_LABEL_NOT_UNIQUE:'+role)
        amount = disclosure.amount(rows[0],col,width)
        _need(amount == Decimal(reports[role]['chosen']['value']),'BALANCE_CLASSIFICATION_AMOUNT_CONFLICT:'+role)
        selected[role] = {'value':decimal_text(value=amount),'row':rows[0]}
    values = {k:Decimal(v['chosen']['value']) for k,v in reports.items()}
    finance = {k:Decimal(v['chosen']['value']) for k,v in lease['finance_reports'].items()}
    _need(values['operating_current']+values['operating_noncurrent'] == values['operating_total']
          and finance['noncurrent']+values['operating_noncurrent'] == values['noncurrent_lease']
          and finance['total']+values['operating_total'] == values['combined_lease'], 'COMBINED_LEASE_RECONCILIATION_CONFLICT')
    _need(Decimal(lease['maturity']['totals']['total']['reported_values']['operating']) == values['operating_total']
          and Decimal(lease['maturity']['totals']['total']['reported_values']['combined']) == values['combined_lease'],
          'MATURITY_RECOGNIZED_LEASE_CLASS_CONFLICT')
    _need(finance['current']+values['operating_current'] <= values['accrued']
          and Decimal(supplier['reported_outstanding']) <= values['merchandise_payable'],
          'REPORTED_INCLUDED_LIABILITY_EXCEEDS_STATEMENT_CLASS')
    # The lease table explicitly locates finance liabilities in accrued and
    # long-term lease lines; the debt line is a different balance-sheet row.
    _need({lease['classification']['selected'][k]['statement_class'] for k in ['current','noncurrent']}
          == {POLICY['balance_sheet_labels']['accrued'],POLICY['balance_sheet_labels']['noncurrent_lease']},
          'FINANCE_LEASE_STATEMENT_CLASS_DIFFERS')
    return {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],'selected':selected,
            'separate_finance_lease_liabilities':lease['recognized_finance_lease'],
            'supplier_trade_payable':supplier['reported_outstanding'],
            'reported_combined_lease_liabilities':reports['combined_lease']['chosen']['value']}


def inspect_bond_lease_composition(*, primary, xml, prepared):
    """Reconcile composition; independent financing completeness is still pending."""
    notes = _notes(primary,xml,prepared); end = prepared['filing']['reportDate']
    reports = _balance_reports(primary,xml,prepared)
    bonds = _bond_schedule(notes['schedule'],end,reports)
    fair_value = _fair_value_scope(notes,end,reports)
    lease = inspect_separate_finance_leases(primary=primary,xml=xml,prepared=prepared)
    supplier = inspect_supplier_payment_terms(primary=primary,xml=xml,prepared=prepared)
    separation = _balance_separation(primary,end,reports,lease,supplier)
    total = Decimal(bonds['reported_borrowing'])+Decimal(lease['recognized_finance_lease'])
    return {'record_type':'BOND_AND_LEASE_COMPOSITION_COMPONENT','policy_hash':content_hash(value=POLICY),
        'source_references':lease['source_references'],'bonds':bonds,'fair_value':fair_value,
        'lease':lease,'supplier':supplier,'balance_separation':separation,'balance_reports':reports,
        'proven_composition_amount':decimal_text(value=total),'unit':'USD',
        'complete_b06_proven':False,'remaining_check':'INDEPENDENT_FINANCING_INVENTORY_AND_CURRENT_BORROWING_ASSERTIONS',
        'source_acquisition_credit':False,'production_authorized':False}


def _native_bond_members(primary, xml, prepared, bonds):
    """Bind each current note dimension to an actual current-column table row."""
    from .text_results_v2 import _ReportedFactMetadata, _verified_context
    from .governance_signals import _source_value
    from .financial_structured import _InlineTableIndex, _fact_cells
    expected = {row['label']:row['value'] for group in bonds['members'].values() for row in group}
    sources = {}
    for kind,source in [('xml',xml),('primary',primary)]:
        raw = source['raw_bytes']; parsed = parse_accession_xbrl_source(raw_bytes=raw)
        meta = _ReportedFactMetadata(); meta.feed(raw.decode('utf-8-sig')); meta.close()
        found = []
        for f in parsed.facts:
            c = parsed.contexts[f['context_ref']]; m = meta.facts[f['ordinal']]
            uri,local = m['concept']
            bond_amount = local.casefold() == 'debtinstrumentcarryingamount' or (
                local.casefold() == 'debtcurrent' and bool(c['dimensions']))
            if not bond_amount or c['period_start'] != c['period_end'] or c['period_end'] != prepared['filing']['reportDate']:
                continue
            _need(re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri) and not c['typed_dimension_count']
                  and str(int(c['entity_identifier'])) == prepared['entity'],'BOND_MEMBER_SCOPE_OR_NAMESPACE_CONFLICT')
            _need(c['dimensions'] and any(k.split(':')[-1] == 'DebtInstrumentAxis' for k in c['dimensions']),
                  'BOND_MEMBER_DIMENSION_MISSING')
            _need(meta.units.get(f['unit_ref']) == {'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False},
                  'BOND_MEMBER_UNIT_CONFLICT')
            context = {**c,'dimensions':dict(c['dimensions'])}
            proof = _verified_context(native=context,metadata=meta)
            found.append({'ordinal':f['ordinal'],'context_ref':f['context_ref'],'dimensions':dict(c['dimensions']),
                'context_proof':proof,'value':_source_value(f,m),'decimals':m['attrs'].get('decimals')})
        _need(found,'BOND_NATIVE_MEMBERS_MISSING')
        if kind == 'primary':
            index = _InlineTableIndex(raw); index.feed(raw.decode('utf-8-sig')); index.close()
            cells = _fact_cells(index,parsed,{r['ordinal'] for r in found})
            for r in found:
                _need(r['ordinal'] in cells,'BOND_MEMBER_VISIBLE_CELL_MISSING')
                table,cell = cells[r['ordinal']]; row = table['rows'][cell['origin_row_index']]
                label = disclosure.label(row); col,width,_ = disclosure._period_column(table,prepared['filing']['reportDate'],False)
                _need(label in expected and expected[label] == r['value'] and col <= cell['column_index'] < col+width,
                      'BOND_MEMBER_NOT_IN_CURRENT_COMPOSITION')
                _need(any(disclosure.label(row) == POLICY['bond_cost_label'] for row in table['rows']),
                      'BOND_MEMBER_IN_UNRELATED_TABLE')
                r['source_row'] = {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],
                    'row_index':row['row_index'],'label':label,'cell':cell}
            _need({r['source_row']['label'] for r in found} == set(expected),'BOND_NATIVE_MEMBER_ROW_SET_DIFFERS')
        groups = {}
        for r in found: groups.setdefault(content_hash(value=r['dimensions']),[]).append(r)
        sources[kind] = groups
    _need(set(sources['xml']) == set(sources['primary']),'BOND_NATIVE_DIMENSION_SETS_DIFFER')
    result = []
    for key in sorted(sources['xml']):
        left,right = sources['xml'][key],sources['primary'][key]
        chosen = precision_choice(left+right)
        _need(len({r['source_row']['label'] for r in right}) == 1,'BOND_DIMENSION_REUSED_FOR_DIFFERENT_ROWS')
        result.append({'dimensions':left[0]['dimensions'],'value':chosen['value'],
                       'xml_reports':left,'primary_reports':right})
    _need(len(result) == len(expected),'BOND_MEMBER_DIMENSION_CARDINALITY_CONFLICT')
    return result


def _reported_other_natures(notes, prepared):
    from datetime import timedelta
    from .b06_disclosure_v2 import _date_text
    end = prepared['filing']['reportDate']
    previous = (date.fromisoformat(prepared['table_input']['target_period']['period_start'])-timedelta(days=1)).isoformat()
    dates = re.escape(_date_text(end))+r' and '+re.escape(_date_text(previous))
    debt = disclosure.text(notes['debt']['text'])
    zero = re.search(r'As of '+dates+r', there were no outstanding borrowings under the agreement\.',debt)
    _need(zero is not None,'REVOLVER_CURRENT_ZERO_UNPROVEN')
    standby = re.search(r'There were \$([0-9,]+) million and \$([0-9,]+) million of other standby letters of credit outstanding as of '
        +dates+r', respectively, which reduced the available borrowing capacity to \$([0-9,]+) million and \$([0-9,]+) million, respectively\.',debt)
    _need(standby is not None,'STANDBY_CAPACITY_NATURE_UNPROVEN')
    limit = re.search(r'The Amendment reduced the asset-based credit facility to \$([0-9,]+) million',debt)
    _need(limit is not None,'REVOLVER_LIMIT_UNPROVEN')
    amount = lambda value:Decimal(value.replace(',',''))*POLICY['scale']
    _need(amount(standby[1])+amount(standby[3]) == amount(limit[1]),'STANDBY_UNUSED_CAPACITY_RECONCILIATION_CONFLICT')
    commitments = disclosure.text(notes['commitments']['text'])
    purchase = re.search(r'Our estimated total purchase obligations, which primarily consist of merchandise purchase obligations and obligations under outsourcing arrangements, software license and other service commitments, energy and other supply agreements identified by the Company and construction contracts, were approximately \$([0-9,]+) million and \$([0-9,]+) million as of '
        +dates+r', respectively\. These purchase obligations are primarily due within 1 year and recorded as liabilities when goods are received or services rendered\.',commitments)
    _need(purchase is not None,'PURCHASE_GOODS_SERVICES_RECOGNITION_UNPROVEN')
    return {'revolver_zero_statement':zero[0],'standby_statement':standby[0],
        'standby_current':decimal_text(value=amount(standby[1])),
        'unused_capacity':decimal_text(value=amount(standby[3])),
        'facility_limit':decimal_text(value=amount(limit[1])),
        'purchase_statement':purchase[0],'purchase_current':decimal_text(value=amount(purchase[1]))}


def _current_borrowing_assertions(notes, prepared, other):
    from .b06_disclosure_v2 import _Narrative, _BORROWING, _BALANCE, _MONETARY_CUE, _MONEY
    class Paragraphs(_Narrative):
        def handle_starttag(self, tag, attrs):
            if tag == 'table' and not self.depth: self.parts.append('\n')
            super().handle_starttag(tag,attrs)
        def handle_endtag(self, tag):
            super().handle_endtag(tag)
            if tag == 'table' and not self.depth: self.parts.append('\n')
    result = []
    for role in ['debt','lease_classification','fair_value','commitments']:
        note = notes[role]; parser = Paragraphs(); parser.feed(note['text']); parser.close()
        paragraphs = [' '.join(p.split()) for p in ' '.join(parser.parts).split('\n')]
        for sentence in [s for p in paragraphs for s in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])',p)]:
            if not _BORROWING.search(sentence): continue
            additional = re.search(r'\b(?:additional borrowings?|other borrowings?|other loans?|outside|not included|excluded from)\b',sentence,re.I)
            if additional and not re.search(r'\b(?:may|could|would|option)\b',sentence,re.I):
                raise BondLeaseError('BOND_LEASE_UNRESOLVED_ADDITIONAL_BORROWING:'+sentence)
            if sentence == other['revolver_zero_statement']:
                disposition = 'EXPLICIT_CURRENT_REVOLVER_ZERO'
            elif sentence.removeprefix('Other Financing Arrangements ') == other['standby_statement']:
                disposition = 'STANDBY_CREDIT_CAPACITY_NOT_BORROWED'
            elif re.search(r'\b(?:additional|outside|not included|excluded from)\b',sentence,re.I) and _BALANCE.search(sentence):
                raise BondLeaseError('BOND_LEASE_UNRESOLVED_ADDITIONAL_BORROWING:'+sentence)
            elif not _BALANCE.search(sentence) or not _MONETARY_CUE.search(sentence):
                disposition = 'NO_MONETARY_BALANCE_ASSERTION'
            elif re.fullmatch(r"[A-Za-z][A-Za-z0-9 .&'’–-]{0,100} used the net proceeds from the Notes Offering, together with cash on hand, to \(i\) fund a tender offer for certain outstanding senior notes and debentures, \(ii\) redeem approximately \$[0-9,]+ million of certain other outstanding senior notes and debentures and \(iii\) pay fees, premiums and expenses in connection with the Notes Offering, tender offer and redemption\.",sentence):
                disposition = 'USE_OF_ISSUANCE_CASH_FOR_REDEMPTION_AND_FEES'
            elif ('completed a tender offer' in sentence and 'were tendered for early settlement and purchased' in sentence
                  and not re.search(r'\b(?:remain|remains|are|is|were|was) outstanding\b',sentence,re.I)
                  and re.search(r'\bOn [A-Za-z]+ [0-9]{1,2}, [0-9]{4},',sentence)
                  and len(_MONEY.findall(sentence)) == 1
                  and re.search(r'were tendered for early settlement and purchased by [A-Za-z][A-Za-z0-9 .&\'-]{0,70}\.$',sentence)):
                # This is a completed repurchase transaction, not a statement
                # that the tendered principal remains owed at period end.
                disposition = 'COMPLETED_DEBT_REPURCHASE_ACTIVITY'
            elif re.fullmatch(r'The Company recognized (?:a \$[0-9,]+ million loss|\$[0-9,]+ million of losses) related to the extinguishment of debt on the Consolidated Statements of Income during [0-9]{4} as a result of the transactions above\.',sentence):
                disposition = 'REPORTED_INCOME_STATEMENT_DEBT_EXTINGUISHMENT_EXPENSE'
            elif re.fullmatch(r'The Company recognized \$[0-9,]+ million of losses on extinguishment of debt on the Consolidated Statements of Income during the third quarter of [0-9]{4}\.',sentence):
                disposition = 'REPORTED_INCOME_STATEMENT_DEBT_EXTINGUISHMENT_EXPENSE'
            else:
                raise BondLeaseError('BOND_LEASE_CURRENT_BORROWING_ASSERTION_UNRESOLVED:'+sentence)
            result.append({'note_role':role,'sentence':sentence,'disposition':disposition})
    return result


def _financing_inventory(primary, xml, prepared, composition, members, other):
    """Every current potential financing fact is retained, including dimensions."""
    from .text_results_v2 import _ReportedFactMetadata, _verified_context
    from .governance_signals import _source_value, _qname
    result = {}
    maturity = composition['lease']['maturity']
    future_suffixes = ['nexttwelvemonths','yeartwo','yearthree','yearfour','yearfive','afteryearfive']
    for kind,source in [('xml',xml),('primary',primary)]:
        raw = source['raw_bytes']; parsed = parse_accession_xbrl_source(raw_bytes=raw)
        meta = _ReportedFactMetadata(); meta.feed(raw.decode('utf-8-sig')); meta.close()
        represented = {r['ordinal'] for group in composition['balance_reports'].values() for r in group[kind]}
        represented.update(r['ordinal'] for group in composition['lease']['finance_reports'].values() for r in group[kind])
        represented.update(r['ordinal'] for group in composition['supplier']['native_reports'].values() for r in group[kind])
        represented.update(r['ordinal'] for member in members for r in member[kind+'_reports'])
        rows = []
        for f in parsed.facts:
            c = parsed.contexts[f['context_ref']]; m = meta.facts[f['ordinal']]; uri,local = m['concept']; name = local.casefold()
            if c['period_start'] != c['period_end'] or c['period_end'] != prepared['filing']['reportDate'] or not f['unit_ref']:
                continue
            if not re.search(r'debt|borrow|loan|lease|credit|facility|financing|funding|obligation|promissory',name): continue
            _need(str(int(c['entity_identifier'])) == prepared['entity'],'INVENTORY_ENTITY_CONFLICT')
            context = {**c,'dimensions':dict(c['dimensions'])}; _verified_context(native=context,metadata=meta)
            unit = meta.units.get(f['unit_ref']); usd = unit == {'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}
            pure = unit == {'measures':[('http://www.xbrl.org/2003/instance','pure')],'divided':False}
            standard = re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri) is not None
            if name == 'lineofcreditfacilityfairvalueofamountoutstanding' and f['text'].strip().casefold() == 'no':
                transform_uri,transform = _qname(m['attrs'].get('format',''),m['namespaces'])
                nil = [v for k,v in m['attrs'].items() if _qname(k,m['namespaces']) == ('http://www.w3.org/2001/XMLSchema-instance','nil')]
                _need(standard and usd and transform == 'fixed-zero'
                      and re.fullmatch(r'https?://www\.xbrl\.org/inlineXBRL/transformation/\d{4}-\d{2}-\d{2}',transform_uri)
                      and (not nil or nil in [['false'],['0']]) and m['attrs'].get('sign','') in {'','-'}
                      and other['revolver_zero_statement'],
                      'REVOLVER_NATIVE_WORD_ZERO_UNPROVEN')
                value = Decimal(0)
            else:
                value = Decimal(_source_value(f,m))
            disposition = None
            if f['ordinal'] in represented:
                _need(usd,'INVENTORY_REPRESENTED_UNIT_CONFLICT'); disposition = 'RECONCILED_IN_SOURCE_COMPOSITION'
            elif pure and standard and (name in {'financeleaseweightedaveragediscountratepercent','operatingleaseweightedaveragediscountratepercent',
                    'debtinstrumentinterestratestatedpercentage','debtinstrumentinterestrateeffectivepercentage'} or name.startswith('definedbenefitplanassumptions')):
                disposition = 'REPORTED_RATE_NOT_MONETARY_DEBT'
            elif usd and value == 0:
                disposition = 'EXPLICIT_CURRENT_ZERO'
            elif usd and standard and name == 'lettersofcreditoutstandingamount':
                _need(value == Decimal(other['standby_current']),'STANDBY_NATIVE_AMOUNT_CONFLICT')
                disposition = 'RECONCILED_STANDBY_CAPACITY_WITH_ZERO_REVOLVER_BORROWING'
            elif usd and standard and name == 'lineofcreditfacilityremainingborrowingcapacity':
                _need(value == Decimal(other['unused_capacity']),'UNUSED_CAPACITY_NATIVE_AMOUNT_CONFLICT')
                disposition = 'RECONCILED_UNUSED_BORROWING_CAPACITY'
            elif usd and standard and name == 'purchaseobligation':
                _need(value == Decimal(other['purchase_current']),'PURCHASE_NATIVE_AMOUNT_CONFLICT')
                disposition = 'REPORTED_GOODS_SERVICES_COMMITMENTS_RECOGNIZED_ON_RECEIPT'
            elif usd and standard and name in {'accountsnotesandloansreceivablenetcurrent','creditcardreceivables',
                    'financeleaserightofuseasset','financeleaserightofuseassetaccumulatedamortization','operatingleaserightofuseasset'}:
                disposition = 'STANDARD_REPORTED_RECEIVABLE_OR_RIGHT_OF_USE_ASSET'
            elif usd and standard and name.startswith('definedbenefitplan'):
                disposition = 'STANDARD_EMPLOYEE_BENEFIT_PROVISION_OR_EQUITY_COMPONENT'
            elif usd and standard and name == 'guaranteeobligationsmaximumexposure':
                _need(any(v.split(':')[-1] == 'PropertyLeaseGuaranteeMember' for v in c['dimensions'].values()),
                      'GUARANTEE_EXPOSURE_NATURE_UNPROVEN')
                disposition = 'MAXIMUM_PROPERTY_LEASE_GUARANTEE_EXPOSURE_NOT_REPORTED_CARRYING_DEBT'
            elif usd and not standard and name in {'leaserightofuseasset','financeleaseassetnonleasecomponent',
                    'operatingleaseassetnonleasecomponent','deferredtaxassetsleaseliabilities'}:
                disposition = 'EXPLICIT_CUSTOM_REPORTED_ASSET_OR_TAX_ASSET'
            elif usd and not standard and name.startswith(('operatinglease','lesseeoperatinglease')):
                disposition = 'EXPLICIT_CUSTOM_OPERATING_LEASE_COMPONENT_OR_COMMITMENT'
            elif usd and not standard and name == 'financeleaseliabilitynonleasecomponentnoncurrent':
                _need(value <= Decimal(composition['lease']['finance_reports']['noncurrent']['chosen']['value']),
                      'NONLEASE_COMPONENT_EXCEEDS_FINANCE_LIABILITY')
                disposition = 'NONLEASE_SUBCOMPONENT_NOT_ADDED_TO_COMBINED_REPORTED_FINANCE_LIABILITY'
            elif usd:
                for prefix,category in [('financeleaseliability','finance'),('lesseeoperatingleaseliability','operating'),('leaseliability','combined')]:
                    if not name.startswith(prefix): continue
                    suffix = name[len(prefix):]; expected = None
                    if suffix.startswith('paymentsdue') and suffix[len('paymentsdue'):] in future_suffixes:
                        i = future_suffixes.index(suffix[len('paymentsdue'):]); expected = maturity['members'][i]['reported_values'][category]
                    elif suffix == 'paymentsdue': expected = maturity['totals']['payments']['reported_values'][category]
                    elif suffix == 'undiscountedexcessamount': expected = maturity['totals']['interest']['reported_values'][category]
                    if expected is not None:
                        _need(value == Decimal(expected),'FUTURE_LEASE_TABLE_NATIVE_AMOUNT_CONFLICT')
                        disposition = 'RECONCILED_FUTURE_LEASE_PAYMENTS_OR_DISCOUNT_NOT_ADDED_TO_CARRYING'; break
                if disposition is None and standard and name.startswith('longtermdebtmaturitiesrepaymentsofprincipal'):
                    disposition = 'REPORTED_FUTURE_PRINCIPAL_MATURITY_NOT_ADDED_TO_CURRENT_CARRYING'
            _need(disposition is not None,'UNRESOLVED_FINANCING_FACT:'+local)
            rows.append({'ordinal':f['ordinal'],'concept_qname':[uri,local],'context':context,'value':decimal_text(value=value),
                         'decimals':m['attrs'].get('decimals'),'unit_definition':unit,'disposition':disposition})
        result[kind] = rows
    grouped = {}
    for kind,rows in result.items():
        groups = {}
        for row in rows:
            key = content_hash(value={'concept':[row['concept_qname'][0],row['concept_qname'][1].casefold()],
                'dimensions':row['context']['dimensions'],'unit':row['unit_definition']})
            groups.setdefault(key,[]).append(row)
        grouped[kind] = groups
    _need(set(grouped['xml']) == set(grouped['primary']),'FINANCING_INVENTORY_DOCUMENT_SETS_DIFFER')
    for key in grouped['xml']:
        precision_choice(grouped['xml'][key]+grouped['primary'][key])
    return result


def inspect_bond_debt_scope(*, primary, xml, prepared):
    composition = inspect_bond_lease_composition(primary=primary,xml=xml,prepared=prepared)
    notes = _notes(primary,xml,prepared)
    members = _native_bond_members(primary,xml,prepared,composition['bonds'])
    other = _reported_other_natures(notes,prepared)
    assertions = _current_borrowing_assertions(notes,prepared,other)
    inventory = _financing_inventory(primary,xml,prepared,composition,members,other)
    return {**composition,'record_type':'BOND_AND_SEPARATE_LEASE_DEBT_SCOPE_PROOF',
        'native_bond_members':members,'other_reported_natures':other,'borrowing_assertions':assertions,
        'independent_financing_inventory':inventory,'complete_b06_proven':True,'remaining_check':None}
