"""Read the bank's A01, A02, A05, A06, A07, A08 and A10 off its annual reports' inline XBRL.

The route resolves these through the deterministic catalog
(``catalog/deterministic_metrics.json``): A05-A08 and A10 from SEC's Company
Facts API, A01 and A02 from the accession's XBRL instance under two required
dimensions. This reads the annual report's primary document instead, with the
statement reader's parser (tools/read_statement_facts.py: every value a
decimal, scale and sign applied, duplicates consistent or no value), and
imports none of the route's modules. What it takes from the catalog is the
approved definition - each component's concepts, period, which filing it comes
from, and for A01/A02 the exact dimensions - not the route's code.

* A component the catalog takes from the prior filing (A05's and A06's prior
  year end, A07's prior year) is read from the prior annual report the period
  selection names. The target report states the same prior-year figure as a
  comparative; the two must agree, or the position is not read
  (PRIOR_YEAR_RESTATED_IN_THE_TARGET): a pair whose halves come from two
  versions of the same year is the case the route withholds.
* A01/A02 read only facts whose context carries exactly the required
  dimensions, no more.
* The arithmetic is the catalog's formula at Decimal precision 28,
  ROUND_HALF_EVEN: ratio a / b, difference a - b, average-denominator ratio
  a / ((b + c) / 2).

Usage:
    python3 tools/read_bank_statement_facts.py --runs-root <flat runs root> \
        --closure sha256:<closure the compared results ran under> \
        --reading <positions.json reading> --output <path> --source-root <restored root>
"""
import argparse
import json
import re
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

from acceptance_readings import reading_cases, saved_bytes  # noqa: E402
from read_statement_facts import consolidate, document_text  # noqa: E402

CATALOG = "catalog/deterministic_metrics.json"
METRICS = ("A01", "A02", "A05", "A06", "A07", "A08", "A10")
_FACT = re.compile(r"<ix:nonFraction([^>]*)>(.*?)</ix:nonFraction>", re.S)
_ATTRIBUTE = re.compile(r"([a-zA-Z:\-]+)=\"([^\"]*)\"")
_CONTEXT = re.compile(r"<xbrli:context id=\"([^\"]+)\"(.*?)</xbrli:context>", re.S)
_MEMBER = re.compile(r"<xbrldi:explicitMember[^>]*dimension=\"([^\"]+)\"[^>]*>([^<]+)"
                     r"</xbrldi:explicitMember>")


def specs(root=REPO):
    """Each metric's catalog entry, holding one approved branch."""
    catalog = json.loads((root / CATALOG).read_text(encoding="utf-8"))
    found = {}
    for metric in METRICS:
        if len(catalog["metrics"][metric]["branches"]) != 1:
            raise SystemExit("ONE_APPROVED_BRANCH_EXPECTED:" + metric)
        found[metric] = catalog["metrics"][metric]
    return found


def _contexts(text):
    contexts = {}
    for block in _CONTEXT.finditer(text):
        inner = block.group(2)
        start = re.search(r"<xbrli:startDate>([^<]+)</xbrli:startDate>", inner)
        end = re.search(r"<xbrli:endDate>([^<]+)</xbrli:endDate>", inner)
        instant = re.search(r"<xbrli:instant>([^<]+)</xbrli:instant>", inner)
        contexts[block.group(1)] = {
            "start": start.group(1) if start else None,
            "end": end.group(1) if end else (instant.group(1) if instant else None),
            "instant": bool(instant),
            "dimensions": tuple(sorted((axis, member.strip())
                                       for axis, member in _MEMBER.findall(inner)))}
    return contexts


def parse_facts(text, concepts):
    """The named facts by (concept, start, end, instant, dimensions), in any namespace.

    The catalog approves local names. A filer may tag a quantity the US GAAP
    taxonomy has no element for under its own namespace with the same name (the
    bank's CET1 ratio); a match there is read and its namespace recorded, and two
    namespaces that tag one key differently are inconsistent duplicates.

    Returns ``(facts, unread, namespaces)``: ``facts[key]`` is a list of
    ``(value, decimals)``; ``namespaces[key]`` the prefixes that tagged it.
    """
    contexts = _contexts(text)
    facts, unread, namespaces = {}, [], {}
    for tag in _FACT.finditer(text):
        attributes = dict(_ATTRIBUTE.findall(tag.group(1)))
        name = attributes.get("name", "")
        if ":" not in name or name.split(":")[-1] not in concepts:
            continue
        context = contexts.get(attributes.get("contextRef"))
        if context is None:
            continue
        shown = re.sub(r"<[^>]+>", "", tag.group(2)).replace(",", "").strip()
        if attributes.get("format", "").endswith("fixed-zero"):
            value = Decimal(0)
        else:
            try:
                value = Decimal(shown)
            except ArithmeticError:
                unread.append({"concept": name, "context": attributes.get("contextRef"),
                               "shown": shown[:40]})
                continue
        value *= Decimal(10) ** int(attributes.get("scale", "0") or 0)
        if attributes.get("sign") == "-":
            value = -value
        key = (name.split(":")[-1], context["start"], context["end"], context["instant"],
               context["dimensions"])
        facts.setdefault(key, []).append((value, attributes.get("decimals", "INF")))
        namespaces.setdefault(key, set()).add(name.split(":")[0])
    return facts, unread, {key: sorted(found) for key, found in namespaces.items()}


