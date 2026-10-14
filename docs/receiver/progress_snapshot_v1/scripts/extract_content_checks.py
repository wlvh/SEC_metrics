#!/usr/bin/env python3
"""Extract per-cell original-source reading checks from #47 content-acceptance records.

usage: extract_content_checks.py <git-dir> <commit> <out.json>
Walks every JSON file under docs/evidence/issue47_history/content-acceptance/ at the
given commit. A check is any mapping with a 'verdict' plus a 'read', 'published' or
'value_sha256' (text results are recorded by the SHA-256 of the published value);
its company comes from the nearest enclosing 'company_id', its metric from the
nearest enclosing key shaped like A01..E05, else from the record type
(ISSUE_47_D01_...), else from the file-name prefix listed in FILE_METRIC; its
period/filings from 'checked_identity', else the check's own or the nearest
enclosing 'period_end'. Files whose records do not fit this shape are listed as
unparsed, never guessed.
"""
import json, re, subprocess, sys

METRIC = re.compile(r'^[A-E]\d\d$')
POSITION = re.compile(r'^([a-z][a-z0-9_]*)-(\d{4})$')  # e.g. marriott-2023
RECORD_METRIC = re.compile(r'^ISSUE_?47_([A-E]\d\d)_')
FILE_METRIC = {'c03-': 'C03', 'paramount-compensation-': 'C03', 'e01-': 'E01', 'debt-to-equity-': 'B06',
               'rpo-': 'B12', 'd01-': 'D01', 'c02-': 'C02', 'd02-': 'D02', 'b06-': 'B06'}
git_dir, commit, out = sys.argv[1], sys.argv[2], sys.argv[3]
prefix = 'docs/evidence/issue47_history/content-acceptance/'
names = subprocess.check_output(['git', '-C', git_dir, 'ls-tree', '-r', '--name-only', commit, prefix], text=True).split()
checks, per_file = [], {}


def walk(node, ctx, path, fname):
    if isinstance(node, dict):
        ctx = dict(ctx)
        if isinstance(node.get('company_id'), str):
            ctx['company_id'] = node['company_id']
        for key in ('period_end', 'fiscal_year'):
            if isinstance(node.get(key), (str, int)):
                ctx['ctx_' + key] = node[key]  # the innermost value applies
        period = node.get('period')
        if isinstance(period, list) and len(period) == 2 and all(isinstance(x, str) for x in period):
            ctx['ctx_period_end'] = period[1]
        if 'verdict' in node and ('read' in node or 'published' in node or 'value_sha256' in node):
            ident = node.get('checked_identity') or {}
            metric = next((p for p in reversed(path) if isinstance(p, str) and METRIC.match(p)), None)
            how = 'PATH_KEY' if metric else None
            if metric is None and RECORD_METRIC.match(ctx.get('record_type') or ''):
                metric, how = RECORD_METRIC.match(ctx['record_type']).group(1), 'RECORD_TYPE'
            if metric is None:
                metric = next((m for prefix, m in FILE_METRIC.items() if fname.startswith(prefix)), None)
                how = 'FILE_NAME' if metric else None
            checks.append({'file': fname, 'company_id': ctx.get('company_id'), 'metric_id': metric,
                           'metric_from': how,
                           'period_end': ident.get('period_end') or ctx.get('ctx_period_end'),
                           'period_start': ident.get('period_start'),
                           'filings': ident.get('filings') or ([node['accession']] if isinstance(node.get('accession'), str) else None),
                           'unit': ident.get('unit'),
                           'read': node.get('read'), 'published': node.get('published'),
                           'value_sha256': node.get('value_sha256'),
                           'verdict': node['verdict'], 'result_id': (ident.get('bound_from') or {}).get('result_id'),
                           'entities': ident.get('entities'), 'position_key': ctx.get('position_key'),
                           'path': '/'.join(str(p) for p in path)})
            return
        for k, v in node.items():
            walk(v, {**ctx, 'position_key': k} if POSITION.match(str(k)) else ctx, path + [k], fname)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, ctx, path + [i], fname)


for name in names:
    if not name.endswith('.json'):
        continue
    try:
        data = json.loads(subprocess.check_output(['git', '-C', git_dir, 'show', commit + ':' + name]))
    except (subprocess.CalledProcessError, ValueError) as error:
        per_file[name] = {'error': str(error)[:200]}
        continue
    before = len(checks)
    walk(data, {'record_type': data.get('record_type') if isinstance(data, dict) else None}, [], name.rsplit('/', 1)[-1])
    per_file[name.rsplit('/', 1)[-1]] = {'checks': len(checks) - before,
                                         'record_type': data.get('record_type') if isinstance(data, dict) else None}
json.dump({'commit': commit, 'files': per_file, 'checks': checks}, open(out, 'w'), indent=1, ensure_ascii=False)
import collections
print('files', len(per_file), 'checks', len(checks))
print('verdicts', collections.Counter(c['verdict'] for c in checks).most_common())
print('metric from', collections.Counter(c['metric_from'] for c in checks).most_common())
print('by metric', sorted(collections.Counter(c['metric_id'] for c in checks if c['metric_id']).items()))
print('with company+metric+period', sum(1 for c in checks if c['company_id'] and c['metric_id'] and c['period_end']))
print('missing company or period (resolved later from entities/position key)', collections.Counter(c['file'] for c in checks if not (c['company_id'] and c['metric_id'] and c['period_end'])))
print('unparsed files', sorted(f for f, v in per_file.items() if not v.get('checks')))
