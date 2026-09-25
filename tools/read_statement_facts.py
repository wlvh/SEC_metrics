"""Read the eight statement metrics out of each filing's own inline XBRL.

The route resolves B01-B05 and B07-B09 from the Company Facts API; this walks
the filing's primary document instead, so agreement is a cross-source check.
The candidate chains are the approved definition's
(02_指标定义_SEC_10公司单年指标.md), not the route's code.

It replaces a reading whose code was never committed, and that reading had a
defect this one exists to not have: it parsed each value with ``int()`` and
skipped whatever failed. A fact written "1.2" with scale 9 fails ``int()``, so
Salesforce's DepreciationDepletionAndAmortization - "Depreciation and
amortization of fixed assets totaled $1.2 billion" - was invisible, the
reading followed the chain past it, and the difference was written up as the
route being right. Here every value is parsed as a decimal, the SEC's
fixed-zero dash is zero, and a needed fact that still cannot be parsed is
listed, never dropped.

Two more rules the filings need:

* Duplicates. A filing may tag the same concept and context twice - a table
  value and the same number rounded in a sentence. XBRL treats them as one fact
  when the less precise rounds to the more precise; the most precise is kept.
  Duplicates that do not round to each other are inconsistent and the concept
  has no value here.
* Alternative names. The three direct D&A concepts are three names for one
  quantity, total depreciation and amortization. When a filing gives two of
  them different values, one of them is not that quantity, and this reading
  does not accept a B03 built on either (DIRECT_CANDIDATES_DISAGREE). The
  revenue, net income and interest chains are not like that: their concepts
  are different quantities in the definition's order of preference - contract
  revenue before total revenues - so a later one differing is the definition's
  choice, recorded and not treated as a contradiction.

Usage:
    python3 tools/read_statement_facts.py --runs-root <flat runs root> \
        --closure sha256:<closure the compared results ran under>
"""
import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tools"))

OUT = "docs/evidence/issue47_history/content-acceptance/cross-source-read.json"
CASES = [("marriott_international", "2025-12-31", "marriott-2025"),
         ("marriott_international", "2024-12-31", "marriott-2024"),
         ("marriott_international", "2023-12-31", "marriott-2023"),
         ("ford_motor_company", "2025-12-31", "ford-2025"),
         ("pfizer", "2025-12-31", "pfizer-2025"),
         ("lumen_technologies", "2025-12-31", "lumen-2025"),
         ("enphase_energy", "2025-12-31", "enphase-2025"),
         ("southwest_airlines", "2025-12-31", "southwest-2025"),
         ("salesforce", "2026-01-31", "salesforce-2026"),
         ("macys", "2026-01-31", "macys-2026")]
REVENUE = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
           "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"]
NET_INCOME = ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]
CAPEX = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]
INTEREST = ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"]
DA = ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
      "DepreciationAndAmortization"]
# Operating income: OperatingIncomeLoss, or pretax continuing income less an
# AGGREGATE nonoperating bridge - never one assembled from fragments - cross-
# checked against Revenues - CostsAndExpenses where the filer tags the latter.
PRETAX = ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
          "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]
NONOPERATING = ["NonoperatingIncomeExpense", "OtherNonoperatingIncomeExpense"]
NEEDED = frozenset(REVENUE + NET_INCOME + CAPEX + INTEREST + DA + PRETAX + NONOPERATING
                   + ["Depreciation", "AmortizationOfIntangibleAssets",
                      "NetCashProvidedByUsedInOperatingActivities", "OperatingIncomeLoss",
                      "AssetsCurrent", "LiabilitiesCurrent",
                      "CashAndCashEquivalentsAtCarryingValue", "CostsAndExpenses"])
_FACT = re.compile(r"<ix:nonFraction([^>]*)>(.*?)</ix:nonFraction>", re.S)
_ATTRIBUTE = re.compile(r"([a-zA-Z:\-]+)=\"([^\"]*)\"")
_CONTEXT = re.compile(r"<xbrli:context id=\"([^\"]+)\"(.*?)</xbrli:context>", re.S)


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
            "dimensional": bool(re.search(r"<xbrldi:explicitMember", inner))}
    return contexts


