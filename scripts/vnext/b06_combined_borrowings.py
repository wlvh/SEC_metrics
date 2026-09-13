"""Reconcile carrying borrowings inside a combined financial-instrument note.

This component proves the current/noncurrent borrowing composition only. The
remaining finance-lease and complete-debt inventory work cannot be inferred
from its subtotal. It creates no Result, Run or source acquisition.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path
import re

from . import b06_disclosure as disclosure
from .canonical import content_hash, decimal_text, sha256_bytes, sha256_file, strict_json_file
from .constraints import parse_numeric_claim
from .deterministic_router import parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex, _fact_cells
from .fiscal_year_labels import _DefinitionBlocks
from .governance_signals import _source_value
from .normal_annual_input import annual_period
from .normal_annual_input_v2 import exact_json_value
from .normal_candidates import _prepare_b06
from .normal_source_authority import ROOT, verify_saved_source_proofs
from .r5_b06_scope import precision_choice
from .sources import resolve_repository_file, companyfacts_structured_facts
from .text_results_v2 import _ReportedFactMetadata, _verified_context


POLICY_PATH = 'config/b06_combined_borrowings_v1.json'
POLICY = strict_json_file(path=ROOT/POLICY_PATH)


class CombinedBorrowingError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise CombinedBorrowingError(reason)


def _parsed(raw, *, prepared, kind):
    period = prepared['table_input']['target_period']
    _need(annual_period(raw=raw, cik=prepared['entity'], filing=prepared['filing']) == period,
          'COMBINED_BORROWING_SOURCE_IDENTITY_CONFLICT')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    metadata = _ReportedFactMetadata()
    metadata.feed(raw.decode('utf-8-sig'))
    metadata.close()
    _need(metadata.ordinal == len(parsed.facts), 'COMBINED_BORROWING_FACT_STREAM_DIFFERS')
    notes, reports = {}, {role:[] for role in POLICY['source_monetary_concepts']}
    for fact in parsed.facts:
        meta = metadata.facts[fact['ordinal']]
        uri, local = meta['concept']
        context = parsed.contexts[fact['context_ref']]
        if context['period_end'] != period['period_end'] or context['dimensions'] or context['typed_dimension_count']:
            continue
        monetary = [role for role,name in POLICY['source_monetary_concepts'].items() if name.casefold() == local.casefold()]
        note_roles = [role for role,name in POLICY['source_note_concepts'].items() if name.casefold() == local.casefold()]
        if not monetary and not note_roles:
            continue
        _need(re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri), 'COMBINED_BORROWING_CONCEPT_NAMESPACE_CONFLICT')
        _need(str(int(context['entity_identifier'])) == prepared['entity'], 'COMBINED_BORROWING_ENTITY_CONFLICT')
        native = {**context, 'dimensions':dict(context['dimensions'])}
        context_proof = _verified_context(native=native, metadata=metadata)
        if note_roles:
            _need(context['period_start'] == period['period_start'], 'COMBINED_BORROWING_NOTE_DURATION_CONFLICT')
            for role in note_roles:
                _need(role not in notes, 'COMBINED_BORROWING_NOTE_NOT_UNIQUE:'+role)
                notes[role] = {'fact':fact, 'context':native, 'context_proof':context_proof,
                               'concept_qname':[uri,local]}
        if monetary and context['period_start'] == context['period_end']:
            unit = metadata.units.get(fact['unit_ref'])
            _need(unit == {'measures':[('http://www.xbrl.org/2003/iso4217','USD')], 'divided':False},
                  'COMBINED_BORROWING_UNIT_CONFLICT')
            value = _source_value(fact,meta)
            _need(Decimal(value) >= 0, 'COMBINED_BORROWING_NEGATIVE_RECOGNIZED_BALANCE')
            report = {'value':value, 'decimals':meta['attrs'].get('decimals'), 'ordinal':fact['ordinal'],
                      'context_ref':fact['context_ref'], 'context_proof':context_proof,
                      'concept_qname':[uri,local], 'source_unit_definition':unit}
            for role in monetary:
                reports[role].append(report)
    _need(set(notes) == set(POLICY['source_note_concepts']), 'COMBINED_BORROWING_REQUIRED_NOTE_MISSING')
    for role,items in reports.items():
        _need(items, 'COMBINED_BORROWING_REQUIRED_BALANCE_MISSING:'+role)
    if kind == 'primary':
        index = _InlineTableIndex(raw)
        index.feed(raw.decode('utf-8-sig'))
        index.close()
        cells = _fact_cells(index,parsed,{r['ordinal'] for group in reports.values() for r in group})
        for role,group in reports.items():
            chosen = precision_choice(group)
            visible_chosen = False
            for report in group:
                report['raw_start_byte'] = index.fact_positions[report['ordinal']]
                if report['ordinal'] not in cells:
                    # Retain rounded narrative reports in the precision check.
                    # They cannot replace the selected visible table balance.
                    continue
                table,cell = cells[report['ordinal']]
                fact = parsed.facts[report['ordinal']-1]
                if role == 'current_long':
                    label = re.fullmatch(POLICY['current_long_balance_label_pattern'],cell['text'])
                    _need(label is not None and label['current_year'] == period['period_end'][:4]
                          and int(label['prior_year']) == int(label['current_year'])-1,
                          'COMBINED_BORROWING_CURRENT_LONG_LABEL_PERIOD_UNPROVEN')
                    visible = parse_numeric_claim(raw_value=label['current_value'],reported_unit='USD')
                else:
                    visible = parse_numeric_claim(raw_value=cell['text'],reported_unit='USD')
                visible *= Decimal(10) ** int(fact['scale'] or '0')
                _need(visible == Decimal(report['value']), 'COMBINED_BORROWING_VISIBLE_SIGN_OR_SCALE_CONFLICT')
                # The full displayed table is separately compared with each
                # corresponding XML note and reconciled below.
                report['cell'] = {'table_id':table['table_id'], 'grid_sha256':table['grid_sha256'],
                    **{k:cell[k] for k in ['row_index','column_index','rowspan','colspan','raw_text','text']}}
                visible_chosen |= (report['value'],report['decimals']) == (chosen['value'],chosen['decimals'])
            _need(visible_chosen, 'COMBINED_BORROWING_SELECTED_VISIBLE_BALANCE_MISSING')
    return parsed,notes,reports


def _column(table, end):
    day = date.fromisoformat(end)
    header = POLICY['date_header_prefix'] + day.strftime('%B') + ' ' + str(day.day) + ','
    rows = table['rows']
    dates = [i for i,row in enumerate(rows) if any(c['text'] == header for c in disclosure.origins(row))]
    _need(len(dates) == 1, 'COMBINED_BORROWING_TABLE_DATE_HEADER_AMBIGUOUS')
    i = dates[0]
    _need(i+1 < len(rows), 'COMBINED_BORROWING_TABLE_YEAR_HEADER_MISSING')
    years = disclosure.origins(rows[i+1])
    _need(any(c['text'] == POLICY['scale_header'] for c in years), 'COMBINED_BORROWING_TABLE_SCALE_UNPROVEN')
    selected = [c for c in years if c['text'] == str(day.year)]
    _need(len(selected) == 1, 'COMBINED_BORROWING_TARGET_COLUMN_AMBIGUOUS')
    c = selected[0]
    return c['column_index'],c['colspan'],i+1


def _table(note, patterns, end, *, maturity=False, optional_roles=()):
    tables = disclosure.tables(note['fact']['text'])
    matching = [t for t in tables if any(re.fullmatch(patterns['carrying'],disclosure.label(r),re.I)
                                        for r in t['rows'])]
    _need(len(matching) == 1, 'COMBINED_BORROWING_CARRYING_TABLE_NOT_UNIQUE')
    table = matching[0]
    column,width,header = _column(table,end)
    selected,members = {},[]
    for row in table['rows'][header+1:]:
        label = disclosure.label(row)
        if not label:
            continue
        cells = [c for c in disclosure.origins(row) if column <= c['column_index'] < column+width]
        if not cells:
            continue
        roles = [role for role,pattern in patterns.items() if re.fullmatch(pattern,label,re.I)]
        member = maturity and re.fullmatch(POLICY['maturity_member_pattern'],label,re.I) is not None
        _need(len(roles) == 1 or not roles and member, 'COMBINED_BORROWING_UNRECONCILED_TABLE_ROW:'+label)
        value = disclosure.amount(row,column,width)
        displayed = ''.join(c['text'] for c in cells).replace('$','').replace(',','').strip()
        quantum = (Decimal(0) if displayed in {'—','–','-'} else
                   Decimal(10) ** Decimal(displayed.replace('(','-').replace(')','')).as_tuple().exponent
                   * POLICY['scale'])
        record = {'label':label,'value':decimal_text(value=value),'row_index':row['row_index'],
                  'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],
                  'target_cells':cells,'reported_quantum':decimal_text(value=quantum)}
        if roles:
            role = roles[0]
            _need(role not in selected, 'COMBINED_BORROWING_ROLE_DUPLICATED:'+role)
            selected[role] = record
        else:
            _need(value >= 0, 'COMBINED_BORROWING_NEGATIVE_PRINCIPAL_MEMBER')
            members.append(record)
    _need(set(patterns)-set(optional_roles) <= set(selected) <= set(patterns),
          'COMBINED_BORROWING_TABLE_ROLE_MISSING')
    if maturity:
        _need(members, 'COMBINED_BORROWING_MATURITY_MEMBERS_MISSING')
    return {'roles':selected,'members':members,'table_count_in_note':len(tables),
            'table_id':table['table_id'],'grid_sha256':table['grid_sha256']}


def inspect_combined_borrowings(*, primary, xml, prepared):
    """Pure semantic inspection; caller-created source bytes gain no trust."""
    for source in [primary,xml]:
        _need(source['source_reference']['raw_asset_id'] == 'sha256:'+sha256_bytes(content=source['raw_bytes'])
              and source['source_reference']['accession'] == prepared['filing']['accessionNumber']
              and source['source_reference']['company_id'] == prepared['company_id'],
              'COMBINED_BORROWING_SOURCE_BINDING_CHANGED')
    _,xnotes,xreports = _parsed(xml['raw_bytes'],prepared=prepared,kind='xml')
    _,inotes,ireports = _parsed(primary['raw_bytes'],prepared=prepared,kind='primary')
    inline = disclosure._InlineNotes()
    inline.feed(primary['raw_bytes'].decode('utf-8-sig'))
    inline.close()
    _need(not inline.active and not inline.excluded,'COMBINED_BORROWING_PRIMARY_NOTE_TRUNCATED')
    compact = lambda value:re.sub(r'\s','',value)
    source_notes = []
    for role,note in xnotes.items():
        xml_text = disclosure.text(note['fact']['text'])
        candidate = inotes[role]['fact']
        found = [f for f in inline.facts if f['attrs'].get('contextref') == candidate['context_ref']
                 and f['attrs'].get('name','').casefold() == candidate['qualified_name'].casefold()]
        _need(len(found) == 1 and compact(xml_text) == compact(inline.value(found[0])),
              'COMBINED_BORROWING_FULL_PRIMARY_XML_NOTE_CONFLICT:'+role)
        source_notes.append({'role':role,'xml_ordinal':note['fact']['ordinal'],
            'primary_ordinal':candidate['ordinal'],'text':xml_text,'context_proof':note['context_proof']})
    combined = compact(disclosure.text(xnotes['combined']['fact']['text']))
    for role in ['short','long']:
        _need(compact(disclosure.text(xnotes[role]['fact']['text'])) in combined,
              'COMBINED_BORROWING_NOTE_NOT_WITHIN_FINANCIAL_INSTRUMENTS:'+role)
    text = primary['raw_bytes'].decode('utf-8-sig')
    blocks = _DefinitionBlocks(text)
    blocks.feed(text)
    blocks.close()
    blocks._flush()
    rounding = [b for b in blocks.blocks if b['text'] == POLICY['rounding_statement']
                and not b['quoted_context'] and not b['linked']]
    if (len(rounding) != 1 or POLICY['rounding_statement'] not in
            disclosure.text(xnotes['accounting_policy']['fact']['text'])):
        rounding = []
    end = prepared['filing']['reportDate']
    short = _table(xnotes['short'],POLICY['short_labels'],end,optional_roles=POLICY['optional_short_roles'])
    long = _table(xnotes['long'],POLICY['long_labels'],end,maturity=True)
    reports = {role:{'xml':xreports[role],'primary':ireports[role],
                    'chosen':precision_choice(xreports[role]+ireports[role])} for role in xreports}
    s = {k:Decimal(v['value']) for k,v in short['roles'].items()}
    l = {k:Decimal(v['value']) for k,v in long['roles'].items()}
    values = {k:Decimal(v['chosen']['value']) for k,v in reports.items()}
    adjustments = [key for key in ['adjustment','fair_value_adjustment'] if key in s]
    short_rows = lambda names:[short['roles'][name] for name in names]
    long_rows = lambda names:[long['roles'][name] for name in names]
    equations = [
        ('SHORT_PRINCIPAL_COMPONENTS',s['commercial_paper']+s['current_principal']+s['other_short'],s['principal'],
         short_rows(['commercial_paper','current_principal','other_short','principal'])),
        ('SHORT_CARRYING_ADJUSTMENT',s['principal']+sum(s[k] for k in adjustments),s['carrying'],
         short_rows(['principal',*adjustments,'carrying'])),
        ('LONG_MATURITY_MEMBERS',sum(Decimal(m['value']) for m in long['members']),l['principal'],
         [*long['members'],long['roles']['principal']]),
        ('LONG_CARRYING_ADJUSTMENTS',l['principal']+l['fair_value_adjustment']+l['issuance_adjustment'],l['carrying'],
         long_rows(['principal','fair_value_adjustment','issuance_adjustment','carrying'])),
        ('SHORT_REPORTED_CARRYING',s['carrying'],values['short'],[]),
        ('LONG_REPORTED_CARRYING',l['carrying'],values['noncurrent'],[]),
        ('CURRENT_LONG_SEPARATELY_EXCLUDED',l['current_excluded'],values['current_long'],[]),
        ('OTHER_SHORT_REPORTED',s['other_short'],values['other_short'],[]),
    ]
    checks = []
    for name,left,right,operands in equations:
        radius = sum((Decimal(row['reported_quantum']) for row in operands),Decimal(0))/2 if rounding else Decimal(0)
        _need(abs(left-right) <= radius,'COMBINED_BORROWING_RECONCILIATION_FAILED:'+name)
        checks.append({'check':name,'left':decimal_text(value=left),'right':decimal_text(value=right),
                       'agreement':'EXACT' if left == right else 'DECLARED_ROUNDING_INTERVALS_OVERLAP',
                       'difference':decimal_text(value=left-right),'rounding_radius':decimal_text(value=radius)})
    body = {'record_type':'B06_BORROWING_CARRYING_RECONCILIATION','schema_version':1,
        'company_id':prepared['company_id'],'entity':prepared['entity'],'filing':prepared['filing'],
        'period_end':end,'source_references':[primary['source_reference'],xml['source_reference']],
        'policy_hash':content_hash(value=POLICY),'source_notes':source_notes,'short_table':short,'long_table':long,
        'native_reports':reports,'reconciliations':checks,'source_rounding_statement':rounding,
        'short_present_adjustment_roles':adjustments,
        'current_long_treatment':{
            'principal_is_in_short_composition':short['roles']['current_principal'],
            'carrying_is_explicitly_outside_long_total':long['roles']['current_excluded'],
            'current_long_is_not_added_separately':True,
            'costs_are_reconciled_at_each_reported_total':True},
        'proven_borrowing_subtotal':decimal_text(value=values['short']+values['noncurrent']),
        'unit':POLICY['unit'],'proven_classes':POLICY['proven_classes'],
        'not_evaluated_classes':POLICY['remaining_classes'],'debt_completeness':'NOT_PROVEN',
        'metric_result_created':False,'source_acquisition_credit':False,'production_authorized':False}
    body = exact_json_value(body)
    return {**body,'reconciliation_id':content_hash(value=body)}


def prepare_saved_combined_borrowings(*, repo_root:Path, company_id:str):
    path = resolve_repository_file(repo_root=repo_root,repo_relative_path=POLICY_PATH)
    _need(path.read_bytes() == (ROOT/POLICY_PATH).read_bytes() and strict_json_file(path=path) == POLICY,
          'COMBINED_BORROWING_INSTALLED_POLICY_CHANGED')
    preparation = _prepare_b06(repo_root=repo_root,company_id=company_id)
    prepared = preparation['input_binding']['prepared_annual_input']
    proofs = [*preparation['input_binding']['source_proofs'],*prepared['source_proofs']]
    proofs = list({content_hash(value=p):p for p in proofs}.values())
    admission = verify_saved_source_proofs(data_root=repo_root,proofs=proofs)
    proof = inspect_combined_borrowings(primary=preparation['primary'],xml=preparation['xml'],prepared=prepared)
    source = preparation['facts']
    facts = companyfacts_structured_facts(raw_bytes=source['raw_bytes'],source_reference=source['source_reference'],
        approved_concepts=['us-gaap:'+c for c in POLICY['source_monetary_concepts'].values()],
        allowed_ciks=[prepared['entity']],include_instant=True)
    same_filing = {}
    for role,concept in POLICY['source_monetary_concepts'].items():
        matches = [f for f in facts if f['concept'] == 'us-gaap:'+concept
                   and f['accession'] == prepared['filing']['accessionNumber']
                   and f['entity'] == prepared['entity']
                   and f['period_start'] == f['period_end'] == proof['period_end']]
        values = {r['value'] for kind in ['xml','primary'] for r in proof['native_reports'][role][kind]}
        _need(matches and all(f['unit'] == 'USD' and f['value'] in values for f in matches),
              'COMBINED_BORROWING_COMPANYFACTS_CONFLICT_OR_MISSING:'+role)
        same_filing[role] = matches
    return {'prepared_input':prepared,'reconciliation':proof,'source_proofs':proofs,
            'source_admission':admission,'source_records':preparation['records'],
            'same_filing_companyfacts':same_filing,
            'policy_sha256':sha256_file(path=path),'module_sha256':sha256_file(path=Path(__file__)),
            'calls':{'provider':0,'paid':0,'sec':0},'native_run_created':False,'production_authorized':False}
