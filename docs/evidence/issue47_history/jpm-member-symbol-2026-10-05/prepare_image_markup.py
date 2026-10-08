"""Offline development input: all original img tags with source positions.

Uses the production raw table parser; adds no pixel interpretation, business
answer, provider transport, source grant, Run or accepted Result.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'scripts'))
from vnext.table_grid import _AllTablesParser, _semantic_text
from vnext.continuous_request_context import measure_request

EXPLANATION='''\nAdditional original-source image markup is supplied in image_source_markup.
It contains every img start tag from the original HTML, including outside tables.
Each occurrence preserves raw_tag, parsed attributes, exact original byte span,
and containing table-cell origin/span when one exists. Table ids and coordinates
refer to the same complete table layout already supplied. Null cell means no
containing table cell, not an absence of source information. Repeated src/alt/
style attributes are spelling identities, not business conclusions. You may
use an explicit source legend together with its actual table position to
interpret a repeated symbol, if that relation is supported by the source.
No image pixels were supplied or interpreted. Generic alt text, filenames or a
blank grid cell do not prove qualification, negative membership or zero. Keep
other image meaning unresolved when the source markup/layout cannot establish
it. The original task, output requirements and time/entity boundaries still apply.
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Parser(_AllTablesParser):
    def __init__(self):
        super().__init__();self.images=[]

    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        if tag=='img':
            table=self._stack[-1] if self._stack else None
            self.images.append({'cell_object':table.current_cell if table else None,
                                'table_order':table.order if table else None,
                                'attributes':dict(attrs),'raw_tag':self.get_starttag_text(),
                                'position':self.getpos()})
            assert len(attrs)==len(dict(attrs)), 'Duplicate source attributes need a separate representation'


def collect(raw,grid):
    source=raw.decode('utf-8');starts=[0]
    starts.extend(i+1 for i,c in enumerate(source) if c=='\n')
    parser=Parser();parser.feed(source);parser.close()
    assert len(parser.tables)==len(grid['tables'])
    origins={}
    for builder,table in zip(parser.tables,grid['tables']):
        assert table['table_id']==f'table_{builder.order+1:06}'
        occupied=set()
        for row_index,row in enumerate(builder.rows):
            column=0
            for cell in row:
                while (row_index,column) in occupied:column+=1
                saved=table['rows'][row_index]['cells'][column]
                assert saved['is_origin']
                assert (saved['rowspan'],saved['colspan'],saved['header'])==(cell.rowspan,cell.colspan,cell.header)
                assert saved['raw_text']==''.join(cell.raw_parts)
                assert saved['text']==_semantic_text(raw_text=''.join(cell.raw_parts))
                origins[id(cell)]={'table_id':table['table_id'],'row':row_index,'column':column,
                                   'rowspan':cell.rowspan,'colspan':cell.colspan}
                for r in range(row_index,row_index+cell.rowspan):
                    for c in range(column,column+cell.colspan):
                        assert (r,c) not in occupied;occupied.add((r,c))
                column+=cell.colspan
    records=[]
    for occurrence in parser.images:
        line,column=occurrence['position'];offset=starts[line-1]+column
        start=len(source[:offset].encode('utf-8'));tag=occurrence['raw_tag'];tag_bytes=tag.encode('utf-8')
        assert raw[start:start+len(tag_bytes)]==tag_bytes
        cell=occurrence['cell_object'];locator=origins[id(cell)] if cell is not None else None
        records.append({'raw_tag':tag,'attributes':occurrence['attributes'],
                        'raw_start_byte':start,'raw_end_byte':start+len(tag_bytes),
                        'raw_tag_sha256':sha(tag_bytes),'cell':locator,
                        'enclosing_table_id':f"table_{occurrence['table_order']+1:06}" if occurrence['table_order'] is not None else None})
    assert [r['raw_start_byte'] for r in records]==sorted(r['raw_start_byte'] for r in records)
    return records


def main():
    parser=argparse.ArgumentParser()
    for name in ('input','raw','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--representation',choices=['raw-tags','attribute-tuples'],default='raw-tags')
    args=parser.parse_args()
    request=json.loads((args.input/'request-body.json').read_text())
    document=json.loads((args.input/'document.json').read_text())
    grid=json.loads((args.input/'table-grid.json').read_text())
    raw=args.raw.read_bytes();assert sha(raw)==document['raw_asset_id'][7:]
    assert len(request['messages'])==2
    original=json.loads(request['messages'][1]['content'])
    assert 'image_source_markup' not in original
    images=collect(raw,grid)
    image_packet={'raw_asset_id':document['raw_asset_id'],
                  'image_pixels_supplied':False,'occurrences':images}
    explanation=EXPLANATION
    roundtrip=False
    if args.representation=='attribute-tuples':
        strings=[];ids={}
        def sid(value):
            if value not in ids:ids[value]=len(strings);strings.append(value)
            return ids[value]
        occurrences=[]
        projected=[]
        for image in images:
            locator=image['cell']
            cell=[locator[k] for k in ('table_id','row','column','rowspan','colspan')] if locator else None
            attrs=[[sid(k),sid(v)] for k,v in image['attributes'].items()]
            occurrences.append([image['raw_start_byte'],image['raw_end_byte'],
                                image['enclosing_table_id'],cell,attrs])
            projected.append({k:image[k] for k in ('raw_start_byte','raw_end_byte','enclosing_table_id','cell','attributes')})
        rebuilt=[]
        for start,end,table,cell,attrs in occurrences:
            rebuilt.append({'raw_start_byte':start,'raw_end_byte':end,
                            'enclosing_table_id':table,
                            'cell':dict(zip(('table_id','row','column','rowspan','colspan'),cell)) if cell else None,
                            'attributes':{strings[k]:strings[v] for k,v in attrs}})
        assert rebuilt==projected
        roundtrip=True
        image_packet={'raw_asset_id':document['raw_asset_id'],'image_pixels_supplied':False,
                      'representation':'all-parsed-attributes-and-locators-v1',
                      'strings':strings,'occurrences':occurrences}
        explanation='''\nAdditional image_source_markup contains every original HTML img node,
including nodes outside table cells. This is parsed source metadata, not pixels.
image_source_markup.strings is a separate dictionary from the original text strings.
Each occurrence is [raw_start_byte,raw_end_byte,enclosing_table_id,cell,attributes].
cell is null or [table_id,row,column,rowspan,colspan] of the actual containing
cell's origin in the same full supplied grid. attributes is a list of
[name_string_index,value_string_index] pairs, decoded with the image dictionary.
All parsed attribute names/values and every node/location are retained. Original
tag bytes, quoting and spelling remain in the raw source at the given byte span;
they are not reproduced in this parsed representation. Repeated src/alt/style
are literal references, not business conclusions. An explicit source legend and
its actual layout may support interpretation of a repeated symbol. No image
pixels were supplied/read; generic filenames/alt text or blank grid cells cannot
prove qualification, nonmembership or zero. Keep other image meanings unresolved.
The original task and output/time/entity requirements still apply.
'''
    packet={**original,'image_source_markup':image_packet}
    assert {k:packet[k] for k in original}==original
    proposed={**request,'messages':[dict(request['messages'][0],content=request['messages'][0]['content']+explanation),
                                 dict(request['messages'][1],content=json.dumps(packet,ensure_ascii=False,separators=(',',':')))]}
    body=json.dumps(proposed,ensure_ascii=False,separators=(',',':')).encode()
    measurement=measure_request(body,require_reference=True)
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/'request-body.json').write_bytes(body)
    (args.out/'all-original-image-markup.json').write_text(json.dumps(images,ensure_ascii=False,indent=1)+'\n')
    (args.out/'context-measurement.json').write_text(json.dumps(measurement,indent=1)+'\n')
    receipt={'record_type':'ISSUE47_C02_ALL_IMAGE_MARKUP_DEVELOPMENT_INPUT',
             'generator_sha256':sha(Path(__file__).read_bytes()),
             'original_request_sha256':sha((args.input/'request-body.json').read_bytes()),
             'request_sha256':sha(body),'raw_source_sha256':sha(raw),
             'image_tags':len(images),'outside_cell_tags':sum(r['cell'] is None for r in images),
             'original_text_and_full_grid_packet_unchanged':True,
             'representation':args.representation,
             'raw_tag_bytes_in_provider_representation':args.representation=='raw-tags',
             'all_original_tag_bytes_preserved_in_sidecar':True,
             'all_parsed_attributes_and_locators_roundtrip_equal':roundtrip,
             'all_parser_img_start_tags_retained':True,'input_tokens':measurement['input_tokens'],
             'fits':measurement['fits'],'image_pixels_supplied':False,'model_tested':False,
             'runtime_wired':False,'native_runs':0,'new_acceptances':0,'calls':[0,0,0]}
    (args.out/'metadata.json').write_text(json.dumps(receipt,indent=1)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
