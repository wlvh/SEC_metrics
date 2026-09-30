"""C03 from the Summary Compensation Table of a proxy without inline XBRL.

``historical_proxy_compensation`` reads each executive's fiscal-year row as its
amounts in order and takes the last as the Total only when it equals the sum
of the others (Item 402(c)'s definition of the Total). These cases read the
eight saved 2022 proxies from the acquisition's export, and check each answer
against the pay-versus-performance ECD tag the same registrant's 2023 proxy
gives the same fiscal year's chief executive - a later document, tagged,
read here by a separate regex reader, so it is an independent check and not
the value's source. They belong to the source-material tier.

Load-bearing:
  * six proxies give one chief executive's Total, equal to the sum of the
    row's other amounts and to the later tag;
  * Marriott (successor and predecessor) and Salesforce (co-chief
    executives) give two, both kept, and are withheld - the later tags carry
    two too;
  * a subsidiary's chief executive (Macy's "Chairman & CEO, Bloomingdale's")
    is not the registrant's;
  * a Total that is not the sum, a table without a dollar sign, a title for
    another year, a foreign currency in the context, and a table without a
    title are each refused by name (constructed proxies, one change each).
"""
from __future__ import annotations

import re
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tests.vnext.test_historical_proxy_identity import PROXIES, _cover, _filing, _inventory, _records
from tools.acceptance_readings import saved_bytes
from vnext.historical_proxy_compensation import (SPEC_PATH, HistoricalProxyCompensationError,
                                                 names_the_chief_executive,
                                                 resolve_proxy_compensation_table, row_amounts)
from vnext.observations import scope_key
from vnext.specs import compile_spec_file

SCOPE = {"entity_scope": "registrant"}
# (proxy document, fiscal-year start and end, fiscal-year label, the 2023 proxy)
PERIODS = {
    "d184198ddef14a.htm": ("2021-01-01", "2021-12-31", 2021,
                           "evidence/request_attempts/e8/e80b11597c0f92458927fb6f55454b5fdd0a29386b9717aa79e133d737c14667/d436078ddef14a.htm"),
    "d235712ddef14a.htm": ("2021-01-01", "2021-12-31", 2021,
                           "evidence/request_attempts/55/559da695a997c02bbfc5a3def4ed96c432acc82385153c241f118819a5a3ec3c/ny20006599x500_def14a.htm"),
    "d301179ddef14a.htm": ("2021-02-01", "2022-01-31", 2022,
                           "evidence/request_attempts/33/3332d4d4136c624e07773cf17f26d9453d61969cff9a4601d41ffc8776bcfd31/d406753ddef14a.htm"),
    "defproxy2022doc.htm": ("2021-01-01", "2021-12-31", 2021,
                            "evidence/request_attempts/6b/6b672121eae7104bf879beb63b9343c0b141690871877b57ff1611f75b26bbf4/enph-20230406.htm"),
    "lumenproxy2022.htm": ("2021-01-01", "2021-12-31", 2021,
                           "evidence/request_attempts/a2/a2ab506f740fa63eff2b7b6af22787b686d5720c6932077fec2f20495c474edb/lumn-20230405.htm"),
    "proxywc22.htm": ("2021-01-01", "2021-12-31", 2021,
                      "evidence/request_attempts/cf/cfc584e96fa3611e5c72bd4bef190792131a206bef17421ee98c61312c69c626/pfe-20230315.htm"),
    "tm2130881-4_def14a.htm": ("2021-01-01", "2021-12-31", 2021,
                               "evidence/request_attempts/1a/1a3b6fedb789ddf2cedce0050317744da84afc737d754fba4d57b40d261fb2b1/f-20230511xdef14a.htm"),
    "tmb-20220520xdef14a.htm": ("2021-01-31", "2022-01-29", 2021,
                                "evidence/request_attempts/da/da7d47d8c8efbf7983a2fdeedebe637dccfb23e90fa912d6a132c08d4017dc43/m-20230519xdef14a.htm"),
}
EXPECTED = {"d184198ddef14a.htm": "20035212", "defproxy2022doc.htm": "19019162",
            "lumenproxy2022.htm": "22654781", "proxywc22.htm": "24353219",
            "tm2130881-4_def14a.htm": "22813174", "tmb-20220520xdef14a.htm": "12290931"}
