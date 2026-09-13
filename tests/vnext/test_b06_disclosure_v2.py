"""Real saved filings plus explicit TEST_ONLY semantic counterexamples.

Derived bytes never enter trusted acquisition or native Run admission. The
fixtures come from the existing PR43 review index, not expected answer literals
or per-company production rules.
"""
import copy
from functools import lru_cache
import json
from pathlib import Path
import re
import socket
import unittest
from unittest.mock import patch

from vnext import b06_disclosure as v1, b06_disclosure_v2 as v2
from vnext.canonical import sha256_bytes
from vnext.specs import compile_spec

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def successor_spec():
    # The isolated semantic suite uses an explicit new resolver identity;
    # native integration separately loads the installed successor Spec.
    text = (ROOT / v1.SPEC_PATH).read_text()
    text = text.replace('"' + v1.RESOLVER + '"', '"' + v2.RESOLVER + '"')
    return compile_spec(text=text, dependency_specs={})


@lru_cache(maxsize=2)
def original(company):
    index = json.loads((ROOT / "docs/evidence/b06_new_source/replay-index.json").read_text())
    files = {row["path"]: row for row in index["files"]}
    prefix = "cases/" + company + "/accepted-data/"

    def body(path):
        row = files[prefix + path]
        raw = (ROOT / row["repository_path"]).read_bytes()
        assert sha256_bytes(content=raw) == row["sha256"] and len(raw) == row["size"]
        return raw

    binding_path = next(name[len(prefix):] for name in files
                        if name.startswith(prefix + "b06_bindings/"))
    binding = json.loads(body(binding_path))
    selected = binding["selected"]
    proof = selected["proofs"][2]
    raw = body(proof["request_repo_relative_path"])
    primary = body(selected["proofs"][3]["request_repo_relative_path"])
    source = binding["verification"]["calculation_facts"][0]["source_binding"]
    return dict(raw=raw, primary=primary, source=source,
        spec=successor_spec(),
        target={"company_id": company, "accession": selected["filing"]["accessionNumber"],
                "entity": selected["entity"], "period_start": selected["target_period"]["period_end"],
                "period_end": selected["target_period"]["period_end"],
                "scope": {"entity_scope": "consolidated"}},
        filed=selected["filing"]["filingDate"], data_root=ROOT)


def verify(args, module=v2):
    args = copy.deepcopy(args)
    args["source"]["raw_asset_id"] = "sha256:" + sha256_bytes(content=args["raw"])
    args["source"]["source_reference_id"] = "source:TEST_ONLY:" + sha256_bytes(content=args["raw"])
    proposal = module.propose(raw=args["raw"], primary=args["primary"], target=args["target"])
    return module.verify(**args, proposal=proposal)


def add_sentence(args, sentence):
    args = copy.deepcopy(args)
    patterns = [("raw", rb"(<us-gaap:DebtDisclosureTextBlock\b[^>]*>)"),
                ("primary", rb'(<ix:nonNumeric\b(?=[^>]*name="us-gaap:DebtDisclosureTextBlock")[^>]*>)')]
    for field, pattern in patterns:
        args[field], count = re.subn(pattern, lambda m: m[1] + sentence.encode() + b" ", args[field])
        assert count == 1
    return args


def change_current_primary_equity(args, attribute=None):
    args = copy.deepcopy(args)
    parsed = v1.parse_accession_xbrl_source(raw_bytes=args["raw"])
    ref = next(f["context_ref"] for f in parsed.facts
        if f["qualified_name"] == "us-gaap:stockholdersequity"
        and parsed.contexts[f["context_ref"]]["period_end"] == args["target"]["period_end"]
        and not parsed.contexts[f["context_ref"]]["dimensions"])
    pattern = (rb'(<ix:nonFraction\b(?=[^>]*name="us-gaap:StockholdersEquity")'
               rb'(?=[^>]*contextRef="' + ref.encode() + rb'")[^>]*>)(.*?)(</ix:nonFraction>)')

    def replace(match):
        if attribute:
            key, value = attribute
            opening = re.sub(key.encode() + rb'="[^"]*"', b'', match[1])
            return opening[:-1] + b' ' + key.encode() + b'="' + value.encode() + b'">' + match[2] + match[3]
        value = re.sub(rb"<[^>]+>", b"", match[2]).strip().replace(b",", b"")
        return match[1] + str(int(value) + 100).encode() + match[3]

    args["primary"], count = re.subn(pattern, replace, args["primary"], flags=re.S)
    assert count
    return args


