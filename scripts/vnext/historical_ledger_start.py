"""A ledger's one start, published where the host that holds the ledger cannot take it along.

Purpose: Issue #47's SEC acquisition and its model calls run in the executor's
cloud container, by the owner's decision (plan revision 6). A container is
reclaimed with its disk, and a cumulative cap is only as good as its count's
durability: a ledger that vanished with the container would let the same
approval be spent again from an empty one. So each ledger is started once - a
local record beside its root, carrying a random number, and a marker comment on
issue 47 carrying the record without that number and a digest of the whole -
and the live path refuses unless the earliest marker for the approval is
unedited, was posted on this issue by the repository owner's account and
matches the local record. A lost container meets a marker it cannot match, and
cannot make one: the number is not published (an independent review copied a
marker that carried the whole record back beside an empty root, and the start
matched). Resuming is the owner's decision.

The live path also refuses a ledger that is behind the branch's export of it:
the export binds its claim log by digest and size, and the local log must
begin with exactly those bytes. A host that kept its start record but lost or
reset its ledger, or restored an older export, would otherwise count from
less than was spent.

What the marker does not guard is a deleted marker comment. The owner's account
can delete it, and so can the executor, which acts on GitHub as that account
(measured: the container's GitHub API calls carry the owner's account through
the Claude GitHub App), and the comments API shows no trace of a deleted
comment. The second guard is the export pushed to the branch, which cannot be
removed without a commit that shows it: a start is refused once the checkout
carries an export of a ledger the approval granted. Before the first export is
pushed, a deleted marker and a lost container leave no guard at all. And none
of this is a boundary against the executor itself, which holds the host, the
reader and the provider key: it guards against accidents and keeps what was
spent auditable on the branch.

The SEC ledger and the model ledger each start through this module with their
own record type, refusal prefix and export index, so one's marker can never
stand in for the other's. It imports neither ledger's module: the process that
sends model requests may load only the code its authorization binds, and this
file is bound by the SEC wiring receipt and by the model call path alike.

Call relationships: ``historical_sec_session`` and ``historical_model_calls``
call it with their ``LedgerKind``; nothing here reads GitHub except through the
reader the caller passes.
"""
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical_json_bytes, sha256_bytes, strict_json_file, strict_json_loads

MARKER_PAGES = 100
_PAGE_SIZE = 100


@dataclass(frozen=True)
class LedgerKind:
    """What makes one ledger's start its own.

    ``record_type`` is written into the record and checked in every marker;
    ``prefix`` begins every refusal; ``error`` is the exception the owning
    module raises; ``ledger_paths`` names the files beside a root whose
    presence means a ledger is already there; ``export_index`` gives, for an
    allowance, the repository-relative path of that approval's export index;
    ``export_claims`` gives, for an export index, the binding (``sha256`` and
    ``size``) of the claim log it carries; ``title`` opens the marker comment;
    ``owner_id`` is the numeric account a marker must come from.
    """
    record_type: str
    prefix: str
    title: str
    error: type
    ledger_paths: object
    export_index: object
    export_claims: object
    repository: str
    issue_number: int
    requirement_id: str
    owner_id: int


def _need(kind, condition, reason):
    if not condition:
        raise kind.error(kind.prefix + "_" + reason)


def start_record_path(root):
    """Where the local half of a ledger's start lives: beside the root, with the anchor."""
    root = Path(root)
    return root.parent / ("." + root.name + ".start.json")


def marker_view(record):
    """What a marker publishes: the start record without its random number, and a digest of the whole.

    The local record stays the only place the number is, so the digest can be
    checked against a record but not turned back into one.
    """
    view = {key: value for key, value in record.items() if key != "instance_nonce"}
    view["start_record_sha256"] = sha256_bytes(content=canonical_json_bytes(value=record))
    return view


def marker_record(kind, body):
    """The start record in a comment's first fenced json block, or None."""
    text = body.replace("\r\n", "\n")
    opening = text.find("```json\n")
    if opening < 0:
        return None
    closing = text.find("\n```", opening + len("```json\n"))
    if closing < 0:
        return None
    try:
        record = strict_json_loads(text=text[opening + len("```json\n"):closing])
    except ValueError:
        return None
    return record if type(record) is dict and record.get("record_type") == kind.record_type else None