TWO_CHIEF_EXECUTIVES = {"d235712ddef14a.htm": {"18391882", "12278151"},
                        "d301179ddef14a.htm": {"28602112", "22794415"}}


def _target(start, end):
    return {"company_id": "company", "period_start": start, "period_end": end, "scope": SCOPE,
            "scope_key": scope_key(scope=SCOPE)}


def later_tagged_totals(raw, period_end):
    """The chief executives' Summary Compensation Table totals a later proxy tags for a year.

    A separate reader from the route: every ``ecd:PeoTotalCompAmt`` whose
    context ends within 60 days of ``period_end``, whatever its individual
    member. Not the exact day, because the tags do not all follow the fiscal
    year: Macy's 2023 proxy tags its fiscal 2021 (ended 29 January 2022) on the
    calendar year 2021.
    """
    from datetime import date
    text = raw.decode("utf-8", "replace")
    ends = {}
    for context in re.finditer(r'<(?:xbrli:)?context\b[^>]*\bid="([^"]+)"(.*?)</(?:xbrli:)?context>', text, re.S):
        end = re.search(r"<(?:xbrli:)?endDate>\s*([^<\s]+)", context.group(2))
        ends[context.group(1)] = end and date.fromisoformat(end.group(1))
    target, values = date.fromisoformat(period_end), set()
    for fact in re.finditer(r'<ix:nonFraction\b[^>]*name="ecd:PeoTotalCompAmt"[^>]*>(.*?)</ix:nonFraction>', text, re.S):
        context = re.search(r'contextRef="([^"]+)"', fact.group(0)).group(1)
        value = re.sub(r"<[^>]+>|,", "", fact.group(1)).strip()
        if ends.get(context) and abs((ends[context] - target).days) <= 60 and value.isdigit():
            values.add(value)
    return values


class TheEightProxiesAreReadByTheirOwnArithmetic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.spec = compile_spec_file(path=ROOT / SPEC_PATH, dependency_specs={})
        cls.resolved = {}
        for row in PROXIES:
            raw = saved_bytes(repo_root=ROOT, relative=row[4])
            blob, reference = _records(row, raw)
            start, end, label, _later = PERIODS[row[2]]
            cls.resolved[row[2]] = resolve_proxy_compensation_table(
                raw_bytes=raw, raw_blob=blob, source_reference=reference, filing=_filing(row),
                inventory=_inventory(row[0]), company_id="company", cik=row[0],
                target=_target(start, end), fiscal_year=label, compiled_spec=cls.spec)

    def test_six_give_one_chief_executive_s_total(self):
        for document, value in EXPECTED.items():
            resolved = self.resolved[document]
            with self.subTest(document):
                self.assertEqual("PASS", resolved["selection"]["reason_code"])
                self.assertEqual(value, resolved["result"]["value"])
                self.assertEqual(1, len(resolved["selection"]["candidates"]))

    def test_each_total_is_the_sum_of_its_row(self):
        for document in EXPECTED:
            candidate = self.resolved[document]["selection"]["candidates"][0]
            with self.subTest(document):
                self.assertGreaterEqual(len(candidate["components"]), 2)
                self.assertEqual(int(candidate["value"]), sum(candidate["components"]))

    def test_two_chief_executives_are_both_kept_and_withheld(self):
        for document, values in TWO_CHIEF_EXECUTIVES.items():
            resolved = self.resolved[document]
            with self.subTest(document):
                self.assertEqual("C03_PROXY_SCT_MORE_THAN_ONE_CHIEF_EXECUTIVE",
                                 resolved["selection"]["reason_code"])
                self.assertIsNone(resolved["result"]["value"])
                self.assertEqual(values, {c["value"] for c in resolved["selection"]["candidates"]})

    def test_every_candidate_agrees_with_the_later_proxy_s_tag(self):
        for row in PROXIES:
            start, end, _label, later = PERIODS[row[2]]
            tagged = later_tagged_totals(saved_bytes(repo_root=ROOT, relative=later), end)
            read = {c["value"] for c in self.resolved[row[2]]["selection"]["candidates"]}
            with self.subTest(row[2]):
                self.assertTrue(read)
                self.assertEqual(read, tagged)

    def test_a_subsidiary_s_chief_executive_is_not_the_registrant_s(self):
        candidates = self.resolved["tmb-20220520xdef14a.htm"]["selection"]["candidates"]
        self.assertEqual(["Jeff Gennette Chief Executive Officer"],
                         [c["person_and_position"] for c in candidates])

    def test_the_period_is_the_pinned_year_and_the_cover_named_the_registrant(self):
        selection = self.resolved["proxywc22.htm"]["selection"]
        self.assertEqual("TABLE_YEAR_EQUALS_PINNED_FISCAL_YEAR", selection["period_basis"])
        self.assertEqual("Pfizer Inc.", selection["proxy_cover_identity"]["cover_registrant_name"])
        self.assertEqual("2021", self.resolved["proxywc22.htm"]["selection"]["candidates"][0]["year"]["text"])


