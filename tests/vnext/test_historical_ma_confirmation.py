"""E01's confirmation contract on synthetic candidates: the question, the answer's form, the count.

Every check here is on form. The model is asked what an item's text reports;
what the program holds it to is that its answer is about exactly these items,
in these items' own words, with one of three decisions - and that a window
with an item its text does not settle is withheld rather than undercounted.
"""
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from vnext import historical_ma_confirmation as confirmation
from vnext.canonical import sha256_bytes

ROUTE = json.loads((ROOT / "catalog/r6/E01_content_confirmed_ma_v1.json").read_text(encoding="utf-8"))["route"]
MERGER = ("Item 1.01. Entry into a Material Definitive Agreement. On July 7, 2024, the Company "
          "entered into an Agreement and Plan of Merger with Buyer Holdings, under which a "
          "subsidiary of Buyer Holdings will merge with and into the Company.")
LOAN = ("Item 1.01. Entry into a Material Definitive Agreement. On April 17, 2025, the Company "
        "entered into an amendment to its revolving credit agreement with its lenders.")
POINTER = "Item 8.01. Other Events. The information in Exhibit 99.1 is incorporated herein by reference."


def candidate(text, *, accession, code, start=0):
    return {"accession": accession, "item_code": code, "heading": text.split(".")[0] + ".",
            "start": start, "text": text,
            "primary_source_reference_id": "sha256:" + sha256_bytes(content=accession.encode()),
            "text_sha256": "sha256:" + sha256_bytes(content=text.encode("utf-8"))}


def request(*texts):
    candidates = [candidate(text, accession="0000000001-25-%06d" % index, code=text[5:9])
                  for index, text in enumerate(texts, start=1)]
    return confirmation.confirmation_request(
        route=ROUTE, company_id="example", target_cik="1",
        window={"period_start": "2025-01-01", "period_end": "2025-12-31"}, candidates=candidates)


def answer(req, decisions):
    rows = []
    for item, (decision, quote) in zip(req["items"], decisions):
        rows.append({"item_id": item["item_id"], "decision": decision,
                     "quote": quote if quote is not None else item["text"][12:80]})
    return json.dumps({"item_decisions": rows}).encode("utf-8")


class TheRequestIsTheItemsTextsAndTheDefinition(unittest.TestCase):

    def test_the_request_holds_each_item_text_bound_by_its_hash(self):
        req = request(MERGER, LOAN)
        self.assertEqual([MERGER, LOAN], [item["text"] for item in req["items"]])
        self.assertEqual(ROUTE["confirmation"]["counts"], req["definition"]["counts"])
        self.assertEqual(req, request(MERGER, LOAN))

    def test_a_changed_text_is_a_different_request(self):
        self.assertNotEqual(request(MERGER)["request_id"], request(LOAN)["request_id"])
        self.assertNotEqual(request(MERGER)["source_id"], request(LOAN)["source_id"])

    def test_a_text_that_is_not_the_one_hashed_is_refused(self):
        forged = candidate(MERGER, accession="0000000001-25-000001", code="1.01")
        forged["text"] = LOAN
        with self.assertRaisesRegex(confirmation.ConfirmationContractError,
                                    "E01_CONFIRMATION_ITEM_TEXT_CHANGED"):
            confirmation.confirmation_request(route=ROUTE, company_id="example", target_cik="1",
                                              window={"period_start": "2025-01-01",
                                                      "period_end": "2025-12-31"},
                                              candidates=[forged])

    def test_no_candidate_is_no_request(self):
        with self.assertRaisesRegex(confirmation.ConfirmationContractError,
                                    "E01_CONFIRMATION_REQUEST_HAS_NO_CANDIDATE"):
            request()


