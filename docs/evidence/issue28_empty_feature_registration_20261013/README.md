# Empty feature declarations are not valid test registration

This finite follow-up addresses receiver PR224 findings [4253469713](https://github.com/wlvh/SEC_metrics/pull/224#discussion_r4253469713) and [4253492653](https://github.com/wlvh/SEC_metrics/pull/224#discussion_r4253492653), read directly. Base is received main `16e82aae8a7b3d75a42bb2cf6aef7b7e2dc344f4` (tree `ea06c3badb56646fca3ac673beb4809c1a563566`). The later main `ce7a9f69` changes only the independently received historical usage guide; it does not change either edited module or these controls.

`before-controls.log` reproduces all three empty declarations silently succeeding: `fast: []`, `source-material: []`, and both empty. One test reports three failures. After the existing schema/type checks, the loader now requires at least one actual selector per feature file. It still accepts an empty unused suite when the other suite is nonempty. No selector, ordering, material shard, timeout or business expectation changes.

`after-controls.log` records the initial repair: 13 tests / 0.006s, zero failures/errors/skips. `final-controls.log` additionally covers the nonempty positive branch: 14 tests, zero failures/errors/skips. These are actual working-tree executions, not a full material rerun or a remote CI result.

```sh
PYTHONPATH=tools:. python3 tests/required_unittests.py tests.test_selector_registry tests.test_foundation_ci
```

The earlier received PR224 full fast/material registration evidence is reused for unchanged responsibilities. No SEC/provider/paid call, business result, source, response, ledger, model configuration or historical consumer is changed. No author Ready, merge, deployment or adoption.