class TheChiefExecutiveAndTheAmountsAreReadNarrowly(unittest.TestCase):

    def test_the_registrant_s_chief_executive(self):
        for text in ("A. Bourla Chairman and Chief Executive Officer(6)",
                     "Robert M. Bakish(7) President and Chief Executive Officer; Director",
                     "Bret Taylor Vice Chair of the Board and Co-CEO",
                     "Jeffrey K. Storey President and CEO",
                     "Arne M. Sorenson Former President and Chief Executive Officer"):
            with self.subTest(text):
                self.assertTrue(names_the_chief_executive(text))

    def test_not_the_registrant_s_chief_executive(self):
        for text in ("Tony Spring EVP, Macy's, Inc. & Chairman & CEO, Bloomingdale's",
                     "Jane Doe Chief Executive Officer of Example Pro",
                     "Jane Doe Deputy Chief Executive Officer",
                     "Jane Doe Assistant to the CEO",
                     "William Clay Ford, Jr. Executive Chair",
                     "Eric Branderiz Former EVP and CFO"):
            with self.subTest(text):
                self.assertFalse(names_the_chief_executive(text))

    def test_amounts_keep_their_order_and_drop_footnote_marks(self):
        # "(4)" alone is a footnote mark, not an amount.
        self.assertEqual([(1451977, "1,451,977"), (500, "500"), (0, "0")],
                         row_amounts(["$1,451,977(3)", "(4)", "$500(5)", "$ −"]))
        self.assertIsNone(row_amounts(["1,000", "n/a", "1,000"]))


def _proxy(table_rows, *, title="SUMMARY COMPENSATION TABLE", context="", header=None):
    """A constructed proxy: a definitive cover, a title, and one table."""
    header = header or ["Name and Principal Position", "Year", "Salary ($)", "Bonus ($)", "Total ($)"]
    cells = lambda row: "".join("<td>" + cell + "</td>" for cell in row)  # noqa: E731
    table = "<table><tr>" + cells(header) + "</tr>" + "".join(
        "<tr>" + cells(row) + "</tr>" for row in table_rows) + "</table>"
    blocks = ("<p>" + title + "</p>" if title else "") + ("<p>" + context + "</p>" if context else "")
    return _cover().replace(b"Proxy statement body.</p>", ("Proxy statement body.</p>" + blocks + table).encode())


