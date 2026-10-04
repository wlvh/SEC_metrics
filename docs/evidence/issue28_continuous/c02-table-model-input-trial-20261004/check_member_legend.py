"""One saved original's image/legend relationship; no extraction acceptance.

This diagnostic does not change the common formatter or old model request.
The existing table parser supplies the same original cell objects. Only this
flat pair of tables is mapped; it is not a general image interpretation rule.
"""
import hashlib
import json
from pathlib import Path

from vnext.table_grid import _AllTablesParser, _semantic_text


HERE = Path(__file__).resolve().parent
INPUT = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-development-evidence/c02-table-input-reception-20261004')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


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
                                    dict(attrs), self.get_starttag_text()))


def run():
    raw = (INPUT / 'raw-source.html').read_bytes()
    assert digest(raw) == 'bea52712a4297691c6844441f3a138bb53d9e8f38278b08b3d3731280c4fc476'
    grid = json.loads((INPUT / 'table-grid.json').read_text())
    doc = json.loads((INPUT / 'document.json').read_text())
    parser = ImageLocations()
    parser.feed(raw.decode('utf-8'))
    parser.close()
    assert len(parser.tables) == len(grid['tables']) == 409

    locations = []
    for order in (115, 116):
        for row_index, row in enumerate(parser.tables[order].rows):
            column = 0
            for cell in row:
                assert cell.rowspan == 1  # This diagnostic only uses flat rows.
                saved = grid['tables'][order]['rows'][row_index]['cells'][column]
                text = _semantic_text(raw_text=''.join(cell.raw_parts))
                assert saved['is_origin'] and saved['text'] == text
                assert saved['colspan'] == cell.colspan
                for t, original_cell, attrs, tag in parser.images:
                    if t != order or original_cell is not cell:
                        continue
                    tag_bytes = tag.encode('utf-8')
                    assert raw.count(tag_bytes) == 1
                    start = raw.index(tag_bytes)
                    locations.append({
                        'table': grid['tables'][order]['table_id'],
                        'row': row_index, 'column': column,
                        'row_name': grid['tables'][order]['rows'][row_index]['cells'][0]['text'],
                        'column_name': grid['tables'][order]['rows'][1]['cells'][column]['text'],
                        'attributes': attrs, 'raw_start_byte': start,
                        'raw_end_byte': start + len(tag_bytes),
                        'tag_sha256': digest(tag_bytes),
                    })
                column += cell.colspan

    members = [x for x in locations if x['table'] == 'table_000116']
    legends = [x for x in locations if x['table'] == 'table_000117']
    assert len(members) == 14 and len(legends) == 1
    legend, = legends
    legend_cells = grid['tables'][116]['rows'][legend['row']]['cells']
    assert legend_cells[3]['text'] == 'Member'
    assert legend_cells[6]['text'] == 'C' and legend_cells[9]['text'] == 'Chair'
    for x in members:
        assert x['attributes']['src'] == legend['attributes']['src']
        assert x['attributes']['alt'] == legend['attributes']['alt']
        assert x['attributes']['style'] == legend['attributes']['style']
    cited = [b for b in doc['blocks'] if b['block_index'] in (1252, 1276, 1277, 1278, 1279)]
    for block in cited:
        assert digest(raw[block['raw_start_byte']:block['raw_end_byte']]) == block['raw_span_sha256']
    out = {
        'record_type': 'PARENT_SAVED_ORIGINAL_MEMBER_LEGEND_DIAGNOSTIC',
        'raw_source_sha256': digest(raw),
        'original_request_sha256': digest((INPUT / 'request-body.json').read_bytes()),
        'reference_before_blind_sha256': digest((HERE / 'reference-before-blind.json').read_bytes()),
        'response_sha256': digest((HERE / 'independent-input/response.log').read_bytes()),
        'member_locations': members, 'legend_location': legend,
        'legend_label_source': next(b for b in cited if b['block_index'] == 1276),
        'context_blocks': cited,
        'judgment': 'Same literal src/alt/style appears in the adjacent Member legend and 14 flat table cells. Source layout supports these positive membership relations without interpreting pixels. This meaning was not supplied in the unchanged text-only request.',
        'scope': 'Source-input gap diagnosis only. Does not classify qualification pictures, infer absence from blank cells, alter source/old answer or grant complete C02 acceptance.',
        'image_bytes_read': False, 'new_model_response': False,
        'native_or_result_credit': False, 'business_calls': [0, 0, 0],
    }
    (HERE / 'member-legend-source-check.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'member_locations': len(members), 'legend_locations': len(legends),
                      'same_literal_symbol_reference': True, 'new_response': False, 'calls': [0, 0, 0]}))


if __name__ == '__main__':
    run()