def _period(role, period):
    """The (start, end, instant) a component's period role names."""
    current = (period["period_start"], period["period_end"])
    prior = (period["prior_start"], period["prior_end"])
    return {"current_annual": (*current, False), "current_instant": (None, current[1], True),
            "prior_annual": (*prior, False), "prior_instant": (None, prior[1], True)}[role]


def component_value(parsed, component, period):
    """The first approved concept with a consistent value, and what was seen."""
    facts, _, namespaces = parsed
    start, end, instant = _period(component["period_role"], period)
    dimensions = tuple(sorted(component["required_dimensions"].items()))
    if component["dimension_policy"] == "NONE" and dimensions:
        raise SystemExit("UNDIMENSIONED_COMPONENT_NAMES_DIMENSIONS:" + component["role"])
    seen = {}
    for concept in component["approved_concepts"]:
        key = (concept, start, end, instant, dimensions)
        entries = facts.get(key)
        if not entries:
            continue
        value, problem = consolidate(entries)
        seen[concept] = {"value": str(value) if problem is None else None, "problem": problem,
                         "namespaces": namespaces[key]}
        if problem is None:
            return concept, value, seen
    return None, None, seen


def formula(formula_id, values):
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        if formula_id == "direct":
            return +values[0]
        if formula_id == "difference":
            return +(values[0] - values[1])
        if formula_id == "ratio":
            return +(values[0] / values[1])
        if formula_id == "average_denominator_ratio":
            return +(values[0] / ((values[1] + values[2]) / Decimal(2)))
    raise SystemExit("FORMULA_NOT_READ_HERE:" + formula_id)


def read_metric(*, branch, target, prior, period):
    """One metric from the target report's and the prior report's facts.

    ``target`` and ``prior`` are ``(facts, unread)`` of the two documents;
    ``prior`` may be None where no component needs it.
    """
    components, values = [], []
    for component in branch["components"]:
        source = {"current": target, "prior": prior}[component["accession_role"]]
        if source is None:
            return {"read": None, "why_not_read": "PRIOR_FILING_NOT_READ", "components": components}
        concept, value, seen = component_value(source, component, period)
        entry = {"role": component["role"], "accession_role": component["accession_role"],
                 "concept": concept, "value": None if value is None else str(value),
                 "approved_concepts_seen": seen}
        if component["accession_role"] == "prior" and value is not None:
            # The same year as the target report states it, beside it.
            _, comparative, _ = component_value(target, component, period)
            entry["target_report_states"] = None if comparative is None else str(comparative)
            if comparative is not None and comparative != value:
                components.append(entry)
                return {"read": None, "why_not_read": "PRIOR_YEAR_RESTATED_IN_THE_TARGET",
                        "components": components}
        components.append(entry)
        if value is None:
            return {"read": None, "why_not_read": "NO_APPROVED_CONCEPT_FOR_" + component["role"],
                    "components": components}
        values.append(value)
    return {"read": str(formula(branch["formula_id"], values)), "why_not_read": None,
            "formula_id": branch["formula_id"], "components": components}


def read_position(*, target_text, prior_text, period, root=REPO):
    """Every metric for one bank year."""
    branches = {metric: entry["branches"][0] for metric, entry in specs(root).items()}
    concepts = {concept for branch in branches.values() for component in branch["components"]
                for concept in component["approved_concepts"]}
    target = parse_facts(target_text, concepts)
    prior = None if prior_text is None else parse_facts(prior_text, concepts)
    out = {metric: read_metric(branch=branches[metric], target=target, prior=prior, period=period)
           for metric in METRICS}
    out["_unread"] = {"target": target[1], "prior": None if prior is None else prior[1]}
    return out


