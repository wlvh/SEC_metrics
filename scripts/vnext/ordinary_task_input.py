"""Fixed parsed D04 document input for change detection, not a semantic answer.

Raw originals and their locators remain separate. Only explicit byte-offset
provenance is omitted from the comparison; IDs, facts, units, tables and media
relationships remain. No metric selector, model or calculator runs here.
"""
from collections.abc import Mapping
from html.parser import HTMLParser
import json
from pathlib import Path

from .canonical import sha256_bytes, sha256_file
from .deterministic_router import parse_accession_xbrl_source
from .governance_signals import _FactAttributes
from .table_grid import build_table_grid
from .text_coverage import build_text_document

_OFFSETS = {'raw_start_byte','raw_end_byte','raw_span_sha256'}
_RELATION_ATTRS = {'id','name','href','headers','for','scope','role','aria-labelledby','aria-describedby',
                   'xlink:href','xlink:label','xlink:from','xlink:to','xlink:role','xlink:arcrole'}
_MEDIA = {'img','svg','image','object','embed','audio','video','source','iframe'}


def _plain(value, *, omit_offsets=False):
    if isinstance(value,Mapping):
        return {str(k):_plain(v,omit_offsets=omit_offsets) for k,v in value.items()
                if not omit_offsets or k not in _OFFSETS}
    if isinstance(value,(list,tuple)):
        return [_plain(v,omit_offsets=omit_offsets) for v in value]
    return value


class _Relations(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.rows=[];self.script=None;self.script_bodies=[]
        self.svg_depth=0;self.svg_tokens=None;self.svg_subtrees=[]

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='svg' and self.svg_depth==0:self.svg_tokens=[]
        if tag=='svg':self.svg_depth+=1
        if self.svg_depth:
            self.svg_tokens.append({'event':'start','tag':tag,'attributes':attrs})
        relationships={k:v for k,v in attrs.items() if k in _RELATION_ATTRS}
        if tag in _MEDIA:
            self.rows.append({'tag':tag,'attributes':attrs})
        elif relationships:
            self.rows.append({'tag':tag,'attributes':relationships})
        if tag=='script': self.script={'attributes':attrs,'parts':[]}

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if self.svg_depth or tag=='script':self.handle_endtag(tag)

    def handle_data(self,data):
        if self.svg_depth:self.svg_tokens.append({'event':'text','text':data})
        if self.script is not None:self.script['parts'].append(data)

    def handle_entityref(self,name):
        if self.svg_depth:self.svg_tokens.append({'event':'entity','name':name})

    def handle_charref(self,name):
        if self.svg_depth:self.svg_tokens.append({'event':'charref','name':name})

    def handle_comment(self,data):
        if self.svg_depth:self.svg_tokens.append({'event':'comment','text':data})

    def handle_endtag(self,tag):
        if self.svg_depth:
            self.svg_tokens.append({'event':'end','tag':tag})
            if tag=='svg':
                self.svg_depth-=1
                if self.svg_depth==0:self.svg_subtrees.append(self.svg_tokens);self.svg_tokens=None
        if tag=='script' and self.script is not None:
            body=''.join(self.script.pop('parts'))
            # Empty external script references are outside the existing D04
            # visible/native task. Embedded data or code is retained opaque,
            # so new potentially relevant content cannot vanish in comparison.
            if body.strip(): self.script_bodies.append({**self.script,'body':body})
            self.script=None


def parsed_d04_document(*,raw_bytes,raw_blob,source_reference,
                        expected_company_id,expected_cik,expected_period_end):
    """Compare the complete fixed parse, retaining original citation locators."""
    doc=build_text_document(raw_bytes=raw_bytes,raw_blob=raw_blob,source_reference=source_reference,
        expected_company_id=expected_company_id,expected_cik=expected_cik,expected_period_end=expected_period_end)
    if doc['source_state']!='COMPLETE_LOCAL_DOCUMENT':
        raise ValueError('PARSED_D04_INPUT_INCOMPLETE:'+','.join(doc['source_reasons']))
    parsed=parse_accession_xbrl_source(raw_bytes=raw_bytes)
    text=raw_bytes.decode('utf-8-sig')
    attrs=_FactAttributes();attrs.feed(text);attrs.close()
    relations=_Relations();relations.feed(text);relations.close()
    if relations.script is not None: raise ValueError('PARSED_D04_UNCLOSED_SCRIPT')
    if relations.svg_depth: raise ValueError('PARSED_D04_UNCLOSED_SVG')
    grid=build_table_grid(html_bytes=raw_bytes,parent_raw_asset_ids=[raw_blob['raw_asset_id']],
                         storage_uri='derived/parsed-task-grid.json')
    dependencies=('ordinary_task_input.py','text_coverage.py','table_grid.py',
                  'deterministic_router.py','governance_signals.py','resource_limits.py')
    body={'task_metric':'D04','parser_version':1,
        'parser_files':{p:sha256_file(path=Path(__file__).with_name(p)) for p in dependencies},
        'source':{k:source_reference[k] for k in ('company_id','source_url','accession','document_name','source_role')},
        'identity':{k:doc[k] for k in ('company_id','cik','period_end','form','registrant_names','source_state','source_reasons')},
        'blocks':_plain(doc['blocks'],omit_offsets=True),'sections':_plain(doc['sections'],omit_offsets=True),
        'native_contexts':_plain(parsed.contexts),'native_facts':_plain(parsed.facts),
        'native_fact_attributes':_plain(attrs.facts),'native_units':_plain(attrs.units),
        'tables':_plain(grid['tables']),'relationships':relations.rows,
        'svg_subtrees':relations.svg_subtrees,'embedded_scripts':relations.script_bodies}
    # NFC canonical identity is not used for verbatim source content equality.
    payload=json.dumps(body,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return {'parsed_input_sha256':sha256_bytes(content=payload),'parsed_input':body,
        'raw_source_sha256':sha256_bytes(content=raw_bytes),
        'original_locators':[{k:b[k] for k in ('block_index','raw_start_byte','raw_end_byte','raw_span_sha256')}
                             for b in doc['blocks']],
        'source_admission_or_result_credit':False,'semantic_disclosure_verified':False}
