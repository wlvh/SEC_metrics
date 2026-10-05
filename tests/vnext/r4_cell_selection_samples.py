"""Read-only, field-level audit of the nine original wires; never JSON repair."""
import json
import re
from pathlib import Path
from vnext.canonical import sha256_bytes
from vnext.cell_selection import reference_map, period_evidence, period_matches_claim, unit_evidence, _column_scope
from vnext.evidence import _bounded_raw_value_match
from vnext.scope_contract import exact_enum_alias


def schema_check(value, schema):
    """Test-only evaluator of the exact keyword subset in saved R4 schemas."""
    allowed={'type','properties','required','additionalProperties','items','anyOf','enum','const',
             'minLength','minimum','minItems','maxItems','uniqueItems','description'}
    if set(schema)-allowed: raise AssertionError('Unsupported saved schema keyword')
    if 'anyOf' in schema:
        return any(schema_check(value,s) for s in schema['anyOf'])
    types={'object':dict,'array':list,'string':str,'integer':int,'boolean':bool}
    if 'type' in schema and type(value) is not types[schema['type']]: return False
    if 'const' in schema and value!=schema['const']: return False
    if 'enum' in schema and value not in schema['enum']: return False
    if isinstance(value,str) and len(value)<schema.get('minLength',0): return False
    if type(value) is int and value<schema.get('minimum',value): return False
    if type(value) is dict:
        props=schema.get('properties',{})
        if not set(schema.get('required',[])).issubset(value): return False
        if schema.get('additionalProperties') is False and set(value)-set(props): return False
        return all(schema_check(v,props[k]) for k,v in value.items() if k in props)
    if type(value) is list:
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',len(value)): return False
        if schema.get('uniqueItems') and len({json.dumps(v,sort_keys=True) for v in value})!=len(value): return False
        return all(schema_check(v,schema.get('items',{})) for v in value)
    return True


def field(fragment,name):
    match=re.search(r'"'+re.escape(name)+r'"\s*:\s*("(?:\\.|[^"\\])*"|-?[0-9]+)',fragment)
    return None if match is None else json.loads(match[1])


def locator_fragments(text):
    # Flat position fields are individually readable even when another string
    # in the response is malformed. No reconstructed Candidate is produced.
    rows=[]
    for m in re.finditer(r'"locator"\s*:\s*\{([^{}]*)\}',text):
        rows.append({'offset':m.start(),'fields':{k:field(m[1],k) for k in
            ('derived_asset_id','table_id','row_index','column_index','origin_row_index','origin_column_index','rowspan','colspan')}})
    return rows


def _claim_segments(text):
    start=text.find('"competing_candidates"')
    if start<0: return text,[]
    tail=text[start:]
    points=[m.start() for m in re.finditer(r'\{\s*"claimed_period"\s*:',tail)]
    return text[:start],[tail[a:b] for a,b in zip(points,points[1:]+[len(tail)])]


