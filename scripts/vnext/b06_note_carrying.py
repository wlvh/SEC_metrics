"""Reconcile note-by-note carrying debt with an explicit no-finance-lease policy.

This is an additional source grammar, not a taxonomy alias for the historical
debt verifier. The whole debt schedule, original lease assertion, balance sheet,
related notes and independent native financing inventory are checked together.
Unknown statements or components fail. No issuer, year or source hash approves
a relationship. Source authenticity belongs to the ordinary admission layer.
"""
from decimal import Decimal
import re

from . import b06_disclosure as disclosure
from .canonical import content_hash, decimal_text, sha256_bytes, strict_json_file
from .constraints import parse_numeric_claim
from .deterministic_router import parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex, _fact_cells
from .fiscal_year_labels import _DefinitionBlocks
from .governance_signals import _source_value, _qname
from .normal_annual_input import annual_period
from .normal_annual_input_v2 import exact_json_value
from .normal_source_authority import ROOT
from .r5_b06_scope import precision_choice
from .text_results_v2 import _ReportedFactMetadata, _verified_context


POLICY_PATH = 'config/b06_note_carrying_v1.json'
POLICY = strict_json_file(path=ROOT/POLICY_PATH)


class NoteCarryingError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise NoteCarryingError('NOTE_CARRYING_'+reason)


def matches_source_grammar(raw, end):
    """Dispatch only; this grants no completeness, source or calculation credit."""
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    names = {f['qualified_name'].split(':')[-1].casefold() for f in parsed.facts
             if parsed.contexts[f['context_ref']]['period_end'] == end}
    return all(name.casefold() in names for name in POLICY['note_concepts'].values())


def _value(fact, metadata):
    if str(fact['text']).strip().casefold() != 'no':
        return _source_value(fact,metadata)
    attrs,namespaces = metadata['attrs'],metadata['namespaces']
    uri,local = _qname(attrs.get('format',''),namespaces)
    nil = [v for k,v in attrs.items() if _qname(k,namespaces) == ('http://www.w3.org/2001/XMLSchema-instance','nil')]
    _need(local == 'fixed-zero' and re.fullmatch(r'https?://www\.xbrl\.org/inlineXBRL/transformation/\d{4}-\d{2}-\d{2}',uri)
          and attrs.get('sign','') in {'','-'} and (not nil or nil in [['false'],['0']])
          and fact['qualified_name'].split(':')[-1].casefold() == 'longtermdebt', 'EXPLICIT_ZERO_TRANSFORM_UNPROVEN')
    # Only this explicit native word-zero enters the per-note reconciliation;
    # a missing monetary fact or blank cell is never replaced with zero.
    return '0'


