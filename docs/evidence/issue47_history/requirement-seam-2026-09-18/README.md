# What registering a historical Requirement actually costs

Issue #47 comment #2 said a native historical Run was blocked on a decision, and
offered four options with a recommendation. The reasoning behind that comment
was read off the code rather than measured. This directory measures it, and the
result changes the recommendation.

Regenerate with (the data root is any installed historical package; the work
directory must not exist):

```
python3 tools/vnext_requirement_seam.py \
  --data-root <installed package> --work <fresh external dir> \
  --binding-id <binding> --company-id <company> --metric-id <metric> \
  --output docs/evidence/issue47_history/requirement-seam-2026-09-18/seam-measurement.json
```

It copies the package, edits the copy, and runs probes in separate processes. It
writes nothing into the development checkout, nothing into Issue #28's
workspace, creates no Run, and makes no SEC or model request.

## Two byte checks, and they are not the same check

This is where the original reasoning went wrong. A Requirement binds bytes twice
and the two checks run in different places:

* `new_rule_files` is verified inside `load_profile_requirement_snapshot`,
  against the data root **and** the installed code root. Breaking it breaks
  installation itself.
* `execution_authority.files` is verified by `validate_execution_authority`,
  which runs **only** inside `load_run_requirement_snapshot`. Breaking it breaks
  loading or creating a Run, and nothing else.

Measured membership for the files a historical Requirement has to touch:

| file | issue_28_v13 | issue_28_v14 |
| --- | --- | --- |
| `scripts/vnext/requirement_profile.py` | authority only | authority only |
| `scripts/vnext/run_store.py` | authority only | authority only |
| `scripts/vnext/normal_run_v3.py` | rule + authority | authority only |
| `scripts/vnext/requirements.py` | authority only | authority only |
| `scripts/vnext/capacity_run.py` | — | rule + authority |

Neither seam file is in any rule set. That alone is why "this breaks the current
production path" was too strong.

## The seam the repository already built

Registering a further generation and a further Run branch is not new work whose
shape has to be invented. `PROFILE_ENGINES` already carries one generation as a
module path string, imported only when a snapshot asks for it, with the reason
written next to it: a retained runtime need not import an engine absent from its
own execution file set. `run_store` already dispatches Run authority validation
on the Run's own `requirement_id`, with an `issue_28_v14` branch into
`capacity_run`, and `normal_run_v3.replay_case` does the same.

So the historical seam is one engine entry plus one `elif`, in the same two
places, in the same shape. The experiment applies exactly that.

## The measurement

The same installed package, read by its own runtime and by the changed runtime:

| probe | its own runtime | the changed runtime |
| --- | --- | --- |
| `load_requirement_snapshot:issue_28_v13` | OK | OK |
| `load_run_requirement_snapshot:issue_28_v13` | OK | **OK** |
| `replay_historical_inputs` | OK | **OK** |

An already-installed package is not affected by the change at all. The reason is
concrete: an installed data root carries its own copies of the 360 authority
files, and `validate_execution_authority(repo_root=data_root)` checks those
copies, not the checkout's.

What does break is visible in the other configuration, where the changed bytes
are the data root's own:

```
load_run_requirement_snapshot:issue_28_v13   RequirementError: Run explicit Requirement identity differs
```

That is precisely the state of a **newly installed** package after the change:
installation copies the live `requirement_profile.py` and `run_store.py` in, and
they no longer match what `issue_28_v13`'s manifest records.

## So the decision is smaller, and it is not this Issue's

Restated with the measurement in hand:

* every package installed **before** the change keeps loading, keeps validating
  its Run Requirement, and keeps replaying;
* every package installed **after** the change cannot load a Run that declares
  `issue_28_v13` or `issue_28_v14` until those two manifests re-record the two
  hashes;
* re-recording changes `baseline_sha256`, therefore `requirement_closure_hash`,
  therefore the Run identity of packages installed before it. The repository has
  made this trade before: commit `8346c32` edits both manifests together.

So Issue #47 does not need a new decision about Requirement architecture. It
needs its registration to land **in the same change as Issue #28's next
Requirement generation**, so the re-record happens once, for a reason #28 has
already accepted, instead of twice. That is a scheduling question for #28's
integrator, and it replaces the four-option choice posted earlier.

## One further thing the measurement settles

```
replay_historical_inputs   ValueError: B06_EXTERNAL_CANDIDATE_ROOT_REQUIRED
```

when the changed runtime is asked to treat its own tree as the data root.
`_external` requires an installed data root to be outside the code root, so a
self-contained package — code and data in one directory — is not merely
unimplemented, it is refused by an existing invariant. The material test is
labelled accordingly: it proves a separate process rebuilding from an installed
data root using the development checkout's code, which is the only shape the
current design allows.