def start_markers(kind, *, allowance, reader):
    """This approval's start markers on the issue, oldest first.

    Only comments on this issue from the repository owner's account count: the
    issue is public, and a stranger's comment must neither block a start nor
    stand in for one. The comment's own issue and account are checked, not
    only the page it came from.
    """
    issue_api = ("https://api.github.com/repos/" + kind.repository + "/issues/"
                 + str(kind.issue_number))
    markers = []
    for page in range(1, MARKER_PAGES + 1):
        comments = reader("repos/" + kind.repository + "/issues/" + str(kind.issue_number)
                          + "/comments?per_page=" + str(_PAGE_SIZE) + "&page=" + str(page))
        _need(kind, type(comments) is list and all(type(item) is dict for item in comments),
              "START_MARKERS_UNREADABLE")
        for comment in comments:
            record = marker_record(kind, str(comment.get("body") or ""))
            user = comment.get("user")
            if (record is not None and comment.get("author_association") == "OWNER"
                    and comment.get("issue_url") == issue_api and type(user) is dict
                    and user.get("id") == kind.owner_id and user.get("type") == "User"
                    and record.get("delegation_body_sha256")
                    == allowance["delegation_body_sha256"]):
                markers.append({"comment": comment, "record": record})
        if len(comments) < _PAGE_SIZE:
            break
    else:
        _need(kind, False, "START_MARKERS_BEYOND_THE_PAGES_READ")
    return sorted(markers, key=lambda item: (str(item["comment"].get("created_at")),
                                             int(item["comment"].get("id") or 0)))


def marker_comment_body(kind, record):
    """The comment the executor posts; its first json block is the record's public view."""
    return (kind.title + " start marker, posted by the executor. The live path reads this "
            "issue's comments and refuses unless the earliest marker for this approval is "
            "unedited, was posted on this issue by the repository owner's account and matches "
            "the local start record beside the ledger, whose random number is not published "
            "here.\n\n```json\n"
            + json.dumps(marker_view(record), indent=1, sort_keys=True) + "\n```\n")


def exported_here(kind, *, allowance, checkout):
    """Whether ``checkout`` carries an export of a ledger this approval granted.

    An index that cannot be read counts as one: an export nobody can read is
    not evidence that nothing was spent. An export of a recorded test ledger
    names no approval and does not count.
    """
    path = Path(checkout) / kind.export_index(allowance)
    if not path.exists() and not path.is_symlink():
        return False
    try:
        index = strict_json_file(path=path)
    except (OSError, ValueError):
        return True
    if type(index) is not dict:
        return True
    approval = index.get("approval")
    return approval is not None and (type(approval) is not dict or approval.get(
        "delegation_body_sha256") == allowance["delegation_body_sha256"])


def _host_facts(reader):
    """How this host reads GitHub, recorded at the start: the reader, the HTTPS proxy, the CA bundle.

    Facts, not guarantees: in the executor's container the executor controls
    all three, so the record makes the path auditable, not trustworthy (an
    independent review showed a stand-in ``gh`` on PATH answering as GitHub).
    """
    from urllib.parse import urlsplit
    from urllib.request import getproxies
    proxy = getproxies().get("https")
    if proxy:
        parts = urlsplit(proxy)
        proxy = parts.scheme + "://" + (parts.hostname or "") + (":" + str(parts.port) if parts.port else "")
    bundle = os.environ.get("SSL_CERT_FILE")
    return {"github_reader": str(getattr(reader, "__qualname__", type(reader).__name__)),
            "https_proxy": proxy or None,
            "ca_bundle_sha256": (sha256_bytes(content=Path(bundle).read_bytes())
                                 if bundle and Path(bundle).is_file() else None)}


