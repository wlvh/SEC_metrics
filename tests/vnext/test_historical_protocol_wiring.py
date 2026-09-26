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

Two negatives are load-bearing. Each case runs the payload twice, once
declaring the revised Spec's identity and once declaring its predecessor's;
accepting both would mean the route had simply raised the bound for everyone.
And a positive here is a normal return, never "it failed differently": an
entry point that raised on every call would satisfy the weaker reading while
comparing nothing, so the trace case also substitutes an observation at item
80 and requires the named comparison to refuse it.
"""
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
# The trace case needs observations the production factory would accept; a
# hand-rolled dict is refused one layer earlier, for a reason that says nothing
# about the bound. These are that factory's callers, already reviewed there.
from tests.vnext.test_historical_text_protocol import (TRACE_SUBSTITUTIONS, _observations,
                                                       _payload as _protocol_payload,
                                                       _trace as _protocol_trace)
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


def _trace_and_observations(*, closure):
    """A trace and the observations it names, both built the production way.

    `_observations` assigns each item the identity its built observation
    actually has, so the trace has to be built from the payload afterwards.
    """
    payload = _protocol_payload(ITEMS)
    observations = _observations(payload, closure=closure)
    return _protocol_trace(payload, closure=closure), observations, payload


# Two of the per-item comparisons verify_text_trace makes after the renderer
# has passed: one on the observation's own content, one on the review bindings.
# Naming the exact refusal is the point - "some exception" would be satisfied
# by a route that never reached the comparison at all.
REACHED_COMPARISONS = {
    "value_replaced": "TEXT_TRACE_OBSERVATION_VALUE_CHANGED",
    "order_replaced": "TEXT_TRACE_REVIEW_BINDING_CHANGED",
}


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
        """Returning normally, refusing at the bound, and still comparing item 80.

        The first two are the route; the third is what the route is for. A
        positive case that only asserted "the failure was not the capacity
        error" would be satisfied by an entry point that raised something else
        every time, so the accepted outcome here is a normal return.
        """
        from vnext.constraints import verify_trace_observation_values
        trace, observations, _ = _trace_and_observations(closure=self.revised)
        self.assertIsNone(verify_trace_observation_values(trace=trace,
                                                          observations=observations))
        trace, observations, _ = _trace_and_observations(closure=self.predecessor)
        with self.assertRaises(Exception) as refused:
            verify_trace_observation_values(trace=trace, observations=observations)
        self.assertIn("TEXT_PAYLOAD_ITEMS_INVALID", str(refused.exception))

    def test_trace_verification_still_compares_the_items_past_the_frozen_bound(self):
        """A route that renders 92 and compares 64 passes everything else."""
        from vnext.constraints import verify_trace_observation_values

        def refusal(name, index):
            trace, observations, payload = _trace_and_observations(closure=self.revised)
            TRACE_SUBSTITUTIONS[name](observations,
                                      payload["items"][index]["observation_id"])
            try:
                verify_trace_observation_values(trace=trace, observations=observations)
                return ("ACCEPTED", None)
            except Exception as error:      # noqa: BLE001 - the refusal is the result
                return ("REFUSED", str(error))

        for name, reason in REACHED_COMPARISONS.items():
            with self.subTest(substitution=name):
                inside = refusal(name, 7)
                beyond = refusal(name, 80)
                self.assertEqual(("REFUSED", reason), inside)
                self.assertEqual(inside, beyond)

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
