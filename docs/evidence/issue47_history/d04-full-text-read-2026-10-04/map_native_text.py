import json, re
from pathlib import Path
from html.parser import HTMLParser

import argparse
p = argparse.ArgumentParser(description='Map every native fact and supplement text to the complete visible-text reading; emit uncovered text separately without business filtering.')
p.add_argument('--root', type=Path, required=True)
ROOT = p.parse_args().root
class Text(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.parts=[]
    def handle_data(self,data): self.parts.append(data)
def plain(value):
    p=Text();p.feed(value);p.close();return ''.join(p.parts)
def norm(value): return re.sub(r'\s+','',value)
for entry in json.loads((ROOT/'index.json').read_text()):
    label=entry['label'];doc=json.loads((ROOT/(label+'.json')).read_text())
    visible=norm(''.join(doc['blocks'][str(k)]['text'] for k in sorted(map(int,doc['blocks']))))
    mapping=[];extras=[]
    for k, row in doc['facts'].items():
        fact=row['fact'];text=plain(fact['text']);n=norm(text)
        covered=bool(n) and n in visible
        numeric=bool(re.fullmatch(r'[+\-]?\d+(?:[.,]\d+)*',n)) and fact['tag']=='ix:nonfraction'
        mapping.append({'kind':'NATIVE_FACT','source_index':int(k),'qualified_name':fact['qualified_name'],
                        'text_covered_by_visible':covered,'numeric_literal':numeric})
        if not covered and not numeric:
            extras.append(f'NATIVE_FACT {k} {fact["qualified_name"]}: {text}\n')
    for k,obj in enumerate(doc['supplements']):
        text=plain(obj['raw_xml']);n=norm(text);covered=bool(n) and n in visible
        mapping.append({'kind':'NATIVE_SUPPLEMENT','source_index':k,'local_name':obj['local_name'],
                        'text_covered_by_visible':covered,'empty_text':not n})
        if n and not covered: extras.append(f'SUPPLEMENT {k} {obj["local_name"]}: {text}\n')
    (ROOT/(label+'-native-extra.txt')).write_text(''.join(extras))
    (ROOT/(label+'-native-text-map.json')).write_text(json.dumps(mapping,indent=1)+'\n')
    print(label,len(mapping),'extra_items',len(extras),'extra_chars',sum(map(len,extras)))
