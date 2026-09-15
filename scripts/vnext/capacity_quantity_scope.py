"""Original HTML heading ranges for the explicit B13 quantity reader.

These records preserve structure and source bytes, not model judgments. Only
real h1-h6 levels close a heading's scope; emphasis is not a section boundary.
"""
from copy import deepcopy
import re

from .canonical import content_hash, sha256_bytes
from .text_coverage import _Blocks, _byte_offsets

FORMAT = 'B13_HTML_QUANTITY_SCOPE_V1'
_HEADING = re.compile(r'h([1-6])$')
_EXAMPLE = re.compile(r'\s*(?:an?\s+)?(?:hypothetical|illustrative)\s+(?:examples?|scenarios?)\s*[:.]?\s*', re.I)
_EXAMPLE_HINT = re.compile(r'\b(?:hypothetical|illustrative)\b', re.I)
_POST_QUALIFIER = re.compile(r'\b(?:these|the\s+preceding)\s+(?:quantities|figures|amounts)\s+'
    r'(?:are|were)\s+(?:hypothetical|illustrative)\s+(?:examples?|figures|amounts)?'
    r'[^.!?]*\bnot\s+actual\b', re.I)


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


class _Headings(_Blocks):
    def __init__(self, text):
        super().__init__(text)
        self.headings = []
        self.open_heading = None

    def handle_starttag(self, tag, attrs):
        position = self._offset()
        super().handle_starttag(tag, attrs)
        match = _HEADING.fullmatch(tag)
        if match and not any(row[1] for row in self.stack) and any(row[0] == 'body' for row in self.stack):
            need(self.open_heading is None, 'B13_QUANTITY_NESTED_HEADING_UNSUPPORTED')
            self.open_heading = {'level': int(match.group(1)), 'start': position, 'tag': tag}

    def handle_endtag(self, tag):
        position = self._offset()
        super().handle_endtag(tag)
        if self.open_heading and self.open_heading['tag'] == tag:
            heading = self.open_heading
            end = self.text.find('>', position) + 1
            need(end > position, 'B13_QUANTITY_HEADING_END_MISSING')
            rows = [b for b in self.blocks if heading['start'] <= b['start'] < end]
            # Linked contents entries do not introduce a narrative section.
            if rows and not any(b['linked'] for b in rows):
                self.headings.append({'level': heading['level'], 'start': heading['start'],
                    'end': end, 'text': ' '.join(b['text'] for b in rows)})
            self.open_heading = None


def document_scope(*, raw, document_id, blocks):
    text = raw.decode('utf-8-sig')
    bom = 3 if raw.startswith(b'\xef\xbb\xbf') else 0
    parser = _Headings(text)
    parser.feed(text); parser.close(); parser._flush()
    need(parser.open_heading is None and not parser.structural_errors,
         'B13_QUANTITY_HEADING_STRUCTURE_UNSUPPORTED')
    need(len(parser.blocks) == len(blocks), 'B13_QUANTITY_SCOPE_BLOCK_CENSUS_CHANGED')
    points = [n[k] for n in parser.headings for k in ('start', 'end')]
    points += [n[k] for n in parser.blocks for k in ('start', 'end')]
    offsets = _byte_offsets(text, points)
    for original, block in zip(parser.blocks, blocks):
        a, b = offsets[original['start']] + bom, offsets[original['end']] + bom
        need(block['text'] == original['text'] and block['raw_start_byte'] == a and block['raw_end_byte'] == b
             and block['raw_span_sha256'] == sha256_bytes(content=raw[a:b]), 'B13_QUANTITY_SOURCE_BLOCK_CHANGED')
    headings = []
    for i, heading in enumerate(parser.headings):
        a, b = offsets[heading['start']] + bom, offsets[heading['end']] + bom
        closing = next((h for h in parser.headings[i+1:] if h['level'] <= heading['level']), None)
        headings.append({'level': heading['level'], 'text': heading['text'],
            'raw_start_byte': a, 'raw_end_byte': b, 'raw_span_sha256': sha256_bytes(content=raw[a:b]),
            'scope_end_byte': offsets[closing['start']] + bom if closing else len(raw)})
    introducers = []
    for block in blocks:
        if not _EXAMPLE.fullmatch(block['text']):
            continue
        a, b = block['raw_start_byte'], block['raw_end_byte']
        if any(h['raw_start_byte'] <= a < h['raw_end_byte'] for h in headings):
            continue
        active = [h for h in headings if h['raw_end_byte'] <= a < h['scope_end_byte']]
        # An unstructured introduction has no heading level. Its extent is
        # unproved within the current genuine section, not silently two blocks.
        # A new genuine section provides an independent discourse boundary.
        if active:
            end = max(active, key=lambda h: h['raw_start_byte'])['scope_end_byte']
        else:
            following = next((h for h in headings if h['raw_start_byte'] > b), None)
            end = following['raw_start_byte'] if following else len(raw)
        introducers.append({k: block[k] for k in ('block_index','text','raw_start_byte','raw_end_byte','raw_span_sha256')}
                           | {'scope_end_byte': end})
    return {'document_id': document_id, 'raw_asset_id': 'sha256:' + sha256_bytes(content=raw),
            'byte_length': len(raw), 'headings': headings, 'unstructured_introducers': introducers}


