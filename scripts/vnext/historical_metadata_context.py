"""The metadata view for a pinned annual period, from every block it needs.

The frozen ``_current_metadata_context`` answers one question - which filings
do the text roles mean - and answers it only from ``filings.recent``. To keep
that safe it first refuses while any declared history shard could hold a filing
dated on or after the target period end, because an amendment of the target
period would appear there and a recent-only scan would not see it. For the
latest annual period that condition is nearly always satisfied, so the refusal
is invisible; for an earlier pinned period it is not.

Measured on this repository's saved submissions indexes: the refusal reaches
Salesforce's 2019-01-31 through 2023-01-31 periods, JPMorgan's 2024-12-31 and
Pfizer's 2018-12-31 through 2020-12-31 - thirteen company periods, three of
them inside the five-year frame. Five Salesforce 10-K rows and one JPMorgan
10-K row are themselves in a history shard rather than in ``recent``, so no
recent-only scan can find them at all. This is a consumer limitation and not a
material one: fetching those primary documents does not remove it.

What this module changes is the second half only. The invariant is the same -
no unread block may hold a filing dated on or after the pinned period end - and
it is met by reading those blocks instead of by refusing. The reading is the
existing historical catalog's, which loads newest-first, stops as soon as the
window is proven, and keeps an unsaved, misaligned or unparseable shard as an
explicit limitation rather than as "no filing". Every block it reads is a
request-proved source in the same reader, so the metadata behind a selected
filing is admitted exactly as the recent block is.

What it does not change: which filing the pinned period selects, the identity
fields that filing must match, or the source plan the text roles are built
from. Those are the frozen module's and are imported, not restated.
"""
from pathlib import Path

from .canonical import content_hash
from .normal_governance_input import _order
from .normal_history_catalog import load_history_for_period
from .text_results_v2 import TextResultV2Error

RECORD_TYPE = "HISTORICAL_TEXT_METADATA_SCOPE"
SUPPORTED_METRICS = ("C02", "D01", "D02")
# Which forms each metric's roles are chosen from. The frozen module keys the
# same set off the metric id; restating it here rather than importing it would
# be a second copy of a rule that decides which filings exist at all.
# D01 reads the annual filing and nothing else, so its forms are D02's. It is
# listed rather than defaulted: a metric that reaches here without an entry
# should stop, not silently inherit whichever set happens to be first.
_FORMS = {"C02": {"10-K", "10-K/A", "DEF 14A", "DEF 14A/A"},
          "D01": {"10-K", "10-K/A"},
          "D02": {"10-K", "10-K/A"}}
HISTORY_RULE = "EVERY_DECLARED_SHARD_REACHING_THE_PINNED_PERIOD_IS_READ_AND_ADMITTED"
METADATA_ROLES = ("sec_submissions_inventory", "sec_submissions_history")
_IDENTITY = ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument")


class HistoricalMetadataError(TextResultV2Error):
    """A metadata limitation, never a disclosure conclusion."""

    def __init__(self, reason, category="SOURCE_INTEGRITY_ERROR"):
        super().__init__(reason)
        self.category = category


def _need(condition, reason, category="SOURCE_INTEGRITY_ERROR"):
    if not condition:
        raise HistoricalMetadataError(reason, category)


