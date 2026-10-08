"""Every D&A-family fact each B03 filing tags for its fiscal year, with the words beside it.

B03's approved chain takes the first of DepreciationDepletionAndAmortization,
DepreciationAmortizationAndAccretionNet and DepreciationAndAmortization that the
filing carries. A concept name is a clue, not proof of what the number covers,
so this lists, for each filing the cross-source reading opened, every
undimensioned fact of the family in the fiscal-year duration context, with its
value, scale, decimals and the text immediately before it - enough to see
whether the fact the chain takes is the filing's total D&A or a narrower one.
Reads saved bytes only; zero network calls.
"""
import html
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FAMILY = ("DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
          "DepreciationAndAmortization", "Depreciation", "AmortizationOfIntangibleAssets",
          "DepreciationNonproduction", "AmortizationOfIntangibleAssetsAndDepreciation",
          "OperatingLeaseRightOfUseAssetAmortizationExpense")
FACT = re.compile(r"<ix:nonFraction\b([^>]*)>(.*?)</ix:nonFraction>", re.S | re.I)
ATTR = re.compile(r'(\w[\w:.-]*)="([^"]*)"')
CONTEXT = re.compile(r"<xbrli:context\b[^>]*\bid=\"([^\"]+)\"[^>]*>(.*?)</xbrli:context>", re.S)


def _contexts(raw):
    out = {}
    for cid, body in CONTEXT.findall(raw):
        start = re.search(r"<xbrli:startDate>([^<]+)<", body)
        end = re.search(r"<xbrli:endDate>([^<]+)<", body)
        out[cid] = {"start": start.group(1).strip() if start else None,
                    "end": end.group(1).strip() if end else None,
                    "dimensioned": "xbrldi:" in body}
    return out


def _text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def census(*, document, period_start, period_end):
    raw = (REPO / document).read_text(encoding="utf-8")
    contexts = _contexts(raw)
    rows = []
    for match in FACT.finditer(raw):
        attrs = dict(ATTR.findall(match.group(1)))
        name = attrs.get("name", "")
        local = name.split(":")[-1]
        if not name.startswith("us-gaap:") or local not in FAMILY:
            continue
        context = contexts.get(attrs.get("contextRef"))
        if (context is None or context["dimensioned"] or context["start"] != period_start
                or context["end"] != period_end):
            continue
        shown = _text(match.group(2))
        value = Decimal(shown.replace(",", "") or "0") * (Decimal(10) ** int(attrs.get("scale", "0")))
        if attrs.get("sign") == "-":
            value = -value
        rows.append({"concept": local, "id": attrs.get("id"), "value": str(value),
                     "decimals": attrs.get("decimals"), "scale": attrs.get("scale"),
                     "text_before": _text(raw[max(0, match.start() - 1500):match.start()])[-220:]})
    return rows


if __name__ == "__main__":
    reading = json.loads((REPO / "docs/evidence/issue47_history/content-acceptance/"
                          "cross-source-read.json").read_text(encoding="utf-8"))["per_position"]
    out = {}
    for label, case in sorted(reading.items()):
        if "error" in case or "B03" not in case["metrics"]:
            continue
        identity = case["metrics"]["B03"].get("checked_identity") or {}
        start = identity.get("period_start")
        end = identity.get("period_end") or case["period_end"]
        if start is None:
            continue
        out[label] = {"document": case["document"], "period": [start, end],
                      "facts": census(document=case["document"], period_start=start,
                                      period_end=end)}
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
