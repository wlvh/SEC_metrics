# What the Requirement seam measurement does and does not establish

Issue #47 comment #2 said a native historical Run was blocked on a decision and
offered four options. That reasoning was read off the code. This directory
measures part of it. The measurement narrowed the problem; it did not remove it.

Read the scope line first, because an earlier version of this file overstated
the result and the overstatement is the thing worth guarding against:

> **Established:** changing the two registration/dispatch files does not by
> itself break an already-installed v13 data root's Requirement loading, its Run
> *Requirement identity*, or historical input rebuilding.
>
> **Not established:** full `issue_28_v14` compatibility, the behaviour of a
> newly installed package, and — the one that matters — any native historical
> Run. No Run record is read or created anywhere in this measurement.

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

A Requirement binds bytes twice and the two checks run in different places:

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

Neither seam file is in any rule set. That is why "this breaks the current
production path" was too strong — but it is a statement about two byte checks,
not about whether a historical Run works.

## The seam the repository already built

`PROFILE_ENGINES` already carries one generation as a module path string,
imported only when a snapshot asks for it. `run_store` already dispatches Run
authority validation on the Run's own `requirement_id`, with an `issue_28_v14`
branch into `capacity_run`, and `normal_run_v3.replay_case` does the same. The
experiment applies exactly that shape.

## The measurement

The same installed package, read by its own runtime and by the changed runtime:

| probe | its own runtime | the changed runtime |
| --- | --- | --- |
| `load_requirement_snapshot:issue_28_v13` | OK | OK |
| `load_run_requirement_snapshot:issue_28_v13` | OK | OK |
| `replay_historical_inputs` | OK | OK |
| `load_requirement_snapshot:issue_28_v14` | NOT_COVERED | NOT_COVERED |
| `load_run_requirement_snapshot:issue_28_v14` | NOT_COVERED | NOT_COVERED |

The v14 rows are **not covered**, in the unmodified baseline as well: a v13 data
root carries only the files v13's own execution authority lists, so it has never
held `requirement_profile_v15.py` or v14's snapshot. An earlier version of this
report let the resulting exception read as a failure of the change. It is not a
result at all, and the tool now says so instead of raising there.

What the v13 rows show is real but bounded: an installed data root carries its
own copies of the 360 authority files, and
`validate_execution_authority(repo_root=data_root)` checks those copies rather
than the checkout's.

The other configuration, where the changed bytes are the data root's own:

```
load_run_requirement_snapshot:issue_28_v13   RequirementError: Run explicit Requirement identity differs
```

That is the state of a **newly installed** package after the change:
installation copies the live `requirement_profile.py` and `run_store.py` in, and
they no longer match what `issue_28_v13`'s manifest records.

### What `load_run_requirement_snapshot` was given

The identity triple passed to it is taken from the Requirement that had just
loaded. That exercises the Requirement side of a Run's identity. It does **not**
read a persisted Run manifest, its records, its review decision or its terminal
result, and it does not create one. `replay_historical_inputs` likewise rebuilds
an installed *input*; it is not a native Run replay. Both facts are recorded in
the output as `proves_no_native_run: true`.

## So the decision is smaller, and it is still an open engineering dependency

* every package installed **before** the change keeps loading, keeps validating
  its Run Requirement, and keeps rebuilding its inputs;
* every package installed **after** the change cannot load a Run that declares
  `issue_28_v13` until those two manifests re-record the two hashes;
* re-recording changes `baseline_sha256`, therefore `requirement_closure_hash`,
  therefore the Run identity of packages installed before it. The repository has
  made this trade before: commit `8346c32` edits both manifests together.

Calling this "a scheduling question for #28" was also too quick. It is a
concrete dependency that still needs an owner, a commit, a compatibility
acceptance and an entry point for Issue #47, and those belong on #47 rather than
in a sentence deferring to someone else's next version. What is settled is only
that the four-option table should not have been put to the user: the work is to
build the compatible implementation and run it.

Nor does adding two registrations prove that the 12 successor modules become
unnecessary. The parent loader still recurses into the parent Requirement and
still checks rule-file bytes against the data root and the code root. How the
shared rules evolve has to be shown by an actual install and run.

## The packaging claim, corrected

An earlier version of this file said a self-contained package was "forbidden by
an existing invariant". That generalised one refused layout into a prohibition.
`_external` refuses **overlap** between the code root and the candidate data
root, which the tool now measures directly:

| layout | verdict |
| --- | --- |
| one tree used as both roots | REFUSED |
| data root inside the code root | REFUSED |
| `runtime/` and `data/` beside each other in one package | **ADMITTED** |
| code root inside the data root | ADMITTED |

So a delivery package holding a pinned runtime beside its data is not excluded
by this rule. That says nothing about whether such a package has been built or
would validate: a portable delivery still needs a trusted runtime identity, and
data must never be able to nominate its own code. The material test remains
labelled as what it proves — a new process rebuilding inputs from an installed
data root, with the code imported from this development checkout.