class TheAnswerIsHeldToItsForm(unittest.TestCase):

    def setUp(self):
        self.req = request(MERGER, LOAN)

    def refused(self, raw, reason):
        with self.assertRaisesRegex(confirmation.ConfirmationContractError, reason):
            confirmation.validate_answer(request=self.req, raw_output=raw)

    def test_a_well_formed_answer_is_read(self):
        decisions = confirmation.validate_answer(request=self.req, raw_output=answer(
            self.req, [("REPORTS_A_TRANSACTION", None), ("DOES_NOT_REPORT_A_TRANSACTION", None)]))
        self.assertEqual(["REPORTS_A_TRANSACTION", "DOES_NOT_REPORT_A_TRANSACTION"],
                         [decisions[item["item_id"]]["decision"] for item in self.req["items"]])

    def test_a_quote_not_in_the_item_is_refused(self):
        self.refused(answer(self.req, [("REPORTS_A_TRANSACTION", "merger with a company it acquired"),
                                       ("DOES_NOT_REPORT_A_TRANSACTION", None)]),
                     "E01_CONFIRMATION_QUOTE_NOT_IN_THE_ITEM")

    def test_a_quote_from_another_item_is_refused(self):
        self.refused(answer(self.req, [("REPORTS_A_TRANSACTION", None),
                                       ("DOES_NOT_REPORT_A_TRANSACTION", MERGER[60:120])]),
                     "E01_CONFIRMATION_QUOTE_NOT_IN_THE_ITEM")

    def test_a_quote_too_short_or_too_long_is_refused(self):
        self.refused(answer(self.req, [("REPORTS_A_TRANSACTION", "Merger"),
                                       ("DOES_NOT_REPORT_A_TRANSACTION", None)]),
                     "E01_CONFIRMATION_QUOTE_LENGTH")

    def test_an_unknown_decision_is_refused(self):
        self.refused(answer(self.req, [("PROBABLY_A_MERGER", None),
                                       ("DOES_NOT_REPORT_A_TRANSACTION", None)]),
                     "E01_CONFIRMATION_DECISION_UNKNOWN")

    def test_every_item_is_answered_exactly_once(self):
        one = json.loads(answer(self.req, [("REPORTS_A_TRANSACTION", None),
                                           ("DOES_NOT_REPORT_A_TRANSACTION", None)]))
        missing = {"item_decisions": one["item_decisions"][:1]}
        self.refused(json.dumps(missing).encode(), "E01_CONFIRMATION_ITEMS_UNANSWERED")
        twice = {"item_decisions": [one["item_decisions"][0]] * 2 + one["item_decisions"][1:]}
        self.refused(json.dumps(twice).encode(), "E01_CONFIRMATION_ITEM_ANSWERED_TWICE")
        stranger = {"item_decisions": one["item_decisions"]
                    + [{**one["item_decisions"][0], "item_id": "0000000009-25-000009#8.01@0"}]}
        self.refused(json.dumps(stranger).encode(), "E01_CONFIRMATION_ANSWERS_AN_ITEM_NOT_ASKED")

    def test_extra_keys_and_non_json_are_refused(self):
        one = json.loads(answer(self.req, [("REPORTS_A_TRANSACTION", None),
                                           ("DOES_NOT_REPORT_A_TRANSACTION", None)]))
        self.refused(json.dumps({**one, "count": 1}).encode(), "E01_CONFIRMATION_ANSWER_SHAPE")
        self.refused(b"one merger", "E01_CONFIRMATION_ANSWER_NOT_STRICT_JSON")
        self.refused(b'{"item_decisions": [], "item_decisions": []}',
                     "E01_CONFIRMATION_ANSWER_NOT_STRICT_JSON")


class TheCountIsWhatWasConfirmed(unittest.TestCase):

    def test_the_count_is_the_confirmed_items(self):
        req = request(MERGER, LOAN)
        decisions = confirmation.validate_answer(request=req, raw_output=answer(
            req, [("REPORTS_A_TRANSACTION", None), ("DOES_NOT_REPORT_A_TRANSACTION", None)]))
        value, reason, items = confirmation.confirmed_count(request=req, decisions=decisions)
        self.assertEqual((1, None, [req["items"][0]["item_id"]]), (value, reason, items))

    def test_an_item_its_text_does_not_settle_withholds_the_window(self):
        req = request(MERGER, POINTER)
        decisions = confirmation.validate_answer(request=req, raw_output=answer(
            req, [("REPORTS_A_TRANSACTION", None), ("CANNOT_TELL_FROM_THE_ITEM_TEXT", None)]))
        value, reason, items = confirmation.confirmed_count(request=req, decisions=decisions)
        self.assertIsNone(value)
        self.assertEqual(confirmation.WITHHELD_REASON, reason)
        self.assertEqual([req["items"][1]["item_id"]], items)


class ARegistrationIsCheckedAgainUnderTheCurrentCode(unittest.TestCase):

    def setUp(self):
        self.req = request(MERGER, LOAN)
        self.output = answer(self.req, [("REPORTS_A_TRANSACTION", None),
                                        ("DOES_NOT_REPORT_A_TRANSACTION", None)])
        self.record = confirmation.registered_confirmation(
            request=self.req, period_selection_id="sha256:" + "0" * 64, output=self.output,
            mode="RECORDED_TEST_ONLY")

    def test_the_record_re_derives(self):
        self.assertEqual(1, self.record["counted"]["value"])
        self.assertEqual(self.record, confirmation.validate_registered(
            record=self.record, request=self.req, period_selection_id="sha256:" + "0" * 64,
            mode="RECORDED_TEST_ONLY"))

    def test_a_record_for_another_request_or_mode_is_refused(self):
        with self.assertRaisesRegex(confirmation.ConfirmationContractError,
                                    "E01_CONFIRMATION_REGISTERED_FOR_ANOTHER_REQUEST"):
            confirmation.validate_registered(record=self.record, request=request(MERGER),
                                             period_selection_id="sha256:" + "0" * 64,
                                             mode="RECORDED_TEST_ONLY")
        with self.assertRaisesRegex(confirmation.ConfirmationContractError,
                                    "E01_CONFIRMATION_REGISTRATION_IS_FOR_ANOTHER_REQUIREMENT_OR_MODE"):
            confirmation.validate_registered(record=self.record, request=self.req,
                                             period_selection_id="sha256:" + "0" * 64, mode="LIVE")

    def test_an_edited_count_is_refused_even_when_resealed(self):
        from vnext.canonical import content_hash
        body = {key: value for key, value in self.record.items() if key != "input_record_id"}
        body["counted"] = {**body["counted"], "value": 2}
        forged = {**body, "input_record_id": content_hash(value=body)}
        with self.assertRaisesRegex(confirmation.ConfirmationContractError,
                                    "E01_CONFIRMATION_DOES_NOT_RE_DERIVE"):
            confirmation.validate_registered(record=forged, request=self.req,
                                             period_selection_id="sha256:" + "0" * 64,
                                             mode="RECORDED_TEST_ONLY")


if __name__ == "__main__":
    unittest.main()
