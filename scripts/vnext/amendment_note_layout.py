"""Keep original note blocks while distinguishing inline fragments from paragraphs."""
from html.parser import HTMLParser
import re
from .text_coverage import _Blocks

LAYOUT = 'inline-paragraphs-v2'


class _Gap(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inline = True
        self.stack = []

    def handle_starttag(self, tag, attrs):
        allowed = {'font','span','b','i','u','strong','em','sub','sup','a',
                   'ix:nonnumeric','ix:nonfraction'}
        style = dict(attrs).get('style', '')
        display = re.search(r'(?:^|;)\s*display\s*:\s*([^;]+)', style, re.I)
        value = display[1].strip().casefold() if display else None
        inline = (tag in allowed or tag == 'div' and value == 'inline') and value in (None,'inline')
        self.stack.append((tag, inline))
        if not inline:
            self.inline = False

    def handle_endtag(self, tag):
        matches = [i for i, entry in enumerate(self.stack) if entry[0] == tag]
        if matches:
            index = matches[-1]
            if not self.stack[index][1]:self.inline = False
            del self.stack[index:]
        elif tag not in {'font','span','b','i','u','strong','em','sub','sup','a','ix:nonnumeric','ix:nonfraction'}:
            self.inline = False

    def handle_data(self, text):
        if text.strip():
            self.inline = False


def paragraph_blocks(blocks, raw):
    """Return groups of unchanged blocks; only empty inline-markup gaps join."""
    groups = []
    previous = None
    gap = _Gap()
    for block in blocks:
        start, end = block['raw_start_byte'], block['raw_end_byte']
        if not (type(start) is int and type(end) is int and 0 <= start < end <= len(raw)):
            raise ValueError('AMENDMENT_NOTE_SOURCE_RANGE_INVALID')
        join = False
        if previous is not None:
            if previous > start:
                raise ValueError('AMENDMENT_NOTE_SOURCE_RANGES_OVERLAP')
            gap.inline = True; gap.feed(raw[previous:start].decode('utf-8'))
            join = gap.inline
        if join:
            groups[-1].append(block)
        else:
            groups.append([block])
        previous = end
    return groups


def paragraph_text(blocks, raw):
    """Reuse the visible-text parser without inserting spaces at inline cuts."""
    class Joined(_Blocks):
        def _flush(self):
            pass
    fragment=raw[blocks[0]['raw_start_byte']:blocks[-1]['raw_end_byte']].decode('utf-8')
    text='<html><body>'+fragment+'</body></html>'
    parser=Joined(text);parser.feed(text);parser.close()
    return ' '.join(''.join(part[2] for part in parser.parts).split())


def part_iii_pattern(pattern):
    """Recognize the same Part III purpose with its exact proxy-replacement clause."""
    suffix = r'such Items\.'
    if pattern.count(suffix) != 1:
        raise ValueError('AMENDMENT_NOTE_POLICY_PATTERN_UNSUPPORTED')
    return pattern.replace(' to amend Part III', ' (?:solely )?to amend Part III').replace(
        'References to ', 'References (?:in this document )?to ').replace(
        suffix, r'such Items(?:\.|, rather than incorporate such information into Part III by reference to a proxy statement\.)')


def conditional_recovery_patterns(patterns):
    """The explicit full name/defined alias of the same Exchange Act rule."""
    alias=r'(?:Exchange Act|Securities Exchange Act of 1934, as amended \(the “Exchange Act”\)) Rule 10D-1'
    return [p.replace('Exchange Act Rule 10D-1',alias) for p in patterns]
