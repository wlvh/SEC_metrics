#!/usr/bin/env python3
"""Break the 1,150 reference subset into confirmed / value-unconfirmed / terminal / open.

usage: subset_1150.py <scope_table.csv> [<older scope_table.csv>]
confirmed = terminal_class VALUE and check_vs_current SAME_VALUE (value, period, unit, subject and
filing match one existing original-read record); value_unconfirmed = VALUE otherwise; terminal =
TERMINAL_NON_NUMERIC, WITHHELD_BY_CURRENT_RULE or CURRENT_ROUTE_RESULT_REPORTED; open = everything else.
With an older table, also prints which cells changed kind.
"""
import collections, csv, json, sys

TERMINAL = ('TERMINAL_NON_NUMERIC', 'WITHHELD_BY_CURRENT_RULE', 'CURRENT_ROUTE_RESULT_REPORTED')


def kind(row):
    if row['terminal_class'] == 'VALUE':
        return 'confirmed' if row['check_vs_current'] == 'SAME_VALUE' else 'value_unconfirmed'
    return 'terminal' if row['terminal_class'] in TERMINAL else 'open'


def load(path):
    return {(r['company_id'], r['metric_id'], r['fiscal_year_label']): r
            for r in csv.DictReader(open(path, encoding='utf-8')) if r['in_reference_subset_1150'] == 'Y'}


rows = load(sys.argv[1])
report = {'cells': len(rows), 'kind': dict(collections.Counter(kind(r) for r in rows.values())),
          'open_by_class': dict(collections.Counter(r['terminal_class'] for r in rows.values() if kind(r) == 'open').most_common()),
          'confirmed_by_metric': {m: f'{c["confirmed"]}/{c["n"]}' for m, c in sorted(
              ((m, collections.Counter({'n': 0, 'confirmed': 0})) for m in {k[1] for k in rows}), key=lambda x: x[0])}}
for key, row in rows.items():
    cell = report['confirmed_by_metric'][key[1]].split('/')
    report['confirmed_by_metric'][key[1]] = f'{int(cell[0]) + (kind(row) == "confirmed")}/{int(cell[1]) + 1}'
if len(sys.argv) > 2:
    old = load(sys.argv[2])
    report['changed'] = dict(collections.Counter(
        f'{kind(old[k])}->{kind(r)}:{old[k]["terminal_class"]}->{r["terminal_class"]}'
        for k, r in rows.items() if (kind(old[k]), old[k]['terminal_class']) != (kind(r), r['terminal_class'])).most_common())
print(json.dumps(report, indent=1, ensure_ascii=False))
