"""Original-source evidence for B06 finance-lease and supplier limitations.

This inventory identifies what the filing reports, including its actual table
labels. Finding no separate finance-lease disclosure never establishes zero;
a supplier taxonomy name never decides its debt-set disposition. A caller
cannot supply a number, relation, selected fact or source-coverage approval.
"""
from pathlib import Path
import re

from .canonical import content_hash,sha256_bytes,sha256_file,strict_json_file
from .deterministic_router import parse_accession_xbrl_source
from .financial_structured import _InlineTableIndex,_fact_cells
from .fiscal_year_labels import _DefinitionBlocks
from .governance_signals import _source_value
from .normal_annual_input import annual_period
from .normal_annual_input_v2 import exact_json_value
from .normal_candidates import _prepare_b06
from .normal_source_authority import ROOT,verify_saved_source_proofs
from .r5_b06_scope import precision_choice
from .sources import resolve_repository_file
from .text_results_v2 import _ReportedFactMetadata,_verified_context
from .b06_disclosure import label as row_label


POLICY_PATH = 'config/b06_financing_inventory_v1.json'
POLICY = strict_json_file(path=ROOT/POLICY_PATH)


class FinancingInventoryError(ValueError):
    pass


def _need(condition,reason):
    if not condition:
        raise FinancingInventoryError(reason)


def _native(source,prepared,kind):
    raw = source['raw_bytes']
    period = prepared['table_input']['target_period']
    _need(source['source_reference']['raw_asset_id'] == 'sha256:'+sha256_bytes(content=raw)
          and source['source_reference']['accession'] == prepared['filing']['accessionNumber']
          and source['source_reference']['company_id'] == prepared['company_id'],
          'FINANCING_INVENTORY_SOURCE_BINDING_CHANGED')
    _need(annual_period(raw=raw,cik=prepared['entity'],filing=prepared['filing']) == period,
          'FINANCING_INVENTORY_ANNUAL_IDENTITY_CHANGED')
    parsed = parse_accession_xbrl_source(raw_bytes=raw)
    metadata = _ReportedFactMetadata()
    metadata.feed(raw.decode('utf-8-sig'));metadata.close()
    _need(metadata.ordinal == len(parsed.facts),'FINANCING_INVENTORY_NATIVE_STREAM_DIFFERS')
    rows = []
    for fact in parsed.facts:
        meta = metadata.facts[fact['ordinal']]
        uri,name = meta['concept']
        group = ('finance_lease' if re.search(POLICY['finance_lease_concept_pattern'],name,re.I)
                 else 'supplier' if re.search(POLICY['supplier_concept_pattern'],name,re.I) else None)
        if group is None:
            continue
        context = parsed.contexts[fact['context_ref']]
        if context['period_end'] != period['period_end'] or context['dimensions'] or context['typed_dimension_count']:
            continue
        _need(str(int(context['entity_identifier'])) == prepared['entity'],'FINANCING_INVENTORY_SUBJECT_CONFLICT')
        native = {**context,'dimensions':dict(context['dimensions'])}
        proof = _verified_context(native=native,metadata=metadata)
        standard = re.fullmatch(r'https?://fasb\.org/us-gaap/[0-9]{4}',uri) is not None
        row = {'group':group,'ordinal':fact['ordinal'],'qualified_name':fact['qualified_name'],
               'concept_qname':[uri,name],'official_us_gaap_concept':standard,'context':native,
               'context_proof':proof,'reported_text':fact['text'],'kind':kind}
        if fact['unit_ref']:
            unit = metadata.units.get(fact['unit_ref'])
            row['native_unit'] = unit
            monetary = unit == {'measures':[('http://www.xbrl.org/2003/iso4217','USD')],'divided':False}
            row['unit_class'] = 'USD' if monetary else 'OTHER_UNIT_RETAINED'
            if monetary:
                row.update(value=_source_value(fact,meta),decimals=meta['attrs'].get('decimals'),context_ref=fact['context_ref'])
        else:
            row['unit_class'] = 'NONMONETARY_TEXT_OR_ENUMERATION'
        rows.append(row)
    if kind == 'primary':
        index = _InlineTableIndex(raw)
        index.feed(raw.decode('utf-8-sig'));index.close()
        cells = _fact_cells(index,parsed,{r['ordinal'] for r in rows if r['unit_class']=='USD'})
        for row in rows:
            row['raw_start_byte'] = index.fact_positions[row['ordinal']]
            if row['ordinal'] in cells:
                table,cell = cells[row['ordinal']]
                origin_row = table['rows'][cell['origin_row_index']]
                row['source_table_row'] = {'table_id':table['table_id'],'grid_sha256':table['grid_sha256'],
                    'reported_row_label':row_label(origin_row),
                    'row_cells':origin_row['cells'],
                    'amount_cell':cell}
    return rows


