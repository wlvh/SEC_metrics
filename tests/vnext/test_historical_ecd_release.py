"""C03 on proxies that declare the first ECD taxonomy release (``ecd/2022q4``).

The frozen C03 resolver takes a fact as an executive-compensation fact only when
its namespace is ``http://xbrl.sec.gov/ecd/`` and four digits, and the proxy's
document type as a DEI fact the same way. The 2023 proxies (and Pfizer's 2024
one) declare the first release of both taxonomies, named with a quarter, so the
frozen resolver refuses them - first on the DEI document type
(``C03_DEF14A_SOURCE_REQUIRED``) and, with only DEI widened, on the ECD facts
(``C03_ECD_TAXONOMY_REQUIRED``). The historical DEI view answers the ECD
question with the same three release suffixes it accepts for DEI.

Each answer read through the view is set against a different document: the
next year's proxy, which declares a four-digit release, read by the frozen
resolver for the same year. That check is recorded as it comes out, not as it
was hoped: Ford's next proxy carries a nil for its former chief executive's
2022 cell and the frozen resolver refuses the year, and Marriott's next proxy
reports the 2022 total corrected by $28,822 (its footnote says so). Where the
definition gives no single value - two chief executives in a year, a proxy
whose contexts are calendar years for a January year-end - the view gives the
frozen resolver's named answer, not a value. Reads the proxies from the
acquisition's export (saved-source tier). Zero calls.
"""
import re
import unittest
from unittest.mock import patch

from tests.vnext.common import REPO_ROOT as ROOT
from tools.acceptance_readings import saved_bytes
from vnext import governance_signals as frozen
from vnext import historical_dei
from vnext.canonical import content_hash, sha256_bytes
from vnext.governance_signals import C03_SPEC_PATH, GovernanceSignalError
from vnext.historical_dei import ECD_NAMESPACE_PATTERN, is_ecd_namespace, release_aware
from vnext.observations import scope_key
from vnext.records import validate_record
from vnext.specs import compile_spec_file

VIEW = release_aware(frozen.resolve_c03)
PREFIX = "evidence/request_attempts/"
# (company_id, cik, fiscal year (start, end), first-release proxy, value,
#  next proxy, the frozen resolver's (reason, value) for the year on the next proxy)
CASES = (
    ("enphase_energy", "1463101", ("2022-01-01", "2022-12-31"),
     ("0001463101-23-000061", "6b/6b672121eae7104bf879beb63b9343c0b141690871877b57ff1611f75b26bbf4/enph-20230406.htm"),
     "16627977",
     ("0001463101-24-000049", "1c/1c8339b97e3eda141ae574a36ddc34c496e306ed2f497775a615d9aa4b15865a/enph-20240404.htm"),
     ("PASS", "16627977")),
    # The next proxy's table carries a nil for the former chief executive's
    # 2022 cell, which the frozen resolver takes as an invalid target fact.
    ("ford_motor_company", "37996", ("2022-01-01", "2022-12-31"),
     ("0001558370-23-005203", "1a/1a3b6fedb789ddf2cedce0050317744da84afc737d754fba4d57b40d261fb2b1/f-20230511xdef14a.htm"),
     "20996146",
     ("0001104659-24-040871", "70/706abbd3080e856948fd83c21105df78154a3ad9bdfec0bb7257e7e45629d3d7/tm2318496-d4_def14a.htm"),
     ("C03_TARGET_FACT_INVALID", None)),
    # The next proxy corrects the 2022 total: "All Other Compensation for
    # fiscal year 2022 has also been adjusted to reflect an additional $28,822".
    ("marriott_international", "1048286", ("2022-01-01", "2022-12-31"),
     ("0001140361-23-014123", "55/559da695a997c02bbfc5a3def4ed96c432acc82385153c241f118819a5a3ec3c/ny20006599x500_def14a.htm"),
     "18686271",
     ("0001140361-24-015465", "a2/a25ce3426110e7f6ec546419607bff5d718b01825d5fa4faf970929acf294954/ny20015439x1_def14a.htm"),
     ("PASS", "18715093")),
    ("paramount_skydance_paramount_global", "813828", ("2022-01-01", "2022-12-31"),
     ("0001193125-23-074091", "e8/e80b11597c0f92458927fb6f55454b5fdd0a29386b9717aa79e133d737c14667/d436078ddef14a.htm"),
     "32046006",
     ("0001193125-24-105026", "65/655b8420b5e23e022242d3d6f268c21caf179d6d8acab7941e8e6ff3980abeb9/d558817ddef14a.htm"),
     ("PASS", "32046006")),
    # Pfizer's 2024 proxy declares the first release too, so both Pfizer
    # years are checked against its 2025 proxy.
    ("pfizer", "78003", ("2022-01-01", "2022-12-31"),
     ("0000078003-23-000040", "cf/cfc584e96fa3611e5c72bd4bef190792131a206bef17421ee98c61312c69c626/pfe-20230315.htm"),
     "33017453",
     ("0000078003-25-000062", "c0/c0f25fc2b3a93829e7c59cacd3960c43a1e05ebadd3807fad76eeee81776e0db/pfe-20250313.htm"),
     ("PASS", "33017453")),
    ("pfizer", "78003", ("2023-01-01", "2023-12-31"),
     ("0000078003-24-000068", "1d/1d4cd29495b7f6a1de80ebecd0f48991988bf2daf9f502651e4e7707dc1bc823/pfe-20240313.htm"),
     "21562064",
     ("0000078003-25-000062", "c0/c0f25fc2b3a93829e7c59cacd3960c43a1e05ebadd3807fad76eeee81776e0db/pfe-20250313.htm"),
     ("PASS", "21562064")),
)
# First-release proxies whose year the definition does not give one value for.
NAMED = (
    ("lumen_technologies", "18926", ("2022-01-01", "2022-12-31"),
     ("0000018926-23-000038", "a2/a2ab506f740fa63eff2b7b6af22787b686d5720c6932077fec2f20495c474edb/lumn-20230405.htm"),
     "C03_MULTIPLE_REPORTED_AMOUNTS"),
    ("macys", "794367", ("2022-01-30", "2023-01-28"),
     ("0001558370-23-005400", "da/da7d47d8c8efbf7983a2fdeedebe637dccfb23e90fa912d6a132c08d4017dc43/m-20230519xdef14a.htm"),
     "C03_TARGET_PERIOD_NOT_FOUND"),
    ("salesforce", "1108524", ("2022-02-01", "2023-01-31"),
     ("0001193125-23-122123", "33/3332d4d4136c624e07773cf17f26d9453d61969cff9a4601d41ffc8776bcfd31/d406753ddef14a.htm"),
     "C03_MULTIPLE_REPORTED_AMOUNTS"),
)


