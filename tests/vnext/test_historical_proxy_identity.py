"""A proxy without inline XBRL is identified by its Schedule 14A cover.

The eight saved proxies filed in 2022 carry no inline XBRL, and the frozen
governance reader stops on each with ``XBRL source contains no contexts``.
``historical_proxy_identity`` reads the form and the registrant's name from
the cover instead, and the name must be one the SEC's submissions record
gives the CIK on the filing date. These cases read the real proxies (from the
acquisition's export, where they are kept) and the saved submissions records,
so they belong to the source-material tier.

Load-bearing cases:
  * every one of the eight covers gives its registrant and the definitive box;
  * the record's dates decide: Salesforce's and Paramount's proxies match the
    names in effect when they were filed and would not match the names the
    same CIKs had before their renames;
  * a proxy with inline XBRL gets exactly the frozen governance document;
  * a cover whose definitive box is not the one checked, or whose glyph is
    unknown, or whose name is not above the caption, is refused by name.
"""
from __future__ import annotations

import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools.acceptance_readings import saved_bytes
from vnext.canonical import content_hash, sha256_bytes
from vnext.historical_proxy_identity import (CHECKED, HistoricalProxyIdentityError,
                                             carries_inline_xbrl, cover_name_in_effect,
                                             governance_source_document, proxy_bound_source,
                                             proxy_cover, sec_names_in_effect)
from vnext.historical_dei import release_aware
from vnext import text_business_candidates as frozen
from vnext.records import validate_record

# (cik, accession, primary document, filing date, saved path, name as printed)
PROXIES = (
    ("813828", "0001193125-22-106893", "d184198ddef14a.htm", "2022-04-15",
     "evidence/request_attempts/98/983566e61c76c6154770576694ea19713956941063d2925de3c5ef4f5bc352eb/d184198ddef14a.htm",
     "Paramount Global"),
    ("1048286", "0001193125-22-081138", "d235712ddef14a.htm", "2022-03-22",
     "evidence/request_attempts/69/69270175d55cecc73b52c6837941c1a2cebafba0b2ba7924a8b413c3d5eda6b0/d235712ddef14a.htm",
     "Marriott International, Inc."),
    ("1108524", "0001193125-22-127612", "d301179ddef14a.htm", "2022-04-28",
     "evidence/request_attempts/68/689f8d8e37d4744c675aa64edc38fd3a87f5dbd77e5aac8aab8f0b9c0419daf6/d301179ddef14a.htm",
     "Salesforce, Inc."),
    ("1463101", "0001463101-22-000032", "defproxy2022doc.htm", "2022-04-08",
     "evidence/request_attempts/e4/e4a0c14b94d0a5c5f547d75755e3804bfeff6bc141b4f70dd85efbd3856fd642/defproxy2022doc.htm",
     "Enphase Energy, Inc."),
    ("18926", "0000018926-22-000013", "lumenproxy2022.htm", "2022-04-08",
     "evidence/request_attempts/f3/f3c138a9411eaeeb7272b6da5be398dd79e9c92d1fbdf42fea8f72f25b1067d8/lumenproxy2022.htm",
     "Lumen Technologies, Inc."),
    ("78003", "0000078003-22-000038", "proxywc22.htm", "2022-03-17",
     "evidence/request_attempts/b0/b0a01d92c7c652ff5c81c9e0b78a57f3d6616b57944ef655ada33f532dc844db/proxywc22.htm",
     "Pfizer Inc."),
    ("37996", "0001104659-22-041499", "tm2130881-4_def14a.htm", "2022-04-01",
     "evidence/request_attempts/45/454d96d48873921b1a9c8c89666392cf3bfebd7d7da985ff460ff57545d9cca2/tm2130881-4_def14a.htm",
     "Ford Motor Company"),
    ("794367", "0001558370-22-005031", "tmb-20220520xdef14a.htm", "2022-04-01",
     "evidence/request_attempts/d4/d46ebb89b7331be082a1cd8fbf725fc4be1ff1e274edfb3f344be11c13feb007/tmb-20220520xdef14a.htm",
     "Macy’s, Inc."),
)
INLINE = ("78003", "0000078003-26-000033", "pfe-20260312.htm", "2026-03-12",
          "evidence/accession_materials/pfizer_78003_000007800326000033/pfe-20260312.htm", None)


