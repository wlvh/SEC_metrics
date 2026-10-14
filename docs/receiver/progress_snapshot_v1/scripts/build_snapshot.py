#!/usr/bin/env python3
"""Receiver progress snapshot: registered companies x 39 metrics x five issuer fiscal years.

Builds one complete scope table from inputs that already exist:

* a code checkout (company registry, Issue #44 reference map, period selection);
* the saved historical source root (only read, for fiscal-year -> period selection);
* receiver offline history runs of the public company CLI (one directory per company);
* the D02 preparation comparison (tools/compare_d02_preparation.py output) plus
  optional extra D02 samples, and the saved model ledger, to say whether a D02
  request can be prepared and whether a saved answer matches it;
* the active publication bundle (current-period view);
* an acceptance registry (recorded original-source checks and adoption records).

No network, no model/SEC/paid calls, nothing outside --out is written. Every
input is optional except the code root and source root; a missing layer is
reported as missing in the table, never filled in.
"""
import argparse, csv, collections, datetime as dt, hashlib, json, os, re, sys, tarfile
from pathlib import Path

VALUE_STATUSES = {'OK', 'OK_APPROX', 'APPROX', 'XBRL_OK', 'DIM_XBRL_OK', 'STD_XBRL_OK', 'TEXT_QUAL', '8K_ITEM_OK',
                  'DEF14A_OK', 'MDA_OK', 'NONE_FOUND', 'NO_EVENT', 'ZERO_EVENTS'}
NON_NUMERIC_TERMINAL = {'N_A_STRUCTURAL', 'NOT_MEANINGFUL', 'NOT_APPLICABLE'}
NOT_DISCLOSED = {'NOT_AVAILABLE_SEC', 'NOT_DISCLOSED'}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path):
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def load_code(code_root):
    sys.path[:0] = [str(code_root / 'scripts'), str(code_root / 'tools'), str(code_root)]


# ---------------------------------------------------------------- scope layer
def registry(code_root):
    return read_csv(code_root / 'config/company_registry.csv')


def reference_rows(code_root):
    data = json.loads((code_root / 'catalog/reference/generated/sic_metric_map.json').read_text(encoding='utf-8'))
    return data, data['rows']


