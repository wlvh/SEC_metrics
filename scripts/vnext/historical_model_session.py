"""#47's model-call session for the historical semantic routes.

The model-call counterpart of ``historical_sec_session``: it plans the requests
a pinned D04 source needs, registers assessments into #47's own creator journal,
and refuses a live call by name. It is not a rule file. What a Run consumes is
re-derived from the registered outputs by ``historical_semantic_results``,
whose bytes the Requirement binds, so no credit rests on this module's bytes.

Live mode refuses, and for two separate reasons that are both stated:

1. **No allowance.** #47 has no model-call allowance of its own and does not
   borrow #28's. ``ALLOWANCE_PATH`` does not exist.
2. **No egress path.** Even with an allowance there is no way for #47 to open a
   provider socket. Three gates decide it, all bound by bytes in the frozen
   generations: WB-3's invocation controller
   (``invocation_control._prepare_successor_invocation_authority_from_requirement``)
   registers requirement generations by id - issue_28_v2, the R4 revision and
   issue_28_v14 - and refuses any other; the adapter
   (``ai_adapter._scoped_transport_payload``) hands bytes to the socket only for
   request types it names; and ``tools/check_provider_egress.py`` fixes the
   exact set of transport callers, the only semantic one being #28's
   (``continuous_semantic_calls._Transport.send``, bound to #28's ledger and
   delegation). The change that would open them for ``issue_47_v1`` is written
   as a patch for independent security review, with #47's own allowance,
   ledger and request binding in ``historical_model_calls`` and the verified
   offline evidence beside it (docs/evidence/issue47_history/model-egress/);
   this module does not route around it, and the refusal below names all three.

Recorded mode takes assistant outputs a caller supplies - a test's synthetic
responses - and registers them as RECORDED_TEST_ONLY. That proves the path from
a response to a historical Run, never a filing's content, and a batch never
consumes it: the Run path defaults to LIVE and takes a recorded registration
only when it is named.
"""
from pathlib import Path

from .historical_semantic_results import (JOURNAL, SUPPORTED_METRICS, journal_directory,
                                          pinned_native_source, pinned_requests,
                                          registered_export_bytes, registered_record)
from .normal_source_authority import ROOT

REQUIREMENT_ID = "issue_47_v1"
ALLOWANCE_PATH = "config/issue47_historical_model_calls_v1.json"
EGRESS_GATES = ("scripts/vnext/invocation_control.py", "scripts/vnext/ai_adapter.py",
                "tools/check_provider_egress.py")
_FACTORY = object()


class HistoricalModelSessionError(ValueError):
    """A model-call session request this Issue cannot serve; the reason names why."""


def _need(condition, reason):
    if not condition:
        raise HistoricalModelSessionError(reason)


def live_historical_model_session(*, repo_root: Path = ROOT):
    """Refuse, naming the first missing authority.

    The allowance is checked first because it is the owner's decision; the
    egress registration is named even when an allowance exists, so granting
    one cannot be mistaken for having enabled calls.
    """
    _need((Path(repo_root) / ALLOWANCE_PATH).is_file(),
          "ISSUE_47_MODEL_ALLOWANCE_NOT_GRANTED:" + ALLOWANCE_PATH)
    raise HistoricalModelSessionError(
        "ISSUE_47_MODEL_EGRESS_NOT_REGISTERED:" + ",".join(EGRESS_GATES))


def recorded_historical_model_session():
    """A session that registers supplied outputs as RECORDED_TEST_ONLY."""
    return RecordedHistoricalModelSession(_FACTORY)


class RecordedHistoricalModelSession:
    """Registers test-supplied outputs; the only mode that can register today."""

    mode = "RECORDED_TEST_ONLY"

    def __init__(self, factory):
        _need(factory is _FACTORY, "ISSUE_47_MODEL_SESSION_FACTORY_REQUIRED")
        self._written = []

    def plan(self, *, repo_root: Path, company_id: str, metric_id: str, period_selection):
        """The pinned source and every request it partitions into; no call."""
        source = pinned_native_source(repo_root=repo_root, company_id=company_id,
                                      metric_id=metric_id, period_selection=period_selection)
        return {"source": source, "requests": pinned_requests(source),
                "calls": {"provider": 0, "paid": 0, "sec": 0}}

    def register(self, *, repo_root: Path, company_id: str, metric_id: str, period_selection,
                 outputs):
        """Accept every output and write the registration to the creator journal.

        Returns:
            The registered record. The file is content-addressed and written
            immutably: the same record registered twice is the same file, and
            different bytes under an existing name are refused.
        """
        from sec_http import write_immutable_bytes
        _need(metric_id in SUPPORTED_METRICS, "ISSUE_47_MODEL_SESSION_METRIC_NOT_WIRED:" + metric_id)
        planned = self.plan(repo_root=repo_root, company_id=company_id, metric_id=metric_id,
                            period_selection=period_selection)
        record = registered_record(source=planned["source"], period_selection=period_selection,
                                   outputs=outputs, mode=self.mode)
        directory = journal_directory(mode=self.mode, metric_id=metric_id,
                                      source_id=record["source_id"])
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (record["input_record_id"][len("sha256:"):] + ".json")
        write_immutable_bytes(path=path, content=registered_export_bytes(record))
        self._written.append(path)
        return record

    def discard(self):
        """Remove the registrations this session wrote - test clean-up only.

        Only this session's own RECORDED_TEST_ONLY files are removed, and the
        directories they sat in if that leaves them empty; nothing LIVE can be
        reached from here.
        """
        base = (ROOT / JOURNAL / self.mode).resolve()
        for path in self._written:
            _need(base in path.resolve().parents, "ISSUE_47_MODEL_SESSION_DISCARD_OUTSIDE_RECORDED")
            if path.exists():
                path.unlink()
            for parent in path.parents:
                if not parent.is_dir() or any(parent.iterdir()):
                    break
                parent.rmdir()
                if parent == base.parent:
                    break
        self._written = []