def _filing(row):
    return {"form": "DEF 14A", "accessionNumber": row[1], "primaryDocument": row[2],
            "filingDate": row[3], "reportDate": ""}


def _inventory(cik):
    path = ROOT / "evidence/submissions/CIK{:010d}.json".format(int(cik))
    return json.loads(path.read_text(encoding="utf-8"))


def _records(row, raw):
    cik, accession, document = row[0], row[1], row[2]
    blob = validate_record(record={"record_type": "RAW_BLOB",
                                   "raw_asset_id": "sha256:" + sha256_bytes(content=raw),
                                   "byte_length": len(raw), "media_type": "text/html",
                                   "storage_uri": row[4]})
    url = "https://www.sec.gov/Archives/edgar/data/{}/{}/{}".format(
        cik, accession.replace("-", ""), document)
    identity = {"raw_asset_id": blob["raw_asset_id"], "company_id": "company", "source_url": url,
                "accession": accession, "document_name": document, "source_role": "governance_proxy"}
    reference = validate_record(record={"record_type": "SOURCE_REFERENCE",
                                        "source_reference_id": content_hash(value=identity),
                                        **identity, "request_attempt_id": "attempt"})
    return blob, reference


class EachCoverGivesItsRegistrantAndTheDefinitiveBox(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = {row[2]: saved_bytes(repo_root=ROOT, relative=row[4]) for row in PROXIES}

    def test_none_of_the_eight_carries_inline_xbrl(self):
        for row in PROXIES:
            with self.subTest(row[2]):
                self.assertFalse(carries_inline_xbrl(self.raw[row[2]]))

    def test_the_cover_names_the_registrant_and_checks_only_the_definitive_box(self):
        for row in PROXIES:
            with self.subTest(row[2]):
                cover = proxy_cover(raw_bytes=self.raw[row[2]], filing=_filing(row))
                self.assertEqual(row[5], cover["registrant_name"])
                self.assertIn(cover["marks"]["DEFINITIVE"], CHECKED)
                self.assertEqual(5, len(cover["marks"]))

    def test_the_name_is_the_sec_name_on_the_filing_date(self):
        for row in PROXIES:
            with self.subTest(row[2]):
                cover = proxy_cover(raw_bytes=self.raw[row[2]], filing=_filing(row))
                identity = cover_name_in_effect(cover=cover, inventory=_inventory(row[0]),
                                                filing=_filing(row))
                self.assertEqual(row[5], identity["cover_registrant_name"])

    def test_the_record_s_dates_decide_which_name_counts(self):
        # Salesforce's proxy was filed four weeks after SALESFORCE.COM, INC.
        # became Salesforce, Inc.; Paramount's two months after ViacomCBS Inc.
        # became Paramount Global. Before each rename the same cover does not
        # name the registrant the record had.
        for document, before in (("d301179ddef14a.htm", "2022-03-01"),
                                 ("d184198ddef14a.htm", "2022-01-03")):
            row = next(row for row in PROXIES if row[2] == document)
            cover = proxy_cover(raw_bytes=self.raw[document], filing=_filing(row))
            with self.subTest(document):
                self.assertNotIn(row[5], sec_names_in_effect(inventory=_inventory(row[0]),
                                                             on_date=before))
                with self.assertRaisesRegex(HistoricalProxyIdentityError,
                                            "NOT_THE_SEC_NAME_ON_FILING_DATE") as caught:
                    cover_name_in_effect(cover=cover, inventory=_inventory(row[0]),
                                         filing={**_filing(row), "filingDate": before})
                self.assertEqual("SOURCE_INTEGRITY_ERROR", caught.exception.category)

    def test_a_former_name_does_not_count_after_the_rename(self):
        # A cover still carrying ViacomCBS Inc. in April 2022 does not name the
        # registrant the record had then; the constructed cover says so.
        row = PROXIES[0]
        cover = proxy_cover(raw_bytes=_cover(name="ViacomCBS Inc."), filing=_filing(row))
        with self.assertRaisesRegex(HistoricalProxyIdentityError, "NOT_THE_SEC_NAME_ON_FILING_DATE"):
            cover_name_in_effect(cover=cover, inventory=_inventory(row[0]), filing=_filing(row))
        cover_name_in_effect(cover=cover, inventory=_inventory(row[0]),
                             filing={**_filing(row), "filingDate": "2021-04-15"})

    def test_another_registrant_s_proxy_is_refused(self):
        row = PROXIES[0]
        cover = proxy_cover(raw_bytes=self.raw[row[2]], filing=_filing(row))
        with self.assertRaisesRegex(HistoricalProxyIdentityError, "NOT_THE_SEC_NAME_ON_FILING_DATE"):
            cover_name_in_effect(cover=cover, inventory=_inventory(PROXIES[1][0]), filing=_filing(row))

    def test_the_bound_source_reads_the_cover_only_after_the_frozen_checks(self):
        row = PROXIES[5]
        raw = self.raw[row[2]]
        blob, reference = _records(row, raw)
        arguments = dict(raw_blob=blob, source_reference=reference, company_id="company",
                         cik=row[0], filing=_filing(row))
        self.assertEqual((None, None, [row[5]]), proxy_bound_source(raw_bytes=raw, **arguments))
        # The frozen record checks still run first: changed bytes are refused
        # by them, before any parse or cover.
        with self.assertRaisesRegex(Exception, "TEXT_BUSINESS_SOURCE_BYTES_CHANGED"):
            proxy_bound_source(raw_bytes=raw + b" ", **arguments)
        with self.assertRaisesRegex(Exception, "TEXT_BUSINESS_SOURCE_IDENTITY_CONFLICT"):
            proxy_bound_source(raw_bytes=raw, **{**arguments, "cik": PROXIES[1][0]})

    def test_the_governance_document_carries_the_cover_name(self):
        row = PROXIES[3]
        raw = self.raw[row[2]]
        blob, reference = _records(row, raw)
        document = governance_source_document(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                                              company_id="company", cik=row[0], filing=_filing(row))
        self.assertEqual([row[5]], document["registrant_names"])
        self.assertEqual("COMPLETE_LOCAL_DOCUMENT", document["source_state"])
        with self.assertRaisesRegex(Exception, "XBRL source contains no contexts"):
            release_aware(frozen.governance_source_document)(
                raw_bytes=raw, raw_blob=blob, source_reference=reference,
                company_id="company", cik=row[0], filing=_filing(row))


class OnlyTheNoContextsErrorOnAPlainDocumentReachesTheCover(unittest.TestCase):

    def test_another_router_error_keeps_its_error(self):
        from unittest import mock
        from vnext import historical_proxy_identity as proxy
        from vnext.deterministic_router import DeterministicRouterError
        row = PROXIES[5]
        raw = saved_bytes(repo_root=ROOT, relative=row[4])
        blob, reference = _records(row, raw)

        def other(**_arguments):
            raise DeterministicRouterError("XBRL source has another problem")
        with mock.patch.object(proxy, "_frozen_bound_source", other):
            with self.assertRaisesRegex(DeterministicRouterError, "another problem"):
                proxy_bound_source(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                                   company_id="company", cik=row[0], filing=_filing(row))

    def test_the_coverage_says_the_cover_identified_the_proxy(self):
        from vnext.historical_proxy_identity import IDENTITY_BASIS, record_cover_identity
        plain, inline = b"<html>plain</html>", b"<html><ix:header></ix:header></html>"

        def prepared(raw):
            coverages = {"a": {"scope": "ORDINARY_ANNUAL_IDENTITY_ANCHOR_ONLY", "coverage_hash": "x"},
                         "g": {"scope": "COMPLETE_LOCAL_GOVERNANCE_DOCUMENT_SUPPORTED_STATEMENTS",
                               "coverage_hash": "y"}}
            documents = {"a": {"raw_asset_id": "annual"},
                         "g": {"raw_asset_id": "proxy", "registrant_names": ["Example Corporation"],
                               "source_filing": {"form": "DEF 14A"}}}
            return {"documents": documents, "coverages": coverages}, {"annual": b"", "proxy": raw}
        record, raw_by_id = prepared(plain)
        recorded = record_cover_identity(prepared=record, raw_bytes_by_id=raw_by_id)
        identity = recorded["coverages"]["g"]["governance_identity"]
        self.assertEqual(IDENTITY_BASIS, identity["basis"])
        self.assertEqual(["Example Corporation"], identity["cover_registrant_names"])
        self.assertNotEqual("y", recorded["coverages"]["g"]["coverage_hash"])
        self.assertEqual(record["coverages"]["a"], recorded["coverages"]["a"])
        record, raw_by_id = prepared(inline)
        self.assertIs(record, record_cover_identity(prepared=record, raw_bytes_by_id=raw_by_id))


class AProxyWithInlineXbrlKeepsTheFrozenAnswer(unittest.TestCase):

    def test_the_governance_document_is_the_frozen_one(self):
        raw = saved_bytes(repo_root=ROOT, relative=INLINE[4])
        self.assertTrue(carries_inline_xbrl(raw))
        blob, reference = _records(INLINE, raw)
        arguments = dict(raw_bytes=raw, raw_blob=blob, source_reference=reference,
                         company_id="company", cik=INLINE[0], filing=_filing(INLINE))
        self.assertEqual(release_aware(frozen.governance_source_document)(**arguments),
                         governance_source_document(**arguments))

    def test_a_broken_inline_document_keeps_its_error(self):
        raw = saved_bytes(repo_root=ROOT, relative=PROXIES[5][4])
        broken = raw.replace(b"<body", b"<ix:header></ix:header><body", 1)
        blob, reference = _records(PROXIES[5], broken)
        with self.assertRaisesRegex(Exception, "XBRL source contains no contexts"):
            proxy_bound_source(raw_bytes=broken, raw_blob=blob, source_reference=reference,
                               company_id="company", cik=PROXIES[5][0], filing=_filing(PROXIES[5]))


def _cover(*, marks=None, name="Example Corporation", caption="(Name of Registrant as Specified In Its Charter)"):
    """A minimal Schedule 14A cover, one block per line, marks beside their options."""
    marks = {"PRELIMINARY": "\u2610", "CONFIDENTIAL": "\u2610", "DEFINITIVE": "\u2612",
             "ADDITIONAL": "\u2610", "SOLICITING": "\u2610", **(marks or {})}
    lines = ["UNITED STATES", "SCHEDULE 14A", "Check the appropriate box:",
             marks["PRELIMINARY"] + " Preliminary Proxy Statement",
             marks["CONFIDENTIAL"] + " Confidential, for Use of the Commission Only",
             marks["DEFINITIVE"] + " Definitive Proxy Statement",
             marks["ADDITIONAL"] + " Definitive Additional Materials",
             marks["SOLICITING"] + " Soliciting Material under \u00a7240.14a-12",
             name, caption, "Payment of Filing Fee", "Proxy statement body."]
    body = "".join("<p>" + line + "</p>" for line in lines if line)
    return ("<html><body>" + body + "</body></html>").encode("utf-8")


class ACoverThatDoesNotSayItIsRefusedByName(unittest.TestCase):
    """Each case changes one thing on a cover the reader otherwise accepts."""

    FILING = {"form": "DEF 14A", "accessionNumber": "0000000000-22-000001",
              "primaryDocument": "proxy.htm", "filingDate": "2022-04-01", "reportDate": ""}

    def _refused(self, raw, reason, form="DEF 14A"):
        with self.assertRaisesRegex(HistoricalProxyIdentityError, reason) as caught:
            proxy_cover(raw_bytes=raw, filing={**self.FILING, "form": form})
        return caught.exception

    def test_the_control_cover_is_read(self):
        cover = proxy_cover(raw_bytes=_cover(), filing=self.FILING)
        self.assertEqual("Example Corporation", cover["registrant_name"])

    def test_a_preliminary_proxy_is_not_the_definitive_one(self):
        self._refused(_cover(marks={"PRELIMINARY": "\u2612", "DEFINITIVE": "\u2610"}),
                      "DEFINITIVE_BOX_NOT_THE_ONLY_CHECKED:PRELIMINARY$")

    def test_two_checked_boxes_are_refused(self):
        self._refused(_cover(marks={"ADDITIONAL": "\u2612"}),
                      "DEFINITIVE_BOX_NOT_THE_ONLY_CHECKED:ADDITIONAL,DEFINITIVE$")

    def test_an_unknown_glyph_is_refused_not_guessed(self):
        error = self._refused(_cover(marks={"DEFINITIVE": "\u25a0"}),
                              "CHECKBOX_GLYPH_UNRECOGNIZED:DEFINITIVE:U\\+25A0")
        self.assertEqual("IMPLEMENTATION_GAP", error.category)

    def test_a_missing_box_is_refused(self):
        self._refused(_cover().replace(b" Definitive Additional Materials", b" Other Materials"),
                      "BOX_NOT_UNIQUE:ADDITIONAL:0")

    def test_a_name_beside_its_caption_is_a_layout_this_reader_does_not_read(self):
        self._refused(_cover(name="", caption="Example Corporation (Name of Registrant as Specified In Its Charter)"),
                      "NAME_LAYOUT_UNSUPPORTED")

    def test_a_cover_without_a_name_above_the_caption_is_refused(self):
        self._refused(_cover(name=""), "NAME_NOT_ESTABLISHED")

    def test_only_a_definitive_proxy_form_is_read(self):
        self._refused(_cover(), "FORM_NOT_DEF14A", form="DEFA14A")

    def test_a_document_with_inline_markup_is_not_read_by_its_cover(self):
        self._refused(_cover().replace(b"<body>", b"<body><ix:header></ix:header>"),
                      "COVER_ON_INLINE_DOCUMENT")


class C03ReadsTheProxyTableWhenTheProxyHasNoEcdFacts(unittest.TestCase):
    """C03 on a proxy without inline XBRL reads the proxy's own table.

    The approved source is the proxy (DEF 14A, ECD facts preferred); a 2022
    proxy has no ECD facts, so the route reads its Summary Compensation Table
    (``historical_proxy_compensation``). Before, the frozen parser's router
    error escaped unnamed.
    """

    @classmethod
    def setUpClass(cls):
        from vnext.governance_signals import C03_SPEC_PATH
        from vnext.observations import scope_key
        from vnext.specs import compile_spec_file
        cls.row = PROXIES[5]
        cls.raw = saved_bytes(repo_root=ROOT, relative=cls.row[4])
        cls.spec = compile_spec_file(path=ROOT / C03_SPEC_PATH, dependency_specs={})
        scope = {"entity_scope": "registrant"}
        cls.target = {"company_id": "company", "period_start": "2021-01-01",
                      "period_end": "2021-12-31", "scope": scope, "scope_key": scope_key(scope=scope)}

    def _resolve(self, raw):
        from vnext.historical_governance_results import _compensation_resolution
        blob, reference = _records(self.row, raw)

        class Reader:
            def primary(self, filing):
                return {"raw_bytes": raw, "raw_blob": blob, "source_reference": reference}
        selection = {"pinned_def14a": _filing(self.row), "def14a_amendments": [],
                     "def14a_status": None, "current_filing_chain": []}
        return _compensation_resolution(
            root=ROOT, reader=Reader(), selection=selection, target=self.target,
            company_id="company", cik=self.row[0],
            period={"period_start": "2021-01-01", "period_end": "2021-12-31", "fiscal_year": 2021},
            spec=self.spec, inventory=_inventory(self.row[0]))

    def test_the_proxy_table_answers(self):
        from vnext.historical_proxy_compensation import SPEC_PATH
        path, resolved, limitation = self._resolve(self.raw)
        self.assertEqual(SPEC_PATH, path)
        self.assertIsNone(limitation)
        self.assertEqual("24353219", resolved["result"]["value"])

    def test_an_inline_document_that_fails_the_parse_keeps_its_error(self):
        from vnext.deterministic_router import DeterministicRouterError
        broken = self.raw.replace(b"<body", b"<ix:header></ix:header><body", 1)
        self.assertNotEqual(self.raw, broken)
        with self.assertRaisesRegex(DeterministicRouterError, "no contexts"):
            self._resolve(broken)


if __name__ == "__main__":
    unittest.main()