def historical_metadata_context(*, repo_root: Path, company_id: str, prepared,
                                inventory, reader, metric_id: str):
    """Which filings the text roles mean when the period is pinned.

    Args:
        repo_root: Repository or installed data root.
        company_id: Configured company identity.
        prepared: The historical annual input, which owns the selected filing.
        inventory: The already-read current submissions block.
        reader: The caller's source reader, so the blocks this loads are
            admitted through the caller's own proofs rather than a second set.
        metric_id: Only D02 is wired; C02 needs the proxy roles as well.

    Returns:
        The same shape ``_source_plan`` consumes, plus the blocks that were
        read and the source references that admit them.

    Raises:
        HistoricalMetadataError: When a block the pinned period needs is not
            saved, does not agree with its declared range, or when the filing
            the blocks name is not the one the selection pinned.
    """
    _need(metric_id in SUPPORTED_METRICS,
          "HISTORICAL_TEXT_METADATA_METRIC_NOT_WIRED:" + str(metric_id), "IMPLEMENTATION_GAP")
    period = prepared["table_input"]["target_period"]
    history = load_history_for_period(repo_root=Path(repo_root), company_id=company_id,
                                      report_end=period["period_end"], reader=reader)
    _need(str(history["primary_cik"]) == str(prepared["entity"]),
          "HISTORICAL_TEXT_METADATA_ENTITY_CHANGED")
    # A shard that is missing, misaligned or unreadable is not "no filing".
    # Naming the kinds keeps an unsaved block and a body that contradicts its
    # declared range from reading as the same problem.
    _need(not history["limitations"],
          "HISTORICAL_TEXT_METADATA_BLOCK_UNUSABLE:"
          + ",".join(sorted({item["kind"] for item in history["limitations"]})),
          "SOURCE_UNAVAILABLE")
    # The invariant the frozen refusal was protecting, restated as a check on
    # what was actually read.
    _need(not history["unloaded_history_reaching_period"],
          "HISTORICAL_TEXT_METADATA_BLOCK_NOT_READ:"
          + ",".join(history["unloaded_history_reaching_period"]), "SOURCE_UNAVAILABLE")
    _need(history["window_proven"], "HISTORICAL_TEXT_METADATA_WINDOW_NOT_PROVEN",
          "SOURCE_UNAVAILABLE")
    rows = [row for row in history["all_rows"] if row["form"] in _FORMS[metric_id]]
    ordinary = [row for row in rows
                if row["form"] == "10-K" and row["reportDate"] == period["period_end"]]
    _need(len(ordinary) == 1, "HISTORICAL_TEXT_METADATA_ANNUAL_NOT_UNIQUE")
    _need(all(ordinary[0][key] == prepared["filing"][key] for key in _IDENTITY),
          "HISTORICAL_TEXT_METADATA_ANNUAL_SELECTION_CHANGED")
    amendments = _order([row for row in rows if row["form"] == "10-K/A"
                         and row["reportDate"] == period["period_end"]])
    # The proxy roles. The frozen module keeps every DEF 14A filed on or after
    # the period end and takes the first of a NEWEST-FIRST ordering, which is
    # the newest of them. For the latest period only one proxy has been filed
    # since its end, so the two readings pick the same filing; for an earlier
    # pinned period they do not, and the newest would answer 2023 with the
    # annual meeting held in 2026. The earliest one at or after the pinned end
    # is the meeting that reports on that year, so that is the one taken. D02
    # reads neither role and gets neither.
    proxies = _order([row for row in rows if row["form"] == "DEF 14A"
                      and row["filingDate"] >= period["period_end"]])
    proxy = proxies[-1] if proxies and metric_id == "C02" else None
    # The frozen amendment rule, restated against the pinned proxy rather than
    # against the newest one. For an earlier period this can reach a LATER
    # year's proxy amendment, and the plan then refuses with
    # TEXT_INPUT_GOVERNANCE_PROXY_AMENDMENT_REPLAY_REQUIRED. That is a named
    # implementation gap, not a wrong value, and narrowing the window to "before
    # the next proxy" would be a rule this corpus cannot check: it holds no
    # DEF 14A/A at all.
    proxy_amendments = _order(
        [row for row in rows if row["form"] == "DEF 14A/A"
         and row["filingDate"] >= (proxy["filingDate"] if proxy else period["period_end"])]
    ) if metric_id == "C02" else []
    selection = {"ordinary": ordinary[0], "amendments": amendments,
                 "latest_def14a": proxy, "def14a_amendments": proxy_amendments}
    scope = {"record_type": RECORD_TYPE, "company_id": prepared["company_id"],
             "cik": prepared["entity"], "metric_id": metric_id,
             "pinned_period_end": period["period_end"],
             "source_reference_id": inventory["source_reference"]["source_reference_id"],
             "raw_asset_id": inventory["raw_blob"]["raw_asset_id"],
             "complete_history_declarations": history["declared_shards"],
             "loaded_inventories": history["loaded_inventories"],
             "considered_shards": history["considered_shards"],
             "selected_filing_inventory": ordinary[0]["metadata_origin"]["inventory_name"],
             "amendment_inventories": sorted({row["metadata_origin"]["inventory_name"]
                                              for row in amendments}),
             "governance_inventories": sorted({row["metadata_origin"]["inventory_name"]
                                               for row in ([proxy] if proxy else [])
                                               + list(proxy_amendments)}),
             "history_rule": HISTORY_RULE, "selection": selection}
    return {"prepared_annual_input": prepared, "selection": selection,
            "loaded_inventories": history["loaded_inventories"],
            "history": history,
            "scope": {**scope, "scope_id": content_hash(value=scope)}}


def check_historical_metadata_scope(*, plan, context, references):
    """Every block the selection rests on is a block this input admitted.

    The frozen check requires the selected filing to come from the one current
    block, which is what makes an earlier period unreachable. The requirement
    that replaces it is not weaker: the blocks read and the metadata sources
    admitted have to be the same set, so a filing cannot be selected from a
    block that was read without being proved, and a block cannot be proved
    without being one the pinned period needed.
    """
    admitted = sorted(reference["document_name"] for reference in references
                      if reference["source_role"] in METADATA_ROLES)
    loaded = sorted(context["loaded_inventories"])
    _need(len(admitted) == len(set(admitted)),
          "HISTORICAL_TEXT_METADATA_SOURCE_NOT_UNIQUE")
    _need(admitted == loaded, "HISTORICAL_TEXT_METADATA_BLOCK_NOT_ADMITTED:"
          + ",".join(sorted(set(admitted) ^ set(loaded))))
    _need(all(filing.get("metadata_origin", {}).get("inventory_name") in set(loaded)
              for filing in plan["text_filings"]),
          "HISTORICAL_TEXT_SELECTED_FILING_OUTSIDE_READ_METADATA", "SOURCE_COVERAGE_CONFLICT")