def _source(source, prepared, kind):
    raw = source['raw_bytes']; ref = source['source_reference']
    period = prepared['table_input']['target_period']
    _need(ref['raw_asset_id'] == 'sha256:'+sha256_bytes(content=raw)
          and ref['accession'] == prepared['filing']['accessionNumber']
          and ref['company_id'] == prepared['company_id'], 'SOURCE_BINDING_CHANGED')
    _need(annual_period(raw=raw,cik=prepared['entity'],filing=prepared['filing']) == period,
          'SOURCE_IDENTITY_CONFLICT')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    meta = _ReportedFactMetadata(); meta.feed(raw.decode('utf-8-sig')); meta.close()
    _need(meta.ordinal == len(parsed.facts), 'NATIVE_STREAM_CONFLICT')
    notes, related, inventory = {}, [], []
    reports = {role:[] for role in POLICY['monetary_concepts']}
    for fact in parsed.facts:
        c = parsed.contexts[fact['context_ref']]; attrs = meta.facts[fact['ordinal']]
        uri, local = attrs['concept']
        if c['period_end'] != period['period_end']:
            continue
        if re.search(r'(?:finance|capital)lease',local,re.I) and fact['unit_ref']:
            unit = meta.units.get(fact['unit_ref'])
            _need(unit == {'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}
                  and Decimal(_value(fact,attrs)) == 0, 'FINANCE_LEASE_FACT_CONFLICT')
        if c['dimensions'] or c['typed_dimension_count']:
            potential = re.search(POLICY['potential_financing_concept_pattern']+'|deferredfinancecosts',local,re.I)
            if fact['unit_ref'] and c['period_start'] == c['period_end'] and potential:
                standard = re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri) is not None
                unit = meta.units.get(fact['unit_ref'])
                usd = unit == {'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}
                role = next((v for k,v in POLICY['dimension_concept_roles'].items() if k.casefold() == local.casefold()),None)
                record = {'ordinal':fact['ordinal'],'concept_qname':[uri,local],'context_ref':fact['context_ref'],
                          'dimensions':dict(c['dimensions']),'reported_text':fact['text']}
                if role:
                    _need(standard and usd and not c['typed_dimension_count'], 'DIMENSION_UNIT_OR_TYPE_CONFLICT')
                    _verified_context(native={**c,'dimensions':dict(c['dimensions'])},metadata=meta)
                    dims = {k.split(':')[-1]:v.split(':')[-1] for k,v in c['dimensions'].items()}
                    member = re.fullmatch(POLICY['dimension_member_pattern'],dims.get('DebtInstrumentAxis',''))
                    _need(member is not None and set(dims) == {'DebtInstrumentAxis','LongtermDebtTypeAxis'}
                          and dims['LongtermDebtTypeAxis'] == 'ConvertibleNotesPayableMember', 'DIMENSION_NOTE_SCOPE_UNPROVEN')
                    record.update(disposition='NOTE_MEMBER_REQUIRES_RECONCILIATION',role=role,year=member['year'],
                                  value=_value(fact,attrs),decimals=attrs['attrs'].get('decimals'))
                elif standard and (re.search(POLICY['different_nature_standard_pattern'],local,re.I) or local.casefold() == 'debtsecurities') and usd:
                    record['disposition'] = 'DIMENSIONED_STANDARD_DIFFERENT_NATURE'
                elif not standard and re.search(POLICY['different_nature_custom_pattern'],local,re.I) and usd:
                    record['disposition'] = 'DIMENSIONED_CUSTOM_TAX_OPERATING_OR_ASSET'
                elif local.casefold() == 'productwarrantyobligationsmeasurementinput' and unit == {
                        'measures':[('http://www.xbrl.org/2003/instance','pure')],'divided':False}:
                    record['disposition'] = 'DIMENSIONED_WARRANTY_MEASUREMENT_RATE'
                else:
                    raise NoteCarryingError('NOTE_CARRYING_UNRESOLVED_FINANCING_FACT:'+local)
                inventory.append(record)
            continue
        _need(str(int(c['entity_identifier'])) == prepared['entity'], 'SUBJECT_CONFLICT')
        standard = re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri) is not None
        roles = [k for k,v in POLICY['monetary_concepts'].items() if v.casefold() == local.casefold()]
        note_roles = [k for k,v in POLICY['note_concepts'].items() if v.casefold() == local.casefold()]
        if roles or note_roles:
            _need(standard, 'CONCEPT_NAMESPACE_CONFLICT')
            _verified_context(native={**c,'dimensions':dict(c['dimensions'])},metadata=meta)
        if note_roles:
            _need(c['period_start'] == period['period_start'], 'NOTE_PERIOD_CONFLICT')
            for role in note_roles:
                _need(role not in notes, 'NOTE_NOT_UNIQUE:'+role)
                notes[role] = fact
        potential = re.search(POLICY['potential_financing_concept_pattern'],local,re.I)
        if local.casefold().endswith('textblock') and potential:
            related.append(fact)
        if not fact['unit_ref']:
            continue
        unit = meta.units.get(fact['unit_ref'])
        usd = unit == {'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}
        if c['period_start'] != c['period_end']:
            continue
        if roles:
            _need(usd, 'UNIT_CONFLICT')
            row = {'value':_value(fact,attrs),'decimals':attrs['attrs'].get('decimals'),
                   'ordinal':fact['ordinal'],'context_ref':fact['context_ref']}
            for role in roles:
                _need(role == 'equity' or Decimal(row['value']) >= 0, 'NEGATIVE_DEBT')
                reports[role].append(row.copy())
        if not potential:
            continue
        if not usd:
            _need(not roles, 'UNIT_CONFLICT')
            if standard and local.casefold() == 'operatingleaseweightedaveragediscountratepercent' and unit == {
                    'measures':[('http://www.xbrl.org/2003/instance','pure')],'divided':False}:
                disposition = 'OPERATING_LEASE_DISCOUNT_RATE'
            else:
                disposition = 'NON_USD_OR_NONMONETARY_REQUIRES_REVIEW'
        elif Decimal(_value(fact,attrs)) == 0:
            disposition = 'EXPLICIT_CURRENT_ZERO'
        elif roles:
            disposition = 'RECONCILED_BORROWING'
        elif standard and re.search(POLICY['different_nature_standard_pattern'],local,re.I):
            disposition = 'STANDARD_ASSET_TAX_OPERATING_OR_WARRANTY'
        elif not standard and re.search(POLICY['different_nature_custom_pattern'],local,re.I):
            disposition = 'EXPLICIT_CUSTOM_TAX_OPERATING_OR_WARRANTY'
        else:
            disposition = 'UNRESOLVED'
        _need(disposition not in {'UNRESOLVED','NON_USD_OR_NONMONETARY_REQUIRES_REVIEW'},
              'UNRESOLVED_FINANCING_FACT:'+local)
        inventory.append({'ordinal':fact['ordinal'],'concept_qname':[uri,local],
            'reported_text':fact['text'],'context_ref':fact['context_ref'],'disposition':disposition})
    _need(set(notes) == set(POLICY['note_concepts']), 'REQUIRED_NOTE_MISSING')
    _need(all(reports.values()), 'REQUIRED_BALANCE_MISSING')
    if kind == 'primary':
        index = _InlineTableIndex(raw); index.feed(raw.decode('utf-8-sig')); index.close()
        cells = _fact_cells(index,parsed,{r['ordinal'] for group in reports.values() for r in group})
        for group in reports.values():
            chosen = precision_choice(group); visible = False
            for row in group:
                if row['ordinal'] not in cells:
                    continue
                table, cell = cells[row['ordinal']]; fact = parsed.facts[row['ordinal']-1]
                amount = parse_numeric_claim(raw_value=cell['text'],reported_unit='USD')*Decimal(10)**int(fact['scale'] or '0')
                label = disclosure.label(table['rows'][cell['origin_row_index']])
                deduction = label == POLICY['current_label'] and fact['qualified_name'].split(':')[-1].casefold() == POLICY['monetary_concepts']['current'].casefold()
                _need(amount == Decimal(row['value'])*(-1 if deduction else 1), 'VISIBLE_SCALE_OR_SIGN_CONFLICT')
                row['cell'] = {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],
                    **{k:cell[k] for k in ['row_index','column_index','rowspan','colspan','raw_text','text']}}
                visible |= row['value'] == chosen['value'] and row['decimals'] == chosen['decimals']
            _need(visible, 'VISIBLE_SELECTED_BALANCE_MISSING')
    return notes, related, reports, inventory


