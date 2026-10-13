#!/usr/bin/env python3
"""Compare ordinary D02 preparation between two pinned commits on one saved source root.

For every requested company and fiscal year, this runs the production entry
``vnext.d02_reviewed_source.prepare_historical_legal_sources`` twice: once with
the baseline commit and once with the candidate commit. Both runs use the same
saved source root, run offline, and report what changed in status and content.

Each sample runs in its own worker process with its own time limit, so a
crash or hang affects only that sample. The comparison is incomplete, and the
exit code is 2, when any of these holds:
- a requested sample has no result;
- a worker fails or exceeds ``--timeout-per-sample``;
- the tool fails outside the production call;
- the source root changes during the run;
- a code worktree changes during the run, including any new untracked or
  ignored file (workers do not write bytecode).
A sample that fails the same way on both sides is listed as unverified, not as
unchanged.

The tool creates two temporary git worktrees under the output directory. It
removes them afterwards unless ``--keep-code`` is given. It never writes to the
source root and does not call SEC or any model. Usage:
``docs/d02_preparation_comparison.md``.
"""
import argparse
import csv
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ENTRY_MODULE = 'vnext.d02_reviewed_source'
ENTRY_FUNCTION = 'prepare_historical_legal_sources'
CATEGORIES = ('SAME_OK', 'CHANGED_OK', 'FAIL_TO_OK', 'OK_TO_FAIL', 'SAME_FAIL', 'CHANGED_FAIL', 'NOT_COMPARED')
EXIT_COMPLETE, EXIT_FAIL_ON, EXIT_INCOMPLETE = 0, 1, 2
NETWORK_REFUSAL = 'NETWORK_DISABLED_BY_D02_PREPARATION_COMPARISON'
_PROPOSAL_FIELDS = frozenset({
    'coverage_status', 'coverage_reasons', 'note_references', 'checked_ranges', 'D02', 'D03',
    'd02_page_furniture', 'policy_hash', 'proposal_id', 'document_id', 'source_reference_id'})


def _reject_unserializable(value):
    raise TypeError('value is not JSON serializable: ' + type(value).__name__)


def _digest(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, default=_reject_unserializable)
    return 'sha256:' + hashlib.sha256(text.encode('utf-8')).hexdigest()


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(root):
    """Digest every file under ``root`` by relative path, size and SHA-256."""
    root = Path(root)
    entries, total = [], 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        for name in dirs + sorted(files):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                entries.append([relative, 'SYMLINK', os.readlink(path)])
            elif name in files:
                size = path.stat().st_size
                total += size
                entries.append([relative, size, _file_sha256(path)])
    entries.sort()
    return {'digest': _digest(entries), 'files': sum(1 for e in entries if e[1] != 'SYMLINK'),
            'symlinks': sum(1 for e in entries if e[1] == 'SYMLINK'), 'bytes': total}


