"""Receiver check: which rows that users read from the active publication carry a confirmed error.

Reads, never writes, the code checkout and the saved originals:
* the active publication pointer and its metrics_matrix.csv, plus the root
  mirrors outputs/metrics_matrix.csv and REPORT_十公司财务指标.md (the default
  read path in docs/business_user_guide.md);
* the defect register docs/evidence/issue28_continuous/known_result_defects.json;
* optional #28 value checks for registered errors whose value the register
  does not record (source-and-publication-read.json, six_missing_value_checks);
* optional replacement recipes recomputed from each company's own original
  10-K XBRL instance (inputs/published_error_replacements.json).

A published row counts as a confirmed error only when its value equals the
registered wrong value (or #28's read shows the same value). Rows that sit on a
registered coordinate but carry text or a non-numeric status are listed for
review, not declared wrong: the publication CSV has no native Result ID, so
coordinate equality alone proves nothing about text content.

usage: published_errors.py --code-root DIR --source-root DIR --out CSV
                            [--value-checks JSON] [--replacements JSON]
"""
import argparse
import csv
import decimal
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

XBRLI = '{http://www.xbrl.org/2003/instance}'
REPORT = 'REPORT_十公司财务指标.md'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def xbrl_fact(path, start, end, concept):
    """One undimensioned duration fact; fail if absent or ambiguous."""
    root = ET.parse(path).getroot()
    contexts = {}
    for c in root.iter(XBRLI + 'context'):
        period = c.find(XBRLI + 'period')
        s, e = period.find(XBRLI + 'startDate'), period.find(XBRLI + 'endDate')
        if c.find(XBRLI + 'entity/' + XBRLI + 'segment') is None and s is not None and e is not None:
            contexts[c.get('id')] = (s.text.strip(), e.text.strip())
    values = {el.text.strip() for el in root.iter() if el.tag.split('}')[-1] == concept
              and contexts.get(el.get('contextRef')) == (start, end)}
    if len(values) != 1:
        raise SystemExit(f'{path}: {concept} {start}..{end} gives {sorted(values)}')
    return decimal.Decimal(values.pop())


def replacement(cell, source_root):
    decimal.getcontext().prec = 30
    facts = {}
    for name, spec in cell['facts'].items():
        rel, start, end = spec[:3]
        concept = spec[3] if len(spec) > 3 else name
        facts[name] = xbrl_fact(source_root / 'evidence/accession_materials' / rel, start, end, concept)
    formula = cell['formula']
    if formula == 'Revenues':
        value = facts['Revenues']
    elif formula == 'Revenues / PriorRevenues - 1':
        value = facts['Revenues'] / facts['PriorRevenues'] - 1
    elif formula.startswith('(OperatingIncomeLoss + '):
        da = next(k for k in facts if k not in ('Revenues', 'OperatingIncomeLoss'))
        value = (facts['OperatingIncomeLoss'] + facts[da]) / facts['Revenues']
    else:
        raise SystemExit('unknown formula ' + formula)
    basis = '; '.join(f'{k}={v}' for k, v in facts.items())
    return value, formula + ' with ' + basis


def same_number(a, b):
    try:
        return decimal.Decimal(str(a)) == decimal.Decimal(str(b))
    except (decimal.InvalidOperation, TypeError):
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code-root', required=True, type=Path)
    ap.add_argument('--source-root', required=True, type=Path)
    ap.add_argument('--value-checks', type=Path)
    ap.add_argument('--replacements', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    if a.out.exists():
        raise SystemExit('refusing to overwrite ' + str(a.out))
    root = a.code_root
    pointer = json.loads((root / 'outputs/active_publication.json').read_text())
    bundle = root / 'outputs/publications' / pointer['publication_id']
    mirror = {name: sha256(root / 'outputs' / name) == sha256(bundle / name)
              for name in ('metrics_matrix.csv', 'metric_evidence.csv')}
    mirror[REPORT] = sha256(root / REPORT) == sha256(bundle / REPORT)
    report_text = (root / REPORT).read_text(encoding='utf-8')
    names = {r['display_name']: r['company_id'] for r in csv.DictReader(open(root / 'config/company_registry.csv'))}
    defects = json.loads((root / 'docs/evidence/issue28_continuous/known_result_defects.json').read_text())['defects']
    by_key = {}
    for d in defects:
        by_key.setdefault((d.get('company_id'), d.get('metric_id'), d.get('period_end')), []).append(d)
    checks = {}
    if a.value_checks:
        for c in json.loads(a.value_checks.read_text())['six_missing_value_checks']:
            checks[(c['company_id'], c['metric_id'])] = c
    recipes = {}
    if a.replacements:
        for cell in json.loads(a.replacements.read_text())['cells']:
            recipes[(cell['company_id'], cell['metric_id'], cell['period_end'])] = cell
    out = []
    for row in csv.DictReader(open(bundle / 'metrics_matrix.csv')):
        cid = names.get(row['company'])
        key = (cid, row['metric_id'], row['period_end'])
        regs = [d for d in by_key.get(key, []) if not d.get('released')]
        if not regs:
            continue
        value = row['value']
        recorded = [d for d in regs if d.get('reported_value') not in (None, '')]
        check = checks.get((cid, row['metric_id']))
        if value and any(same_number(value, d['reported_value']) for d in recorded):
            confirmation = 'VALUE_EQUALS_REGISTERED_ERROR'
        elif value and check and check.get('same_reported_value') and same_number(value, check['known_old_result_value']):
            confirmation = 'VALUE_EQUALS_REGISTERED_ERROR_PER_28_READ'
        elif value:
            confirmation = 'NUMERIC_ON_REGISTERED_COORDINATE_VALUE_NOT_CONFIRMED'
        else:
            confirmation = 'NON_NUMERIC_ON_REGISTERED_COORDINATE_NOT_ESTABLISHED'
        replacement_value, replacement_basis = '', ''
        if key in recipes and confirmation.startswith('VALUE_EQUALS'):
            v, replacement_basis = replacement(recipes[key], a.source_root)
            replacement_value = str(v)
        if not confirmation.startswith('VALUE_EQUALS'):
            action = 'REVIEW_BY_OWNER'
        elif replacement_value:
            action = 'REPLACE_WITH_VERIFIED_VALUE'
        else:
            action = 'WITHHOLD'
        out.append({'company_id': cid, 'metric_id': row['metric_id'], 'period_end': row['period_end'],
                    'published_value': value, 'published_status': row['status'],
                    'in_root_report': bool(value) and value in report_text,
                    'defect_ids': ';'.join(sorted(d['defect_id'] for d in regs)),
                    'current_credit': ';'.join(sorted({str(d.get('current_credit', '')) for d in regs})),
                    'confirmation': confirmation, 'proposed_action': action,
                    'verified_replacement': replacement_value, 'replacement_basis': replacement_basis})
    fields = list(out[0]) if out else ['company_id']
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(sorted(out, key=lambda r: (r['proposed_action'], r['company_id'], r['metric_id'])))
    summary = {'publication_id': pointer['publication_id'], 'root_files_equal_bundle': mirror,
               'rows_on_registered_coordinates': len(out),
               'by_action': {k: sum(1 for r in out if r['proposed_action'] == k)
                             for k in sorted({r['proposed_action'] for r in out})},
               'register_sha256': sha256(root / 'docs/evidence/issue28_continuous/known_result_defects.json'),
               'replacements_sha256': sha256(a.replacements) if a.replacements else None,
               'value_checks_sha256': sha256(a.value_checks) if a.value_checks else None,
               'argv': sys.argv}
    a.out.with_suffix('.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
