"""The counted model calls a LIVE registration came from, and the ledger that granted them.

A registration stands in for a model's reading of a filing: a Run consumes the
answer it holds. A LIVE registration says real, counted calls produced that
answer. An independent review registered LIVE answers for E01, D02 and D04
without any call - each register function accepted ``mode="LIVE"`` from its
caller - and the batch's default loader consumed them: a withheld E01 window
was published as 3. So a LIVE registration now carries the calls that answered
it, and a consumer accepts it only if:

1. each call's intent, terminal and wire journal hold their seals, name each
   other, and are the very records the terminal hashed;
2. the call succeeded with no stop, counted one provider and one paid call,
   and its assistant output is the output the registration holds;
3. its request is the consumer's own rebuilt request - the exact provider body
   and request bytes - under a digest the ledger's binding grants;
4. the ledger it was counted in is the one the owner's registered approval
   granted: the binding and transport recorded when the approval was
   registered from GitHub (``historical_model_calls.register_model_approval``),
   which no test writes.

The fourth condition is also why a test's leftovers are never consumed: the
review killed the suite mid-test and its fixture allowance and LIVE record
stayed in the tree. A fixture ledger is never the registered one.

This module reads no ledger root and makes no call; it checks records. Every
seal is a content hash, so a forger with write access to the checkout could
still write records that pass; what it rules out is a LIVE registration made by
a function call, or by accident, without the counted calls it claims. It is a
rule file: every Run that consumes a registration executes it.
"""
from pathlib import Path

from .canonical import canonical_json_bytes, content_hash, sha256_bytes, strict_json_loads

REQUIREMENT_ID = "issue_47_v1"
MODES = ("LIVE", "RECORDED_TEST_ONLY")
LEDGER_TYPE = "ISSUE_47_HISTORICAL_MODEL_ALLOWANCE"
COUNTED_TYPE = "ISSUE_47_COUNTED_MODEL_CALLS"
GRANTED_TYPE = "ISSUE_47_GRANTED_MODEL_LEDGER"
# Written once, by the approval's registration from GitHub, beside the approval
# record it was derived from.
GRANTED_LEDGER_PATH = "docs/evidence/issue47_history/model-egress/granted-model-ledger.json"


class CountedCallError(ValueError):
    """A registration's counted calls, or the ledger they name, do not hold."""


def _need(condition, reason):
    if not condition:
        raise CountedCallError(reason)


def _sealed(body, field):
    return {**body, field: content_hash(value=body)}


def _holds(value, field):
    return (type(value) is dict and value.get(field)
            == content_hash(value={key: item for key, item in value.items() if key != field}))


def ledger_binding(allowance, *, root, live):
    """What a ledger at ``root`` is bound to: its grant, limits and the approval it came from."""
    return _sealed({"record_type": LEDGER_TYPE, "requirement_id": REQUIREMENT_ID,
                    "root": str(root),
                    "limits": list(allowance["maximum_additional_provider_paid_sec_calls"]),
                    "purposes": list(allowance["scope"]["purposes"]),
                    "request_digests_by_grant": {
                        grant["grant"]: sorted(grant["request_digests"])
                        for grant in allowance["scope"]["grants"]},
                    "delegation_url": allowance["delegation_url"],
                    "delegation_body_sha256": allowance["delegation_body_sha256"],
                    "execution_mode": "LIVE" if live else "RECORDED_TEST_ONLY"}, "binding_id")


def request_digest(request, transport):
    """The SHA-256 of the exact provider body ``request`` sends under ``transport``."""
    from .ai_adapter import TransportPolicy
    from .continuous_semantic_calls import request_body
    policy = TransportPolicy.from_mapping(value=dict(transport))
    return "sha256:" + sha256_bytes(content=request_body(request, policy))


def counted_calls(*, ledger_binding, transport, mode, calls):
    """The block a registration carries: the ledger, its transport and each answering call.

    ``calls`` holds, per answered request in order, the request id and the
    slot's intent, terminal and wire journal as the ledger wrote them.
    """
    return _sealed({"record_type": COUNTED_TYPE, "requirement_id": REQUIREMENT_ID, "mode": mode,
                    "ledger_binding": ledger_binding, "transport": dict(transport),
                    "calls": [{"request_id": call["request_id"], "intent": call["intent"],
                               "terminal": call["terminal"], "wire": call["wire"]}
                              for call in calls]}, "counted_calls_id")


