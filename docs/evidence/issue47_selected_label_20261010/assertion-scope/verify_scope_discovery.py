"""Bounded recorded-source counterexamples through the actual range API."""
import hashlib, json, time
from pathlib import Path
from unittest.mock import patch
from tests.vnext.test_company_fiscal_range import CompanyFiscalRangeTest
from vnext import company_fiscal_range as ranges
from vnext.historical_fiscal_labels import resolve_selected_fiscal_year_label
from vnext.canonical import sha256_bytes

fixture=CompanyFiscalRangeTest();fixture.setUp()
source=fixture.source
from tests.vnext.test_selected_source_requirements import COMPANY, CIK
from tests.vnext.test_selected_historical_fiscal_label import annual
scenarios=[
    ('conditional','If the proposed naming convention is approved, References to fiscal 2026, for example, refer to the fiscal year ending December 31, 2025.',False),
    ('hypothetical','The following is a hypothetical example, not our actual naming convention: "References to fiscal 2026, for example, refer to the fiscal year ending December 31, 2025."',False),
    ('conditional_ordered','If the proposed naming convention is approved, Fiscal years 2026 and 2025 ended on December 31, 2025 and December 31, 2024, respectively, and included 52 weeks.',False),
    ('actual_example','References to fiscal 2026, for example, refer to the fiscal year ending December 31, 2025.',True),
]
rows=[]
try:
    for name,sentence,valid in scenarios:
        raw=annual().replace(b'19617',str(CIK).encode()).replace(b'2021',b'2025')
        raw=raw.replace(b'</body></html>',('<p>Our fiscal year ends on December 31. '+sentence+'</p></body></html>').encode())
        fixture.fixture.record(fixture.fixture.urls[2025],raw)
        before=fixture.fixture.digest_tree();started=time.monotonic()
        with patch('socket.socket.connect',side_effect=AssertionError('No HTTP')), \
             patch('vnext.historical_annual_input.prepare_historical_annual_input',side_effect=AssertionError('No complete annual processing')):
            result=ranges.discover_fiscal_range(repo_root=source,company_id=COMPANY,
                fiscal_year_start=2026,fiscal_year_end=2026,metric_ids=['B01'])
        assert before==fixture.fixture.digest_tree()
        task=result['tasks'][0]
        if valid:
            assert task['status']=='FISCAL_YEAR_RESOLVED' and task['label']['fiscal_year']==2026
        else:
            assert task['status']=='FISCAL_YEAR_SOURCE_UNRESOLVED'
            assert any('EXPLICIT_DEFINITION_UNRESOLVED' in str(x) for x in task['limitations'])
            assert not task.get('source_bytes_available',False)
        rows.append({'scenario':name,'seconds':time.monotonic()-started,'status':result['status'],
                     'task':task,'source_tree_preserved':True,'valid_current_definition':valid})
finally:fixture.doCleanups()
record={'constructed_controls_not_financial_results':True,'scenarios':rows,
        'full_annual_or_calculation_calls':0,'new_calls':[0,0,0]}
Path('work/fiscal-range-consumer/scope-discovery.json').write_text(json.dumps(record,indent=2)+'\n')
print([(r['scenario'],r['status'],round(r['seconds'],4)) for r in rows])