def _amount(row, column, width, scale):
    return disclosure.amount(row,column,width)*Decimal(scale)/1000000


def _composition(note, end):
    tables = disclosure.tables(note['text'])
    choices = [t for t in tables if any(disclosure.label(r) == POLICY['total_label'] for r in t['rows'])]
    _need(len(choices) == 1, 'COMPOSITION_TABLE_AMBIGUOUS')
    table = choices[0]; col,width,header = disclosure._period_column(table,end,False)
    scales = {POLICY['scale_labels'][c['text']] for r in table['rows'][:header+4]
              for c in disclosure.origins(r) if c['text'] in POLICY['scale_labels']}
    _need(len(scales) == 1, 'COMPOSITION_SCALE_UNPROVEN'); scale = next(iter(scales))
    members, inventory, totals = [], [], {}; pending = None
    for row in table['rows'][header+1:]:
        label = disclosure.label(row)
        cells = [c for c in disclosure.origins(row) if col <= c['column_index'] < col+width]
        if not cells:
            _need(not label or label == POLICY['group_label'], 'UNREAD_COMPOSITION_ROW:'+label)
            continue
        if all(c['text'] in POLICY['scale_labels'] for c in cells):
            continue
        value = _amount(row,col,width,scale)
        record = {'label':label,'value':decimal_text(value=value),'row_index':row['row_index'],'cells':cells}
        start = re.fullmatch(POLICY['member_pattern'],label)
        stop = re.fullmatch(POLICY['carrying_pattern'],label)
        if start:
            _need(pending is None and not totals and value >= 0, 'MEMBER_ORDER_CONFLICT')
            pending = {'year':start['year'],'principal':record,'adjustments':[]}
        elif label in POLICY['adjustment_labels']:
            _need(pending is not None and value <= 0 and label not in [a['label'] for a in pending['adjustments']],
                  'ADJUSTMENT_SCOPE_CONFLICT')
            pending['adjustments'].append(record)
        elif stop:
            _need(pending is not None and stop['year'] == pending['year'], 'MEMBER_CARRYING_SCOPE_CONFLICT')
            expected = Decimal(pending['principal']['value'])+sum(Decimal(a['value']) for a in pending['adjustments'])
            _need(value == expected, 'MEMBER_RECONCILIATION_FAILED')
            pending['carrying'] = record; members.append(pending); pending = None
        elif label in [POLICY['total_label'],POLICY['current_label'],POLICY['noncurrent_label']]:
            _need(pending is None and label not in totals, 'TOTAL_ORDER_CONFLICT')
            totals[label] = record
        else:
            raise NoteCarryingError('NOTE_CARRYING_UNKNOWN_COMPOSITION_ROW:'+label)
        inventory.append(record)
    _need(pending is None and members and len({m['year'] for m in members}) == len(members), 'INCOMPLETE_MEMBERS')
    _need(list(totals) == [POLICY['total_label'],POLICY['current_label'],POLICY['noncurrent_label']], 'TOTAL_SET_CONFLICT')
    values = {role:Decimal(totals[POLICY[role+'_label']]['value']) for role in ['total','current','noncurrent']}
    _need(values['total'] == sum(Decimal(m['carrying']['value']) for m in members)
          and values['current'] <= 0 and values['total']+values['current'] == values['noncurrent'], 'TOTAL_RECONCILIATION_FAILED')
    return {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],'scale':scale,
            'table_count_in_note':len(tables),'members':members,'rows':inventory,
            'balances':{k:decimal_text(value=abs(v)) for k,v in values.items()}}


