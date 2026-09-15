"""Full visible/native D04 interpretation inputs, without model execution.

Named fact fields retain the native parser stream. Contexts, units and namespace
environments are shared by reference within each unit, never selected by an
answer or a semantic keyword. Raw continuation/footnote objects remain inputs.
The plan proves serialization coverage only, not a judgment or source freshness.
"""
from pathlib import Path
import json
import re

from .canonical import content_hash,sha256_bytes,sha256_file,strict_json_file
from .governance_signals import _qname
from .going_concern_source import prepare_ordinary_going_concern_source
from .normal_annual_input_v2 import exact_json_value,prepare_saved_annual_input
from .normal_source_authority import ROOT
from .sources import resolve_repository_file
from .text_results_v2 import _ReportedFactMetadata
from .deterministic_router import parse_accession_xbrl_source
from .regulatory_investigation_candidates import _quotation_ranges

POLICY_PATH='catalog/r6/semantic_source_v1.json'
POLICY=strict_json_file(path=ROOT/POLICY_PATH)


class SemanticSourceError(ValueError):
    pass


def _need(condition,reason):
    if not condition:raise SemanticSourceError(reason)


def _bytes(value):
    return json.dumps(exact_json_value(value),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


class _NativeObjects(_ReportedFactMetadata):
    def __init__(self,raw):
        super().__init__();self.source=raw.decode('utf-8-sig')
        self.lines=[0]+[m.end() for m in re.finditer('\n',self.source)]
        self.open_objects=[];self.objects=[]

    def position(self):
        line,column=self.getpos();return self.lines[line-1]+column

    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        namespaces=self.stack[-1][1] if self.stack else {}
        uri,local=_qname(tag,namespaces)
        if [uri,local] in POLICY['native_object_names']:
            self.open_objects.append({'tag':tag,'namespace':uri,'local_name':local,'attributes':dict(attrs),
                'namespaces':dict(namespaces),'start_character':self.position(),'depth':len(self.stack)})

    def handle_endtag(self,tag):
        for i in range(len(self.open_objects)-1,-1,-1):
            item=self.open_objects[i]
            if item['tag']==tag and item['depth']==len(self.stack):
                end=self.source.find('>',self.position())+1
                _need(end>item['start_character'],'SEMANTIC_NATIVE_OBJECT_END_INVALID')
                self.objects.append({**item,'end_character':end,
                    'raw_xml':self.source[item['start_character']:end]})
                del self.open_objects[i]
                break
        super().handle_endtag(tag)


def _shared(rows,objects):
    contexts={};units={};namespaces={};facts=[]
    for row in rows:
        fact=dict(row['fact']);env=row['namespaces'];env_id=content_hash(value=env)
        namespaces[env_id]=env
        context_id=fact['context_ref'];context=objects[('context',context_id)]
        contexts[context_id]={k:context[k] for k in ('raw_xml','namespace_environment_id')}
        namespaces[context['namespace_environment_id']]=context['namespaces']
        unit_id=fact['unit_ref']
        if unit_id:
            unit=objects[('unit',unit_id)]
            units[unit_id]={k:unit[k] for k in ('raw_xml','namespace_environment_id')}
            namespaces[unit['namespace_environment_id']]=unit['namespaces']
        facts.append({'fact':fact,'expanded_concept':row['expanded_concept'],
            'attributes':row['attributes'],'namespace_environment_id':env_id})
    return {'facts':facts,'contexts':contexts,'units':units,'namespace_environments':namespaces}


def _seal_unit(document_id,kind,payload,ordinal):
    raw=_bytes(payload)
    body={'document_id':document_id,'kind':kind,'ordinal':ordinal,'payload':payload,
          'payload_bytes':len(raw),'payload_sha256':sha256_bytes(content=raw)}
    return {**body,'unit_id':content_hash(value=body)}


def _group(rows,render,document_id,kind):
    groups=[];current=[]
    # Count exactly serialized bytes, including the dictionaries used by this
    # unit. Oversized individual source objects reject before any model request.
    for row in rows:
        trial=current+[row]
        if current and len(_bytes(render(trial)))>POLICY['max_unit_payload_bytes']:
            groups.append(current);current=[row]
        else:current=trial
        _need(len(_bytes(render(current)))<=(POLICY['max_single_object_payload_bytes'] if len(current)==1 else POLICY['max_unit_payload_bytes']),
              'SEMANTIC_SINGLE_SOURCE_OBJECT_EXCEEDS_INPUT_BOUND')
    if current:groups.append(current)
    return [_seal_unit(document_id,kind,render(group),i) for i,group in enumerate(groups)]


def _compact_supplements(objects):
    """Retain outer XML once and byte-check every contained object's location."""
    roots=[]
    for obj in sorted(objects,key=lambda r:(r['start_character'],-r['end_character'])):
        if roots and obj['start_character']<roots[-1]['end_character']:
            root=roots[-1]
            _need(obj['end_character']<=root['end_character'],'SEMANTIC_NATIVE_OBJECTS_CROSS_WITHOUT_CONTAINMENT')
            a=obj['start_character']-root['start_character'];b=obj['end_character']-root['start_character']
            _need(root['raw_xml'][a:b]==obj['raw_xml'],'SEMANTIC_NESTED_NATIVE_XML_CHANGED')
            root['nested_objects'].append({**{k:v for k,v in obj.items() if k!='raw_xml'},
                                            'relative_start_character':a,'relative_end_character':b})
        else:roots.append({**obj,'nested_objects':[]})
    _need(sum(1+len(r['nested_objects']) for r in roots)==len(objects),'SEMANTIC_NATIVE_OBJECT_SET_CHANGED')
    return roots


def _native_units(raw,component):
    parsed=parse_accession_xbrl_source(raw_bytes=raw)
    metadata=_NativeObjects(raw);metadata.feed(raw.decode('utf-8-sig'));metadata.close()
    _need(not metadata.open_objects and metadata.ordinal==len(parsed.facts),
          'SEMANTIC_NATIVE_STREAM_OR_OBJECTS_INCOMPLETE')
    objects={};supplements=[]
    for item in sorted(metadata.objects,key=lambda x:(x['start_character'],x['end_character'])):
        obj={k:item[k] for k in ('namespace','local_name','attributes','raw_xml','namespaces','start_character','end_character')}
        obj['namespace_environment_id']=content_hash(value=obj['namespaces'])
        obj['raw_xml_sha256']=sha256_bytes(content=obj['raw_xml'].encode('utf-8'))
        if item['local_name'] in {'context','unit'}:
            key=(item['local_name'],item['attributes'].get('id'))
            _need(key[1] and key not in objects,'SEMANTIC_NATIVE_OBJECT_ID_MISSING_OR_DUPLICATE')
            objects[key]=obj
        else:supplements.append(obj)
    rows=[]
    for fact in parsed.facts:
        meta=metadata.facts[fact['ordinal']]
        _need(('context',fact['context_ref']) in objects,'SEMANTIC_NATIVE_CONTEXT_MISSING')
        _need(not fact['unit_ref'] or ('unit',fact['unit_ref']) in objects,'SEMANTIC_NATIVE_UNIT_MISSING')
        rows.append({'fact':dict(fact),'expanded_concept':list(meta['concept']),
                     'attributes':dict(meta['attrs']),'namespaces':dict(meta['namespaces'])})
    document_id=component['document']['text_document_id']
    units=_group(rows,lambda group:_shared(group,objects),document_id,'NATIVE_FACTS')
    flattened=[]
    for unit in units:
        payload=unit['payload']
        for row in payload['facts']:
            flattened.append({'fact':row['fact'],'expanded_concept':row['expanded_concept'],
                'attributes':row['attributes'],'namespaces':payload['namespace_environments'][row['namespace_environment_id']]})
    _need(flattened==rows,'SEMANTIC_NATIVE_FACT_ROUNDTRIP_CHANGED')
    compact=_compact_supplements(supplements)
    supplement_units=_group(compact,lambda group:{'objects':group},document_id,'NATIVE_SUPPLEMENTS')
    _need([r for u in supplement_units for r in u['payload']['objects']]==compact,
          'SEMANTIC_NATIVE_SUPPLEMENT_ROUNDTRIP_CHANGED')
    return units+supplement_units,{'fact_count':len(rows),'source_object_count':len(objects),
        'supplement_count':len(supplements),'encoded_outer_supplement_count':len(compact),
        'duplicate_nested_xml_bytes_removed':sum(len(r['raw_xml'].encode('utf-8')) for r in supplements)-sum(len(r['raw_xml'].encode('utf-8')) for r in compact),
        'native_fact_stream_sha256':sha256_bytes(content=_bytes(rows)),
        'native_contexts_and_units_retained':True,'native_roundtrip_verified':True}


def prepare_d04_semantic_source(*,repo_root:Path,company_id:str):
    path=resolve_repository_file(repo_root=repo_root,repo_relative_path=POLICY_PATH)
    _need(strict_json_file(path=path)==POLICY==strict_json_file(path=ROOT/POLICY_PATH),
          'SEMANTIC_SOURCE_INSTALLED_POLICY_CHANGED')
    source=prepare_ordinary_going_concern_source(repo_root=repo_root,company_id=company_id)
    annual=prepare_saved_annual_input(repo_root=repo_root,company_id=company_id)
    _need(annual['original_input']==source['prepared_annual_input'],'SEMANTIC_ANNUAL_SOURCE_BINDING_CHANGED')
    units=[];documents=[]
    for component in source['components']:
        doc=component['document'];doc_id=doc['text_document_id']
        _need(set(doc['source_reasons']) <= {'TEXT_AMENDMENT_SOURCE_SET_REQUIRED'},
              'SEMANTIC_ORIGINAL_DOCUMENT_NOT_COMPLETE')
        raw=resolve_repository_file(repo_root=repo_root,repo_relative_path=component['raw_blob']['storage_uri']).read_bytes()
        quotation_ranges=_quotation_ranges(raw)
        blocks=[{**{k:b[k] for k in ('block_index','text','raw_start_byte','raw_end_byte','raw_span_sha256')},
                 'html_quotation_context':any(a<b['raw_end_byte'] and b['raw_start_byte']<z for a,z in quotation_ranges)}
                for b in doc['blocks']]
        visible=_group(blocks,lambda rows:{'blocks':rows},doc_id,'VISIBLE_TEXT')
        _need([b for u in visible for b in u['payload']['blocks']]==blocks,'SEMANTIC_VISIBLE_ROUNDTRIP_CHANGED')
        native,coverage=_native_units(raw,component)
        units.extend(visible+native)
        documents.append({'document_id':doc_id,'source_reference':component['source_reference'],
            'raw_blob':component['raw_blob'],'filing':component['source_filing'],
            'registrant_name_binding':component['registrant_name_binding'],
            'visible_block_count':len(blocks),'native_coverage':coverage,
            'language_candidate_block_indices':[r['block_index'] for r in component['language_candidates']],
            'native_candidate_ordinals':[r['fact']['ordinal'] for r in component['native_concept_candidates']],
            'source_unit_ids':[u['unit_id'] for u in visible+native]})
    ids=[u['unit_id'] for u in units];_need(len(ids)==len(set(ids)),'SEMANTIC_SOURCE_UNIT_DUPLICATE')
    body=exact_json_value({'record_type':'D04_COMPLETE_SEMANTIC_SOURCE','company_id':company_id,'metric_id':'D04',
        'prepared_annual_input':annual,'original_source_packet_id':source['packet_id'],
        'source_proofs':source['source_proofs'],'source_admission':source['source_admission'],
        'documents':documents,'units':units,'required_unit_ids':ids,'source_serialization_complete':True,
        'semantic_coverage_verified':False,'interpretation_created':False,'provider_request_created':False,
        'source_freshness_verified':False,'production_authorized':False,'calls':{'provider':0,'paid':0,'sec':0},
        'policy_sha256':sha256_file(path=path),'module_sha256':sha256_file(path=Path(__file__))})
    return {**body,'semantic_source_id':content_hash(value=body)}