def attach_quantity_scope(*, source, raw_bytes_by_id):
    """Explicit successor metadata; original units and their hashes stay exact."""
    documents = {}
    for document in source['documents']:
        did = document['document_id']
        blocks = [b for u in source['units'] if u['document_id'] == did and u['kind'] == 'VISIBLE_TEXT'
                  for b in u['payload']['blocks']]
        raw = raw_bytes_by_id[document['raw_blob']['raw_asset_id']]
        scope = document_scope(raw=raw, document_id=did, blocks=blocks)
        need(scope['raw_asset_id'] == document['raw_blob']['raw_asset_id'], 'B13_QUANTITY_ORIGINAL_BYTES_CHANGED')
        documents[did] = scope
    body = {k: deepcopy(v) for k, v in source.items() if k != 'semantic_source_id'}
    body['quantity_scope_context'] = {'format': FORMAT, 'documents': documents}
    return {**body, 'semantic_source_id': content_hash(value=body)}


def verified_scope(*, source, raw_bytes_by_id):
    rebuilt = attach_quantity_scope(source=source, raw_bytes_by_id=raw_bytes_by_id)['quantity_scope_context']
    supplied = source.get('quantity_scope_context')
    if supplied is not None:
        need(supplied == rebuilt, 'B13_QUANTITY_SCOPE_ORIGINAL_MISMATCH')
    return rebuilt


def check_scope_shape(scope):
    need(isinstance(scope, dict) and set(scope) == {'format', 'documents'} and scope['format'] == FORMAT
         and isinstance(scope['documents'], dict), 'B13_QUANTITY_SCOPE_FORMAT_UNSUPPORTED')
    for did, doc in scope['documents'].items():
        need(set(doc) == {'document_id','raw_asset_id','byte_length','headings','unstructured_introducers'} and doc['document_id'] == did
             and isinstance(doc['headings'], list) and isinstance(doc['unstructured_introducers'], list), 'B13_QUANTITY_SCOPE_DOCUMENT_CHANGED')
        previous = -1
        for heading in doc['headings']:
            need(set(heading) == {'level','text','raw_start_byte','raw_end_byte','raw_span_sha256','scope_end_byte'}
                 and type(heading['level']) is int and 1 <= heading['level'] <= 6
                 and previous < heading['raw_start_byte'] < heading['raw_end_byte'] <= heading['scope_end_byte'] <= doc['byte_length'],
                 'B13_QUANTITY_HEADING_RANGE_CHANGED')
            previous = heading['raw_start_byte']
        for intro in doc['unstructured_introducers']:
            need(set(intro) == {'block_index','text','raw_start_byte','raw_end_byte','raw_span_sha256','scope_end_byte'}
                 and _EXAMPLE.fullmatch(intro['text'])
                 and 0 <= intro['raw_start_byte'] < intro['raw_end_byte'] <= intro['scope_end_byte'] <= doc['byte_length'],
                 'B13_QUANTITY_INTRODUCER_RANGE_CHANGED')


def quantity_qualification(*, block, document_id, scope, statement):
    """Return only a supported exclusion or an explicit missing-structure gap."""
    if any(statement['end_character'] <= match.start() for match in _POST_QUALIFIER.finditer(block['text'])):
        return 'EXPLICIT_PRECEDING_NONACTUAL_QUANTITIES'
    if scope is None:
        return 'B13_QUANTITY_HTML_SCOPE_NOT_SUPPLIED'
    check_scope_shape(scope)
    need(document_id in scope['documents'], 'B13_QUANTITY_SCOPE_DOCUMENT_MISSING')
    headings = scope['documents'][document_id]['headings']
    active = [h for h in headings if h['raw_end_byte'] <= block['raw_start_byte'] < h['scope_end_byte']]
    if any(_EXAMPLE.fullmatch(h['text']) for h in active):
        return 'HYPOTHETICAL_HTML_HEADING_SCOPE'
    if any(_EXAMPLE_HINT.search(h['text']) for h in active):
        return 'B13_QUANTITY_HEADING_SCOPE_UNRESOLVED'
    if any(i['raw_end_byte'] <= block['raw_start_byte'] < i['scope_end_byte']
           for i in scope['documents'][document_id]['unstructured_introducers']):
        return 'B13_QUANTITY_NONHEADING_INTRODUCTION_SCOPE_UNRESOLVED'
    return None


def local_context_blocks(*, blocks, block, document_id, scope):
    """Keep adjacent prose checks within the original active heading section."""
    start = 0
    if scope is not None:
        check_scope_shape(scope)
        headings = scope['documents'][document_id]['headings']
        active = [h for h in headings if h['raw_end_byte'] <= block['raw_start_byte'] < h['scope_end_byte']]
        if active:
            start = max(h['raw_end_byte'] for h in active)
    return [b['text'] for b in blocks if b['block_index'] < block['block_index']
            and b['raw_start_byte'] >= start][-2:]
