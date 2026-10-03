"""Read exact previously acquired 8-K12B primary/header bytes for C04 clues."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {'script', 'style'} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


root = Path('/Users/lyuhongwang/.local/state/sec_metrics/issue28-2026-09-13')
data_root = root / 'source-inputs'
evidence = Path(__file__).resolve().parent
plan = json.loads((evidence / 'four-url-plan.json').read_text())
expected = {row['source_url']: row for row in plan['requirements']}
patterns = {
    'item_4_01':r'item\s*4\s*[.]\s*0?1\b',
    'changes_in_accountant':r'changes?\s+in\s+(?:the\s+)?(?:registrant|certifying|accountant)',
    'certifying_accountant':r'certifying\s+accountant',
    'independent_accounting_firm':r'independent\s+(?:registered\s+)?(?:public\s+)?account(?:ing|ant)\s+firm',
    'pricewaterhouse':r'pricewaterhouse|\bpwc\b',
    'ernst_young':r'ernst\s*(?:&|and)\s*young',
    'auditor':r'\bauditor\b|\bauditors\b',
}
rows = []
for ordinal in range(105, 109):
    slot = root / 'calls' / ('%04d' % ordinal)
    intent = json.loads((slot / 'intent.json').read_text())
    terminal = json.loads((slot / 'terminal.json').read_text())
    receipt = json.loads((slot / 'sec-receipt.json').read_text())
    proof = receipt['proof']
    url = proof['source_url']
    assert url in expected and intent['channel'] == 'SEC'
    assert receipt['status'] == terminal['status'] == 'SUCCEEDED'
    assert receipt['actual_sec_egress_count'] == 1 and terminal['counts'] == [0, 0, 1]
    path = data_root / proof['request_repo_relative_path']
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == proof['content_sha256']
    value = raw.decode('utf-8', errors='replace')
    if expected[url]['media_type'] == 'text/html':
        parser = VisibleText();parser.feed(value)
        value = ' '.join(parser.parts)
    value = re.sub(r'\s+', ' ', value)
    matches = {}
    for label, expression in patterns.items():
        found = list(re.finditer(expression, value, flags=re.IGNORECASE))
        matches[label] = {'count':len(found), 'excerpts':[
            value[max(0, item.start() - 120):min(len(value), item.end() + 160)]
            for item in found[:5]]}
    rows.append({'ordinal':ordinal, 'url':url, 'form':expected[url]['filing_form'],
                 'role':expected[url]['roles'][0], 'bytes':len(raw),
                 'sha256':proof['content_sha256'],
                 'request_attempt_id':proof['request_attempt_id'],
                 'normalized_text_characters':len(value), 'search_matches':matches})
assert set(row['url'] for row in rows) == set(expected)
summary = {'record_type':'ISSUE28_PARAMOUNT_C04_INSTALLED_8K12B_CONTENT_CLUES',
           'source_identity':'EXACT_PRIOR_LIVE_SEC_ATTEMPTS_105_TO_108',
           'documents':rows,
           'content_search_is_not_full_C04_acceptance':True,
           'no_same_registrant_prior_annual_created':True,
           'new_real_calls':[0,0,0], 'C04_result_created':False}
(evidence/'installed-content-clues.json').write_text(
    json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([(row['ordinal'],row['form'],row['role'],
    {name:hit['count'] for name,hit in row['search_matches'].items()}) for row in rows]))
