# Frozen R4 release entrypoints — future PR-C only

These commands describe implemented entrypoints, not permission to execute
them in PR-B. PR30 stays Draft; v2 activation, merge, model execution and real
publication remain unauthorized. There is no CLI recorded/rehearsal switch.

The existing qualification CLI owns `draft`, `plan`, `execute`, and `replay`.
Replay now persists its append-only content-addressed receipt under
`artifacts/vnext/qualification/r4_scoped/replays/`; it never calls a provider.
The offline `SCOPED_READER_PLAN` cannot replace a pending-live plan.

## Receipt sequence

After independent review and PR-B merge, the separate v2 transition activation
receipt is recorded at `docs/evidence/issue_28_v2_transition_activation.json`.
PR-C then uses a pending-live plan, a real exact-head live-owner comment, twelve
new invocation terminals and three structured terminals. Their independent
replay must return `EXACT_PLAN_LIVE_QUALIFICATION_ONLY` before stage can proceed.
Ordinary FROZEN children and recorded summaries are not publication authority.

The following placeholders must be replaced with actually validated IDs;
none exists as a live R4 grant in this PR:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_r4_qualification.py replay --plan-id <pending-plan-id>
PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_r4_release.py stage --plan-id <pending-plan-id> --replay-id <independent-replay-id> --implementation-merge <approved-PR-B-merge>
PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_r4_release.py validate --publication-id <R4-publication-id>
PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_r4_release.py read-back --publication-id <R4-publication-id>
PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_r4_release.py publish --publication-id <R4-publication-id> --owner-comment-url <exact-release-owner-comment>
PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_r4_release.py active-terminal --publication-id <R4-publication-id>
PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_r4_release.py rollback-to-R3 --publication-id <R4-publication-id> --owner-comment-url <exact-release-owner-comment>
PYTHONDONTWRITEBYTECODE=1 python3 tools/vnext_r4_release.py restore-R4 --publication-id <R4-publication-id> --owner-comment-url <exact-release-owner-comment>
```

The repository function `expected_release_owner_approval` defines the future
`AUTHORIZE_R4_RELEASE_EXACT_HEAD` content: exact head/tree, Requirement closure,
publication/release-receipt/predecessor IDs, explicit publish/rollback/restore/
mirror-recovery operations and no provider/paid/SEC grant. This is separate
from `AUTHORIZE_R4_LIVE_EXACT_HEAD`, whose scope explicitly excludes publication.
Each mutating process fetches the genuine unedited repository-owner comment
and verifies the current open PR/head. It also verifies the earlier transition
and live-owner provenance; serialized self-signed receipts cannot create that
private capability. This preflight is GitHub governance traffic, not provider
or SEC egress, and is not performed in PR-B.

`recover-mirrors` uses the same owner-comment arguments and native switch-intent
recovery. Ordinary rollback/restore refuses mirror drift; explicitly authorized
recovery can repair a genuine interrupted transaction. A changed head requires
a new owner comment; a changed production file requires a new implementation
review, not a PR-C patch or re-sign of v1.

The standard primary validation manifest and report remain consumable through
the existing read-only report interface. New R4 metadata lives in typed
receipts. The immutable bundle includes its own original R3 authority root,
so a successful rollback does not alter the qualification predecessor used
by future read-back. PR-C requires data/receipt generation, not new Python.
