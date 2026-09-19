"""The raised capacity is reachable through the paths a Run actually uses.

`test_historical_text_protocol` checks the successor implementation in
isolation. That is not the same as checking it is wired: the item bound is
enforced at five places across three files, and a payload has to survive all of
them. These cases call the production entry points - record validation, trace
verification and legacy projection - with a 92-item payload, which is the size
Pfizer's D02 actually produces.

Like the other cases that need the registration patch, this skips when the
patch is not applied, and a skip is not a pass. Without the patch those three
files still import the frozen implementation, so what is being tested is the
patch's routing rather than the module it routes to.

The negative is the load-bearing one. Every case runs twice: once with the
payload declaring the revised Spec's identity and once declaring its
predecessor's. Accepting both would mean the route had simply raised the bound
for everyone, which is the failure this arrangement exists to avoid.
"""
import os
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from vnext.historical_text_protocol import revised_spec_ceilings
from vnext.specs import compile_spec_file

PREDECESSOR = "catalog/r6/D02_legal_disclosures_v1.md"
ITEMS = 92


def _wired():
    """Do the production entry points reach the successor in this checkout?

    Read off the module the patch edits rather than off the patch file, so a
    partially applied patch skips rather than reporting a pass.
    """
    import inspect
    try:
        from vnext import constraints, projector, records
    except ImportError:
        return False
    sources = "".join(inspect.getsource(module)
                      for module in (records, constraints, projector))
    return sources.count("historical_text_protocol") == 3


def _payload(count, *, text="excerpt"):
    return {"version": "TEXT_V1", "content_kind": "SOURCE_EXCERPTS",
            "renderer": "ORDERED_NEWLINE_V1",
            "coverage_hashes": ["sha256:" + "a" * 64],
            "candidate_hash": "sha256:" + "b" * 64,
            "review_unit_hash": "sha256:" + "c" * 64,
            "approval_effect_hash": "sha256:" + "d" * 64,
            "items": [{"order": n, "role": "ROLE_%d" % n, "text": "%s %d" % (text, n),
                       "observation_id": "sha256:" + ("%064x" % n)} for n in range(count)]}


def _result(count, *, closure):
    """A schema-complete METRIC_RESULT, built the way the producer builds one.

    validate_record checks the full record schema before it reaches the text
    validator, so a partial record would be refused for the wrong reason and
    prove nothing about the bound.
    """
    from vnext.canonical import content_hash
    payload = _payload(count)
    body = {"record_type": "METRIC_RESULT", "value_kind": "TEXT_V1",
            "company_id": "pfizer", "metric_id": "D02",
            "period_start": "2025-01-01", "period_end": "2025-12-31",
            "scope_key": "CONSOLIDATED", "applicability": "APPLICABLE",
            "publication": "PUBLISHED", "reason_code": "PASS",
            "spec_closure_hash": closure, "text_payload": payload, "unit": "text",
            "quality": "EXACT", "trace_id": "sha256:" + "e" * 64,
            "value": "\n".join(item["text"] for item in payload["items"])}
    return {**body, "result_id": content_hash(
        value={key: value for key, value in body.items() if key != "record_type"})}


def _trace(count, *, closure):
    from vnext.canonical import content_hash
    payload = _payload(count)
    value = "\n".join(item["text"] for item in payload["items"])
    return {"record_type": "EXECUTION_TRACE", "value_kind": "TEXT_V1",
            "spec_closure_hash": closure, "quality": "EXACT", "result": value,
            "input_observation_ids": [item["observation_id"] for item in payload["items"]],
            "steps": [{"event": "TEXT_RESULT_RENDER", "text_payload": payload,
                       "payload_hash": content_hash(value=payload)}]}


@unittest.skipUnless(_wired(),
                     "the registration patch is not applied; the production entry points "
                     "still import the frozen implementation")
class HistoricalProtocolWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.revised = next(iter(revised_spec_ceilings()))
        cls.predecessor = compile_spec_file(path=ROOT / PREDECESSOR,
                                            dependency_specs={})["spec_closure_hash"]
        assert cls.revised != cls.predecessor

    def test_record_validation_reaches_the_raised_bound(self):
        from vnext.records import validate_record
        from vnext.text_results import TextResultError
        # records.validate_record raises RecordError, which wraps the reason.
        validate_record(record=_result(ITEMS, closure=self.revised))
        with self.assertRaises(Exception) as refused:
            validate_record(record=_result(ITEMS, closure=self.predecessor))
        self.assertIn("TEXT_PAYLOAD_ITEMS_INVALID", str(refused.exception))
        # The frozen bound is still the frozen bound on the revised identity.
        validate_record(record=_result(64, closure=self.predecessor))

    def test_trace_verification_reaches_the_raised_bound(self):
        from vnext.constraints import verify_trace_observation_values
        observations = {}
        for closure in (self.revised, self.predecessor):
            trace = _trace(ITEMS, closure=closure)
            payload = trace["steps"][0]["text_payload"]
            observations = {item["observation_id"]: {
                "record_type": "VERIFIED_OBSERVATION", "value_kind": "TEXT_V1",
                "observation_id": item["observation_id"], "semantic_role": item["role"],
                "value": item["text"], "quality": "EXACT",
                "approval_effect_hash": payload["approval_effect_hash"],
                "source_binding": {"text_binding": {
                    "order": item["order"], "spec_closure_hash": closure,
                    "candidate_hash": payload["candidate_hash"],
                    "review_unit_hash": payload["review_unit_hash"],
                    "coverage_hash": payload["coverage_hashes"][0]}}}
                for item in payload["items"]}
            with self.subTest(identity="revised" if closure == self.revised else "predecessor"):
                if closure == self.revised:
                    # Reaches the payload check rather than the bound; whatever
                    # it does next, it is not TEXT_PAYLOAD_ITEMS_INVALID.
                    try:
                        verify_trace_observation_values(trace=trace, observations=observations)
                    except Exception as error:      # noqa: BLE001 - asserted below
                        self.assertNotIn("TEXT_PAYLOAD_ITEMS_INVALID", str(error))
                else:
                    with self.assertRaises(Exception) as refused:
                        verify_trace_observation_values(trace=trace, observations=observations)
                    self.assertIn("TEXT_PAYLOAD_ITEMS_INVALID", str(refused.exception))

    def test_legacy_projection_reaches_the_raised_bound(self):
        from vnext.projector import _projection_value
        projection = {"legacy_metric_id": "D02"}
        value = _projection_value(result=_result(ITEMS, closure=self.revised),
                                  projection=projection)
        self.assertEqual(ITEMS, len(value.split("\n")))
        self.assertEqual("excerpt %d" % (ITEMS - 1), value.split("\n")[-1])
        with self.assertRaises(Exception) as refused:
            _projection_value(result=_result(ITEMS, closure=self.predecessor),
                              projection=projection)
        self.assertIn("TEXT_PAYLOAD_ITEMS_INVALID", str(refused.exception))


if __name__ == "__main__":
    unittest.main()
