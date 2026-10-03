"""Read-only Ford FY2025 visible-table relationships; no B06 answer credit."""
import json
import socket
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from vnext.canonical import sha256_bytes, strict_json_file
from vnext.normal_candidates import _prepare_b06
from vnext.normal_source_authority import ROOT
from vnext.ordinary_source_authority import verify_ordinary_source_proofs


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.rows = []
        self.row = None
        self.cell = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            if self.depth == 0:
                self.rows = []
            self.depth += 1
        elif self.depth and tag == 'tr':
            self.row = []
        elif self.depth and tag in ('td', 'th'):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.depth and tag in ('td', 'th') and self.cell is not None:
            if self.row is not None:
                self.row.append(' '.join(' '.join(self.cell).split()))
            self.cell = None
        elif self.depth and tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == 'table' and self.depth:
            self.depth -= 1
            if self.depth == 0:
                self.tables.append(self.rows)


def find_table(tables, required):
    hits = [(index, rows) for index, rows in enumerate(tables)
            if all(text in ' '.join(' '.join(row) for row in rows)
                   for text in required)]
    if len(hits) != 1:
        raise ValueError('FORD_VISIBLE_TABLE_NOT_UNIQUE:' + repr(required))
    return hits[0]


def row(table, label):
    hits = [cells for cells in table if cells and cells[0] == label]
    if len(hits) != 1:
        raise ValueError('FORD_VISIBLE_ROW_NOT_UNIQUE:' + label)
    return hits[0]


def numbers(cells):
    return [int(cell.replace(',', '')) for cell in cells[1:]
            if cell.replace(',', '').isdigit()]


config = strict_json_file(path=ROOT/'config/issue28_continuous_calls_v1.json')
root = Path(config['budget_root'])/'source-inputs'
with patch.object(socket.socket, 'connect',
                  side_effect=AssertionError('NETWORK_FORBIDDEN')), \
     patch.object(socket, 'getaddrinfo',
                  side_effect=AssertionError('DNS_FORBIDDEN')):
    prepared = _prepare_b06(repo_root=root, company_id='ford_motor_company')
    admission = verify_ordinary_source_proofs(
        data_root=root, proofs=prepared['input_binding']['source_proofs'])
raw = prepared['primary']['raw_bytes']
parser = Tables()
parser.feed(raw.decode('utf-8', 'replace'))
assets_i, assets = find_table(parser.tables,
    ('Company excluding Ford Credit', 'Ford Credit', 'Eliminations', 'Total assets',
     'December 31, 2025'))
liabilities_i = assets_i + 1
liabilities = parser.tables[liabilities_i]
if not ('Company excluding Ford Credit debt payable within one year' in
        ' '.join(' '.join(cells) for cells in liabilities)
        and any(cells and cells[0] == 'Total liabilities'
                for cells in liabilities)):
    raise ValueError('FORD_VISIBLE_LIABILITIES_NOT_ADJACENT_TO_ASSETS')
debt_i, debt = find_table(parser.tables,
    ('Total Company excluding Ford Credit',
     'Other debt (including finance leases)'))
credit_headers = [index for index, cells in enumerate(debt)
                  if cells and cells[0] == 'Ford Credit']
if len(credit_headers) != 1:
    raise ValueError('FORD_VISIBLE_DEBT_SCOPE_SPLIT_NOT_UNIQUE')
company_debt = debt[:credit_headers[0]]
lease_i, lease = find_table(parser.tables,
    ('Total finance lease liabilities',
     'Company excluding Ford Credit debt payable within one year'))
consolidated_i, consolidated = find_table(parser.tables,
    ('Total equity attributable to Ford Motor Company',
     'Equity attributable to noncontrolling interests', 'Total equity'))

selected = {
    'industrial_assets': row(assets, 'Total assets'),
    'industrial_liabilities': row(liabilities, 'Total liabilities'),
    'debt_current': row(company_debt, 'Total debt payable within one year'),
    'debt_long': row(company_debt, 'Total long-term debt payable after one year'),
    'debt_total': row(company_debt, 'Total Company excluding Ford Credit'),
    'lease_current': row(lease,
        'Company excluding Ford Credit debt payable within one year'),
    'lease_long': row(lease, 'Company excluding Ford Credit long-term debt'),
    'lease_total': row(lease, 'Total finance lease liabilities'),
    'consolidated_attributable': row(consolidated,
        'Total equity attributable to Ford Motor Company'),
    'consolidated_nci': row(consolidated,
        'Equity attributable to noncontrolling interests'),
    'consolidated_total_equity': row(consolidated, 'Total equity'),
}
value = {key: numbers(cells)[0] if key in {
        'industrial_assets', 'industrial_liabilities'} else numbers(cells)[-1]
         for key, cells in selected.items()}
if not (value['debt_current'] + value['debt_long'] == value['debt_total']
        and value['lease_current'] + value['lease_long'] == value['lease_total']
        and value['consolidated_attributable'] + value['consolidated_nci']
            == value['consolidated_total_equity']):
    raise ValueError('FORD_VISIBLE_TABLE_INTERNAL_TOTAL_CONFLICT')
body = {
    'record_type': 'ISSUE28_FORD_B06_VISIBLE_BALANCE_AND_DEBT_RELATION_AUDIT',
    'company_id': 'ford_motor_company',
    'accession': prepared['input_binding']['prepared_annual_input']
        ['filing']['accessionNumber'],
    'period_end': '2025-12-31', 'reported_unit': 'USD_MILLIONS',
    'primary_source_reference_id': prepared['primary']['source_reference']
        ['source_reference_id'],
    'primary_raw_sha256': sha256_bytes(content=raw),
    'source_admission_checkpoint_id': admission['checkpoint_id'],
    'table_ordinals_in_this_exact_html': {
        'assets': assets_i, 'liabilities': liabilities_i,
        'debt_note18': debt_i, 'lease_note': lease_i,
        'consolidated_balance_sheet': consolidated_i},
    'raw_visible_rows': selected, 'reported_values_millions': value,
    'same_scope_assets_less_liabilities_millions':
        value['industrial_assets'] - value['industrial_liabilities'],
    'same_scope_attributable_equity_proven': False,
    'finance_lease_included_in_reported_debt_note': True,
    'b06_ratio_or_result_created': False,
    'new_business_calls': [0, 0, 0],
    'interpretation_limit': ('A minus L is a same-column net-assets residual, '
        'not an issuer-reported Ford Motor attributable industrial equity fact. '
        'No segment allocation of consolidated noncontrolling interest or '
        'approved conversion rule is established here.'),
}
print(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True))