def _narrative(notes, composition, end):
    from .b06_disclosure_v2 import _Narrative, _BORROWING, _BALANCE, _MONETARY_CUE, _MONEY, _date_text
    class Paragraphs(_Narrative):
        def handle_starttag(self, tag, attrs):
            if tag == 'table' and not self.depth: self.parts.append('\n')
            super().handle_starttag(tag,attrs)
        def handle_endtag(self, tag):
            super().handle_endtag(tag)
            if tag == 'table' and not self.depth: self.parts.append('\n')
    inventory = []
    for note in notes:
        parser = Paragraphs(); parser.feed(note['text']); parser.close()
        _need(parser.depth == 0, 'NARRATIVE_TABLE_TRUNCATED')
        paragraphs = [' '.join(p.split()) for p in ' '.join(parser.parts).split('\n')]
        sentences = [s for p in paragraphs for s in re.split(r'(?<=[.!?])\s+(?=[A-Z])',p)]
        for sentence in sentences:
            if not _BORROWING.search(sentence): continue
            item = {'concept':note['qualified_name'],'sentence':sentence}
            if not _BALANCE.search(sentence) or not _MONETARY_CUE.search(sentence):
                item['disposition'] = 'NO_MONETARY_BALANCE_ASSERTION'
                inventory.append(item); continue
            money = list(_MONEY.finditer(sentence))
            _need(money, 'NARRATIVE_AMOUNT_UNREADABLE')
            _need(_date_text(end) in sentence, 'NARRATIVE_PERIOD_UNPROVEN:'+sentence)
            member_matches = [m for m in composition['members'] if 'Notes due '+m['year'] in sentence]
            _need(len(member_matches) == 1 and len(money) == 1, 'UNRESOLVED_NARRATIVE_BALANCE:'+sentence)
            member = member_matches[0]
            if re.search(r'\b(?:additional|separate|exclud\w*|not included|outside)\b',sentence,re.I):
                raise NoteCarryingError('NOTE_CARRYING_UNRESOLVED_ADDITIONAL_BORROWING:'+sentence)
            if 'net carrying amount of the Notes due '+member['year'] in sentence and re.search(r'as Debt, (?:non-current|current) on the consolidated balance sheet',sentence):
                expected = Decimal(member['carrying']['value'])
                classification = 'noncurrent' if 'as Debt, non-current' in sentence else 'current'
                _need(expected <= Decimal(composition['balances'][classification]), 'NARRATIVE_CLASSIFICATION_CONFLICT')
                item['disposition'] = 'RECONCILED_MEMBER_CARRYING'
            elif 'the unamortized deferred issuance cost for the Notes due '+member['year'] in sentence:
                expected = -sum(Decimal(a['value']) for a in member['adjustments'] if a['label'] == 'Less: unamortized debt issuance costs')
                item['disposition'] = 'RECONCILED_MEMBER_ISSUANCE_COST'
            else:
                raise NoteCarryingError('NOTE_CARRYING_UNRESOLVED_NARRATIVE_BALANCE:'+sentence)
            dollars,unit,plain,plain_unit = money[0].groups()
            shown = Decimal((dollars or plain).replace(',',''))
            scale = {'':1,'thousand':1000,'million':1000000,'billion':1000000000}[(unit or plain_unit or '').casefold()]
            radius = Decimal(10)**shown.as_tuple().exponent*scale/2
            _need(abs(shown*scale-expected) <= radius, 'NARRATIVE_AMOUNT_CONFLICT')
            item.update(exact_table_value=decimal_text(value=expected),reported_value=decimal_text(value=shown*scale),
                        reported_rounding_radius=decimal_text(value=radius))
            inventory.append(item)
    return inventory