def layered_audit(root):
    sample=root/'tests/fixtures/r4_cell_selection'
    meta=json.loads((sample/'provenance.json').read_bytes());rows=[]
    for entry in meta['cases']:
        data={}
        for kind,binding in entry['files'].items():
            raw=(sample/binding['path']).read_bytes()
            assert len(raw)==binding['size'] and sha256_bytes(content=raw)==binding['sha256']
            data[kind]=json.loads(raw)
        wire,request=data['wire.json'],data['request.json']
        text=wire['choices'][0]['message']['content']
        reader=json.loads(request['messages'][1]['content'])
        scope=json.loads((root/'docs/r4_v3/qualified_cases'/entry['fixture_id']/'source_scope.json').read_bytes())
        refs=reference_map(reader);cells=list(refs.values())
        cell_by_pos={(c['locator']['table_id'],c['locator']['row_index'],c['locator']['column_index']):c for c in cells}
        row={'fixture_id':entry['fixture_id'],'original_native_status':entry['original_native_status'],
            'native_first_failure':entry['first_failure'],'audit_tier':'READ_ONLY_FIELDS_NOT_ADDITIONAL_EXECUTION_TERMINALS',
            'response_sha256':sha256_bytes(content=text.encode()),'finish_reason':wire['choices'][0]['finish_reason'],
            'channel':{k:request[k] for k in ('response_format','stream','temperature','thinking')}}
        try:
            parsed=json.loads(text);row['syntax']='PASS';row['saved_json_schema']='PASS' if schema_check(parsed,data['schema.json']) else 'FAIL'
        except json.JSONDecodeError as error:
            row['syntax']='FAIL';row['saved_json_schema']='NOT_EVALUATED';row['syntax_error']={'message':error.msg,'offset':error.pos}
        ids=re.findall(r'"derived_asset_id"\s*:\s*"([^"\\]*)"',text)
        row['identity']={'expected':reader['full_derived_asset_id'],'observed_strings':sorted(set(ids)),
            'status':'PASS' if ids and all(v==reader['full_derived_asset_id'] for v in ids) else 'FAIL'}
        selected,competitors=_claim_segments(text)
        def value_check(fragment):
            locs=locator_fragments(fragment)
            if not locs:return {'status':'UNREADABLE_POSITION'}
            position=locs[0]['fields'];cell=cell_by_pos.get((position['table_id'],position['row_index'],position['column_index']))
            if cell is None:return {'status':'UNKNOWN_POSITION','model_position':position}
            value=field(fragment,'claimed_raw_value')
            return {'status':'PASS' if value==cell['text'] else 'FAIL','declared_value':value,
                'source_text':cell['text'],'source_cell':cell,'model_position':position,
                'geometry_matches':all(position[k]==cell['locator'][k] for k in ('origin_row_index','origin_column_index','rowspan','colspan'))}
        row['selection']=value_check(selected)
        selected_cell=row['selection'].get('source_cell')
        relevant=[] if selected_cell is None else [c for c in cells if c['locator']['table_id']==selected_cell['locator']['table_id']]
        scope_claims=[]
        match=re.search(r'"claimed_scope"\s*:',selected)
        if match:
            try: scope_claims=json.JSONDecoder().raw_decode(selected[match.end():].lstrip())[0]
            except json.JSONDecodeError: pass
        label_text=selected[selected.find('"scope_evidence_locators"'):]
        labels=locator_fragments(label_text)
        comparisons=[]
        for claim in scope_claims:
            actual=[]
            for l in labels:
                p=l['fields'];c=cell_by_pos.get((p['table_id'],p['row_index'],p['column_index']))
                if c:actual.append({'source_cell':c,'literal_present':_bounded_raw_value_match(raw_text=c['raw_text'],raw_value=claim['raw_value'])})
            comparisons.append({'claim':claim,'source_checks':actual,
                'exact_alias':exact_enum_alias(contract=reader['task_contract']['scope_contract'],dimension=claim['dimension'],raw_value=claim['raw_value'])})
        row['scope_labels']=comparisons
        row['competitors']=[]
        for fragment in competitors:
            check=value_check(fragment);cell=check.get('source_cell')
            if cell:
                own=period_evidence(relevant,cell);check['period']={'declared':field(fragment,'claimed_period'),'source':own,
                    'consistent':period_matches_claim(own,field(fragment,'claimed_period')) if own['kind'] in ('YEAR','COLUMN_DATE') else None}
                try: unit=unit_evidence(relevant,cell,selected_cell,scope,reader['scoped_transport_contract']['reported_unit_contract'])
                except ValueError as error: unit={'unit':'UNKNOWN','reason':str(error)}
                check['unit']={'declared':field(fragment,'claimed_reported_unit'),'source':unit,
                    'consistent':unit['unit']==field(fragment,'claimed_reported_unit') if unit['unit']!='UNKNOWN' else None}
            row['competitors'].append(check)
        if selected_cell:
            target=scope['target_locator'];row['certified_target_source_cell']=cell_by_pos[(target['table_id'],target['row_index'],target['column_index'])]
            row['same_row_cells_with_declared_value']=[{'cell':c,'column_scope':_column_scope(relevant,c,reader['task_contract']['scope_contract']['exact_enum_aliases'])}
                for c in relevant if c['locator']['row_index']==selected_cell['locator']['row_index'] and c['text']==row['selection'].get('declared_value')]
        rows.append(row)
    return {'record_type':'R4_NINE_RESPONSE_LAYERED_READ_ONLY_AUDIT','historical_provider_calls':9,
        'new_provider_paid_sec_calls':[0,0,0],'qualification_credit':'NONE','cases':rows}