def fingerprint(result):
    """Reduce one production result to the parts D02 depends on, in a stable form."""
    arguments, prepared = result['source_arguments'], result['prepared']
    target = arguments['target']
    sources = {}
    for sid, proposal in sorted(prepared['proposals'].items()):
        d02 = proposal.get('D02') or {}
        candidates = d02.get('candidates') or []
        extra = {k: v for k, v in proposal.items() if k not in _PROPOSAL_FIELDS}
        sources[sid] = {
            'coverage': [proposal.get('coverage_status'), sorted(proposal.get('coverage_reasons') or [])],
            'note_references': sorted(
                [r.get('reference'), r.get('status'),
                 [[c.get('start_block'), c.get('end_block_exclusive')] for c in r.get('range_candidates') or []]]
                for r in proposal.get('note_references') or []),
            'checked_ranges': sorted(
                [r.get('section_id'), r.get('start_block'), r.get('end_block_exclusive')]
                for r in proposal.get('checked_ranges') or []),
            'd02_candidates': sorted(
                [c.get('section_id'), c.get('block_index'), sorted(c.get('labels') or [])] for c in candidates),
            'd02_texts_digest': _digest(sorted([c.get('block_index'), c.get('text')] for c in candidates)),
            'd02_finding_status': d02.get('finding_status'),
            'furniture_removed': sorted(
                r.get('block_index') for r in (proposal.get('d02_page_furniture') or {}).get('removed_blocks') or []),
            'd03_digest': _digest(proposal.get('D03')),
            'coverage_record_digest': _digest((prepared.get('coverages') or {}).get(sid)),
            'other_fields': sorted(extra),
            'other_digest': _digest(extra),
            'policy_hash': proposal.get('policy_hash'),
        }
    requests = []
    for request in result['requests']:
        blocks = request.get('blocks') or []
        instructions = {k: request.get(k) for k in (
            'record_type', 'contract', 'metric_id', 'definition', 'system_prompt', 'response_protocol')}
        requests.append({
            'request_id': request.get('request_id'), 'source_id': request.get('source_id'),
            'pool': [b.get('block_id') for b in blocks], 'must_decide': list(request.get('must_decide') or []),
            'texts_digest': _digest([[b.get('block_id'), b.get('text')] for b in blocks]),
            'instructions_digest': _digest(instructions)})
    requests.sort(key=lambda r: (str(r['source_id']), str(r['request_id'])))
    admission = result.get('admission') or {}
    return {
        'selection': {k: target.get(k) for k in ('accession', 'entity', 'period_start', 'period_end')}
                     | {'raw_asset_ids': sorted(arguments.get('raw_blobs') or {})},
        'admission': {'record_type': admission.get('record_type'),
                      'source_manifest_sha256': admission.get('source_manifest_sha256'),
                      'request_attempts': len(admission.get('request_attempt_ids') or []),
                      'digest': _digest(admission)},
        'capability': [prepared.get('capability_status'), _digest(prepared.get('capability_gaps'))],
        'source_references_digest': _digest(prepared.get('source_references')),
        'sources': sources,
        'requests': requests,
    }


def _block_network():
    import socket

    def refuse(*_args, **_kwargs):
        raise OSError(NETWORK_REFUSAL)

    socket.socket.connect = refuse
    socket.socket.connect_ex = refuse
    socket.create_connection = refuse
    socket.getaddrinfo = refuse


def _child(args):
    """Worker: run the production entry of one code root for the given samples."""
    _block_network()
    code_root = Path(args.code_root).resolve()
    sys.path[:0] = [str(code_root / 'scripts'), str(code_root)]
    samples = json.loads(Path(args.samples_file).read_text(encoding='utf-8'))
    with open(args.out, 'a', encoding='utf-8') as out:
        def emit(record):
            out.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + '\n')
            out.flush()
        try:
            module = importlib.import_module(ENTRY_MODULE)
            entry = getattr(module, ENTRY_FUNCTION)
            entry_file = Path(module.__file__).resolve()
            if not entry_file.is_relative_to(code_root):
                raise ImportError('entry loaded from outside the code root: ' + str(entry_file))
        except Exception:
            failure = {'stage': 'import', 'traceback': traceback.format_exc()[-3000:]}
            for company, year in samples:
                emit({'sample': f'{company}:{year}', 'outcome': 'HARNESS_ERROR', 'error': failure})
            return 0
        for company, year in samples:
            started = time.monotonic()
            try:
                result = entry(repo_root=args.source_root, company_id=company, fiscal_year=year)
            except Exception as exc:  # every production refusal or crash is reported, never dropped
                record = {'outcome': 'ERROR', 'error': {
                    'type': type(exc).__name__, 'module': type(exc).__module__,
                    'reason': str(exc), 'category': getattr(exc, 'category', None)}}
            else:
                try:
                    record = {'outcome': 'OK', 'fingerprint': fingerprint(result)}
                except Exception:
                    record = {'outcome': 'HARNESS_ERROR',
                              'error': {'stage': 'fingerprint', 'traceback': traceback.format_exc()[-3000:]}}
            record.update(sample=f'{company}:{year}', seconds=round(time.monotonic() - started, 3),
                          entry_file=entry_file.relative_to(code_root).as_posix())
            emit(record)
    return 0


def _git(repo, *args):
    done = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit('git ' + ' '.join(args) + ' failed: ' + done.stderr.strip())
    return done.stdout.strip()


def registry_companies(code_root):
    with open(Path(code_root) / 'config' / 'company_registry.csv', newline='', encoding='utf-8') as handle:
        companies = [row['company_id'] for row in csv.DictReader(handle)]
    if not companies or len(companies) != len(set(companies)):
        raise SystemExit('company registry is empty or repeats a company_id')
    return companies


