"""Recheck the quoted source facts without a metric selector or old Result package."""
import argparse, json, re, html
from pathlib import Path
from decimal import Decimal

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',type=Path,required=True)
    args=parser.parse_args()
    rows=json.loads(Path(__file__).with_name('native-original-quoted-check.json').read_text())
    for row in rows:
        relative='evidence/'+row['source_file'].split('/evidence/',1)[1]
        raw=(args.source_root/relative).read_text()
        for name in ('raw_fact','raw_context','raw_unit'):
            assert row[name] in raw,(row['metric'],name)
        match=re.fullmatch(r'<ix:nonfraction\b([^>]*)>(.*?)</ix:nonfraction>',row['raw_fact'],re.I|re.S)
        assert match,row['metric']
        attrs={a.lower():html.unescape(v) for a,v in re.findall(r'([\w:.-]+)="([^"]*)"',match[1])}
        lexical=html.unescape(re.sub('<[^>]+>','',match[2])).strip().replace(',','')
        value=Decimal(lexical)*(Decimal(10)**int(attrs.get('scale','0')))
        if attrs.get('sign')=='-':value=-value
        assert value==Decimal(row['scaled_value'])==Decimal(row['saved_value'])
        print(row['metric'],value,row['saved_unit'])

if __name__=='__main__':main()