def parse_facts(text):
    """Every undimensioned us-gaap fact the chains need, with its precision.

    Returns:
        ``(facts, unread)``: ``facts[concept][(start, end, instant)]`` is a list
        of ``(value, decimals)``; ``unread`` lists each needed fact whose shown
        value this reader cannot turn into a number.
    """
    contexts = _contexts(text)
    facts, unread = {}, []
    for tag in _FACT.finditer(text):
        attributes = dict(_ATTRIBUTE.findall(tag.group(1)))
        name = attributes.get("name", "")
        local = name.split(":")[-1]
        if not name.startswith("us-gaap:") or local not in NEEDED:
            continue
        context = contexts.get(attributes.get("contextRef"))
        if context is None or context["dimensional"]:
            continue
        shown = re.sub(r"<[^>]+>", "", tag.group(2)).replace(",", "").strip()
        if attributes.get("format", "").endswith("fixed-zero"):
            value = Decimal(0)
        else:
            try:
                value = Decimal(shown)
            except InvalidOperation:
                unread.append({"concept": local, "context": attributes.get("contextRef"),
                               "format": attributes.get("format"), "shown": shown[:40]})
                continue
        value *= Decimal(10) ** int(attributes.get("scale", "0") or 0)
        if attributes.get("sign") == "-":
            value = -value
        key = (context["start"], context["end"], context["instant"])
        facts.setdefault(local, {}).setdefault(key, []).append(
            (value, attributes.get("decimals", "INF")))
    return facts, unread


def consolidate(entries):
    """One value for duplicate facts, or the reason there is none.

    The most precise is kept; every other must round to it at its own
    precision, which is XBRL's test for consistent duplicates.
    """
    def precision(decimals):
        return float("inf") if decimals == "INF" else int(decimals)
    best_value, best_decimals = max(entries, key=lambda entry: precision(entry[1]))
    for value, decimals in entries:
        if decimals == "INF" or precision(decimals) >= precision(best_decimals):
            if value != best_value:
                return None, "INCONSISTENT_DUPLICATES"
            continue
        quantum = Decimal(1).scaleb(-int(decimals))
        if best_value.quantize(quantum) != value.quantize(quantum):
            return None, "INCONSISTENT_DUPLICATES"
    return best_value, None


def values_for(facts, chain, key):
    """Each chain concept the filing tags for this period, consolidated."""
    found = {}
    for concept in chain:
        entries = facts.get(concept, {}).get(key)
        if entries:
            found[concept] = consolidate(entries)
    return found


def pick(facts, chain, key):
    """The first chain concept with a consistent value for this period."""
    for concept, (value, problem) in values_for(facts, chain, key).items():
        if problem is None:
            return concept, value
    return None, None


