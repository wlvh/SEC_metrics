"""Ordinary lodging statistics selected by source headers and scope geometry.

The whole source table set is rebuilt. This deterministic source adapter does
not manufacture an AI response, reuse a qualification response, or modify the
historical AI-table Specs. The explicit year column and its local qualifiers
are checked separately from the annual filing identity.
"""
from decimal import Decimal
from pathlib import Path
import re

from .annual_update import saved_source
from .canonical import content_hash,decimal_text,sha256_bytes,sha256_file,strict_json_file
from .composite_scope import index_source_structure
from .fiscal_year_labels import _DefinitionBlocks
from .normal_annual_input import annual_period
from .normal_annual_input_v2 import prepare_saved_annual_input,exact_json_value
from .normal_source_authority import ROOT,verify_saved_source_proofs
from .scope_contract import exact_enum_alias,scope_satisfies_contract
from .sources import raw_blob_record,source_reference_record,resolve_repository_file
from .specs import compile_spec_file
from .table_grid import build_table_grid,_resolve_verified_cell
from .text_coverage import _byte_offsets


POLICY_PATH='config/ordinary_lodging_table_v1.json'
POLICY=strict_json_file(path=ROOT/POLICY_PATH)
_FIELDS=('row_index','column_index','origin_row_index','origin_column_index','rowspan','colspan')


class LodgingSourceError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise LodgingSourceError(reason)


def _cells(row):
    return [c for c in row['cells'] if c['is_origin'] and c['text']]


def _label(cell,alias):
    return re.fullmatch(re.escape(alias)+POLICY['scope_footnote_suffix_pattern'],cell['text']) is not None


def _witness(asset,table,cell):
    locator={'derived_asset_id':asset['derived_asset_id'],'table_id':table['table_id'],**{k:cell[k] for k in _FIELDS}}
    _need(_resolve_verified_cell(derived_asset=asset,locator=locator)['raw_text']==cell['raw_text'],
          'LODGING_CELL_REPLAY_DIFFERS')
    return {'locator':locator,'raw_text':cell['raw_text'],'text':cell['text'],'grid_sha256':table['grid_sha256']}


def _without_pagination(blocks):
    kept,omitted=[],[]
    i=0
    while i<len(blocks):
        if (i+1<len(blocks) and re.fullmatch(r'[0-9]+',blocks[i]['text'])
                and blocks[i+1]['text']=='Table of Contents' and blocks[i+1]['linked']):
            omitted.extend(blocks[i:i+2]);i+=2
        else:
            kept.append(blocks[i]);i+=1
    return kept,omitted


def _footnote_members(text,terms):
    match=re.fullmatch(r'\(([1-9][0-9]?)\)\s*Includes (.+)\.',text)
    _need(match is not None,'LODGING_UNSUPPORTED_LOCAL_TABLE_NOTE')
    remaining=match[2];members=[]
    while remaining:
        hits=[term for term in terms if remaining.startswith(term)
              and (len(remaining)==len(term) or remaining[len(term):].startswith((', ',' and ')))]
        _need(len(hits)==1 and hits[0] not in members,'LODGING_GEOGRAPHIC_FOOTNOTE_MEMBER_UNPROVEN')
        term=hits[0];members.append(term);remaining=remaining[len(term):]
        if remaining:
            separator=next((s for s in [', and ', ', ', ' and '] if remaining.startswith(s)),None)
            _need(separator is not None,'LODGING_FOOTNOTE_LIST_SEPARATOR_UNSUPPORTED')
            remaining=remaining[len(separator):]
            _need(bool(remaining),'LODGING_FOOTNOTE_LIST_TRUNCATED')
    return match[1],members