def _dimension_reconciliation(by_kind, composition):
    groups = {}
    for kind,inventory in by_kind.items():
        for row in inventory:
            if row['disposition'] == 'NOTE_MEMBER_REQUIRES_RECONCILIATION':
                groups.setdefault((row['year'],row['role']),{'xml':[],'primary':[]})[kind].append(row)
    members = {m['year']:m for m in composition['members']}; checks = []
    for (year,role),reports in sorted(groups.items()):
        _need(year in members and all(reports.values()), 'DIMENSION_MEMBER_OR_DOCUMENT_MISSING')
        member = members[year]
        if role in {'principal','carrying'}: expected = Decimal(member[role]['value'])
        else:
            label = 'Less: unamortized debt issuance costs' if role == 'issuance_cost' else 'Less: unamortized debt discount'
            amounts = [Decimal(a['value']) for a in member['adjustments'] if a['label'] == label]
            _need(len(amounts) == 1,'DIMENSION_ADJUSTMENT_MISSING'); expected = -amounts[0]
        chosen = precision_choice(reports['xml']+reports['primary'])
        _need(Decimal(chosen['value']) == expected,'DIMENSION_TABLE_AMOUNT_CONFLICT')
        checks.append({'year':year,'role':role,'value':decimal_text(value=expected),'reports':reports})
    _need(all((year,role) in groups for year in members for role in ['principal','carrying']), 'DIMENSION_MEMBER_REPORTS_INCOMPLETE')
    return checks


