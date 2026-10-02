"""Which published results of a batch the same-concept recast rule moves.

For every frozen Run of the named metrics in a runs root, the claims the result
was computed from (each with its concept, period and accession) are put to
``paired_measure_problem`` with the company's saved Company Facts as the target
filing's claims, once as the batch's code asked (a pair on one concept asks
nothing) and once as it asks now. Zero calls; the saved Company Facts are the
checkout's own copies.

The first measurement asked B02 and A07, whose two claims are both durations.
A05 and A06 pair a balance at two year ends - an instant, which Company Facts
states with no start and a claim states with its start equal to its end - and
carry a third claim (the year's net income) that is not paired. ``--metrics``
names them; without it the script asks what the first measurement asked and
writes the same rows.

Usage:
    python3 docs/evidence/issue47_history/b02-same-concept-recast/measure.py <runs root> <output.json> [--metrics B02,A07]
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "scripts"))
from sec_urls import companyfacts_url  # noqa: E402
from vnext import historical_results as route  # noqa: E402
from vnext.annual_update import saved_source  # noqa: E402
from vnext.zero_ai_r2 import _load_deterministic_catalog  # noqa: E402


def facts_of(cik, cache={}):
    if cik not in cache:
        body = json.loads(saved_source(repo_root=REPO, url=companyfacts_url(cik=int(cik)))["raw"])
        claims = []
        for taxonomy in body["facts"].values():
            for concept, entry in taxonomy.items():
                for fact in entry.get("units", {}).get("USD", []):
                    # An instant has no start; its claim's start is its end.
                    claims.append({"locator": {"concept": concept,
                                               "period_start": fact.get("start", fact["end"]),
                                               "period_end": fact["end"]},
                                   "attributes": {"accession": fact["accn"]}, "unit": "USD",
                                   "value": str(fact["val"])})
        cache[cik] = claims
    return cache[cik]


def _paired(route_entry, claims):
    """The current and prior claims of the result's one paired concept list."""
    lists = route._paired_concept_lists(route_entry)
    paired = [c for c in claims if any(c["locator"]["concept"] in concepts for concepts in lists)]
    if len(lists) != 1 or len(paired) != 2:
        return None
    return sorted(paired, key=lambda c: c["locator"]["period_end"])


def main():
    runs, out = Path(sys.argv[1]), Path(sys.argv[2])
    metrics = ["B02", "A07"]
    if len(sys.argv) == 5 and sys.argv[3] == "--metrics":
        metrics = sys.argv[4].split(",")
    catalog = _load_deterministic_catalog(repo_root=REPO)["metrics"]
    rows = []
    for run in [run for metric in metrics for run in sorted(runs.glob("run-*-" + metric))]:
        records = [json.loads(line) for line in (run / "records.jsonl").open()]
        results = [r for r in records if r["record_type"] == "METRIC_RESULT"
                   and r["metric_id"] == run.name[-3:]]
        claims = [r for r in records if r["record_type"] == "DETERMINISTIC_VERIFIED_CLAIM"]
        if len(results) != 1 or results[0].get("value") is None:
            continue
        ordered = _paired(catalog[run.name[-3:]], claims)
        if ordered is None:
            continue
        prior, current = ordered
        cik = current["attributes"]["entity"]
        target = current["attributes"]["accession"]
        problem, _ = route.paired_measure_problem(
            route=catalog[run.name[-3:]],
            claims=[{**c, "unit": "USD", "value": str(c["value"])} for c in claims],
            current_claims=facts_of(cik),
            accessions={"current": target, "prior": prior["attributes"]["accession"]})
        same = current["locator"]["concept"] == prior["locator"]["concept"]
        rows.append({"run": run.name, "metric_id": run.name[-3:], "published": str(results[0]["value"]),
                     "same_concept": same,
                     "asked_before": not same,
                     "withheld_now": problem is not None,
                     "moves": problem is not None and same,
                     "problem": problem})
    moved = [r for r in rows if r["moves"]]
    out.write_text(json.dumps({"record_type": "ISSUE_47_B02_SAME_CONCEPT_RECAST_MEASURE",
                               "runs_root": runs.name, "positions": len(rows),
                               "moved": [r["run"] for r in moved], "rows": rows},
                              indent=1, sort_keys=True) + "\n")
    print(len(rows), "positions;", len(moved), "moved:", [r["run"] for r in moved])


if __name__ == "__main__":
    main()