def _source_context(raw,structure,table_index,blocks,period):
    table=structure['tables'][table_index]
    before=[b for b in blocks if b['end_byte']<=table['start_byte'] and b['text'].strip()]
    previous_end=structure['tables'][table_index-1]['end_byte'] if table_index else 0
    headings=[b for b in before if b['start_byte']>=previous_end and b['text']==POLICY['section_heading']
              and not b['quoted_context'] and not b['linked']]
    _need(len(headings)==1,
          'LODGING_STATISTICS_SECTION_NOT_BOUND')
    heading=headings[0]
    fragments,omitted=_without_pagination([b for b in before if b['start_byte']>heading['end_byte']])
    introduction={'text':' '.join(b['text'] for b in fragments),'blocks':fragments,'pagination_omitted':omitted}
    intro=re.fullmatch(POLICY['table_introduction_pattern'],introduction['text'])
    _need(1<=len(fragments)<=2 and intro is not None and not any(b['quoted_context'] or b['linked'] for b in fragments)
          and int(intro['year'])==period['fiscal_year'] and int(intro['prior'])==period['fiscal_year']-1,
          'LODGING_TABLE_PERIOD_AND_OPERATING_INTRODUCTION_UNPROVEN')
    preface=[b for b in blocks if previous_end<=b['start_byte']<table['start_byte']]
    after=[b for b in blocks if b['start_byte']>=table['end_byte']]
    stop=next((b['start_byte'] for b in after if b['emphasized'] and not re.match(r'^\([0-9]+\)',b['text'])),len(raw))
    notes=[b for b in after if b['start_byte']<stop]
    notes,note_pagination=_without_pagination(notes)
    _need(all(not n['quoted_context'] for n in notes),'LODGING_QUOTED_TABLE_NOTE')
    _need(not any(re.search(POLICY['period_qualifier_pattern'],b['text'],re.I) for b in preface+notes),
          'LODGING_LOCAL_MEASUREMENT_PERIOD_QUALIFIER')
    performance=[i for i,b in enumerate(before) if b['text']==POLICY['performance_heading'] and not b['quoted_context']]
    _need(performance,'LODGING_PERFORMANCE_DEFINITION_MISSING')
    definitions=before[performance[-1]+1:]
    currency=[b for b in definitions if POLICY['currency_declaration'] in b['text'] and not b['quoted_context']]
    _need(len(currency)==1,'LODGING_US_DOLLAR_DEFINITION_NOT_UNIQUE')
    return {'heading':heading,'introduction':introduction,'local_preface':preface,'local_notes':notes,'currency_definition':currency[0],
            'table_source_span':table,'note_pagination_omitted':note_pagination}