def _related_tables_inventory(notes):
    result = []
    for note in notes:
        name = note['qualified_name'].split(':')[-1].casefold()
        text = disclosure.text(note['text'])
        for table in disclosure.tables(note['text']):
            for row in table['rows']:
                label = disclosure.label(row)
                if not re.search(r'borrow|loan|financing|credit facilit|credit agreement|commercial paper|promissory|funding',label,re.I):
                    continue
                if name == 'scheduleofaccountsnotesloansandfinancingreceivabletextblock' and label == 'Loan receivables' and 'The principal outstanding under the Company’s loan receivables were as follows:' in text:
                    disposition = 'REPORTED_LENDER_RECEIVABLE_ASSET'
                elif name == 'debtsecuritiesavailableforsaletabletextblock' and label == 'Commercial paper' and text.startswith('Cash equivalents, restricted cash and marketable securities consist of the following:'):
                    disposition = 'REPORTED_CASH_OR_MARKETABLE_SECURITY_ASSET'
                else:
                    raise NoteCarryingError('NOTE_CARRYING_UNRESOLVED_RELATED_TABLE_ROW:'+label)
                result.append({'concept':note['qualified_name'],'table_id':table['table_id'],
                    'grid_sha256':table['grid_sha256'],'row_index':row['row_index'],'label':label,'disposition':disposition})
    return result