def _arguments(company_id, cik, accession, path, period, spec):
    raw = saved_bytes(repo_root=ROOT, relative=PREFIX + path)
    document = path.rsplit("/", 1)[1]
    blob = validate_record(record={"record_type": "RAW_BLOB", "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
                                   "byte_length": len(raw), "media_type": "text/html",
                                   "storage_uri": PREFIX + path})
    identity = {"raw_asset_id": blob["raw_asset_id"], "company_id": company_id,
                "source_url": "https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(
                    cik, accession.replace("-", ""), document),
                "accession": accession, "document_name": document, "source_role": "governance_proxy"}
    reference = validate_record(record={"record_type": "SOURCE_REFERENCE",
                                        "source_reference_id": content_hash(value=identity),
                                        **identity, "request_attempt_id": "attempt"})
    scope = {"entity_scope": "registrant"}
    target = {"company_id": company_id, "period_start": period[0], "period_end": period[1],
              "scope": scope, "scope_key": scope_key(scope=scope)}
    return raw, {"raw_bytes": raw, "raw_blob": blob, "source_reference": reference, "target": target,
                 "expected_cik": cik, "compiled_spec": spec}


class TheFirstEcdReleaseIsReadThroughTheViewTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.spec = compile_spec_file(path=ROOT / C03_SPEC_PATH, dependency_specs={})

    def test_the_frozen_resolver_refuses_the_first_release_on_both_namespaces(self):
        dei_only = {pattern: historical_dei.DEI_NAMESPACE_PATTERN
                    for pattern in historical_dei.FROZEN_DEI_NAMESPACE_PATTERNS}
        for company, cik, period, (accession, path), *_ in CASES + NAMED:
            with self.subTest(company=company, period=period[1]):
                raw, arguments = _arguments(company, cik, accession, path, period, self.spec)
                self.assertTrue(b"xbrl.sec.gov/ecd/2022q4" in raw, "not a first-release proxy")
                with self.assertRaisesRegex(GovernanceSignalError, "C03_DEF14A_SOURCE_REQUIRED"):
                    frozen.resolve_c03(**arguments)
                with patch.dict(historical_dei._WIDENED, dei_only, clear=True), \
                        self.assertRaisesRegex(GovernanceSignalError, "C03_ECD_TAXONOMY_REQUIRED"):
                    VIEW(**arguments)

    def test_the_view_reads_the_first_release_and_the_next_proxy_is_recorded_as_it_comes_out(self):
        for company, cik, period, first, value, following, later in CASES:
            with self.subTest(company=company, period=period[1]):
                _, arguments = _arguments(company, cik, *first, period, self.spec)
                viewed = VIEW(**arguments)
                self.assertEqual(("PASS", value), (viewed["selection"]["reason_code"],
                                                   viewed["result"]["value"]))
                raw, next_arguments = _arguments(company, cik, *following, period, self.spec)
                self.assertFalse(b"xbrl.sec.gov/ecd/2022q4" in raw, "the check proxy is a first-release one")
                checked = frozen.resolve_c03(**next_arguments)
                self.assertEqual(later, (checked["selection"]["reason_code"], checked["result"]["value"]))

    def test_where_the_definition_gives_no_single_value_the_view_names_why(self):
        for company, cik, period, first, reason in NAMED:
            with self.subTest(company=company, period=period[1]):
                _, arguments = _arguments(company, cik, *first, period, self.spec)
                viewed = VIEW(**arguments)
                self.assertEqual((reason, None), (viewed["selection"]["reason_code"],
                                                  viewed["result"]["value"]))

    def test_a_four_digit_release_gets_the_frozen_answer(self):
        company, cik, period, _, _, following, _ = CASES[0]
        _, arguments = _arguments(company, cik, *following, period, self.spec)
        self.assertEqual(frozen.resolve_c03(**arguments), VIEW(**arguments))