def _candidate(asset,table,period,specs,context):
    header_names={*POLICY['metric_headers'].values(),POLICY['other_measure_header']}
    header_rows=[r for r in table['rows'] if {c['text'] for c in _cells(r)}==header_names and len(_cells(r))==3]
    _need(len(header_rows)==1,'LODGING_MEASURE_HEADER_NOT_UNIQUE')
    header=header_rows[0];measures={c['text']:c for c in _cells(header)}
    _need(not any(_cells(r) for r in table['rows'][:header['row_index']]),'LODGING_UNSUPPORTED_HEADER_QUALIFIER')
    year_index=header['row_index']+1
    _need(year_index<len(table['rows']),'LODGING_YEAR_HEADER_MISSING')
    years=_cells(table['rows'][year_index]);year=period['fiscal_year'];columns={}
    _need(len(years)==6,'LODGING_YEAR_AND_CHANGE_HEADER_SET_DIFFERS')
    for name,measure in measures.items():
        start,end=measure['column_index'],measure['column_index']+measure['colspan']
        owned=[c for c in years if start<=c['column_index'] and c['column_index']+c['colspan']<=end]
        current=[c for c in owned if c['text']==str(year)]
        change=[c for c in owned if re.fullmatch(POLICY['comparison_header_pattern'],c['text'])]
        _need(len(owned)==2 and len(current)==len(change)==1,'LODGING_CURRENT_YEAR_COLUMN_NOT_UNIQUE:'+name)
        _need(int(re.fullmatch(POLICY['comparison_header_pattern'],change[0]['text'])[1])==year-1,
              'LODGING_COMPARISON_YEAR_CONFLICT')
        columns[name]=current[0]
    claims=specs['B10']['compiled']['required_claims'];contract=specs['B10']['compiled']['scope_contract']
    aliases={dimension:contract['exact_enum_aliases'][dimension][claims[dimension]]
             for dimension in contract['required_dimensions']}
    _need(all(len(values)==1 for values in aliases.values()),'LODGING_SCOPE_ALIAS_GRAMMAR_NOT_UNIQUE')
    population=aliases['property_population'][0];operating=aliases['operating_scope'][0]
    _need(population==operating,'LODGING_SHARED_POPULATION_SCOPE_LABEL_REQUIRED')
    groups=[]
    for row in table['rows'][year_index+1:]:
        cells=_cells(row)
        if len(cells)==1 and cells[0]['column_index']<min(c['column_index'] for c in measures.values()):groups.append((row,cells[0]))
    chosen=[(row,c) for row,c in groups if _label(c,population)]
    _need(len(chosen)==1,'LODGING_REQUIRED_POPULATION_SECTION_NOT_UNIQUE')
    _need(groups and not any(_cells(r) for r in table['rows'][year_index+1:groups[0][0]['row_index']]),
          'LODGING_UNSUPPORTED_COLUMN_QUALIFIER')
    group,scope_cell=chosen[0]
    group_end=min([row['row_index'] for row,c in groups if row['row_index']>group['row_index']]+[table['row_count']])
    geography=aliases['geography'][0]
    world=[]
    for row in table['rows'][group['row_index']+1:group_end]:
        cells=_cells(row)
        if cells and cells[0]['column_index']==scope_cell['column_index'] and _label(cells[0],geography):world.append((row,cells[0]))
    _need(len(world)==1,'LODGING_WORLDWIDE_ROW_NOT_UNIQUE')
    row,geo_cell=world[0]
    geography_cells=[_cells(r)[0] for r in table['rows'][group['row_index']+1:group_end] if _cells(r)]
    names={re.sub(r'\s*\([1-9][0-9]?\)$','',c['text']):c for c in geography_cells}
    _need(len(names)==len(geography_cells),'LODGING_GEOGRAPHY_ROW_DUPLICATED')
    domestic,international=POLICY['domestic_region_label'],POLICY['international_total_label']
    _need({geography,domestic,international}<=set(names),'LODGING_WORLDWIDE_COMPOSITION_ROWS_MISSING')
    expected_notes={}
    for name,members in [(geography,{domestic,international}),(international,set(names)-{geography,domestic,international})]:
        marker=re.search(r'\(([1-9][0-9]?)\)$',names[name]['text'])
        _need(marker is not None and marker[1] not in expected_notes and members,'LODGING_GEOGRAPHIC_NOTE_LINK_UNPROVEN')
        expected_notes[marker[1]]=members
    found_notes={}
    for note in context['local_notes']:
        marker,members=_footnote_members(note['text'],names)
        _need(marker in expected_notes and marker not in found_notes and set(members)==expected_notes[marker],
              'LODGING_GEOGRAPHIC_FOOTNOTE_COMPOSITION_DIFFERS')
        found_notes[marker]={'members':members,'source_note':note}
    _need(set(found_notes)==set(expected_notes),'LODGING_GEOGRAPHIC_FOOTNOTE_MISSING')
    normalized={d:exact_enum_alias(contract=contract,dimension=d,raw_value=a[0]) for d,a in aliases.items()}
    _need(scope_satisfies_contract(contract=contract,normalized_scope=normalized),'LODGING_SCOPE_CONTRACT_FAILED')
    facts={}
    for metric,name in POLICY['metric_headers'].items():
        column=columns[name];start,end=column['column_index'],column['column_index']+column['colspan']
        entries=[c for c in _cells(row) if start<=c['column_index'] and c['column_index']+c['colspan']<=end]
        numbers=[c for c in entries if re.fullmatch(POLICY['number_pattern'],c['text'])]
        unit='%' if metric=='B10' else '$'
        units=[c for c in entries if c['text']==unit]
        _need(len(entries)==2 and len(numbers)==len(units)==1,'LODGING_AMOUNT_AND_UNIT_NOT_UNIQUE:'+metric)
        amount=Decimal(numbers[0]['text'].replace(',',''))
        _need(amount>=0 and (metric!='B10' or amount<=100),'LODGING_REPORTED_VALUE_OUT_OF_RANGE')
        value=amount/100 if metric=='B10' else amount
        facts[metric]={'metric_id':metric,'semantic_role':POLICY['metric_roles'][metric],
            'value':decimal_text(value=value),'unit':specs[metric]['compiled']['canonical_unit'],
            'reported_value':numbers[0]['text'],'reported_unit':unit,'scope':normalized,
            'period':period,'period_basis':POLICY['period_basis'],
            'source_witnesses':{'amount':_witness(asset,table,numbers[0]),'unit':_witness(asset,table,units[0]),
                'year':_witness(asset,table,column),'measure':_witness(asset,table,measures[name]),
                'population_and_operating_scope':_witness(asset,table,scope_cell),'geography':_witness(asset,table,geo_cell)}}
    return {'facts':facts,'context':context,'geographic_footnotes':found_notes,
            'table_id':table['table_id'],'scope_section_row':group['row_index'],
            'worldwide_row':row['row_index'],'year_header_row':year_index}