def read_case(*, text, period, published):
    """What the filing says for each metric, against what was published.

    Args:
        text: The primary document.
        period: ``{"period_start", "period_end"}`` of the pinned fiscal year.
        published: metric id -> published value string, or None.
    """
    facts, unread = parse_facts(text)
    duration = (period["period_start"], period["period_end"], False)
    instant = (None, period["period_end"], True)
    year = str(int(period["period_start"][:4]) - 1)
    prior = sorted({key for concept in REVENUE for key in facts.get(concept, {})
                    if not key[2] and key[0] and key[0].startswith(year)})
    revenue_concept, revenue = pick(facts, REVENUE, duration)
    net_income_concept, net_income = pick(facts, NET_INCOME, duration)
    _, ocf = pick(facts, ["NetCashProvidedByUsedInOperatingActivities"], duration)
    capex_concept, capex = pick(facts, CAPEX, duration)
    _, operating_income = pick(facts, ["OperatingIncomeLoss"], duration)
    operating_route = "OperatingIncomeLoss" if operating_income is not None else None
    crosscheck = None
    if operating_income is None:
        pretax_concept, pretax = pick(facts, PRETAX, duration)
        bridge_concept, bridge = pick(facts, NONOPERATING, duration)
        if pretax is not None and bridge is not None:
            operating_income = pretax - bridge
            operating_route = pretax_concept + " - " + bridge_concept
            _, costs = pick(facts, ["CostsAndExpenses"], duration)
            if costs is not None and revenue is not None:
                crosscheck = {"revenue_less_costs": str(revenue - costs),
                              "reconstructed": str(operating_income),
                              "agrees": (revenue - costs) == operating_income}
                if not crosscheck["agrees"]:
                    operating_income = None
                    operating_route += " (withdrawn by cross-check)"
    interest_concept, interest = pick(facts, INTEREST, duration)
    _, current_assets = pick(facts, ["AssetsCurrent"], instant)
    _, current_liabilities = pick(facts, ["LiabilitiesCurrent"], instant)
    _, cash = pick(facts, ["CashAndCashEquivalentsAtCarryingValue"], instant)
    direct = values_for(facts, DA, duration)
    da_concept, da = pick(facts, DA, duration)
    da_parts = None
    if da is None:
        _, depreciation = pick(facts, ["Depreciation"], duration)
        _, amortisation = pick(facts, ["AmortizationOfIntangibleAssets"], duration)
        if depreciation is not None and amortisation is not None:
            da = depreciation + amortisation
            da_concept = "Depreciation+AmortizationOfIntangibleAssets"
            da_parts = [str(depreciation), str(amortisation)]
    direct_values = {str(value) for value, problem in direct.values() if problem is None}
    prior_revenue = None
    for key in prior:
        _, value = pick(facts, REVENUE, key)
        if value is not None:
            prior_revenue = value
            break
    with localcontext() as context:
        context.prec = 28
        computed = {
            "B01": revenue,
            "B02": ((revenue - prior_revenue) / prior_revenue
                    if revenue is not None and prior_revenue else None),
            "B03": ((operating_income + da) / revenue
                    if None not in (operating_income, da, revenue) and revenue else None),
            "B04": net_income,
            "B05": ocf - capex if None not in (ocf, capex) else None,
            "B07": (operating_income / interest
                    if None not in (operating_income, interest) and interest else None),
            "B08": (current_assets / current_liabilities
                    if None not in (current_assets, current_liabilities)
                    and current_liabilities else None),
            "B09": cash}
    rows = {}
    for metric, value in sorted(computed.items()):
        shown = published.get(metric)
        row = {"read": str(value) if value is not None else None, "published": shown,
               "exact_string_match": (shown is not None and value is not None
                                      and str(value) == shown)}
        if shown is None:
            row["verdict"] = "NO_PUBLISHED_VALUE"
        elif value is None:
            row["verdict"] = "NOT_READ"
        elif metric == "B03" and len(direct_values) > 1:
            row["verdict"] = "DIRECT_CANDIDATES_DISAGREE"
            row["direct_d_and_a_candidates"] = {concept: str(value) for concept, (value, _)
                                                in direct.items()}
        else:
            row["verdict"] = "MATCH" if value == Decimal(shown) else "DIFFERS"
        rows[metric] = row
    later = {}
    for name, chain, chosen in (("revenue", REVENUE, revenue_concept),
                                ("net_income", NET_INCOME, net_income_concept),
                                ("interest", INTEREST, interest_concept)):
        others = {concept: str(value) for concept, (value, problem)
                  in values_for(facts, chain, duration).items()
                  if concept != chosen and problem is None}
        if others:
            later[name] = others
    return {"concepts_used": {"revenue": revenue_concept, "net_income": net_income_concept,
                              "capex": capex_concept, "interest": interest_concept,
                              "d_and_a": da_concept, "d_and_a_parts": da_parts,
                              "operating_income": operating_route,
                              "operating_income_crosscheck": crosscheck,
                              "prior_revenue_context": list(prior[0]) if prior else None},
            "later_chain_concepts_the_filing_also_tags": later,
            "needed_facts_not_read": unread, "metrics": rows}