def check_counted_calls(*, counted, answered, mode):
    """Conditions 1-3 for every call: sealed, successful, and answering this request with this output.

    Args:
        counted: the block ``counted_calls`` made.
        answered: ``[(request, output bytes)]``, in the order the calls answer them.
        mode: the registration's mode, which the block and every call must share.
    """
    from .native_unit_index import evidence_json_bytes
    _need(mode in MODES and _holds(counted, "counted_calls_id")
          and counted.get("record_type") == COUNTED_TYPE
          and counted.get("requirement_id") == REQUIREMENT_ID and counted.get("mode") == mode,
          "ISSUE_47_COUNTED_CALLS_CHANGED")
    binding = counted["ledger_binding"]
    _need(_holds(binding, "binding_id") and binding.get("record_type") == LEDGER_TYPE
          and binding.get("requirement_id") == REQUIREMENT_ID
          and binding.get("execution_mode") == mode, "ISSUE_47_COUNTED_CALLS_LEDGER_CHANGED")
    calls = counted["calls"]
    _need(type(calls) is list and len(calls) == len(answered) and bool(calls),
          "ISSUE_47_COUNTED_CALLS_DO_NOT_ANSWER_EVERY_REQUEST")
    ordinals = set()
    for call, (request, output) in zip(calls, answered):
        intent, terminal, wire = call["intent"], call["terminal"], call["wire"]
        _need(call["request_id"] == request["request_id"]
              and _holds(intent, "intent_id") and _holds(terminal, "terminal_id")
              and _holds(wire, "wire_id"), "ISSUE_47_COUNTED_CALL_CHANGED:" + str(call["request_id"]))
        digest = request_digest(request, counted["transport"])
        granted = binding["request_digests_by_grant"]
        _need(intent["record_type"] == "ISSUE_47_HISTORICAL_MODEL_CALL_INTENT"
              and intent["requirement_id"] == REQUIREMENT_ID and intent["execution_mode"] == mode
              and intent["allowance_binding_id"] == binding["binding_id"]
              and intent["request_digest"] == digest
              and bool(intent["grants"])
              and all(name in granted and digest in granted[name] for name in intent["grants"]),
              "ISSUE_47_COUNTED_CALL_IS_FOR_ANOTHER_REQUEST:" + request["request_id"])
        _need(type(intent["ordinal"]) is int and intent["ordinal"] not in ordinals,
              "ISSUE_47_COUNTED_CALL_ANSWERS_TWICE:" + str(intent["ordinal"]))
        ordinals.add(intent["ordinal"])
        # The terminal hashed the slot's files when it sealed it; the intent,
        # the wire journal, the request and the output here must be those files.
        evidence = terminal["evidence"]
        _need(terminal["record_type"] == "ISSUE_47_HISTORICAL_MODEL_CALL_TERMINAL"
              and terminal["intent_id"] == intent["intent_id"] and terminal["status"] == "SUCCEEDED"
              and terminal["stop_reason"] == "" and terminal["counts"] == [1, 1, 0]
              and evidence.get("intent.json") == sha256_bytes(content=canonical_json_bytes(value=intent))
              and evidence.get("wire/journal.json") == sha256_bytes(content=canonical_json_bytes(value=wire))
              and evidence.get("semantic-request.json")
              == sha256_bytes(content=evidence_json_bytes(request))
              and evidence.get("wire/assistant-output.bin") == sha256_bytes(content=output),
              "ISSUE_47_COUNTED_CALL_DID_NOT_ANSWER_WITH_THIS_OUTPUT:" + request["request_id"])
        _need(wire["record_type"] == "ISSUE_47_HISTORICAL_MODEL_WIRE"
              and wire["intent_id"] == intent["intent_id"] and wire["mode"] == mode
              and wire["error_class"] == "" and wire["request_sha256"] == digest[len("sha256:"):]
              and wire["assistant_output_sha256"] == sha256_bytes(content=output),
              "ISSUE_47_COUNTED_CALL_DID_NOT_ANSWER_WITH_THIS_OUTPUT:" + request["request_id"])
    return counted


def granted_ledger_record(allowance):
    """What the approval's registration writes: the live ledger and transport it grants."""
    return _sealed({"record_type": GRANTED_TYPE, "requirement_id": REQUIREMENT_ID,
                    "ledger_binding": ledger_binding(allowance, root=Path(allowance["budget_root"]),
                                                     live=True),
                    "transport": dict(allowance["transport"]),
                    "delegation_url": allowance["delegation_url"],
                    "delegation_body_sha256": allowance["delegation_body_sha256"],
                    "model_wiring_receipt_id": allowance["model_wiring_receipt_id"]},
                   "granted_ledger_id")


def check_granted(*, counted, repo_root):
    """Condition 4: the calls were counted in the ledger the owner's registered approval granted."""
    path = Path(repo_root) / GRANTED_LEDGER_PATH
    _need(path.is_file() and not path.is_symlink(),
          "ISSUE_47_LIVE_REGISTRATION_WITHOUT_A_REGISTERED_APPROVAL:" + GRANTED_LEDGER_PATH)
    granted = strict_json_loads(text=path.read_text(encoding="utf-8"))
    _need(_holds(granted, "granted_ledger_id") and granted.get("record_type") == GRANTED_TYPE
          and granted.get("requirement_id") == REQUIREMENT_ID,
          "ISSUE_47_REGISTERED_APPROVAL_LEDGER_CHANGED")
    _need(counted["mode"] == "LIVE" and counted["ledger_binding"] == granted["ledger_binding"]
          and counted["transport"] == granted["transport"],
          "ISSUE_47_LIVE_REGISTRATION_IS_FROM_A_LEDGER_NO_REGISTERED_APPROVAL_GRANTED")
    return granted


def check_live_registration(*, counted, answered, repo_root):
    """All four conditions, for a LIVE registration a Run is about to consume."""
    _need(counted is not None, "ISSUE_47_LIVE_REGISTRATION_WITHOUT_COUNTED_CALLS")
    check_counted_calls(counted=counted, answered=answered, mode="LIVE")
    return check_granted(counted=counted, repo_root=repo_root)