def inspect_financing_inventory(*,primary,xml,prepared):
    """Pure inspection used for source tests; it supplies no source credit."""
    by_kind = {kind:_native(source,prepared,kind) for kind,source in [('primary',primary),('xml',xml)]}
    text = primary['raw_bytes'].decode('utf-8-sig')
    blocks = _DefinitionBlocks(text);blocks.feed(text);blocks.close();blocks._flush()
    _need(not blocks.structural_errors and (blocks.html_count,blocks.body_count,blocks.html_closed,blocks.body_closed)==(1,1,1,1),
          'FINANCING_INVENTORY_FULL_PRIMARY_REQUIRED')
    mentioned = [{'block_index':i,**b} for i,b in enumerate(blocks.blocks)
                 if re.search(POLICY['finance_lease_text_pattern'],b['text'],re.I)]
    lease_facts = [r for rows in by_kind.values() for r in rows if r['group']=='finance_lease']
    lease_status = ('SEPARATE_NATIVE_FINANCE_LEASE_FACTS_PRESENT' if lease_facts else
                    'FINANCE_LEASE_TEXT_FOUND_WITHOUT_SEPARATE_NATIVE_FACT' if mentioned else
                    'NO_SEPARATE_FINANCE_LEASE_DISCLOSURE_FOUND')
    supplier = {}
    for kind,rows in by_kind.items():
        balances = [r for r in rows if r['concept_qname'][1].casefold()==POLICY['supplier_balance_concept'].casefold()
                    and r['context']['period_start']==r['context']['period_end']]
        enums = [r for r in rows if r['concept_qname'][1].casefold()==POLICY['supplier_statement_class_concept'].casefold()]
        _need(all(r['official_us_gaap_concept'] and r['unit_class']=='USD' for r in balances),
              'SUPPLIER_OBLIGATION_CONCEPT_OR_UNIT_UNPROVEN')
        _need(all(r['official_us_gaap_concept'] for r in enums),'SUPPLIER_STATEMENT_CLASS_CONCEPT_UNPROVEN')
        supplier[kind] = {'balance_reports':balances,'statement_class_reports':enums}
    left,right = supplier['primary']['balance_reports'],supplier['xml']['balance_reports']
    _need(bool(left)==bool(right),'SUPPLIER_PRIMARY_XML_BALANCE_MISSING')
    chosen = precision_choice(left+right) if left else None
    enum_values = [{r['reported_text'] for r in supplier[kind]['statement_class_reports']} for kind in ['primary','xml']]
    _need(enum_values[0]==enum_values[1],'SUPPLIER_PRIMARY_XML_STATEMENT_CLASS_CONFLICT')
    # Keep the literal extensible enumeration; its spelling alone cannot
    # reclassify a financing obligation as trade debt or a non-debt item.
    body = {'record_type':'B06_FINANCING_DISCLOSURE_INVENTORY','schema_version':1,
        'company_id':prepared['company_id'],'filing':prepared['filing'],'period':prepared['table_input']['target_period'],
        'source_references':[primary['source_reference'],xml['source_reference']],
        'native_fact_inventory':by_kind,'finance_lease':{'status':lease_status,'matching_blocks':mentioned,
            'zero_inferred':False,'absence_established':False},
        'supplier':{'sources':supplier,'chosen_current_balance':chosen,
            'reported_statement_classes':sorted(enum_values[0]),'debt_set_disposition':'NOT_GRANTED_BY_INVENTORY'},
        'policy_hash':content_hash(value=POLICY),'source_acquisition_credit':False,
        'debt_completeness':'NOT_PROVEN','metric_result_created':False,'production_authorized':False}
    body = exact_json_value(body)
    return {**body,'inventory_id':content_hash(value=body)}


def prepare_saved_financing_inventory(*,repo_root:Path,company_id:str):
    path = resolve_repository_file(repo_root=repo_root,repo_relative_path=POLICY_PATH)
    _need(path.read_bytes()==(ROOT/POLICY_PATH).read_bytes() and strict_json_file(path=path)==POLICY,
          'FINANCING_INVENTORY_INSTALLED_POLICY_CHANGED')
    preparation = _prepare_b06(repo_root=repo_root,company_id=company_id)
    prepared = preparation['input_binding']['prepared_annual_input']
    proofs = [*preparation['input_binding']['source_proofs'],*prepared['source_proofs']]
    proofs = list({content_hash(value=p):p for p in proofs}.values())
    admission = verify_saved_source_proofs(data_root=repo_root,proofs=proofs)
    inventory = inspect_financing_inventory(primary=preparation['primary'],xml=preparation['xml'],prepared=prepared)
    return {'prepared_input':prepared,'inventory':inventory,'source_proofs':proofs,'source_admission':admission,
            'source_records':preparation['records'],'policy_sha256':sha256_file(path=path),
            'module_sha256':sha256_file(path=Path(__file__)),'calls':{'provider':0,'paid':0,'sec':0},
            'native_run_created':False,'production_authorized':False}
