# Historical D04 is invalidated by unused current code

Progress on #47; concrete consumer feedback for public PR282. Base actually read main `2e1303c942cf52f199004383ce7bb586387cd3a2`. This is one small reproduction, not another runner or a financial result. The same source/package input should not be replayed solely because current-only processing changes.

`historical_d04_case` calls `historical_d04_selection` and `saved_d04_replay`. Profiling the existing small original-call replay executes neither `current_d04_result.py` nor `capacity_update_input.py`. The historical case returns its own media-unverified withholding. Ordinary save/read/projection contain no calls to these current producer helpers. Current D04 does call them and must keep their processing versions.

Actual `_configuration(..., metric='D04', supplied_case=True)` nevertheless adds the entire current `ordinary_d04_saved_route.processing_paths()` unconditionally. Historical `PROCESSING_FILES` also explicitly names unused `current_d04_result.py`; simply deleting that extra declaration cannot remove the public base dependency. `supplied_case` alone must not become a blanket waiver: a supplied current producer may really use these modules.

The executed `.144s` reproduction uses the real public configuration and controller. Source census/check return empty constructed values; the explicitly labelled factory/writer produce only a constructed WITHHELD state. For each current-only module, first processing invokes the historical factory once, identical input repeats without processing, then an in-memory module SHA change invokes it a second time and creates another withholding directory. Repeating that changed input again reuses it. Both original result directories remain. Current default configurations correctly change too; a fix must preserve that contrast. Networking is forbidden and new SEC/provider/paid counts are0.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts:tools:. python3 docs/evidence/issue47_d04_history_consumer_20261010/current-route-dependency/reproduce.py --receipt /absolute/new/d04-dependency-reproduction.json
```

`receipt.json` records the actual modules, configuration changes and factory counts. It is a constructed control, not a financial conclusion. An early portable-script invocation accidentally shadowed its argparse namespace with controller kwargs and failed before writing a receipt; the variable was corrected. An earlier private receipt looked in the unqualified state directory instead of its FY2024 subdirectory when checking old results; the actual final path check confirms they are preserved. Neither mistake is reported as a production failure.

Public configuration/controller changes belong to #28; #47 owns the historical declaration and consumer verification. Current default producer, actual shared parsers/acceptors, selected annual/package changes and ordinary recovery must remain effective. Existing real historical D04 evidence and original package/Run identities in the parent record are reused; no16-answer replay, source acquisition, image interpretation or old-state modification is performed here. Removing a pointless replay does not establish image coverage or whole-filing absence.
