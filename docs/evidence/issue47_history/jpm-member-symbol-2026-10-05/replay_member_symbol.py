"""Replay the fixed upstream Member-legend diagnostic on this task's bytes.

Explicit flat table pair only; no image pixels, negative membership inference,
model response reuse, accepted Result or production formatter change.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'scripts'))
from vnext.table_grid import _AllTablesParser, _semantic_text


class ImageLocations(_AllTablesParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == 'img' and self._stack:
            table = self._stack[-1]
            if table.current_cell is not None:
                self.images.append((table.order, table.current_cell,
                                    dict(attrs), self.get_starttag_text(), self.getpos()))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def same_symbol(left, right):
    return all(left.get(key) == right.get(key) and left.get(key) is not None
               for key in ('src','alt','style'))


def run(args):
    raw = args.raw.read_bytes()
    grid = json.loads((args.input/'table-grid.json').read_text())
    doc = json.loads((args.input/'document.json').read_text())
    assert digest(raw) == doc['raw_asset_id'][7:]
    source_text = raw.decode('utf-8')
    line_starts = [0]
    line_starts.extend(i+1 for i,c in enumerate(source_text) if c=='\n')
    parser = ImageLocations()
    parser.feed(source_text); parser.close()
    assert len(parser.tables) == len(grid['tables'])
    positions = []
    for order in (args.member_table-1,args.legend_table-1):
        table = grid['tables'][order]
        assert table['table_id'] == f'table_{order+1:06}'
        for row_index,row in enumerate(parser.tables[order].rows):
            column = 0
            for cell in row:
                assert cell.rowspan == 1
                saved = table['rows'][row_index]['cells'][column]
                assert saved['is_origin'] and saved['colspan'] == cell.colspan
                assert saved['text'] == _semantic_text(raw_text=''.join(cell.raw_parts))
                for table_order,original_cell,attrs,tag,position in parser.images:
                    if table_order != order or original_cell is not cell:
                        continue
                    tag_bytes = tag.encode('utf-8')
                    line,column_in_line = position
                    char_offset = line_starts[line-1]+column_in_line
                    start = len(source_text[:char_offset].encode('utf-8'))
                    assert raw[start:start+len(tag_bytes)] == tag_bytes
                    positions.append({'table_id':table['table_id'],'row':row_index,
                                      'column':column,'row_name':table['rows'][row_index]['cells'][0]['text'],
                                      'column_name':table['rows'][1]['cells'][column]['text'],
                                      'attributes':attrs,'raw_start_byte':start,
                                      'raw_end_byte':start+len(tag_bytes),'tag_sha256':digest(tag_bytes)})
                column += cell.colspan
            assert column == table['column_count']
    member_name=f'table_{args.member_table:06}';legend_name=f'table_{args.legend_table:06}'
    members=[x for x in positions if x['table_id']==member_name]
    legends=[x for x in positions if x['table_id']==legend_name]
    assert len(legends)==1
    legend=legends[0];cells=grid['tables'][args.legend_table-1]['rows'][legend['row']]['cells']
    assert legend['column']==0 and cells[3]['text']=='Member'
    assert cells[6]['text']=='C' and cells[9]['text']=='Chair'
    assert all(same_symbol(x['attributes'],legend['attributes']) for x in members)
    # In-memory negative probes: unlike symbols cannot acquire this meaning.
    negative_results={}
    for key in ('src','alt','style'):
        changed=dict(legend['attributes']);changed[key]+=' changed'
        negative_results[key]=not same_symbol(changed,legend['attributes'])
    missing=dict(legend['attributes']);missing.pop('src');negative_results['missing_src']=not same_symbol(missing,legend['attributes'])
    assert all(negative_results.values())
    blocks={b['block_index']:b for b in doc['blocks']}
    citations=[]
    for i in args.blocks:
        b=blocks[i];assert digest(raw[b['raw_start_byte']:b['raw_end_byte']])==b['raw_span_sha256'];citations.append(b)
    result={'record_type':'ISSUE47_LOCAL_MEMBER_SYMBOL_LEGEND_REPLAY',
            'peer_commit':'058c80b198cde14a05077c9e448048f895a117c8',
            'local_helper_sha256':digest(Path(__file__).read_bytes()),
            'source_filing':doc['source_filing'],'raw_source_sha256':digest(raw),
            'input_request_sha256':digest((args.input/'request-body.json').read_bytes()),
            'member_locations':members,'legend_location':legend,'source_blocks':citations,
            'necessary_table_pair':[grid['tables'][args.member_table-1],grid['tables'][args.legend_table-1]],
            'in_memory_symbol_mismatch_probes':negative_results,
            'judgment':'These positive symbol cells use the same exact src/alt/style as the source Member legend. This provides a source relation without interpreting pixels; it does not infer nonmembership from blanks.',
            'image_pixels_read':False,'old_request_changed':False,'old_response_read':False,
            'new_model_response':False,'production_formatter_changed':False,
            'complete_c02_acceptance':False,'new_runs':0,'new_acceptances':0,'calls':[0,0,0]}
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    print(json.dumps({'source_sha256':digest(raw),'positive_members':len(members),
                      'negative_probes':negative_results,'calls':[0,0,0]}))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ('input','raw','out'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('member-table','legend-table'):parser.add_argument('--'+name,type=int,required=True)
    parser.add_argument('--blocks',type=int,nargs='+',required=True)
    run(parser.parse_args())