def inspect_note_carrying(*, primary, xml, prepared):
    """Rebuild a bounded semantic proof from two complete original documents."""
    xnotes,xrelated,xreports,xinventory = _source(xml,prepared,'xml')
    inotes,irelated,ireports,iinventory = _source(primary,prepared,'primary')
    raw = primary['raw_bytes'].decode('utf-8-sig')
    blocks = _DefinitionBlocks(raw); blocks.feed(raw); blocks.close(); blocks._flush()
    _need(not blocks.structural_errors and (blocks.html_count,blocks.body_count,blocks.html_closed,blocks.body_closed) == (1,1,1,1),
          'FULL_PRIMARY_REQUIRED')
    inline = disclosure._InlineNotes(); inline.feed(raw); inline.close()
    _need(not inline.active and not inline.excluded, 'PRIMARY_NOTE_TRUNCATED')
    compact = lambda text:re.sub(r'\s','',text)
    full_notes = []
    _need({f['qualified_name'].casefold() for f in xrelated} == {f['qualified_name'].casefold() for f in irelated}, 'RELATED_NOTE_SET_CONFLICT')
    for f in xrelated:
        matches = [n for n in irelated if n['qualified_name'].casefold() == f['qualified_name'].casefold()]
        _need(len(matches) == 1, 'RELATED_NOTE_NOT_UNIQUE')
        i = matches[0]
        spans = [n for n in inline.facts if n['attrs'].get('name','').casefold() == i['qualified_name'].casefold()
                 and n['attrs'].get('contextref') == i['context_ref']]
        normalized = disclosure.text(f['text'])
        _need(len(spans) == 1 and compact(normalized) == compact(inline.value(spans[0])), 'FULL_PRIMARY_XML_NOTE_CONFLICT')
        full_notes.append({'concept':f['qualified_name'],'xml_ordinal':f['ordinal'],'primary_ordinal':i['ordinal'],'text':normalized})
    statement = POLICY['no_finance_lease_statement']
    lease_text = disclosure.text(xnotes['leases']['text'])
    _need(lease_text.count(statement) == 1, 'EXPLICIT_NO_FINANCE_LEASE_REQUIRED')
    lease_mentions = [b for b in blocks.blocks if re.search(r'\b(?:finance|capital) leases?\b',b['text'],re.I)]
    _need(len(lease_mentions) == 1 and lease_mentions[0]['text'].startswith(statement)
          and not lease_mentions[0]['quoted_context'] and not lease_mentions[0]['linked']
          and not re.search(r'\b(?:finance|capital) leases?\b',lease_mentions[0]['text'][len(statement):],re.I),
          'NO_FINANCE_LEASE_ATTRIBUTION_OR_CONTRADICTION')
    debt_text = disclosure.text(xnotes['debt']['text']); schedule_text = disclosure.text(xnotes['schedule']['text'])
    _need(POLICY['debt_table_introduction'] in debt_text and compact(schedule_text) in compact(debt_text),
          'COMPLETE_DEBT_TABLE_SCOPE_UNPROVEN')
    composition = _composition(xnotes['schedule'],prepared['filing']['reportDate'])
    dimension_checks = _dimension_reconciliation({'xml':xinventory,'primary':iinventory},composition)
    narrative = _narrative([n for n in xrelated if n is not xnotes['schedule']],composition,prepared['filing']['reportDate'])
    related_rows = _related_tables_inventory(xrelated)
    reports = {role:{'xml':xreports[role],'primary':ireports[role],
        'chosen':precision_choice(xreports[role]+ireports[role])} for role in xreports}
    for role,value in composition['balances'].items():
        _need(value == reports[role]['chosen']['value'], 'TABLE_NATIVE_AMOUNT_CONFLICT:'+role)
    all_tables = disclosure.tables(raw)
    balances = [t for t in all_tables if all(s in ' '.join(disclosure.label(r).casefold() for r in t['rows'])
        for s in ['total current assets','total current liabilities','cash and cash equivalents'])]
    _need(len(balances) == 1, 'BALANCE_SHEET_AMBIGUOUS')
    table = balances[0]; col,width,_ = disclosure._period_column(table,prepared['filing']['reportDate'],False)
    liability_rows = []; active = False; found = set()
    for row in table['rows']:
        label = disclosure.label(row)
        if re.fullmatch(r'Stockholders[’\'] equity:',label):
            break
        if label == 'Current liabilities:': active = True
        if not active: continue
        cells = [c for c in disclosure.origins(row) if col <= c['column_index'] < col+width]
        if not cells: continue
        amount = _amount(row,col,width,composition['scale'])
        role = POLICY['balance_labels'].get(label)
        if role:
            _need(role not in found and amount == Decimal(reports[role]['chosen']['value']), 'BALANCE_CLASSIFICATION_CONFLICT')
            found.add(role); disposition = 'RECONCILED_DEBT'
        else:
            _need(label in POLICY['ordinary_balance_labels'], 'UNRESOLVED_BALANCE_LIABILITY:'+label)
            disposition = 'ORDINARY_OR_AGGREGATE_LIABILITY'
        liability_rows.append({'label':label,'value':decimal_text(value=amount),'row_index':row['row_index'],'disposition':disposition})
    _need(found == {'current','noncurrent'}, 'BALANCE_DEBT_ROLE_MISSING')
    return exact_json_value({'record_type':'B06_NOTE_CARRYING_SOURCE_PROOF','policy_hash':content_hash(value=POLICY),
        'source_references':[primary['source_reference'],xml['source_reference']], 'notes':full_notes,
        'composition':composition,'reports':reports,'narrative_inventory':narrative,
        'dimension_reconciliations':dimension_checks,
        'narrative_scope':'MONETARY_BALANCE_ASSERTIONS_IN_ALL_CURRENT_FINANCING_RELATED_NOTES',
        'related_table_inventory':related_rows,
        'native_inventory':{'xml':xinventory,'primary':iinventory},
        'balance_sheet':{'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],'rows':liability_rows},
        'finance_lease_absence':{'basis':'EXPLICIT_CURRENT_ISSUER_POLICY','statement':statement,'source_block':lease_mentions[0]},
        'source_acquisition_credit':False,'production_authorized':False})