def inspect_lodging_table_source(*,raw,blob,reference,filing,company_id,cik,period):
    _need(reference['company_id']==company_id and reference['raw_asset_id']==blob['raw_asset_id']=='sha256:'+sha256_bytes(content=raw)
          and reference['accession']==filing['accessionNumber'],'LODGING_SOURCE_BINDING_CONFLICT')
    source_period=annual_period(raw=raw,cik=cik,filing=filing)
    _need(all(source_period[k]==period[k] for k in ['period_start','period_end']),'LODGING_SOURCE_ANNUAL_PERIOD_CONFLICT')
    specs={m:compile_spec_file(path=ROOT/p,dependency_specs={}) for m,p in POLICY['metric_specs'].items()}
    _need(specs['B10']['compiled']['scope_contract']==specs['B11']['compiled']['scope_contract']
          and specs['B10']['compiled']['required_claims']==specs['B11']['compiled']['required_claims'],
          'LODGING_TWO_METRIC_SCOPE_CONTRACTS_DIFFER')
    text=raw.decode('utf-8-sig');parser=_DefinitionBlocks(text);parser.feed(text);parser.close();parser._flush()
    _need(not parser.structural_errors and (parser.html_count,parser.body_count,parser.html_closed,parser.body_closed)==(1,1,1,1),
          'LODGING_FULL_PRIMARY_REQUIRED')
    offsets=_byte_offsets(text,[p for b in parser.blocks for p in (b['start'],b['end'])])
    blocks=[]
    for block in parser.blocks:
        blocks.append({**block,'start_byte':offsets[block['start']],'end_byte':offsets[block['end']]})
    structure=index_source_structure(source_bytes=raw)
    asset=build_table_grid(html_bytes=raw,parent_raw_asset_ids=[blob['raw_asset_id']],storage_uri='ordinary/lodging/full-table-grid.json')
    _need(len(asset['tables'])==len(structure['tables']),'LODGING_TABLE_ORDER_INDEX_DIFFERS')
    candidates=[];unresolved=[]
    for index,table in enumerate(asset['tables']):
        texts=[c['text'] for row in table['rows'] for c in _cells(row)]
        if not all(name in texts for name in POLICY['metric_headers'].values()):continue
        try:
            _need(not any(re.search(POLICY['period_qualifier_pattern'],s,re.I) for s in texts),'LODGING_TABLE_HAS_PERIOD_QUALIFIER')
            context=_source_context(raw,structure,index,blocks,period)
            candidates.append(_candidate(asset,table,period,specs,context))
        except ValueError as error:
            contract=specs['B10']['compiled']['scope_contract']
            aliases=contract['exact_enum_aliases']
            plausible=(str(period['fiscal_year']) in texts and any(
                _label(c,a) for r in table['rows'] for c in _cells(r) for a in aliases['property_population']['comparable'])
                and any(_label(c,a) for r in table['rows'] for c in _cells(r) for a in aliases['geography']['worldwide']))
            unresolved.append({'table_id':table['table_id'],'reason':str(error),'plausible_same_target':plausible})
    _need(len(candidates)==1,'LODGING_MATCHING_TABLE_NOT_UNIQUE:'+str(unresolved))
    _need(not any(t['plausible_same_target'] for t in unresolved),'LODGING_UNRESOLVED_COMPETING_TARGET:'+str(unresolved))
    body={'record_type':'ORDINARY_DETERMINISTIC_LODGING_SOURCE','company_id':company_id,'filing':filing,
        'source_reference':reference,'source_blob':blob,'table_count':len(asset['tables']),
        'derived_asset':asset,'selection':candidates[0],'other_measure_tables':unresolved,
        'original_spec_closures':{m:s['spec_closure_hash'] for m,s in specs.items()},
        'policy_hash':content_hash(value=POLICY),'source_acquisition_credit':False,'qualification_credit':False,
        'ai_response_used':False,'native_run_created':False,'production_authorized':False}
    body=exact_json_value(body)
    return {**body,'component_id':content_hash(value=body)}


def prepare_saved_lodging_source(*,repo_root:Path,company_id:str):
    path=resolve_repository_file(repo_root=repo_root,repo_relative_path=POLICY_PATH)
    _need(path.read_bytes()==(ROOT/POLICY_PATH).read_bytes() and strict_json_file(path=path)==POLICY,'LODGING_INSTALLED_POLICY_CHANGED')
    prepared=prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    _need(prepared['subject_policy']['mode']=='CONTINUOUS_PRIMARY' and not prepared['amendments'],'LODGING_SOURCE_SUBJECT_OR_AMENDMENT_UNRESOLVED')
    admission=verify_saved_source_proofs(data_root=repo_root,proofs=prepared['source_proofs'])
    inp=prepared['table_input'];saved=saved_source(repo_root=repo_root,url=inp['source_url'],accession=inp['accession'])
    proof=saved['proof'];blob=raw_blob_record(repo_root=repo_root,repo_relative_path=proof['request_repo_relative_path'],media_type='text/html')
    reference=source_reference_record(raw_blob=blob,company_id=company_id,source_url=inp['source_url'],accession=inp['accession'],
        document_name=inp['document_name'],source_role='target_primary',request_attempt_id=proof['request_attempt_id'])
    result=inspect_lodging_table_source(raw=saved['raw'],blob=blob,reference=reference,filing=prepared['filing'],company_id=company_id,
        cik=prepared['entity'],period=inp['target_period'])
    return {'prepared_input':prepared,'source_proofs':prepared['source_proofs'],'source_admission':admission,'component':result,
            'module_sha256':sha256_file(path=Path(__file__)),'calls':{'provider':0,'paid':0,'sec':0},'production_authorized':False}