def parse_years(text):
    if '-' in text:
        first, last = (int(part) for part in text.split('-', 1))
        years = list(range(first, last + 1))
    else:
        years = [int(part) for part in text.split(',')]
    if not years or len(years) != len(set(years)) or not all(1990 <= y <= 2100 for y in years):
        raise SystemExit('invalid --fiscal-years: ' + text)
    return years


def run_workers(tasks, jobs, timeout_per_sample):
    """Run one worker process per task; each reports its exit, timeout and stderr tail.

    ``-I`` isolates the worker from the caller's environment and ``-B`` keeps it
    from writing bytecode, so any file left in a code worktree is a real change.
    """
    tool = str(Path(__file__).resolve())

    def run(task):
        command = [sys.executable, '-I', '-B', tool, '--child', '--code-root', task['code_root'],
                   '--source-root', task['source_root'], '--samples-file', task['samples_file'],
                   '--out', task['out']]
        started = time.monotonic()
        try:
            done = subprocess.run(command, cwd=task['code_root'], capture_output=True, text=True,
                                  timeout=timeout_per_sample * len(task['samples']))
            status = {'returncode': done.returncode, 'timeout': False, 'stderr_tail': done.stderr[-3000:]}
        except subprocess.TimeoutExpired as exc:
            stderr = exc.stderr.decode('utf-8', 'replace') if isinstance(exc.stderr, bytes) else (exc.stderr or '')
            status = {'returncode': None, 'timeout': True, 'stderr_tail': stderr[-3000:]}
        status.update(label=task['label'], samples=[f'{c}:{y}' for c, y in task['samples']],
                      seconds=round(time.monotonic() - started, 1))
        return status

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(run, tasks))


def run_version(*, label, code_root, source_root, samples, work_dir):
    """Return one worker task per sample for one code root."""
    tasks = []
    for index, sample in enumerate(samples):
        part = [sample]
        samples_file = Path(work_dir) / f'{label}-{index:03d}.samples.json'
        samples_file.write_text(json.dumps(part), encoding='utf-8')
        tasks.append({'label': label, 'code_root': str(code_root), 'source_root': str(source_root),
                      'samples': part, 'samples_file': str(samples_file),
                      'out': str(Path(work_dir) / f'{label}-{index:03d}.jsonl')})
    return tasks


def load_results(tasks):
    """Collect worker records; a repeated or unreadable record is a harness error."""
    results, problems = {}, []
    for task in tasks:
        path = Path(task['out'])
        lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
        for number, line in enumerate(lines, 1):
            try:
                record = json.loads(line)
                key = record['sample']
            except (ValueError, KeyError, TypeError):
                problems.append(f'{path.name}:{number}: unreadable worker record')
                continue
            if key in results:
                problems.append(f'{key}: more than one result')
                results[key] = {'sample': key, 'outcome': 'HARNESS_ERROR', 'error': {'stage': 'duplicate'}}
            else:
                results[key] = record
    return results, problems


def _set_change(field, before, after, limit=5):
    old = [json.dumps(x, sort_keys=True) for x in before]
    new = [json.dumps(x, sort_keys=True) for x in after]
    added = [x for x in new if x not in set(old)]
    removed = [x for x in old if x not in set(new)]
    return {'field': field, 'added': len(added), 'removed': len(removed),
            'examples_added': added[:limit], 'examples_removed': removed[:limit]}


def compare_fingerprints(base, cand):
    """List every difference between two successful preparations."""
    changes = []
    for field in ('selection', 'admission', 'capability', 'source_references_digest'):
        if base[field] != cand[field]:
            changes.append({'field': field, 'before': base[field], 'after': cand[field]})
    if set(base['sources']) != set(cand['sources']):
        changes.append({'field': 'source_references', 'before': sorted(base['sources']),
                        'after': sorted(cand['sources'])})
    for sid in sorted(set(base['sources']) & set(cand['sources'])):
        old, new = base['sources'][sid], cand['sources'][sid]
        for field in ('coverage', 'coverage_record_digest', 'd02_finding_status', 'd02_texts_digest',
                      'policy_hash', 'd03_digest', 'other_fields', 'other_digest'):
            if old[field] != new[field]:
                changes.append({'field': field, 'before': old[field], 'after': new[field]})
        for field in ('note_references', 'checked_ranges', 'd02_candidates', 'furniture_removed'):
            if old[field] != new[field]:
                changes.append(_set_change(field, old[field], new[field]))
    if len(base['requests']) != len(cand['requests']):
        changes.append({'field': 'request_count', 'before': len(base['requests']), 'after': len(cand['requests'])})
    for old, new in zip(base['requests'], cand['requests']):
        if old['request_id'] != new['request_id']:
            changes.append({'field': 'request_id', 'before': old['request_id'], 'after': new['request_id'],
                            'note': 'saved model answers recorded for the old request no longer apply'})
        for field in ('pool', 'must_decide'):
            if old[field] != new[field]:
                changes.append(_set_change(field, old[field], new[field]))
        for field in ('texts_digest', 'instructions_digest', 'source_id'):
            if old[field] != new[field]:
                changes.append({'field': field, 'before': old[field], 'after': new[field]})
    return changes