class AConstructedTableThatDoesNotSayItIsRefusedByName(unittest.TestCase):
    """Each case changes one thing on a table the reader otherwise accepts."""

    ROW = ("1234567", "0001234567-22-000001", "proxy.htm", "2022-04-01", "evidence/constructed/proxy.htm",
           "Example Corporation")
    INVENTORY = {"name": "Example Corporation", "formerNames": []}
    CHIEF = ["Jane Doe Chief Executive Officer", "2021", "1,000,000", "500,000", "1,500,000"]
    OTHER = ["John Roe Chief Financial Officer", "2021", "600,000", "—", "600,000"]

    @classmethod
    def setUpClass(cls):
        cls.spec = compile_spec_file(path=ROOT / SPEC_PATH, dependency_specs={})

    def _resolve(self, raw):
        blob, reference = _records(self.ROW, raw)
        return resolve_proxy_compensation_table(
            raw_bytes=raw, raw_blob=blob, source_reference=reference, filing=_filing(self.ROW),
            inventory=self.INVENTORY, company_id="company", cik=self.ROW[0],
            target=_target("2021-01-01", "2021-12-31"), fiscal_year=2021, compiled_spec=self.spec)

    def test_the_control_table_is_read(self):
        resolved = self._resolve(_proxy([self.CHIEF, ["2020", "900,000", "0", "900,000"], self.OTHER]))
        self.assertEqual(("PASS", "1500000"), (resolved["selection"]["reason_code"], resolved["result"]["value"]))

    def test_a_total_that_is_not_the_sum_is_refused(self):
        wrong = self.CHIEF[:-1] + ["1,600,000"]
        self.assertEqual("C03_PROXY_SCT_TOTAL_IS_NOT_THE_SUM_OF_ITS_COMPONENTS",
                         self._resolve(_proxy([wrong, self.OTHER]))["selection"]["reason_code"])

    def test_a_table_without_a_dollar_sign_is_refused(self):
        header = ["Name and Principal Position", "Year", "Salary", "Bonus", "Total"]
        self.assertEqual("C03_PROXY_SCT_DOLLAR_NOT_ESTABLISHED",
                         self._resolve(_proxy([self.CHIEF, self.OTHER], header=header))["selection"]["reason_code"])

    def test_a_title_for_another_year_is_refused(self):
        resolved = self._resolve(_proxy([self.CHIEF, self.OTHER], title="2020 SUMMARY COMPENSATION TABLE"))
        self.assertEqual("C03_PROXY_SCT_NOT_ESTABLISHED", resolved["selection"]["reason_code"])
        self.assertEqual(["C03_PROXY_SCT_TITLE_YEAR_CONFLICT"],
                         [d["reason"] for d in resolved["selection"]["diagnostics"]])

    def test_a_foreign_currency_in_the_context_is_refused(self):
        resolved = self._resolve(_proxy([self.CHIEF, self.OTHER], context="Amounts are in Canadian dollars."))
        self.assertEqual(["C03_PROXY_SCT_CONFLICTING_CURRENCY_CONTEXT"],
                         [d["reason"] for d in resolved["selection"]["diagnostics"]])

    def test_a_table_without_a_title_is_not_the_summary_table(self):
        resolved = self._resolve(_proxy([self.CHIEF, self.OTHER], title=""))
        self.assertEqual(["C03_PROXY_SCT_TITLE_NOT_ESTABLISHED"],
                         [d["reason"] for d in resolved["selection"]["diagnostics"]])

    def test_no_chief_executive_row_is_not_found(self):
        self.assertEqual("C03_PROXY_SCT_NOT_FOUND",
                         self._resolve(_proxy([self.OTHER]))["selection"]["reason_code"])

    def test_another_registrant_s_cover_is_refused(self):
        from vnext.historical_proxy_identity import HistoricalProxyIdentityError
        blob, reference = _records(self.ROW, _proxy([self.CHIEF]))
        with self.assertRaisesRegex(HistoricalProxyIdentityError, "NOT_THE_SEC_NAME_ON_FILING_DATE"):
            resolve_proxy_compensation_table(
                raw_bytes=_proxy([self.CHIEF]), raw_blob=blob, source_reference=reference,
                filing=_filing(self.ROW), inventory={"name": "Another Corporation", "formerNames": []},
                company_id="company", cik=self.ROW[0], target=_target("2021-01-01", "2021-12-31"),
                fiscal_year=2021, compiled_spec=self.spec)

    def test_a_proxy_with_inline_xbrl_is_not_read_here(self):
        raw = _proxy([self.CHIEF]).replace(b"<body>", b"<body><ix:header></ix:header>")
        with self.assertRaisesRegex(HistoricalProxyCompensationError, "ONLY_FOR_A_PROXY_WITHOUT_INLINE_XBRL"):
            self._resolve(raw)


if __name__ == "__main__":
    unittest.main()
