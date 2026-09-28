"""A source-reference marker is not a ticker; company routing still fails."""
from pathlib import Path
import shutil
import tempfile
import unittest

from vnext.normal_source_authority import ROOT
from vnext.ordinary_scalability_audit import successor_scalability_snapshot


class OrdinaryScalabilityAuditTest(unittest.TestCase):
    def audit(self, source):
        with tempfile.TemporaryDirectory(prefix='ordinary-scalability-') as temp:
            root = Path(temp).resolve()
            (root / 'config').mkdir()
            (root / 'scripts').mkdir()
            (root / 'tools').mkdir()
            shutil.copyfile(ROOT / 'config/company_registry.csv',
                            root / 'config/company_registry.csv')
            (root / 'scripts/example.py').write_text(source)
            return successor_scalability_snapshot(root)

    def test_current_source_grammar_and_authorization_provenance_are_not_business_literals(self):
        rows = successor_scalability_snapshot(ROOT)
        self.assertEqual([], rows)
        source = ("markers={'NATIVE_FACT':'F'}\n"
                  "ref='F'+str(index) if kind=='NATIVE_FACT' else ''\n"
                  "approved['delegation_source']=={'user_instruction_date':'2026-09-23'}\n")
        self.assertEqual([], self.audit(source))

    def test_actual_company_and_period_literals_remain_rejected(self):
        source = ("ticker='F'\n"
                  "if row['ticker']=='F': pass\n"
                  "company='1048286'\n"
                  "end='2026-09-23'\n"
                  "target={'period_end':'2026-09-23'}\n")
        rows = self.audit(source)
        self.assertEqual(2, sum(row['type'] == 'ticker' and row['literal'] == 'F'
                                for row in rows))
        self.assertTrue(any(row['type'] == 'cik' and row['literal'] == '1048286'
                            for row in rows))
        self.assertEqual(2, sum(row['type'] == 'fixed_fiscal_date'
                                and row['literal'] == '2026-09-23' for row in rows))

    def test_same_line_exemption_does_not_hide_another_literal(self):
        source = ("value=('F'+str(index) if kind=='NATIVE_FACT' else 'F')\n"
                  "approved['delegation_source']=={'user_instruction_date':'2026-09-23',"
                  "'period_end':'2026-09-23'}\n")
        rows = self.audit(source)
        self.assertEqual(1, sum(row['type'] == 'ticker' and row['literal'] == 'F'
                                for row in rows))
        self.assertEqual(1, sum(row['type'] == 'fixed_fiscal_date'
                                and row['literal'] == '2026-09-23' for row in rows))


if __name__ == '__main__':
    unittest.main()
