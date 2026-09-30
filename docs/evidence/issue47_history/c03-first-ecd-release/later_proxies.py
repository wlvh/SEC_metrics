"""Every saved proxy's PEO total, compared across the proxies that report the same year.

A pay-versus-performance table reports up to five years, so a year's PEO total
is reported first in the proxy after that year and again in the following
proxies. The historical C03 route reads the first. This lists every saved
proxy (checkout and the acquisition's export), every PeoTotalCompAmt in it by
period and person, and every year for which two proxies report different
amounts. Reads saved bytes only; zero calls. Run from the repository root.
"""
import hashlib
import json
import re
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT), str(ROOT / "tools")]
from tools import acceptance_readings as readings  # noqa: E402
from tools.read_governance_facts import contexts_of, peo_totals  # noqa: E402

OUT = Path(__file__).with_name("later-proxies.json")


def _documents():
    found = []
    for path in sorted(ROOT.glob("evidence/accession_materials/*/*.htm")) + sorted(
            ROOT.glob("evidence/request_attempts/*/*/*.htm")):
        data = path.read_bytes()
        if b"PeoTotalCompAmt" in data:
            found.append((str(path.relative_to(ROOT)), data))
    members = readings._export_members(ROOT)
    by_archive = defaultdict(list)
    for member, (archive, _) in members.items():
        if member.endswith(".htm"):
            by_archive[archive].append(member)
    for archive, names in sorted(by_archive.items()):
        with tarfile.open(ROOT / readings.EXPORT / archive) as opened:
            for name in sorted(names):
                data = opened.extractfile(name).read()
                if b"PeoTotalCompAmt" in data:
                    found.append((name, data))
    return found


def main():
    seen, reports = {}, defaultdict(list)
    for location, data in _documents():
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            continue
        seen[digest] = location
        text = data.decode("utf-8", "replace")
        cik = re.search(r'name="dei:EntityCentralIndexKey"[^>]*>(?:<[^>]+>)*\s*([0-9]+)', text)
        release = sorted(set(re.findall(r"xbrl\.sec\.gov/ecd/([0-9a-z-]+)", text)))
        for total in peo_totals(text, contexts_of(text)):
            entry = {"document": location.rsplit("/", 1)[1], "sha256": digest, "ecd_release": release,
                     "value": str(total["value"]), "placeholder": total["placeholder"]}
            key = (str(int(cik.group(1))) if cik else None, *total["key"], tuple(total["members"]))
            if entry not in reports[key]:
                reports[key].append(entry)
    rows = [{"cik": key[0], "period": [key[1], key[2]], "members": list(key[3]), "reports": value}
            for key, value in sorted(reports.items(), key=lambda item: tuple(map(str, item[0])))]
    by_several = [row for row in rows if len({r["sha256"] for r in row["reports"]}) > 1]
    differing = [row for row in by_several
                 if len({r["value"] for r in row["reports"] if not r["placeholder"]}) > 1]
    body = {"record_type": "ISSUE47_C03_LATER_PROXY_SCAN", "proxies_read": len(seen),
            "person_years": len(rows), "person_years_reported_by_two_or_more_proxies": len(by_several),
            "person_years_with_different_amounts": differing, "calls": {"sec": 0, "provider": 0}}
    OUT.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: body[key] for key in ("proxies_read", "person_years",
                                                 "person_years_reported_by_two_or_more_proxies")}),
          len(differing))


if __name__ == "__main__":
    main()