def main():
    from acceptance_readings import accession_of_document
    from bind_acceptance_readings import identity_for
    from sec_urls import accession_document_url
    from vnext.annual_update import saved_source
    from vnext.historical_annual_input import prepare_historical_annual_input
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    from vnext.normal_history_plan import checkpoint_replayed_once
    from vnext.normal_period_selection import resolve_period_selection
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    parser.add_argument("--reading", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-root", type=Path, default=REPO)
    arguments = parser.parse_args()
    source = arguments.source_root.resolve()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    body = {"reader": "tools/read_bank_statement_facts.py", "catalog": CATALOG,
            "requirement_closure_hash": arguments.closure, "per_position": {},
            "calls": {"provider": 0, "paid": 0, "sec": 0}}
    with checkpoint_replayed_once():
        for company_id, report_end, label in reading_cases(arguments.reading):
            selection = resolve_period_selection(repo_root=source, company_id=company_id,
                                                 report_end=report_end)
            prepared = prepare_historical_annual_input(repo_root=source, company_id=company_id,
                                                       period_selection=selection)
            table = prepared["original_input"]["table_input"]
            document = table["source_repo_relative_path"]
            target_text = document_text(saved_bytes(repo_root=REPO, relative=document))
            prior_filing = selection.get("prior_filing") or {}
            prior_text, prior_url, prior_document = None, None, None
            if prior_filing.get("accessionNumber"):
                prior_url = accession_document_url(cik=int(prepared["entity"]),
                                                   accession=prior_filing["accessionNumber"],
                                                   document_name=prior_filing["primaryDocument"])
                saved = saved_source(repo_root=source, url=prior_url,
                                     accession=prior_filing["accessionNumber"])
                if saved is not None:
                    prior_text = document_text(saved["raw"])
                    # Where the bytes are, so the test reads the same ones back.
                    prior_document = saved["proof"]["request_repo_relative_path"]
            # The prior year is one year long ending on the selection's prior
            # report end; facts are matched on exact dates, so a year of
            # another length is read as absent, never as another year.
            prior_end = date.fromisoformat(selection["prior_report_end"])
            period = {"period_start": table["target_period"]["period_start"],
                      "period_end": table["target_period"]["period_end"],
                      "prior_start": (date(prior_end.year - 1, prior_end.month, prior_end.day)
                                      + timedelta(days=1)).isoformat(),
                      "prior_end": prior_end.isoformat()}
            measures = read_position(target_text=target_text, prior_text=prior_text,
                                     period=period)
            accession, _ = accession_of_document(repo_root=REPO, document=document)
            entry = {"company_id": company_id, "period_end": report_end, "document": document,
                     "period": period, "prior_filing_url": prior_url,
                     "prior_document": prior_document,
                     "needed_facts_not_read": measures["_unread"], "metrics": {}}
            for metric in METRICS:
                result = select_receipt(found=index.get((company_id, metric, report_end), []),
                                        closure=arguments.closure)["result"]
                shown = None if result is None or result.get("value") is None else str(result["value"])
                read = measures[metric]["read"]
                row = {**measures[metric], "published": shown,
                       "verdict": ("NO_PUBLISHED_VALUE" if shown is None else "NOT_READ" if read is None
                                   else "MATCH" if Decimal(read) == Decimal(shown) else "DIFFERS")}
                if shown is not None:
                    entry_spec = specs()[metric]
                    filings = [accession]
                    if any(c["accession_role"] == "prior" for c in entry_spec["branches"][0]["components"]):
                        filings.append(prior_filing["accessionNumber"])
                    # A result whose components are all year-end instants is an
                    # instant (the capital ratios, A10); one with any annual
                    # component covers the year.
                    annual = any(component["period_role"].endswith("annual")
                                 for component in entry_spec["branches"][0]["components"])
                    window = ([period["period_start"], period["period_end"]] if annual
                              else [period["period_end"], period["period_end"]])
                    identity, refusal = identity_for(
                        position={"company_id": company_id, "metric_id": metric,
                                  "period_end": report_end, "published": shown,
                                  "reading_filings": filings, "reading_window": window,
                                  "filings_are_the_whole_set": False},
                        index=index, closure=arguments.closure)
                    if refusal is not None:
                        raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + metric + ":" + refusal)
                    identity["established_by"] = "RECORDED_AT_READING_TIME"
                    row["checked_identity"] = identity
                    row["window"] = window
                entry["metrics"][metric] = row
            body["per_position"][label] = entry
            print(label, " ".join(metric + ":" + entry["metrics"][metric]["verdict"]
                                  for metric in METRICS), flush=True)
    (REPO / arguments.output).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False)
                                         + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
