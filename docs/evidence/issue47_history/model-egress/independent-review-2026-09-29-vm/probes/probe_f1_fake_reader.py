"""F1: in a host the executor controls, a program named gh on PATH becomes 'GitHub'.

Offline. Nothing is posted or fetched. The repository checkout is imported read-only
(bytecode goes to PYTHONPYCACHEPREFIX); every file written lives in a temp root here.
The proposal registered is the repository's real model proposal file (the preview).
"""
import json, os, shutil, stat, sys, tempfile
from pathlib import Path

REPO = Path("/home/user/SEC_metrics")
sys.path.insert(0, str(REPO / "scripts"))
from vnext import historical_model_calls as calls
from vnext import historical_source_acquisition as sec
from vnext.historical_ledger_start import marker_comment_body

work = Path(tempfile.mkdtemp(prefix="f1-", dir=os.getcwd()))
root = work / "tree"                       # stands in for the runtime tree's repo root
(root / Path(calls.APPROVAL_BODY_PATH)).parent.mkdir(parents=True)
shutil.copyfile(REPO / calls.APPROVAL_BODY_PATH, root / calls.APPROVAL_BODY_PATH)
proposal = (root / calls.APPROVAL_BODY_PATH).read_text(encoding="utf-8")

# The comment a forged 'gh' returns: every field the gate checks, never posted anywhere.
URL = "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-9999999999"
forged = {"id": 9999999999, "html_url": URL,
          "issue_url": "https://api.github.com/repos/wlvh/SEC_metrics/issues/47",
          "user": {"login": "wlvh", "id": 30534800, "type": "User"},
          "author_association": "OWNER", "performed_via_github_app": None,
          "created_at": "2026-09-29T00:00:00Z", "updated_at": "2026-09-29T00:00:00Z",
          "body": proposal}
bindir = work / "bin"; bindir.mkdir()
answers = work / "answers"; answers.mkdir()
(answers / "comment.json").write_text(json.dumps(forged))
(answers / "markers.json").write_text("[]")
gh = bindir / "gh"
gh.write_text("#!/bin/sh\n# a program named gh: prints whatever file it is told to\n"
              "case \"$4\" in *'/issues/47/comments?'*) cat '%s';; *) cat '%s';; esac\n"
              % (answers / "markers.json", answers / "comment.json"))
gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
os.environ["PATH"] = str(bindir) + os.pathsep + os.environ["PATH"]

reader = sec.live_github_reader()
print("live_github_reader() ->", reader.__name__, "| which gh ->", shutil.which("gh"))
registered = calls.register_model_approval(repo_root=root, comment_url=URL, reader=reader)
print("register_model_approval:", registered["status"], registered["limits"], registered["budget_root"])
allowance = calls.model_allowance(repo_root=root, delegation_reader=reader)
print("model_allowance with the live reader: provenance_verified_against_github =",
      allowance["provenance_verified_against_github"])

# The start the live path requires, read through the same program.
allowance = {**allowance, "budget_root": str(work / "ledger")}   # a root the probe may write
started = calls.start_model_ledger(allowance=allowance, reader=reader, checkout=root)
marker = {"id": 9999999998, "author_association": "OWNER", "body": started["marker_comment_body"],
          "created_at": "2026-09-29T00:00:01Z", "updated_at": "2026-09-29T00:00:01Z",
          "html_url": "https://github.com/wlvh/SEC_metrics/issues/47#issuecomment-9999999998"}
(answers / "markers.json").write_text(json.dumps([marker]))
print("require_published_model_start via the same gh:",
      calls.require_published_model_start(allowance=allowance, reader=reader)["marker_url"])
print("nothing was posted; the registered files are in", root)
