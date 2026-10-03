"""A saved filing's bytes and the URL it was fetched from, found by its file name.

Test cases that ask a route about a real filing take its bytes from where the
repository keeps them: the checkout's request attempts, or else the SEC
acquisition's export, whose archives carry a file with its headers and whose
index names each member's digest (``tools.acceptance_readings``). A file saved
in neither place skips the case that asked for it, with the name.
"""
import json
import unittest

from tests.vnext.common import REPO_ROOT as ROOT
from tools.acceptance_readings import (EXPORT_MEMBER_PREFIX, _export_member_bytes,
                                       _export_members)


def saved_filing(file_name):
    """The saved document's bytes and URL, from the checkout or the export."""
    found = sorted(ROOT.glob("evidence/request_attempts/*/*/" + file_name))
    if found:
        path = found[0]
        headers = sorted(path.parent.glob(file_name + ".*.headers.json"))
        record = json.loads(headers[0].read_text(encoding="utf-8"))
        return path.read_bytes(), record.get("url") or record.get("source_url")
    members = _export_members(ROOT)
    named = sorted(m for m in members if m.startswith(EXPORT_MEMBER_PREFIX + "evidence/")
                   and m.endswith("/" + file_name))
    if not named:
        raise unittest.SkipTest("filing not saved: " + file_name)
    member = named[0]
    headers = sorted(m for m in members if m.startswith(member + ".") and m.endswith(".headers.json"))
    record = json.loads(_export_member_bytes(repo_root=ROOT, member=headers[0], members=members))
    return (_export_member_bytes(repo_root=ROOT, member=member, members=members),
            record.get("url") or record.get("source_url"))