def _case_input(*, company_id, report_end):
    from vnext.historical_annual_input import prepare_historical_annual_input
    from vnext.normal_period_selection import resolve_period_selection
    selection = resolve_period_selection(repo_root=REPO, company_id=company_id,
                                         report_end=report_end)
    prepared = prepare_historical_annual_input(repo_root=REPO, company_id=company_id,
                                               period_selection=selection)
    return (prepared["original_input"]["table_input"]["source_repo_relative_path"],
            prepared["original_input"]["table_input"]["target_period"])


def main():
    from acceptance_readings import accession_of_document
    from bind_acceptance_readings import identity_for
    from vnext.historical_coverage import select_receipt
    from vnext.historical_run_receipts import collect_run_receipts, index_receipts
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs-root", required=True, type=Path, action="append")
    parser.add_argument("--closure", required=True)
    arguments = parser.parse_args()
    receipts = []
    for root in arguments.runs_root:
        receipts.extend(collect_run_receipts(runs_root=root)["receipts"])
    index = index_receipts(receipts=receipts)
    previous = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    positions = {}
    for company_id, report_end, label in CASES:
        document, period = _case_input(company_id=company_id, report_end=report_end)
        published = {}
        for metric in ("B01", "B02", "B03", "B04", "B05", "B07", "B08", "B09"):
            result = select_receipt(found=index.get((company_id, metric, report_end), []),
                                    closure=arguments.closure)["result"]
            published[metric] = (None if result is None or result.get("value") is None
                                 else str(result["value"]))
        case = read_case(text=(REPO / document).read_text(encoding="utf-8-sig",
                                                          errors="replace"),
                         period=period, published=published)
        accession, _ = accession_of_document(repo_root=REPO, document=document)
        for metric, row in case["metrics"].items():
            if row["published"] is None:
                continue
            identity, refusal = identity_for(
                position={"company_id": company_id, "metric_id": metric,
                          "period_end": report_end, "published": row["published"],
                          "reading_filings": [accession], "reading_window": None,
                          "filings_are_the_whole_set": False},
                index=index, closure=arguments.closure)
            if refusal is not None:
                raise SystemExit("IDENTITY_NOT_RECORDED:" + label + ":" + metric + ":" + refusal)
            identity["established_by"] = "RECORDED_AT_READING_TIME"
            row["checked_identity"] = identity
        positions[label] = {"company_id": company_id, "period_end": report_end,
                            "period": {"period_start": period["period_start"],
                                       "period_end": period["period_end"]},
                            "document": document, **case}
        print(label, {metric: row["verdict"] for metric, row in case["metrics"].items()},
              flush=True)
    owned = {"record_type", "what_this_is", "requirement_closure_hash", "per_position",
             "calls", "result", "reader"}
    body = {key: value for key, value in previous.items() if key not in owned}
    body.update({
        "record_type": previous.get("record_type", "ISSUE_47_CROSS_SOURCE_STATEMENT_READ"),
        "what_this_is": ("eight statement metrics read out of each company's own 10-K by "
                         "tools/read_statement_facts.py, and compared to what the route "
                         "published. The route resolves them from the Company Facts API; "
                         "this walks the filing's primary document."),
        "reader": "tools/read_statement_facts.py",
        "requirement_closure_hash": arguments.closure,
        "per_position": positions, "calls": {"provider": 0, "paid": 0, "sec": 0}})
    verdicts = {}
    for row in positions.values():
        for metric in row["metrics"].values():
            verdicts[metric["verdict"]] = verdicts.get(metric["verdict"], 0) + 1
    body["result"] = dict(sorted(verdicts.items()))
    (REPO / OUT).write_text(json.dumps(body, indent=1, sort_keys=True, ensure_ascii=False)
                            + "\n", encoding="utf-8")
    print(body["result"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