def windows(code_root, source_root, companies, years=range(2019, 2028)):
    """Latest five issuer fiscal years that resolve from the saved sources."""
    from vnext.normal_period_selection import resolve_period_selection
    out = {}
    for c in companies:
        resolved = {}
        for fy in years:
            try:
                sel = resolve_period_selection(repo_root=Path(source_root), company_id=c, fiscal_year=fy)
            except Exception as error:  # an unresolved label is recorded, not guessed
                resolved[fy] = {'error': type(error).__name__ + ': ' + str(error)[:160]}
                continue
            end = sel['target_report_end']
            prior = sel.get('prior_report_end')
            start = (dt.date.fromisoformat(prior) + dt.timedelta(days=1)).isoformat() if prior else ''
            days = ((dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days + 1) if start else ''
            reg = sel.get('period_registrant') or {}
            resolved[fy] = {'report_end': end, 'period_start': start, 'period_days': days,
                            'accession': sel['current_filing']['accessionNumber'],
                            'filing_date': sel['current_filing']['filingDate'],
                            'amendments': [a['accessionNumber'] for a in sel.get('current_amendments', [])],
                            'reporting_cik': sel['reporting_cik'],
                            'registrant_role': reg.get('role', 'PRIMARY'),
                            'prior_status': sel.get('prior_status', '')}
        ok = sorted(fy for fy, v in resolved.items() if 'error' not in v)
        out[c] = {'resolved': resolved, 'window': ok[-5:]}
    return out


# ---------------------------------------------------------- observation layers
# company_local._run_saved_history at main 681b35d8 has no case factory for B13, C02 and D03;
# D02 is processed only with --saved-legal-reviews (one period per run), which this snapshot does
# not pass: D02 is described by the preparation comparison and the saved ledger instead.
HISTORY_NOT_CONNECTED = {'B13', 'C02', 'D02', 'D03'}


def _partial_rows(cdir, company_id, metrics, years):
    """Rows from per-period controller state while a run is still going."""
    rows = {}
    for m in metrics:
        for fy in years:
            if m in HISTORY_NOT_CONNECTED:
                rows[(company_id, m, fy)] = {'company_id': company_id, 'metric_id': m, 'fiscal_year': str(fy),
                    'local_metric_status': 'PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED',
                    'status': 'PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED',
                    'notes': 'This saved-source branch has no complete current processing interface for ' + m,
                    '_source': 'HISTORY_ENTRY_NOT_CONNECTED'}
                continue
            pdir = cdir / 'work' / 'updates' / m / 'periods' / ('FY%d' % fy)
            check = pdir / 'latest-check.json'
            if not check.is_file():
                continue
            state = json.loads(check.read_text())
            row = {'company_id': company_id, 'metric_id': m, 'fiscal_year': str(fy),
                   'local_metric_status': state.get('status', ''), '_source': 'HISTORY_RUN_PARTIAL'}
            version = state.get('version')
            current = pdir / 'current-result.json'
            if current.is_file():
                version = json.loads(current.read_text()).get('version') or version
            matrix = pdir / 'results' / str(version) / 'metrics_matrix.csv' if version else None
            if matrix is not None and matrix.is_file():
                saved = read_csv(matrix)
                if saved:
                    row.update({k: v for k, v in saved[0].items() if k in (
                        'value', 'unit', 'status', 'period_start', 'period_end', 'accession', 'notes')})
                    row['result_id'] = state.get('result_id') or ''
            row['notes'] = ' '.join(x for x in (state.get('result_reason_code'), state.get('reason'),
                                             state.get('error_category'), (row.get('notes') or '')[:200]) if x)
            if not row.get('status'):
                row['status'] = state.get('status', '')
            rows[(company_id, m, fy)] = row
    return rows


def history_observations(history_root, metrics=(), windows_by_company=None):
    """{(company, metric, fy): row} from each company's receiver run (final or partial)."""
    obs, runs = {}, {}
    if history_root is None:
        return obs, runs
    for cdir in sorted(Path(history_root).iterdir()):
        if not cdir.is_dir():
            continue
        done = cdir / 'done.json'
        info = json.loads(done.read_text()) if done.is_file() else {'exit': None}
        read_back = cdir / 'results-read' / 'metrics_matrix.csv'
        outs = sorted((cdir / 'out').glob('*/metrics_matrix.csv')) if (cdir / 'out').is_dir() else []
        source = read_back if read_back.is_file() else (outs[-1] if outs else None)
        info['run_dir'] = str(source.parent) if source else ''
        info['mode'] = ('RESULTS_READ_BACK' if source == read_back else 'FINAL_OUTPUT') if source else 'PARTIAL_STATE'
        runs[cdir.name] = info
        if source:
            for row in read_csv(source):
                fy = row.get('fiscal_year') or ''
                if not fy.isdigit():
                    continue
                check = cdir / 'work' / 'updates' / row['metric_id'] / 'periods' / ('FY' + fy) / 'latest-check.json'
                if check.is_file():  # the withheld reason code lives in the per-period check
                    state = json.loads(check.read_text())
                    code = ' '.join(x for x in (state.get('result_reason_code'), state.get('error_category')) if x)
                    if code:
                        row['notes'] = code + ' ' + (row.get('notes') or '')
                row['_source'] = 'HISTORY_RUN'
                obs[(row.get('company_id') or cdir.name, row['metric_id'], int(fy))] = row
        elif windows_by_company and cdir.name in windows_by_company:
            obs.update(_partial_rows(cdir, cdir.name, metrics, windows_by_company[cdir.name]))
    return obs, runs


def d02_observations(comparison_paths, ledger):
    """{(company, fy): {'outcome','reason','request_ids','saved_answer'}} from compare outputs."""
    saved = {}
    if ledger and Path(ledger).is_file():
        with tarfile.open(ledger, 'r:gz') as t:
            names = t.getnames()
            for n in names:
                p = n.split('/')
                if len(p) == 4 and p[:2] == ['root', 'calls'] and p[3] == 'semantic-request.json':
                    req = json.load(t.extractfile(n))
                    if req.get('metric_id') != 'D02':
                        continue
                    term = json.load(t.extractfile('root/calls/%s/terminal.json' % p[2]))
                    saved[req['request_id']] = (p[2], term.get('status'))
    out = {}
    for path in comparison_paths:
        data = json.loads(Path(path).read_text())
        for e in data['entries']:
            company, fy = e['sample'].rsplit(':', 1)
            cand = e['candidate']
            rec = {'outcome': cand.get('outcome'), 'source': str(path)}
            if cand.get('outcome') == 'OK':
                ids = cand.get('request_ids', [])
                hits = [saved[i] for i in ids if i in saved]
                rec['request_ids'] = ids
                rec['saved_answer'] = ('MATCHED_SUCCEEDED:' + ','.join(h[0] for h in hits)
                                       if ids and len(hits) == len(ids) and all(h[1] == 'SUCCEEDED' for h in hits)
                                       else 'NONE')
            else:
                err = cand.get('error') or {}
                rec['reason'] = err.get('reason') or err.get('type') or 'UNKNOWN'
            out[(company, int(fy))] = rec
    return out, len(saved)


def publication_rows(pub_dir, name_to_id):
    if pub_dir is None:
        return {}, None
    pub_dir = Path(pub_dir)
    rows = read_csv(pub_dir / 'metrics_matrix.csv')
    out = {}
    for r in rows:
        cid = name_to_id.get(r['company'])
        out[(cid, r['metric_id'])] = r
    manifest = json.loads((pub_dir / 'publication_manifest.json').read_text())
    receipt = json.loads((pub_dir / 'publication_validation_receipt.json').read_text())
    meta = {'publication_id': manifest['publication_id'], 'publication_credit': manifest['publication_credit'],
            'validation_status': receipt['status'],
            'formal_remaining_conditions': receipt.get('formal_remaining_conditions', []),
            'rows': len(rows)}
    return out, meta


# ------------------------------------------------------------- classification
REASON_CODE_CLASS = {  # exact reason codes seen in runs; checked before the regex fallback
    'TRAIT_NOT_APPLICABLE': 'TERMINAL_NON_NUMERIC',
    'RATIO_NUMERATOR_NOT_POSITIVE': 'TERMINAL_NON_NUMERIC',
    'C04_COMPARABLE_AUDITOR_FACTS_MISSING': 'WITHHELD_BY_CURRENT_RULE',
    'HISTORICAL_PAIRED_MEASURE_NOT_COMPARABLE': 'WITHHELD_BY_CURRENT_RULE',
    'C03_MULTIPLE_REPORTED_AMOUNTS': 'WITHHELD_CONFLICT_OR_AMBIGUOUS',
    'C03_PROXY_SCT_MORE_THAN_ONE_CHIEF_EXECUTIVE': 'WITHHELD_CONFLICT_OR_AMBIGUOUS',
    'E01_ITEM_METADATA_BODY_CONFLICT': 'WITHHELD_CONFLICT_OR_AMBIGUOUS',
    'MISSING_SAVED_SOURCE': 'INPUT_GAP_SOURCE',
    'B06_SOURCE_RELATIONSHIP_UNRESOLVED': 'DEV_GAP_SOURCE_RELATION',
    'HISTORICAL_BANK_INPUT_UNRESOLVED': 'DEV_GAP_SOURCE_RELATION',
    'E01_CONTENT_RESPONSE_NOT_AVAILABLE_FOR_REQUEST': 'ANSWER_GAP_MODEL_RESPONSE',
    'HISTORICAL_LODGING_METRIC_NOT_APPLICABLE': 'DEV_GAP_NA_REPORTED_AS_ERROR',
    'HISTORICAL_D04_SAVED_SOURCE_MISSING_OR_AMBIGUOUS': 'ANSWER_GAP_NO_SAVED_D04_CALL',
    'D02_REFERENCED_LETTERED_SUBNOTE_NOT_MIGRATED': 'DEV_GAP_NAVIGATION_OR_PARSE',
    'TEXT_V2_LEGAL_SOURCE_NAVIGATION_INCOMPLETE': 'DEV_GAP_NAVIGATION_OR_PARSE',
    'D02_HISTORICAL_AMENDMENT_OR_SUCCESSOR_NOT_RECEIVED': 'DEV_GAP_AMENDMENT_OR_SUCCESSOR',
}
ACCESSION = re.compile(r'^\d{10}-\d{2}-\d{6}$')
CODE = re.compile(r'\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b')  # upper-case code tokens, in order of appearance

REASON_CLASSES = [  # (class, regex over reason/status text), first match wins
    ('ANSWER_GAP_MODEL_RESPONSE', r'MODEL_RESPONSE_REQUIRED|SAVED_(?:ANSWER|RESPONSE|REVIEW)|NO_MATCHING_(?:ANSWER|RESPONSE)|ANSWER_REQUIRED'),
    ('INPUT_GAP_SOURCE', r'SOURCE_(?:MISSING|NOT_SAVED|UNAVAILABLE)|NOT_SAVED|MISSING_SOURCE|SOURCE_REQUIRED|FISCAL_YEAR_MISSING'),
    ('DEV_GAP_AMENDMENT_OR_SUCCESSOR', r'AMENDMENT|SUCCESSOR|PREDECESSOR'),
    ('DEV_GAP_NOT_CONNECTED', r'PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED|IMPLEMENTATION|NOT_IMPLEMENTED|NOT_MIGRATED|UNSUPPORTED|NOT_CONNECTED'),
    ('DEV_GAP_NAVIGATION_OR_PARSE', r'NAVIGATION|NOT_UNIQUELY_LOCATED|PARSE|LOCATOR|OUTSIDE_ELIGIBLE_POOL'),
    ('WITHHELD_CONFLICT_OR_AMBIGUOUS', r'CONFLICT|AMBIGUOUS|MISMATCH'),
]


def classify(local, status, validity, reason, value):
    codes = CODE.findall(reason or '')
    # the fallback patterns see status fields and reason codes only, never descriptive notes
    # (a note such as 'successor contract' must not decide a class)
    text = ' '.join(x for x in (local, status, validity, *codes) if x)
    if validity == 'CONFIRMED_INVALID' or status == 'WITHHELD_KNOWN_DEFECT':
        return 'KNOWN_DEFECT_WITHHELD'
    for code in codes:
        if code in REASON_CODE_CLASS:
            return REASON_CODE_CLASS[code]
    if status in VALUE_STATUSES and value not in (None, ''):
        return 'VALUE'
    if status in VALUE_STATUSES:
        return 'VALUE_STATUS_WITHOUT_VALUE'
    if status in NON_NUMERIC_TERMINAL:
        return 'TERMINAL_NON_NUMERIC'
    if status in NOT_DISCLOSED:
        return 'TERMINAL_NOT_DISCLOSED'
    for name, pattern in REASON_CLASSES:
        if re.search(pattern, text, re.I):
            return name
    if local == 'INPUT_OR_EXECUTION_FAILED':
        return 'DEV_GAP_EXECUTION_ERROR'
    if 'WITHHELD' in text:
        return 'WITHHELD_OTHER'
    return 'UNCLASSIFIED'


OWNER_NEXT = {
    'VALUE': ('', '核对原件依据与用户采纳（见对应列）'),
    'VALUE_STATUS_WITHOUT_VALUE': ('#47', '状态为有值但值为空，开发者核实'),
    'TERMINAL_NON_NUMERIC': ('', '按现行规则的非数值终态；如需改口径属用户决定'),
    'TERMINAL_NOT_DISCLOSED': ('', '按现行规则为未披露；原件核对依据见对应列'),
    'KNOWN_DEFECT_WITHHELD': ('#28/#47', '已登记错值，修补后重算'),
    'ANSWER_GAP_MODEL_RESPONSE': ('用户', '需新的模型回答；调用额度由用户决定（#153 第 6 节）'),
    'INPUT_GAP_SOURCE': ('#47', '缺保存原件：先查已有恢复来源，确需新 SEC 获取由用户决定'),
    'DEV_GAP_AMENDMENT_OR_SUCCESSOR': ('#47', '修订年报/继任主体处理未接入'),
    'DEV_GAP_NOT_CONNECTED': ('#47', '历史入口未接入该指标或该族'),
    'DEV_GAP_NAVIGATION_OR_PARSE': ('#47', '原件定位/解析缺口，按对应 PR 处理'),
    'DEV_GAP_EXECUTION_ERROR': ('#47', '执行报错，需开发者复现'),
    'WITHHELD_CONFLICT_OR_AMBIGUOUS': ('#47', '按规则扣留（冲突/歧义）；开发者说明是否为合理终态'),
    'WITHHELD_OTHER': ('#47', '扣留原因待开发者归类'),
    'UNCLASSIFIED': ('接收方', '状态组合未归类，接收方补映射'),
    'WITHHELD_BY_CURRENT_RULE': ('', '现行规则下的合理扣留（如 C04 缺上一年审计师事实、B02 前后期不可比）；改规则属用户决定'),
    'DEV_GAP_SOURCE_RELATION': ('#47', '来源关系或输入未解决（B06 负债组成、银行输入等），按对应指标族处理'),
    'DEV_GAP_NA_REPORTED_AS_ERROR': ('#47', '行业不适用却以报错结束，应输出结构性不适用'),
    'ANSWER_GAP_NO_SAVED_D04_CALL': ('用户/#47', '该年没有已保存的 D04 回答；新增调用由用户决定，#47 确认含义'),
    'NO_OBSERVATION': ('接收方', '本次快照未取得观察（运行未完成或未覆盖）'),
}


def to_number(v):
    try:
        return float(str(v).replace(',', ''))
    except (TypeError, ValueError):
        return None


def same_value(recorded, current):
    """Compare at the recorded precision; strings compare exactly."""
    a, b = to_number(recorded), to_number(current)
    if a is not None and b is not None:
        text = str(recorded).strip()
        decimals = len(text.split('.')[1]) if '.' in text else 0
        if decimals:
            return round(b, decimals) == round(a, decimals)
        return abs(a - b) <= max(0.5, 1e-9 * abs(a))
    return str(recorded).strip() == str(current).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--code-root', required=True, type=Path)
    ap.add_argument('--source-root', required=True, type=Path)
    ap.add_argument('--periods', type=Path, help='directory of resolve_periods.py outputs (one JSON per company)')
    ap.add_argument('--history-root', type=Path)
    ap.add_argument('--history-rows', type=Path, help='history_rows.csv written by an earlier build (replaces --history-root)')
    ap.add_argument('--d02-comparison', action='append', default=[])
    ap.add_argument('--d02-ledger')
    ap.add_argument('--publication', type=Path)
    ap.add_argument('--content-checks', type=Path, help='extract_content_checks.py output (#47 content-acceptance)')
    ap.add_argument('--prior-readings', type=Path, help='#47 previous-business-readings.json')
    ap.add_argument('--receiver-checks', type=Path, help='receiver_checks.json')
    ap.add_argument('--adoption-records', type=Path, help='adoption_records.json')
    ap.add_argument('--defects-file', type=Path, help='known_result_defects.json to use instead of the one in --code-root '
                    '(the register is knowledge about results, so a later main may be newer than the observing code)')
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    load_code(a.code_root.resolve())

    reg = registry(a.code_root)
    companies = [r['company_id'] for r in reg]
    name_to_id = {r['display_name']: r['company_id'] for r in reg}
    ref_data, ref = reference_rows(a.code_root)
    ref_by = {}
    problems = []
    for r in ref:
        for cid in r['baseline_sample_company_ids']:
            ref_by[(cid, r['metric_id'])] = r
    metrics = sorted({r['metric_id'] for r in ref})
    for row in reg:  # the company must fall inside its reference SIC range and profile
        for m in metrics:
            r = ref_by.get((row['company_id'], m))
            if r is None:
                problems.append('REFERENCE_ROW_MISSING:%s:%s' % (row['company_id'], m))
            elif not (r['sic_start'] <= row['sic'] <= r['sic_end'] and r['profile'] == row['industry_profile']):
                problems.append('REFERENCE_RANGE_MISMATCH:%s:%s' % (row['company_id'], m))

    if a.periods:
        win = {}
        for f in sorted(Path(a.periods).glob('*.json')):
            data = json.loads(f.read_text())
            for c, v in data['companies'].items():
                v['resolved'] = {int(k): x for k, x in v['resolved'].items()}
                win[c] = v
        missing = [c for c in companies if c not in win]
        if missing:
            win.update(windows(a.code_root, a.source_root, missing, years=range(2020, 2028)))
    else:
        win = windows(a.code_root, a.source_root, companies, years=range(2020, 2028))
    if a.history_rows:
        hist = {(r['company_id'], r['metric_id'], int(r['fiscal_year'])): r for r in read_csv(a.history_rows)}
        runs = json.loads((a.history_rows.parent / 'history_runs.json').read_text()) if (a.history_rows.parent / 'history_runs.json').is_file() else {}
    else:
        hist, runs = history_observations(a.history_root, metrics, {c: win[c]['window'] for c in win})
    for c in companies:
        runs.setdefault(c, {'mode': 'NOT_RUN'})
    for c in companies:  # not-connected metrics are a code fact, independent of run progress
        for m in HISTORY_NOT_CONNECTED:
            for fy in win.get(c, {}).get('window', []):
                hist.setdefault((c, m, fy), {'company_id': c, 'metric_id': m, 'fiscal_year': str(fy),
                    'local_metric_status': 'PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED',
                    'status': 'PROCESSING_INPUT_OR_IMPLEMENTATION_REQUIRED',
                    'notes': ('No history case factory for ' + m if m != 'D02' else 'D02 history needs --saved-legal-reviews (one period per run); not supplied, see d02_* columns'), '_source': 'HISTORY_ENTRY_NOT_CONNECTED'})
    hist_fields = ['company_id', 'metric_id', 'fiscal_year', '_source', 'local_metric_status', 'status', 'value', 'unit',
                   'period_start', 'period_end', 'accession', 'result_validity', 'result_id', 'notes']
    with open(a.out / 'history_rows.csv', 'w', encoding='utf-8', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=hist_fields, extrasaction='ignore')
        wr.writeheader()
        for key in sorted(hist, key=lambda k: (k[0], k[1], k[2])):
            r = dict(hist[key]); r.setdefault('company_id', key[0]); r['fiscal_year'] = str(key[2])
            wr.writerow({k: r.get(k, '') for k in hist_fields})
    (a.out / 'history_runs.json').write_text(json.dumps(runs, indent=1, sort_keys=True))
    d02, ledger_answers = d02_observations(a.d02_comparison, a.d02_ledger)
    pub, pub_meta = publication_rows(a.publication, name_to_id)
    defects = collections.defaultdict(list)
    defect_values = collections.defaultdict(set)  # the withdrawn value itself, when the register records it
    defects_file = a.defects_file or a.code_root / 'docs/evidence/issue28_continuous/known_result_defects.json'
    for d in json.loads(defects_file.read_text())['defects']:
        key = (d.get('company_id'), d.get('metric_id'), d.get('period_end'))
        defects[key].append(
            d['defect_id'] + ('(released:' + str(len(d['released'] if isinstance(d['released'], list) else [d['released']])) + ')' if d.get('released') else ''))
        if d.get('reported_value') not in (None, ''):
            defect_values[key].add(str(d['reported_value']))
    content = json.loads(a.content_checks.read_text()) if a.content_checks else {'checks': [], 'commit': None}
    prior = json.loads(a.prior_readings.read_text()) if a.prior_readings else []
    receiver = json.loads(a.receiver_checks.read_text()) if a.receiver_checks else {'entries': []}
    # record = (basis, verdict, read value, filings, source, sha256 of the checked published text)
    by_period = collections.defaultdict(list)
    by_year = collections.defaultdict(list)
    cik_to_id = {}
    for row in reg:  # every registered CIK role, e.g. predecessor:813828
        for part in [row['primary_cik']] + [x.split(':')[-1] for x in (row.get('roles') or '').split(';') if x]:
            if part.strip():
                cik_to_id.setdefault(str(int(part)), set()).add(row['company_id'])
    content_unplaced = []
    for c in content['checks']:
        company, how = c.get('company_id'), 'RECORD'
        if not company:  # same company named by the checked entity, else by the position key slug
            ids = set().union(*[cik_to_id.get(str(int(e)), set()) for e in (c.get('entities') or []) if str(e).isdigit()])
            slug = (c.get('position_key') or '').rsplit('-', 1)[0]
            by_slug = {x for x in companies if slug and x.startswith(slug)}
            company, how = (next(iter(ids)), 'ENTITY_CIK') if len(ids) == 1 else (next(iter(by_slug)), 'POSITION_KEY') if len(by_slug) == 1 else (None, None)
        # the value read from the original; when only the published value is recorded, a MATCH verdict
        # says it equals the reading (event counts are recorded this way), any other verdict gives no value
        read = c.get('read')
        if read in (None, '') and c['verdict'] in ('MATCH', 'MATCH_BOTH_BASES'):
            read = c.get('published')
        rec = ('CONTENT_READ', c['verdict'], read, c.get('filings') or [], c['file'], c.get('value_sha256'))
        year = (c.get('position_key') or '').rsplit('-', 1)[-1]
        if company and c.get('metric_id') and c.get('period_end'):
            by_period[(company, c['metric_id'], c['period_end'])].append(rec)
        elif company and c.get('metric_id') and year.isdigit():
            by_year[(company, c['metric_id'], int(year))].append(rec)
        else:
            content_unplaced.append({k: c.get(k) for k in ('file', 'path', 'verdict')})
    for r in prior:
        by_period[(r['company_id'], r['metric_id'], r['period_end'])].append(
            ('PRIOR_ACCEPTED_READING', r['acceptance_id'], r['accepted_value'], [], 'previous-business-readings.json', None))
    for r in receiver['entries']:
        by_year[(r['company_id'], r['metric_id'], r['fiscal_year'])].append(
            (r['basis'], 'RECORDED', r['value'], [], r['link'], None))

    fields = ['company_id', 'company_name', 'industry_profile', 'sic', 'metric_id', 'metric_name_zh',
              'fiscal_year_label', 'window_index', 'current_view', 'period_start', 'period_end', 'period_days',
              'target_accession', 'amendment_accessions', 'reporting_cik', 'registrant_role',
              'reference_class', 'in_reference_subset_1150', 'reference_priority', 'reference_rule_clause',
              'obs_source', 'obs_local_status', 'obs_metric_status', 'obs_value', 'obs_unit',
              'obs_period_start', 'obs_period_end', 'obs_accession', 'obs_result_validity', 'obs_reason',
              'obs_result_id', 'd02_prep_outcome', 'd02_saved_answer',
              'pub_row', 'pub_status', 'pub_value', 'pub_unit', 'pub_period_end', 'pub_accession', 'pub_source_class',
              'align_period', 'align_accession', 'align_status', 'align_value',
              'terminal_class', 'registered_defects', 'pub_defect_flag', 'reference_consistency',
              'original_check_basis', 'check_recorded_values', 'check_vs_current', 'check_sources',
              'adoption_status', 'owner', 'next_step']
    table = []
    for row in reg:
        cid = row['company_id']
        w = win[cid]['window']
        for m in metrics:
            r = ref_by.get((cid, m), {})
            for idx, fy in enumerate(w, start=1):
                sel = win[cid]['resolved'].get(fy, {})
                t = {'company_id': cid, 'company_name': row['display_name'], 'industry_profile': row['industry_profile'],
                     'sic': row['sic'], 'metric_id': m, 'metric_name_zh': r.get('metric_name_zh', ''),
                     'fiscal_year_label': fy, 'window_index': idx, 'current_view': 'Y' if idx == len(w) else '',
                     'period_start': sel.get('period_start', ''), 'period_end': sel.get('report_end', ''),
                     'period_days': sel.get('period_days', ''), 'target_accession': sel.get('accession', ''),
                     'amendment_accessions': ';'.join(sel.get('amendments', [])),
                     'reporting_cik': sel.get('reporting_cik', ''), 'registrant_role': sel.get('registrant_role', ''),
                     'reference_class': r.get('business_applicability', 'MISSING'),
                     'in_reference_subset_1150': 'Y' if r.get('business_applicability') in ('APPLICABLE', 'CONDITIONAL') else '',
                     'reference_priority': r.get('business_priority') or '', 'reference_rule_clause': r.get('rule_clause_id', '')}
                h = hist.get((cid, m, fy))
                if h is not None:
                    t.update(obs_source=h.get('_source', 'HISTORY_RUN'), obs_local_status=h.get('local_metric_status', ''),
                             obs_metric_status=h.get('status', ''), obs_value=h.get('value', ''), obs_unit=h.get('unit', ''),
                             obs_period_start=h.get('period_start', ''), obs_period_end=h.get('period_end', ''),
                             obs_accession=h.get('accession', ''), obs_result_validity=h.get('result_validity', ''),
                             obs_reason=(h.get('notes') or '')[:300], obs_result_id=h.get('result_id', ''))
                else:
                    t['obs_source'] = 'NONE'
                if m == 'D02' and (cid, fy) in d02:
                    rec = d02[(cid, fy)]
                    t['d02_prep_outcome'] = 'REQUEST_PREPARABLE' if rec['outcome'] == 'OK' else 'PREP_FAILED:' + rec.get('reason', '')
                    t['d02_saved_answer'] = rec.get('saved_answer', '')
                cls = classify(t.get('obs_local_status', ''), t.get('obs_metric_status', ''),
                               t.get('obs_result_validity', ''), t.get('obs_reason', ''), t.get('obs_value', ''))
                if t['obs_source'] == 'NONE':
                    cls = 'NO_OBSERVATION'
                if m == 'D02' and t.get('d02_prep_outcome'):
                    # The history run has no saved-review input; D02 status comes from preparation.
                    if t['d02_prep_outcome'] == 'REQUEST_PREPARABLE':
                        cls = 'VALUE_PENDING_SAVED_ANSWER' if t['d02_saved_answer'].startswith('MATCHED') else 'ANSWER_GAP_MODEL_RESPONSE'
                    else:
                        cls = classify('', '', '', t['d02_prep_outcome'], '')
                t['terminal_class'] = cls
                t['registered_defects'] = ';'.join(defects.get((cid, m, t['period_end']), []))
                # current view: publication row aligned on the same period end
                p = pub.get((cid, m))
                if p is not None and p.get('period_end') == t['period_end']:
                    t.update(pub_row='Y', pub_status=p['status'], pub_value=p['value'], pub_unit=p['unit'],
                             pub_period_end=p['period_end'], pub_accession=p['accession'], pub_source_class=p['source_class'])
                    t['align_period'] = 'SAME'  # rows of other periods never reach here
                    if t['registered_defects'] and p['value'] not in ('', None):
                        withdrawn = defect_values.get((cid, m, t['period_end']), set())
                        t['pub_defect_flag'] = ('PUBLICATION_VALUE_EQUALS_REGISTERED_DEFECT_VALUE' if p['value'] in withdrawn else
                                                'PUBLICATION_VALUE_ON_CELL_WITH_REGISTERED_DEFECT_VALUE_NOT_RECORDED' if not withdrawn else
                                                'PUBLICATION_VALUE_ON_CELL_WITH_REGISTERED_DEFECT_OTHER_VALUE')
                    if t.get('obs_accession', '') or p['accession']:
                        t['align_accession'] = 'SAME' if t.get('obs_accession', '') == p['accession'] else 'DIFFERENT'
                    # state of each side: VALUE, TERMINAL (reasonable non-numeric end), OPEN (no result yet), NONE
                    # a text conclusion (TEXT_QUAL) is published with an empty matrix value; its text is in the evidence file
                    pub_state = ('VALUE' if p['value'] not in ('', None) else 'TEXT' if p['status'] == 'TEXT_QUAL' else
                                 'TERMINAL' if p['status'] in NON_NUMERIC_TERMINAL | NOT_DISCLOSED else 'OPEN')
                    cur_state = ('NONE' if t['obs_source'] == 'NONE' else 'VALUE' if cls == 'VALUE' else
                                 'TERMINAL' if cls in ('TERMINAL_NON_NUMERIC', 'TERMINAL_NOT_DISCLOSED') else 'OPEN')
                    if pub_state == cur_state == 'VALUE':
                        a_num, b_num = to_number(t.get('obs_value', '')), to_number(p['value'])
                        if a_num is not None and b_num is not None:
                            equal_value = abs(a_num - b_num) <= 1e-9 * max(1.0, abs(b_num))
                        else:
                            equal_value = t.get('obs_value', '') == p['value']
                        t['align_value'] = 'SAME' if equal_value else 'DIFFERENT'
                        t['align_status'] = 'BOTH_VALUE_' + t['align_value']
                    elif pub_state == 'TEXT' and cur_state == 'VALUE':
                        t['align_status'] = 'BOTH_TEXT_RESULT_NOT_COMPARED'
                    elif pub_state == cur_state == 'TERMINAL':
                        t['align_status'] = 'BOTH_TERMINAL_' + ('SAME_STATUS' if t.get('obs_metric_status', '') == p['status'] else 'DIFFERENT_STATUS')
                    else:
                        t['align_status'] = 'PUB_%s__CUR_%s' % (pub_state, cur_state)
                elif t['current_view']:
                    t['pub_row'] = 'NO_ROW' if p is None else 'ROW_FOR_OTHER_PERIOD:' + p.get('period_end', '')
                # reference consistency
                rc = t['reference_class']
                if rc == 'NOT_APPLICABLE' and cls in ('VALUE',):
                    t['reference_consistency'] = 'REFERENCE_NOT_APPLICABLE_BUT_VALUE'
                elif rc in ('APPLICABLE', 'CONDITIONAL') and t.get('obs_metric_status') == 'N_A_STRUCTURAL':
                    t['reference_consistency'] = 'REFERENCE_APPLICABLE_BUT_STRUCTURAL_NA'
                owner, nxt = OWNER_NEXT.get(cls, ('接收方', '未定义'))
                if cls == 'VALUE_PENDING_SAVED_ANSWER':
                    owner, nxt = ('#47', '已有匹配的保存回答，按 D02 保存回答入口运行并读取')
                if t['current_view'] and owner == '#47' and cls.startswith('DEV_GAP'):
                    owner = '#28/#47'
                t['owner'], t['next_step'] = owner, nxt
                t['original_check_basis'] = ''
                t['adoption_status'] = ''
                table.append(t)

    # recorded original-source checks: compared with the current observation, never inherited on ID alone
    for t in table:
        recs = by_period.get((t['company_id'], t['metric_id'], t['period_end']), []) + \
            by_year.get((t['company_id'], t['metric_id'], t['fiscal_year_label']), [])
        if not recs:
            t['original_check_basis'] = ''
            t['check_vs_current'] = ''
            continue
        kinds = collections.Counter(r[0] + ':' + str(r[1]) for r in recs)
        t['original_check_basis'] = '; '.join('%s x%d' % (k, n) for k, n in sorted(kinds.items()))
        t['check_sources'] = '; '.join(sorted({str(r[4]) for r in recs}))
        values = [r[2] for r in recs if r[2] not in (None, '')]
        # a text result is recorded by the digest of the checked value; only a MATCH reading confirms it
        digests = {r[5].split(':', 1)[-1] for r in recs if r[5] and r[1] in ('MATCH', 'MATCH_BOTH_BASES')}
        other_digests = {r[5].split(':', 1)[-1] for r in recs if r[5]} - digests
        t['check_recorded_values'] = '; '.join(sorted({str(v) for v in values} | {'sha256:' + d[:12] for d in digests}))[:200]
        filings = {f for r in recs for f in r[3]}
        cur = t.get('obs_value', '')
        cur_digest = hashlib.sha256(cur.encode('utf-8')).hexdigest() if cur not in ('', None) else None
        # only real accession numbers are compared; event counts cite the submissions index instead
        used = {x for x in (t.get('obs_accession') or '').split(';') if ACCESSION.match(x)}
        filing_note = '' if not filings or not used or used & filings else '_DIFFERENT_FILING'
        if not values and not digests:
            t['check_vs_current'] = 'NO_RECORDED_VALUE' + ('_CHECKED_VALUE_NOT_MATCHED' if other_digests else '')
        elif cur in ('', None):
            t['check_vs_current'] = 'NO_CURRENT_VALUE'
        elif any(same_value(v, cur) for v in values) or cur_digest in digests:
            t['check_vs_current'] = 'SAME_VALUE' + filing_note
        else:
            t['check_vs_current'] = 'DIFFERENT_VALUE' + ('_OLD_READING_HAS_REGISTERED_DEFECT' if t.get('registered_defects') else '')
    # revenue years with a registered B01 defect (whether or not this run produced a current B01)
    b01_defect = {(t['company_id'], t['fiscal_year_label']) for t in table if t['metric_id'] == 'B01'
                  and t.get('registered_defects')}
    for t in table:  # growth/margin cells computed from that revenue inherit the same explanation
        if (t['metric_id'] in ('B02', 'B03') and t.get('check_vs_current') == 'DIFFERENT_VALUE'
                and ((t['company_id'], t['fiscal_year_label']) in b01_defect
                     or (t['metric_id'] == 'B02' and (t['company_id'], t['fiscal_year_label'] - 1) in b01_defect))):
            t['check_vs_current'] = 'DIFFERENT_VALUE_DERIVED_FROM_B01_DEFECT'
    adoption = json.loads(a.adoption_records.read_text()) if a.adoption_records else {'entries': []}
    adopted = {(e['company_id'], e['metric_id'], e['fiscal_year']): e['status'] for e in adoption['entries']}
    if pub_meta and adoption.get('active_publication_id') not in (None, pub_meta['publication_id']):
        problems.append('ADOPTION_RECORDS_FOR_OTHER_PUBLICATION:' + adoption['active_publication_id'])
    for t in table:  # formal adoption needs both the published row for this period and a named record
        if t.get('pub_row') == 'Y':
            t['adoption_status'] = adopted.get((t['company_id'], t['metric_id'], t['fiscal_year_label']),
                                               adoption.get('carried_over_status', 'ACTIVE_PUBLICATION_MEMBER'))
        else:
            t['adoption_status'] = 'NOT_ADOPTED'

    with open(a.out / 'scope_table.csv', 'w', encoding='utf-8', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        wr.writeheader()
        for t in table:
            wr.writerow({k: t.get(k, '') for k in fields})

    count = collections.Counter
    summary = {
        'cells': len(table),
        'companies': len(reg), 'metrics': len(metrics),
        'windows': {c: win[c]['window'] for c in companies},
        'unresolved_labels': {c: {fy: v['error'] for fy, v in win[c]['resolved'].items() if 'error' in v} for c in companies},
        'reference_pairs': dict(count(r['business_applicability'] for r in ref)),
        'reference_cells': dict(count(t['reference_class'] for t in table)),
        'reference_subset_1150_cells': sum(1 for t in table if t['in_reference_subset_1150'] == 'Y'),
        'reference_problems': problems,
        'terminal_class': dict(count(t['terminal_class'] for t in table)),
        'terminal_class_in_subset': dict(count(t['terminal_class'] for t in table if t['in_reference_subset_1150'] == 'Y')),
        'terminal_class_by_reference': {rc: dict(count(t['terminal_class'] for t in table if t['reference_class'] == rc))
                                        for rc in sorted({t['reference_class'] for t in table})},
        'reference_consistency': dict(count(t['reference_consistency'] for t in table if t.get('reference_consistency'))),
        'current_view_cells': sum(1 for t in table if t['current_view']),
        'current_view_alignment': dict(count('|'.join((t.get('pub_row', '') or '-', t.get('align_status', '') or '-', t.get('align_value', '') or '-'))
                                             for t in table if t['current_view'])),
        'history_runs': runs,
        'd02_ledger_saved_answers': ledger_answers,
        'publication': pub_meta,
        'by_metric': {m: dict(count(t['terminal_class'] for t in table if t['metric_id'] == m)) for m in metrics},
        'by_company': {c: dict(count(t['terminal_class'] for t in table if t['company_id'] == c)) for c in companies},
        'owner': dict(count(t['owner'] for t in table if t['terminal_class'] not in ('VALUE', 'TERMINAL_NON_NUMERIC', 'TERMINAL_NOT_DISCLOSED'))),
        'registered_defect_cells': sum(1 for t in table if t.get('registered_defects')),
        'publication_values_on_defect_cells': sum(1 for t in table if t.get('pub_defect_flag')),
        'original_check_cells': sum(1 for t in table if t['original_check_basis']),
        'check_vs_current': dict(count(t.get('check_vs_current', '') for t in table if t['original_check_basis'])),
        'content_checks_unmatched_cells': sorted('|'.join(k) for k in set(by_period) - {(t['company_id'], t['metric_id'], t['period_end']) for t in table}),
        'year_keyed_checks_unmatched_cells': sorted('%s|%s|%s' % k for k in set(by_year) - {(t['company_id'], t['metric_id'], t['fiscal_year_label']) for t in table}),
        'content_checks_unplaced': content_unplaced,
        'content_checks_total': len(content['checks']),
        'adoption': dict(count(t['adoption_status'].split(' ')[0] for t in table)),
    }
    (a.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    inputs = {'code_root': str(a.code_root), 'source_root': str(a.source_root),
              'history_root': str(a.history_root) if a.history_root else None,
              'history_rows': str(a.history_rows) if a.history_rows else None,
              'periods': str(a.periods) if a.periods else None,
              'd02_comparison': a.d02_comparison, 'd02_ledger': a.d02_ledger,
              'd02_ledger_sha256': sha256_file(a.d02_ledger) if a.d02_ledger else None,
              'publication': str(a.publication) if a.publication else None,
              'content_checks': str(a.content_checks) if a.content_checks else None,
              'content_checks_commit': content.get('commit'),
              'prior_readings_sha256': sha256_file(a.prior_readings) if a.prior_readings else None,
              'receiver_checks_sha256': sha256_file(a.receiver_checks) if a.receiver_checks else None,
              'adoption_records_sha256': sha256_file(a.adoption_records) if a.adoption_records else None,
              'reference_map_sha256': sha256_file(a.code_root / 'catalog/reference/generated/sic_metric_map.json'),
              'registry_sha256': sha256_file(a.code_root / 'config/company_registry.csv'),
              'defects_file': str(defects_file), 'defects_sha256': sha256_file(defects_file),
              'builder_sha256': sha256_file(__file__), 'argv': sys.argv,
              'built_at_utc': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    (a.out / 'manifest.json').write_text(json.dumps(inputs, ensure_ascii=False, indent=1, sort_keys=True), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('cells', 'reference_cells', 'reference_subset_1150_cells', 'terminal_class')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