class B06DisclosureV2Test(unittest.TestCase):
    def setUp(self):
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("TEST_FORBIDS_NETWORK"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_original_two_modes_keep_amounts_and_explain_different_measurements(self):
        for company in ["salesforce", "southwest_airlines"]:
            args = original(company)
            old = verify(args, v1)
            new = verify(args)
            self.assertEqual(old, {k: value for k, value in new.items() if k != "successor_content_checks"})
            checks = new["successor_content_checks"]
            self.assertTrue(checks["primary_xml_numeric_agreement"])
            self.assertEqual(1, len(checks["alternate_measurements"]))
            self.assertTrue(checks["narrative_inventory"])

    def test_primary_equity_amount_sign_scale_and_unit_conflicts_reject(self):
        args = original("salesforce")
        for attribute in [None, ("sign", "-"), ("scale", "5"), ("unitRef", "missing")]:
            changed = change_current_primary_equity(args, attribute)
            with self.subTest(attribute=attribute), self.assertRaisesRegex(ValueError, "B06_V2_(PRIMARY_XML_AMOUNT|MONETARY_UNIT)_CONFLICT"):
                verify(changed)

    def test_explicit_additional_current_borrowing_blocks_both_modes(self):
        for company in ["salesforce", "southwest_airlines"]:
            args = original(company)
            end = v2._date_text(args["target"]["period_end"])
            changed = add_sentence(args, "Additional short-term borrowings of $99 million were outstanding as of "
                + end + ", presented in accrued expenses and other liabilities, and excluded from the components of borrowings table.")
            self.assertTrue(verify(changed, v1)["complete"])
            with self.assertRaisesRegex(ValueError, "B06_V2_UNRESOLVED_ADDITIONAL_BORROWING"):
                verify(changed)

    def test_borrowing_keyword_and_explicit_past_issuance_do_not_block(self):
        args = original("salesforce")
        for sentence in ["The Company may borrow under a future credit agreement.",
                         "Loans of $99 million were issued and fully repaid in 2020.",
                         "Borrowings of $99 million were outstanding as of January 31, 2020."]:
            with self.subTest(sentence=sentence):
                self.assertTrue(verify(add_sentence(args, sentence))["complete"])

    def test_current_named_carrying_total_is_reconciled_but_unknown_balance_is_not(self):
        args = original("salesforce")
        end = v2._date_text(args["target"]["period_end"])
        proof = verify(args, v1)
        amount = str(int(proof["components"]["borrowing"]["value"]) // 1000000)
        sentence = "The total carrying value of debt was $" + amount + " million outstanding as of " + end + "."
        checked = verify(add_sentence(args, sentence))
        self.assertTrue(any(row["disposition"] == "RECONCILED_NAMED_TABLE_AMOUNT"
            and row["sentence"] == sentence for row in checked["successor_content_checks"]["narrative_inventory"]))
        for sentence in ["Borrowings of $99 million were outstanding as of " + end + ".",
                         "Debt was $99 million as of " + end + "."]:
            with self.subTest(sentence=sentence), self.assertRaisesRegex(ValueError, "B06_V2_NARRATIVE_BALANCE_UNSUPPORTED"):
                verify(add_sentence(args, sentence))

    def test_current_balance_cannot_inherit_an_unspecified_date(self):
        args = original("salesforce")
        with self.assertRaisesRegex(ValueError, "B06_V2_NARRATIVE_PERIOD_AMBIGUOUS"):
            verify(add_sentence(args, "Additional short-term borrowings of $99 million are outstanding."))

    def test_zero_clause_cannot_hide_a_positive_balance_or_unsupported_amount(self):
        args = original("salesforce")
        end = v2._date_text(args["target"]["period_end"])
        for sentence, error in [
            ("There were no outstanding borrowings except additional loans of $99,000,000 as of " + end + ".",
             "B06_V2_UNRESOLVED_ADDITIONAL_BORROWING"),
            ("Financing of $ninety-nine million was outstanding as of " + end + ".",
             "B06_V2_NARRATIVE_AMOUNT_UNSUPPORTED"),
            ("There were no outstanding borrowings as of " + end + ".",
             "B06_V2_NARRATIVE_ZERO_SCOPE_UNSUPPORTED"),
        ]:
            with self.subTest(sentence=sentence), self.assertRaisesRegex(ValueError, error):
                verify(add_sentence(args, sentence))

    def test_same_xml_and_primary_alternate_total_still_needs_its_own_arithmetic(self):
        for company, concept in [("southwest_airlines", "us-gaap:longtermdebt"),
                                 ("salesforce", "us-gaap:debtinstrumentcarryingamount")]:
            args = copy.deepcopy(original(company))
            parsed = v1.parse_accession_xbrl_source(raw_bytes=args["raw"])
            fact = next(f for f in parsed.facts if f["qualified_name"] == concept
                and parsed.contexts[f["context_ref"]]["period_end"] == args["target"]["period_end"]
                and not parsed.contexts[f["context_ref"]]["dimensions"])
            old = fact["text"].encode()
            shown = format(int(fact["text"]) // 1000000, ",").encode()
            args["raw"] = args["raw"].replace(b">" + old + b"<", b">99000000<")
            for field in ["raw", "primary"]:
                args[field] = re.sub(rb"(?<=>)" + shown + rb"(?=<)", b"99", args[field])
                args[field] = re.sub(rb"(?<=&gt;)" + shown + rb"(?=(?:&#160;)?&lt;)", b"99", args[field])
            self.assertTrue(verify(args, v1)["complete"])
            with self.subTest(company=company), self.assertRaisesRegex(ValueError, "B06_V2_(MATURITY_TOTAL|PRINCIPAL_MEMBERSHIP_SUM)_CONFLICT"):
                verify(args)

    def test_unconsumed_known_concept_must_agree_with_primary(self):
        args = copy.deepcopy(original("southwest_airlines"))
        parsed = v1.parse_accession_xbrl_source(raw_bytes=args["raw"])
        fact = next(f for f in parsed.facts if f["qualified_name"] == "us-gaap:longtermdebt"
            and parsed.contexts[f["context_ref"]]["period_end"] == args["target"]["period_end"]
            and not parsed.contexts[f["context_ref"]]["dimensions"])
        pattern = rb'(<us-gaap:LongTermDebt\b(?=[^>]*contextRef="' + fact["context_ref"].encode() + rb'")[^>]*>)[^<]+'
        args["raw"], count = re.subn(pattern, lambda m: m[1] + b"99000000", args["raw"])
        self.assertTrue(count)
        self.assertTrue(verify(args, v1)["complete"])
        with self.assertRaisesRegex(ValueError, "B06_V2_PRIMARY_XML_AMOUNT_CONFLICT"):
            verify(args)

    def test_newer_disclosed_credit_group_is_derived_from_table_members(self):
        from tests.vnext.test_b06_new_source import development
        args = copy.deepcopy(development("salesforce"))
        args["spec"] = successor_spec()
        checked = verify(args)
        groups = [row for row in checked["successor_content_checks"]["narrative_inventory"]
                  if row["disposition"] == "RECONCILED_NAMED_AGREEMENT_GROUP"]
        self.assertEqual(1, len(groups))
        self.assertEqual(2, len(groups[0]["members"]))
        changed_sentence = groups[0]["sentence"].replace("$6.0 billion", "$6.1 billion")
        self.assertNotEqual(groups[0]["sentence"], changed_sentence)
        with self.assertRaisesRegex(ValueError, "B06_V2_NARRATIVE_BALANCE_UNSUPPORTED"):
            verify(add_sentence(args, changed_sentence))


if __name__ == "__main__":
    unittest.main()