def classify(base, cand):
    """Return (category, changes) for one sample; missing or harness results are never 'same'."""
    if base is None or cand is None or 'HARNESS_ERROR' in (base.get('outcome'), cand.get('outcome')):
        return 'NOT_COMPARED', []
    outcomes = (base['outcome'], cand['outcome'])
    if outcomes == ('OK', 'OK'):
        changes = compare_fingerprints(base['fingerprint'], cand['fingerprint'])
        return ('CHANGED_OK' if changes else 'SAME_OK'), changes
    if outcomes == ('ERROR', 'OK'):
        return 'FAIL_TO_OK', []
    if outcomes == ('OK', 'ERROR'):
        return 'OK_TO_FAIL', []
    if outcomes == ('ERROR', 'ERROR'):
        return ('SAME_FAIL' if base['error'] == cand['error'] else 'CHANGED_FAIL'), []
    return 'NOT_COMPARED', []


def _brief(record):
    if record is None:
        return {'outcome': 'MISSING'}
    brief = {'outcome': record.get('outcome'), 'seconds': record.get('seconds')}
    if record.get('outcome') == 'OK':
        requests = record['fingerprint']['requests']
        brief.update(requests=len(requests), request_ids=[r['request_id'] for r in requests])
    else:
        brief['error'] = record.get('error')
    return brief


def compare(samples, baseline, candidate):
    counts = {category: 0 for category in CATEGORIES}
    entries = []
    for key in samples:
        category, changes = classify(baseline.get(key), candidate.get(key))
        counts[category] += 1
        entries.append({'sample': key, 'category': category, 'baseline': _brief(baseline.get(key)),
                        'candidate': _brief(candidate.get(key)), 'changes': changes})
    unexpected = sorted((set(baseline) | set(candidate)) - set(samples))
    return {'requested': len(samples), 'counts': counts, 'unexpected_results': unexpected,
            'entries': entries, 'all_samples_compared': counts['NOT_COMPARED'] == 0 and not unexpected}


def _describe(change):
    if 'added' in change:
        return f"{change['field']} +{change['added']} -{change['removed']}"
    if change['field'] == 'request_id':
        return 'request_id changed (saved model answers for the old request no longer apply)'
    before, after = change['before'], change['after']
    if isinstance(before, (dict, list)) or isinstance(after, (dict, list)):
        return f"{change['field']} changed"
    return f"{change['field']}: {before} -> {after}"


