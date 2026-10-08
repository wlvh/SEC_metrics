#!/usr/bin/env python3
"""Drive Issue #47's SEC acquisition company by company, exporting and pushing after every chunk.

Why a driver, and why chunks. The ledger lives in the executor's container,
and on 2026-09-29 a snapshot restore took the container's disk while one
company's acquisition was running: everything after the last pushed export was
lost, and the resume had to charge that company's whole due set as a reserve
(``historical_sec_resume``). An export pushed after every ``--chunk`` captures
keeps what a future loss can take - the sources and the count - to one chunk's
worth of work since the last push.

Per chunk: ``acquire --company C --max-captures N``; ``export``; commit the
export with the counts in the message; push with retries. A stop other than
the chunk limit (the cap, an unknown outcome, a fair-access refusal, an error)
ends the drive after the export of what was captured. Every step is appended
to the log given as ``--log``, which should live where the branch can carry it
or where a loss would not take it with the ledger.

Zero model calls. The requests are the acquisition's own, through
``tools/vnext_historical_sec.py``; this script sends none itself. Run from the
repository root:
    python3 docs/evidence/issue47_history/acquisition-wiring/acquire_driver.py \\
        --log <file> --chunk 40 COMPANY [COMPANY ...]
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CLI = ["python3", "tools/vnext_historical_sec.py"]
EXPORT_PATHS = ["config/issue47_historical_calls_v1.json",
                "docs/evidence/issue47_history/acquisition-wiring/approval-comment.json",
                "evidence/issue47_acquired"]
TRAILER = ("\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_01Q173f3bBEKCDof8D9CzG3n\n")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(command, timeout=None):
    return subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=timeout)


def _json_tail(text):
    """The CLI's result object: the JSON document it printed last on stdout."""
    start = text.find("{")
    return json.loads(text[start:]) if start >= 0 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--chunk", type=int, default=40)
    parser.add_argument("--branch", default="task/sec-history-five-year")
    # A background task is killed at its time limit, and a kill during a
    # capture leaves a claimed slot without a terminal - an unknown outcome
    # the ledger then stops on. Past this many minutes no new chunk starts;
    # every chunk already ends exported and pushed. (On 2026-09-30 the drive
    # was killed at the limit while planning, with no request in flight.)
    parser.add_argument("--stop-after-minutes", type=float, default=None)
    parser.add_argument("companies", nargs="+")
    args = parser.parse_args()
    started = time.monotonic()

    def log(*parts):
        with args.log.open("a", encoding="utf-8") as handle:
            handle.write(_now() + " " + " ".join(str(part) for part in parts) + "\n")

    for company in args.companies:
        while True:
            if (args.stop_after_minutes is not None
                    and time.monotonic() - started > 60 * args.stop_after_minutes):
                log("STOP_FOR_TIME", "no new chunk after", args.stop_after_minutes,
                    "minutes; next company", company)
                return 4
            log("ACQUIRE", company, "max-captures", args.chunk)
            acquired = _run(CLI + ["acquire", "--company", company,
                                   "--max-captures", str(args.chunk)])
            result = None
            try:
                result = _json_tail(acquired.stdout)
            except ValueError:
                pass
            log("ACQUIRE_EXIT", acquired.returncode,
                json.dumps(result, sort_keys=True) if result else acquired.stderr[-2000:])
            if acquired.returncode not in (0, 3) or result is None:
                log("STOP", "acquire did not report a result")
                return 2
            item = result["companies"].get(company, {})
            stop = result.get("stop")
            chunk_only = stop is not None and stop.get("reason") == "MAX_CAPTURES_FOR_THIS_INVOCATION"
            # Every invocation is exported, not only one that captured: an
            # invocation cut by a restart after some captures leaves them in the
            # ledger unexported, and the next invocation may find nothing left
            # to capture (on 2026-09-30 the last 24 JPMorgan captures stayed out
            # of the branch that way). An export that changes nothing commits
            # nothing.
            exported = _run(CLI + ["export"])
            log("EXPORT_EXIT", exported.returncode, exported.stdout.strip()[-1500:])
            if exported.returncode != 0:
                log("STOP", "export failed", exported.stderr[-2000:])
                return 2
            _run(["git", "add"] + EXPORT_PATHS)
            changed = _run(["git", "diff", "--cached", "--quiet", "--"] + EXPORT_PATHS).returncode != 0
            if changed:
                message = ("Acquire #47 SEC sources: %s, %d captured (%d failed), cumulative %s of %s"
                           % (company, item["captured"], item["failed"],
                              result["cumulative_calls"], result["limits"]))
                body = ("acquire exit %d, status %s, stop %s.\npasses %s, outside the grants %s, "
                        "already claimed %s, error %s.\nThe export carries the ledger and every "
                        "acquired source so far (evidence/issue47_acquired/). Zero model calls."
                        % (acquired.returncode, result["status"],
                           json.dumps(stop, sort_keys=True), item.get("passes"),
                           item.get("outside_grants"), item.get("already_claimed"),
                           json.dumps(item.get("error"))))
                committed = _run(["git", "commit", "-m", message + "\n\n" + body + TRAILER])
                log("COMMIT_EXIT", committed.returncode, committed.stdout.strip()[-300:])
                if committed.returncode != 0:
                    log("STOP", "commit failed", committed.stderr[-1500:])
                    return 2
                for wait in (0, 2, 4, 8, 16):
                    time.sleep(wait)
                    pushed = _run(["git", "push", "-u", "origin", args.branch], timeout=600)
                    if pushed.returncode == 0:
                        head = _run(["git", "rev-parse", "--short=8", "HEAD"]).stdout.strip()
                        log("PUSHED", head)
                        break
                    log("PUSH_RETRY", pushed.stderr[-500:])
                else:
                    log("STOP", "push failed five times")
                    return 2
            if stop is not None and not chunk_only:
                log("STOP", json.dumps(stop, sort_keys=True))
                return 3
            if not chunk_only:
                break
    log("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