def start_ledger(kind, *, allowance, reader, checkout, now=None):
    """Start this approval's ledger here, once: write the local record, return the marker.

    Refuses if a start record is already here, if anything of a ledger is
    already at the root, if the checkout carries an export of a ledger this
    approval granted, or if this approval already has a marker on the issue -
    started elsewhere, or here and lost. Posting the marker is the caller's:
    until it is on GitHub the live path refuses.
    """
    from .invocation_control import _exclusive_write_json
    root = Path(allowance["budget_root"])
    path = start_record_path(root)
    _need(kind, not path.exists() and not path.is_symlink(),
          "ALREADY_STARTED_HERE:" + str(path))
    _need(kind, not (root.exists() and any(root.iterdir()))
          and not any(Path(other).exists() or Path(other).is_symlink()
                      for other in kind.ledger_paths(root)),
          "EXISTS_WITHOUT_A_START:" + str(root))
    _need(kind, not exported_here(kind, allowance=allowance, checkout=checkout),
          "ALREADY_EXPORTED:this checkout carries an export of this approval's ledger; "
          "restore it and ask the owner instead of starting again")
    _need(kind, not start_markers(kind, allowance=allowance, reader=reader),
          "STARTED_ELSEWHERE:this approval already has a start marker on issue "
          + str(kind.issue_number))
    record = {"record_type": kind.record_type, "schema_version": 1,
              "requirement_id": kind.requirement_id,
              "delegation_url": allowance["delegation_url"],
              "delegation_body_sha256": allowance["delegation_body_sha256"],
              "budget_root": allowance["budget_root"],
              "instance_nonce": secrets.token_hex(16),
              "created_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "host": _host_facts(reader)}
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _exclusive_write_json(path=path, value=record)
    # The random number stays in the local file: what is returned, printed by
    # the runners and posted is the public view.
    return {"status": "LEDGER_START_WRITTEN", "start_record": str(path),
            "record": marker_view(record),
            "marker_comment_body": marker_comment_body(kind, record), "calls": [0, 0, 0]}


def require_published_start(kind, *, allowance, reader, checkout):
    """The ledger was started here, its start is on GitHub and it is not behind its export."""
    path = start_record_path(Path(allowance["budget_root"]))
    markers = start_markers(kind, allowance=allowance, reader=reader)
    if not path.exists() and not path.is_symlink():
        _need(kind, not markers, "STARTED_ELSEWHERE:"
              + str(markers[0]["comment"].get("html_url") if markers else ""))
        _need(kind, False, "NOT_STARTED:run 'start' and post its marker on issue "
              + str(kind.issue_number))
    _need(kind, path.is_file() and not path.is_symlink(), "START_RECORD_UNSAFE:" + str(path))
    record = strict_json_file(path=path)
    _need(kind, record.get("record_type") == kind.record_type
          and record.get("requirement_id") == kind.requirement_id
          and all(record.get(key) == allowance[key]
                  for key in ("delegation_url", "delegation_body_sha256", "budget_root")),
          "START_RECORD_IS_FOR_ANOTHER_APPROVAL:" + str(path))
    _need(kind, bool(markers), "START_NOT_PUBLISHED:post the marker comment on issue "
          + str(kind.issue_number))
    first = markers[0]
    comment = first["comment"]
    _need(kind, type(comment.get("created_at")) is str and comment.get("created_at")
          and comment.get("created_at") == comment.get("updated_at"),
          "START_MARKER_EDITED:" + str(comment.get("html_url")))
    _need(kind, first["record"] == marker_view(record),
          "STARTED_ELSEWHERE:" + str(comment.get("html_url")))
    require_not_behind_export(kind, allowance=allowance, checkout=checkout)
    return {"start_record": record, "marker_url": comment.get("html_url")}


def require_not_behind_export(kind, *, allowance, checkout):
    """This host's ledger holds at least what the checkout's export of it says was claimed.

    The export binds the claim log it carries by digest and size; the local
    log must begin with exactly those bytes. Nothing to check where the
    checkout carries no export of this approval's ledger; an export that
    cannot be read is a refusal, as it is for a start.
    """
    if not exported_here(kind, allowance=allowance, checkout=checkout):
        return None
    path = Path(checkout) / kind.export_index(allowance)
    try:
        binding = kind.export_claims(strict_json_file(path=path))
    except (OSError, ValueError, KeyError, TypeError):
        binding = None
    _need(kind, type(binding) is dict and type(binding.get("size")) is int
          and type(binding.get("sha256")) is str, "EXPORT_UNREADABLE:" + str(path))
    log = Path(allowance["budget_root"]) / "claims.jsonl"
    held = log.read_bytes() if log.is_file() and not log.is_symlink() else b""
    _need(kind, len(held) >= binding["size"]
          and sha256_bytes(content=held[:binding["size"]]) == binding["sha256"],
          "BEHIND_ITS_EXPORT:the checkout's export of this approval's ledger claims more than "
          + str(log) + " holds; this is not the ledger that was exported")
    return binding