class TheEcdNamespaceIsWidenedByTheReleaseSuffixOnlyTest(unittest.TestCase):

    def test_the_three_release_forms_and_nothing_else(self):
        for uri in ("http://xbrl.sec.gov/ecd/2023", "https://xbrl.sec.gov/ecd/2022q4",
                    "http://xbrl.sec.gov/ecd/2022-10-31"):
            with self.subTest(uri=uri):
                self.assertTrue(is_ecd_namespace(uri))
        for uri in ("http://xbrl.sec.gov/ecd/22", "http://xbrl.sec.gov/ecd/2022q5",
                    "http://xbrl.sec.gov/ecd/2023x", "http://example.com/ecd/2023",
                    "http://xbrl.sec.gov/dei/2023", "http://www.ford.com/20231231"):
            with self.subTest(uri=uri):
                self.assertFalse(is_ecd_namespace(uri))

    def test_every_ecd_spelling_in_the_frozen_readers_is_widened(self):
        import types
        from vnext import annual_amendment_scope
        spelled = set()
        for module in (frozen, annual_amendment_scope):
            for value in vars(module).values():
                if isinstance(value, types.FunctionType) and value.__module__ == module.__name__:
                    spelled |= {constant for code in historical_dei._codes(value.__code__)
                                for constant in code.co_consts
                                if isinstance(constant, str) and "xbrl\\.sec\\.gov/ecd/" in constant}
        self.assertEqual(set(historical_dei.FROZEN_ECD_NAMESPACE_PATTERNS), spelled)

    def test_each_frozen_pattern_is_answered_by_its_own_widened_pattern(self):
        widened = historical_dei._WIDENED
        self.assertEqual(set(historical_dei.FROZEN_DEI_NAMESPACE_PATTERNS)
                         | set(historical_dei.FROZEN_ECD_NAMESPACE_PATTERNS), set(widened))
        for frozen_pattern in historical_dei.FROZEN_ECD_NAMESPACE_PATTERNS:
            self.assertEqual(ECD_NAMESPACE_PATTERN, widened[frozen_pattern])
            self.assertIsNotNone(historical_dei.RELEASE_AWARE_RE.fullmatch(
                frozen_pattern, "http://xbrl.sec.gov/ecd/2022q4"))
            self.assertIsNone(re.fullmatch(frozen_pattern, "http://xbrl.sec.gov/ecd/2022q4"))
        for frozen_pattern in historical_dei.FROZEN_DEI_NAMESPACE_PATTERNS:
            self.assertIsNone(historical_dei.RELEASE_AWARE_RE.fullmatch(
                frozen_pattern, "http://xbrl.sec.gov/ecd/2022q4"))


if __name__ == "__main__":
    unittest.main()
