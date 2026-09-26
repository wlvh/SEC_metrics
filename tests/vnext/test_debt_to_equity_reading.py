"""The B06 reading, re-derived from the saved filings.

Each committed position is read again from its filing's bytes and must be the
same; the finance-lease decision is checked on the filing each branch exists
for, and a lease note that put the leases inside a debt caption would not add
them twice.
"""
import json
import unittest
from decimal import Decimal

from tests.vnext.common import REPO_ROOT as ROOT
from tools import read_debt_to_equity as reader

READING = json.loads((ROOT / reader.OUT).read_text(encoding="utf-8"))


def _text(path):
    return (ROOT / path).read_text(encoding="utf-8-sig", errors="replace")


class TheCommittedReadingReDerivesTest(unittest.TestCase):

    def test_every_position_re_derives(self):
        for label, row in READING["per_position"].items():
            with self.subTest(label):
                read = reader.read_filing(text=_text(row["document"]), period_end=row["period_end"])
                for key in ("read", "total_debt", "equity", "balance_sheet", "finance_leases"):
                    self.assertEqual(row[key], read[key])

    def test_the_four_values_match_without_reading_them_first(self):
        self.assertEqual({"MATCH"}, {row["verdict"] for row in READING["per_position"].values()})


class TheFinanceLeaseDecisionTest(unittest.TestCase):

    def test_each_branch_on_the_filing_it_exists_for(self):
        expected = {"enphase-2025": "NONE", "macys-2026": "OUTSIDE_THE_DEBT_ROWS",
                    "paramount-2025": "INSIDE_THE_DEBT_ROWS",
                    "salesforce-2026": "OUTSIDE_THE_DEBT_ROWS"}
        self.assertEqual(expected, {label: row["finance_leases"]["treatment"]
                                    for label, row in READING["per_position"].items()})

    def test_leases_classified_under_a_debt_caption_are_not_added(self):
        """Macy's lease table rewritten to classify its finance leases under debt.

        The captions are replaced inside that one table only - the same words
        appear on the balance sheet - and the edit is asserted to have landed,
        because a negative that edits nothing passes for the wrong reason.
        """
        row = READING["per_position"]["macys-2026"]
        text = _text(row["document"])
        table = next(t for t in reader._TABLE.findall(text)
                     if "Right of Use Assets" in reader._plain(t)
                     and "Finance (a)" in reader._plain(t))
        edited = (table.replace("Accounts payable and accrued liabilities", "Short-term debt")
                  .replace("Long-Term Lease Liabilities", "Long-Term Debt"))
        self.assertNotEqual(table, edited)
        leases = reader.finance_leases(text=text.replace(table, edited, 1),
                                       period_end=row["period_end"])
        self.assertEqual(("INSIDE_THE_DEBT_ROWS", "0"), (leases["treatment"], leases["add"]))

    def test_a_filing_that_says_nothing_about_finance_leases_is_not_read(self):
        row = READING["per_position"]["enphase-2025"]
        text = _text(row["document"]).replace("does not have any finance leases", "leases")
        read = reader.read_filing(text=text, period_end=row["period_end"])
        self.assertEqual((None, "FINANCE_LEASE_TREATMENT_NOT_STATED"), (read["read"], read["why"]))

    def test_the_divisor_is_the_parent_s_equity(self):
        row = READING["per_position"]["paramount-2025"]
        self.assertEqual("Total Parent stockholders’ equity", row["balance_sheet"]["equity_row"]["caption"])
        self.assertEqual(Decimal("11693000000"), Decimal(row["equity"]))


if __name__ == "__main__":
    unittest.main()
