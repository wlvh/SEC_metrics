"""Fixed source-only image representation received from Issue47 c294b12f.

Collect logic is retained; CLI removed and assertions become explicit guards.
No pixels, selector, interpretation, provider transport or acceptance is added.
"""
import hashlib
import json
from .table_grid import _AllTablesParser, _semantic_text

PROVIDER_COMMIT = 'c294b12f05e648e9b598635292c6438a4ea1c072'
PROVIDER_FILE_SHA256 = 'a1ecc8f1d4785869e55cc8c28b7833a1bad69ccf0fb73513e4d66a4b69361837'


def _need(ok, reason):
    if not ok:
        raise ValueError('C02_IMAGE_CONTEXT_' + reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()

class Parser(_AllTablesParser):

    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == 'img':
            table = self._stack[-1] if self._stack else None
            self.images.append({'cell_object': table.current_cell if table else None, 'table_order': table.order if table else None, 'attributes': dict(attrs), 'raw_tag': self.get_starttag_text(), 'position': self.getpos()})
            _need(len(attrs) == len(dict(attrs)), 'ORIGINAL_IMAGE_METADATA_49')

def collect(raw, grid):
    source = raw.decode('utf-8')
    starts = [0]
    starts.extend((i + 1 for i, c in enumerate(source) if c == '\n'))
    parser = Parser()
    parser.feed(source)
    parser.close()
    _need(len(parser.tables) == len(grid['tables']), 'ORIGINAL_IMAGE_METADATA_56')
    origins = {}
    for builder, table in zip(parser.tables, grid['tables']):
        _need(table['table_id'] == f'table_{builder.order + 1:06}', 'ORIGINAL_IMAGE_METADATA_59')
        occupied = set()
        for row_index, row in enumerate(builder.rows):
            column = 0
            for cell in row:
                while (row_index, column) in occupied:
                    column += 1
                saved = table['rows'][row_index]['cells'][column]
                _need(saved['is_origin'], 'ORIGINAL_IMAGE_METADATA_66')
                _need((saved['rowspan'], saved['colspan'], saved['header']) == (cell.rowspan, cell.colspan, cell.header), 'ORIGINAL_IMAGE_METADATA_67')
                _need(saved['raw_text'] == ''.join(cell.raw_parts), 'ORIGINAL_IMAGE_METADATA_68')
                _need(saved['text'] == _semantic_text(raw_text=''.join(cell.raw_parts)), 'ORIGINAL_IMAGE_METADATA_69')
                origins[id(cell)] = {'table_id': table['table_id'], 'row': row_index, 'column': column, 'rowspan': cell.rowspan, 'colspan': cell.colspan}
                for r in range(row_index, row_index + cell.rowspan):
                    for c in range(column, column + cell.colspan):
                        _need((r, c) not in occupied, 'ORIGINAL_IMAGE_METADATA_74')
                        occupied.add((r, c))
                column += cell.colspan
    records = []
    for occurrence in parser.images:
        line, column = occurrence['position']
        offset = starts[line - 1] + column
        start = len(source[:offset].encode('utf-8'))
        tag = occurrence['raw_tag']
        tag_bytes = tag.encode('utf-8')
        _need(raw[start:start + len(tag_bytes)] == tag_bytes, 'ORIGINAL_IMAGE_METADATA_80')
        cell = occurrence['cell_object']
        locator = origins[id(cell)] if cell is not None else None
        records.append({'raw_tag': tag, 'attributes': occurrence['attributes'], 'raw_start_byte': start, 'raw_end_byte': start + len(tag_bytes), 'raw_tag_sha256': sha(tag_bytes), 'cell': locator, 'enclosing_table_id': f"table_{occurrence['table_order'] + 1:06}" if occurrence['table_order'] is not None else None})
    _need([r['raw_start_byte'] for r in records] == sorted((r['raw_start_byte'] for r in records)), 'ORIGINAL_IMAGE_METADATA_86')
    return records

IMAGE_FORMAT = "\nAdditional image_source_markup contains every original HTML img node,\nincluding nodes outside table cells. This is parsed source metadata, not pixels.\nimage_source_markup.strings is a separate dictionary from the original text strings.\nEach occurrence is [raw_start_byte,raw_end_byte,enclosing_table_id,cell,attributes].\ncell is null or [table_id,row,column,rowspan,colspan] of the actual containing\ncell's origin in the same full supplied grid. attributes is a list of\n[name_string_index,value_string_index] pairs, decoded with the image dictionary.\nAll parsed attribute names/values and every node/location are retained. Original\ntag bytes, quoting and spelling remain in the raw source at the given byte span;\nthey are not reproduced in this parsed representation. Repeated src/alt/style\nare literal references, not business conclusions. An explicit source legend and\nits actual layout may support interpretation of a repeated symbol. No image\npixels were supplied/read; generic filenames/alt text or blank grid cells cannot\nprove qualification, nonmembership or zero. Keep other image meanings unresolved.\nThe original task and output/time/entity requirements still apply.\n"


def image_view(images, raw_asset_id):
    """Keep every parsed attribute and locator, with an exact metadata inverse."""
    strings, ids, occurrences, projected = [], {}, [], []
    def sid(value):
        if value not in ids:
            ids[value] = len(strings); strings.append(value)
        return ids[value]
    for image in images:
        locator = image['cell']
        cell = [locator[k] for k in ('table_id','row','column','rowspan','colspan')] if locator else None
        attrs = [[sid(k),sid(v)] for k,v in image['attributes'].items()]
        occurrences.append([image['raw_start_byte'],image['raw_end_byte'],image['enclosing_table_id'],cell,attrs])
        projected.append({k:image[k] for k in ('raw_start_byte','raw_end_byte','enclosing_table_id','cell','attributes')})
    rebuilt = [{'raw_start_byte':start,'raw_end_byte':end,'enclosing_table_id':table,
        'cell':dict(zip(('table_id','row','column','rowspan','colspan'),cell)) if cell else None,
        'attributes':{strings[k]:strings[v] for k,v in attrs}}
        for start,end,table,cell,attrs in occurrences]
    _need(rebuilt == projected, 'ATTRIBUTE_LOCATOR_INVERSE_CHANGED')
    return {'raw_asset_id':raw_asset_id,'image_pixels_supplied':False,
        'representation':'all-parsed-attributes-and-locators-v1','strings':strings,'occurrences':occurrences}


def augment_request(request_body, raw, grid, raw_asset_id):
    _need(raw_asset_id == 'sha256:'+sha(raw), 'RAW_ASSET_CHANGED')
    request = json.loads(request_body)
    _need(len(request['messages']) == 2, 'TWO_MESSAGES_REQUIRED')
    original = json.loads(request['messages'][1]['content'])
    _need('image_source_markup' not in original, 'ALREADY_AUGMENTED')
    images = collect(raw, grid)
    packet = {**original, 'image_source_markup':image_view(images,raw_asset_id)}
    proposed = {**request,'messages':[
        dict(request['messages'][0],content=request['messages'][0]['content']+IMAGE_FORMAT),
        dict(request['messages'][1],content=json.dumps(packet,ensure_ascii=False,separators=(',',':')))]}
    body = json.dumps(proposed,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    return body, packet, images
