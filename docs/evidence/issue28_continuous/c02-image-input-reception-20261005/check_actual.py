"""Bounded source-only receiving checks. No model/provider/Result authority."""
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy

from prepare_image_markup import collect
from vnext.table_grid import build_table_grid

ROOT = Path(__file__).resolve().parents[4]
INPUT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/c02-table-input-reception-20261004')
OUTPUT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/c02-image-input-reception-20261005')

class IndependentImageCount(HTMLParser):
    def __init__(self):
        super().__init__(); self.nodes=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'img': self.nodes.append(dict(attrs))
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

def sha(raw): return hashlib.sha256(raw).hexdigest()

def main():
    raw=(INPUT/'raw-source.html').read_bytes()
    assert sha(raw)=='bea52712a4297691c6844441f3a138bb53d9e8f38278b08b3d3731280c4fc476'
    old=json.loads((INPUT/'request-body.json').read_text())
    new=json.loads((OUTPUT/'request-body.json').read_text())
    old_packet=json.loads(old['messages'][1]['content'])
    new_packet=json.loads(new['messages'][1]['content'])
    packet=new_packet['image_source_markup']; strings=packet['strings']
    assert {k:v for k,v in new_packet.items() if k!='image_source_markup'}==old_packet
    assert new['messages'][0]['content'].startswith(old['messages'][0]['content'])
    assert {k:v for k,v in new.items() if k!='messages'}=={k:v for k,v in old.items() if k!='messages'}
    assert packet['raw_asset_id']=='sha256:'+sha(raw) and packet['image_pixels_supplied'] is False
    images=json.loads((OUTPUT/'all-original-image-markup.json').read_text())
    projected=[]
    for start,end,table,cell,attributes in packet['occurrences']:
        assert type(start) is int and type(end) is int and 0<=start<end<=len(raw)
        projected.append({'raw_start_byte':start,'raw_end_byte':end,'enclosing_table_id':table,
          'cell':dict(zip(('table_id','row','column','rowspan','colspan'),cell)) if cell else None,
          'attributes':{strings[k]:strings[v] for k,v in attributes}})
    assert projected==[{k:x[k] for k in ('raw_start_byte','raw_end_byte','enclosing_table_id','cell','attributes')} for x in images]
    parser=IndependentImageCount();parser.feed(raw.decode());parser.close()
    assert [x['attributes'] for x in images]==parser.nodes and len(images)==604
    for x in images:
        span=raw[x['raw_start_byte']:x['raw_end_byte']]
        assert span.decode()==x['raw_tag'] and sha(span)==x['raw_tag_sha256']
    member=json.loads((ROOT/'docs/evidence/issue28_continuous/c02-table-model-input-trial-20261004/member-legend-source-check.json').read_text())
    by_span={x['raw_start_byte']:x for x in images}
    for expected in member['member_locations']:
        got=by_span[expected['raw_start_byte']]
        assert got['attributes']==expected['attributes']
        assert got['raw_tag_sha256']==expected['tag_sha256']
        assert {k:got['cell'][k] for k in ('table_id','row','column')}=={'table_id':expected['table'],'row':expected['row'],'column':expected['column']}
        original_grid=json.loads((INPUT/'table-grid.json').read_text())
        actual_table=next(t for t in original_grid['tables'] if t['table_id']==expected['table'])
        source_cell=actual_table['rows'][expected['row']]['cells'][expected['column']]
        assert got['cell']['rowspan']==source_cell['rowspan'] and got['cell']['colspan']==source_cell['colspan']
    assert len(member['member_locations'])==14
    # Small structural counterexamples and valid repeated UTF-8 locations.
    fixture='<p>合法;<img src="outside.png"></p><table><tr><td rowspan="2"><img src="same.png"/></td><td>x</td></tr><tr><td><img src="same.png"></td></tr></table>'.encode()
    grid=build_table_grid(html_bytes=fixture,parent_raw_asset_ids=['sha256:'+sha(fixture)],storage_uri='fixture-only')
    nodes=collect(fixture,grid);assert len(nodes)==3 and nodes[0]['cell'] is None
    assert len({x['raw_start_byte'] for x in nodes})==3
    assert nodes[1]['cell']['rowspan']==2 and nodes[2]['cell']['row']==1
    broken=deepcopy(grid); broken['tables'][0]['rows'][0]['cells'][1]['text']='changed'
    try: collect(fixture,broken)
    except AssertionError: pass
    else: raise AssertionError('changed grid accepted')
    duplicate=b'<table><tr><td><img src="a" src="b"></td></tr></table>'
    grid2=build_table_grid(html_bytes=duplicate,parent_raw_asset_ids=['sha256:'+sha(duplicate)],storage_uri='fixture-only')
    try: collect(duplicate,grid2)
    except AssertionError: pass
    else: raise AssertionError('duplicate attributes accepted')
    print('PASS exact old text/grid/envelope,604 independent img nodes/all raw spans/attributes,14 prior original positive positions,UTF8/repeated/self-closing/outside/rowspan,grid-tamper and duplicate-attribute refusal. No pixels or new model facts.')

if __name__=='__main__': main()
