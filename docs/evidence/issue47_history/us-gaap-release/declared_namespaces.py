"""Which US GAAP release each saved HTML filing declares, from its own bytes.

Usage (from the repository root):
    python3 docs/evidence/issue47_history/us-gaap-release/declared_namespaces.py > declared-namespaces.txt

One line per saved ``*<8 digits>.htm`` document - in the checkout's request
attempts or in the acquisition's export - with where it was read and the
``xmlns:us-gaap`` it declares (None for a document without inline XBRL). The
FASB names its releases through 2021 with the date after the year
(``us-gaap/2021-01-31``) and from 2022 with the year alone; this is how the
positions ``positions.txt`` lists were chosen: every FY2021 annual report of
the ten companies declares the dated form, every later one the year alone.
Zero calls.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
from acceptance_readings import EXPORT_MEMBER_PREFIX, _export_member_bytes, _export_members  # noqa: E402

DECLARED = re.compile(rb'xmlns:us-gaap="([^"]+)"')


def main():
    found = {}
    for path in REPO.glob("evidence/request_attempts/*/*/*.htm"):
        found.setdefault(path.name, ("checkout", path))
    members = _export_members(REPO)
    for member in members:
        if member.startswith(EXPORT_MEMBER_PREFIX + "evidence/") and member.endswith(".htm"):
            found.setdefault(member.rsplit("/", 1)[1], ("export", member))
    for name in sorted(found):
        if not re.search(r"\d{8}\.htm$", name):
            continue
        where, ref = found[name]
        raw = (ref.read_bytes() if where == "checkout"
               else _export_member_bytes(repo_root=REPO, member=ref, members=members))
        declared = DECLARED.search(raw)
        print(name, where, declared.group(1).decode() if declared else None)


if __name__ == "__main__":
    main()
