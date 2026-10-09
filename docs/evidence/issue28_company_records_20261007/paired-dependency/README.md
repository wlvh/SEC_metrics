# B02 paired-measure update dependency

The existing ordinary Company Facts B02 path calls paired_measure_v1.py to reject revenue comparisons with different scopes. Parent actually loaded B01/B02/B03 configurations at8819dbff: that consumed helper was absent from every processing identity. Two small regressions failed: a helper-only change was invisible, and the actual updater reused the prior success instead of producing the controlled new withheld conclusion.

The repair names that file only for B02. It changes no revenue choice, scope rule, formula or old record. The actual updater, with explicitly synthetic source/calculation/storage controls, now recalculates after the changed guard, retains the old success as history, and reuses the subsequent stable withheld result with the factory forbidden. A separate check confirms changing only this B02 helper does not alter B01 configuration.

All28controller/configuration/period/recovery controls pass0.135s. The existing whole company-entry module also passes (adjacent log); its saved-original positive/repeat/read path is reused and re-executed only at this affected seam, not all companies/material. The dirty tested tree is identified by8819dbff plus exact two-file hashes, not falsely presented as a committed candidate. Existing paired-helper/default/semantic results remain byte-identical. No new whole-company result, source capture, provider request or acceptance.

The original failed log remains. This is a required correctness correction within PR67 closeout, not a general dependency scanner or new family. Processing updates can create an ordinary new version; old success/withheld Run and Result identities stay. Shared consumer implementations continue to declare their own actual producer dependencies.