def render_summary(manifest, report):
    lines = ['# D02 preparation comparison', '']
    versions, inputs, scope = manifest['versions'], manifest['inputs'], manifest['scope']
    for label in ('baseline', 'candidate'):
        lines.append(f"- {label}: `{versions[label]['ref']}` = `{versions[label]['commit']}`")
    before = inputs['source_root_before']
    lines.append(f"- source root: `{inputs['source_root']}`: {before['files']} files, {before['bytes']} bytes, "
                 f"`{before['digest']}`; unchanged during run: {inputs['unchanged_during_run']}")
    years = scope['fiscal_years']
    shown = f'{years[0]}-{years[-1]}' if years == list(range(years[0], years[-1] + 1)) else ','.join(map(str, years))
    outside = scope['outside_baseline_registry']
    if outside:
        extent = f' (includes companies outside the baseline registry: {outside})'
    elif scope['subset_of_registry']:
        extent = ' (SUBSET of the baseline registry)'
    else:
        extent = ' (whole baseline registry)'
    lines.append(f"- scope: {len(scope['companies'])} companies x fiscal years {shown} = {report['requested']} samples"
                 + extent)
    added = sorted(set(scope['registry_candidate']) - set(scope['registry_baseline']))
    removed = sorted(set(scope['registry_baseline']) - set(scope['registry_candidate']))
    if added or removed:
        lines.append(f'- candidate registry differs from baseline: added {added}, removed {removed}')
    env = manifest['environment']
    lines.append(f"- environment: Python {env['python']}, {env['platform']}, network blocked in workers, "
                 f"{env['workers']} workers")
    lines.append(f"- result: {'COMPLETE' if manifest['complete'] else 'INCOMPLETE'}")
    for problem in manifest['problems']:
        lines.append(f'  - {problem}')
    counts = report['counts']
    lines.append(f"- verified identical: {counts['SAME_OK']}; content changed: {counts['CHANGED_OK']}; "
                 f"status changed: {counts['FAIL_TO_OK'] + counts['OK_TO_FAIL']}; "
                 f"failing on both sides (unverified): {counts['SAME_FAIL'] + counts['CHANGED_FAIL']}; "
                 f"not compared: {counts['NOT_COMPARED']}")
    lines += ['', '| category | samples |', '|---|---|']
    lines += [f'| {c} | {report["counts"][c]} |' for c in CATEGORIES]
    sections = (
        ('NOT_COMPARED', 'Not compared: the comparison is incomplete'),
        ('OK_TO_FAIL', 'Prepared before, fails now'),
        ('FAIL_TO_OK', 'Failed before, prepared now'),
        ('CHANGED_OK', 'Prepared on both sides with different content'),
        ('CHANGED_FAIL', 'Fails on both sides for different reasons'),
        ('SAME_FAIL', 'Fails the same way on both sides: not verified by this comparison'))
    for category, title in sections:
        rows = [e for e in report['entries'] if e['category'] == category]
        if not rows:
            continue
        lines += ['', f'## {title} ({len(rows)})']
        for entry in rows:
            detail = '; '.join(_describe(c) for c in entry['changes'])
            if not detail:
                b, c = entry['baseline'], entry['candidate']
                detail = f"baseline {b.get('outcome')} {(b.get('error') or {}).get('reason', '')}".rstrip() + \
                         f" / candidate {c.get('outcome')} {(c.get('error') or {}).get('reason', '')}".rstrip()
            lines.append(f"- `{entry['sample']}`: {detail}")
    same = report['counts']['SAME_OK']
    lines += ['', f'{same} samples were prepared with identical compared content on both sides.', '']
    return '\n'.join(lines)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--baseline', help='commit-ish of the reference code, e.g. origin/main')
    parser.add_argument('--candidate', help='commit-ish of the code under review')
    parser.add_argument('--source-root', help='saved source-inputs root, read only')
    parser.add_argument('--output-dir', help='new directory for the report; must not exist')
    parser.add_argument('--companies', help='comma-separated company ids; default: whole baseline registry')
    parser.add_argument('--fiscal-years', default='2021-2025', help='e.g. 2021-2025 or 2024,2025')
    parser.add_argument('--jobs', type=int, default=4, help='worker processes across both versions')
    parser.add_argument('--timeout-per-sample', type=int, default=600,
                        help='seconds allowed for each sample, which runs in its own worker process')
    parser.add_argument('--fail-on', default='', help='comma-separated categories that make the exit code 1')
    parser.add_argument('--keep-code', action='store_true', help='keep the two worktrees after the run')
    parser.add_argument('--repo', help='git repository holding both commits; default: this checkout')
    parser.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--code-root', help=argparse.SUPPRESS)
    parser.add_argument('--samples-file', help=argparse.SUPPRESS)
    parser.add_argument('--out', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.child:
        missing = [name for name in ('baseline', 'candidate', 'source_root', 'output_dir') if not getattr(args, name)]
        if missing:
            parser.error('missing: ' + ', '.join('--' + m.replace('_', '-') for m in missing))
        unknown = sorted(set(filter(None, args.fail_on.split(','))) - set(CATEGORIES))
        if unknown or args.jobs < 1 or args.timeout_per_sample < 1:
            parser.error('invalid --fail-on, --jobs or --timeout-per-sample')
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.child:
        return _child(args)
    repo = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[1]
    source_root = Path(args.source_root).resolve()
    out = Path(args.output_dir).resolve()
    if not source_root.is_dir():
        raise SystemExit('source root is not a directory: ' + str(source_root))
    if out == source_root or out.is_relative_to(source_root) or source_root.is_relative_to(out):
        raise SystemExit('output directory and source root must not contain each other')
    out.mkdir(parents=True, exist_ok=False)
    versions = {}
    for label, ref in (('baseline', args.baseline), ('candidate', args.candidate)):
        commit = _git(repo, 'rev-parse', '--verify', ref + '^{commit}')
        # Parents let a reader rebuild a local combination commit from reachable commits.
        versions[label] = {'ref': ref, 'commit': commit, 'tree': _git(repo, 'rev-parse', commit + '^{tree}'),
                           'parents': _git(repo, 'rev-list', '--parents', '-n', '1', commit).split()[1:]}
    code, work = out / 'code', out / 'work'
    code.mkdir()
    work.mkdir()
    added = []
    try:
        for label in versions:
            _git(repo, 'worktree', 'add', '--detach', str(code / label), versions[label]['commit'])
            added.append(code / label)
        registry = {label: registry_companies(code / label) for label in versions}
        companies = ([c for c in args.companies.split(',') if c] if args.companies is not None
                     else registry['baseline'])
        unknown = sorted(set(companies) - set(registry['baseline']) - set(registry['candidate']))
        if not companies or unknown or len(companies) != len(set(companies)):
            raise SystemExit('--companies must name distinct companies from either registry; unknown: '
                             + (', '.join(unknown) or 'none'))
        years = parse_years(args.fiscal_years)
        samples = [f'{company}:{year}' for company in companies for year in years]
        pairs = [[company, year] for company in companies for year in years]
        before = tree_digest(source_root)
        tasks = []
        for label in versions:
            tasks += run_version(label=label, code_root=code / label, source_root=source_root,
                                 samples=pairs, work_dir=work)
        workers = run_workers(tasks, args.jobs, args.timeout_per_sample)
        after = tree_digest(source_root)
        results, problems = {}, []
        for label in versions:
            results[label], unreadable = load_results([t for t in tasks if t['label'] == label])
            problems += [f'{label}: {p}' for p in unreadable]
        for status in workers:
            if status['timeout'] or status['returncode'] != 0:
                problems.append(f"{status['label']} worker for {', '.join(status['samples'])}: "
                                f"returncode {status['returncode']}, timeout {status['timeout']}")
        for label in versions:
            changed = _git(code / label, 'status', '--porcelain', '--untracked-files=all', '--ignored').splitlines()
            if changed:
                problems.append(f'{label} code worktree changed during the run: {changed[:5]}')
        if before != after:
            problems.append('source root changed during the run')
        report = compare(samples, results['baseline'], results['candidate'])
        if not report['all_samples_compared']:
            problems.append(f"{report['counts']['NOT_COMPARED']} of {report['requested']} samples not compared"
                            + (f"; unexpected results {report['unexpected_results']}" if report['unexpected_results'] else ''))
        manifest = {
            'record_type': 'D02_PREPARATION_COMPARISON', 'tool_sha256': _file_sha256(__file__),
            'entry': f'{ENTRY_MODULE}.{ENTRY_FUNCTION}', 'versions': versions,
            'inputs': {'source_root': str(source_root), 'source_root_before': before,
                       'source_root_after': after, 'unchanged_during_run': before == after},
            'scope': {'companies': companies, 'fiscal_years': years,
                      'subset_of_registry': set(companies) < set(registry['baseline']),
                      'outside_baseline_registry': sorted(set(companies) - set(registry['baseline'])),
                      'registry_baseline': registry['baseline'], 'registry_candidate': registry['candidate']},
            'environment': {'python': platform.python_version(), 'implementation': platform.python_implementation(),
                            'platform': platform.platform(), 'git': _git(repo, '--version'),
                            'network': 'socket connect/create_connection/getaddrinfo refused in workers',
                            'workers': args.jobs, 'timeout_per_sample_seconds': args.timeout_per_sample},
            'workers': workers, 'problems': problems, 'complete': not problems}
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        (out / 'comparison.json').write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        summary = render_summary(manifest, report)
        (out / 'summary.md').write_text(summary, encoding='utf-8')
        print(summary)
    finally:
        if not args.keep_code:
            for path in added:
                _git(repo, 'worktree', 'remove', '--force', str(path))
    if not manifest['complete']:
        return EXIT_INCOMPLETE
    flagged = set(filter(None, args.fail_on.split(',')))
    return EXIT_FAIL_ON if any(report['counts'][c] for c in flagged) else EXIT_COMPLETE


if __name__ == '__main__':
    sys.exit(main())
