#!/bin/zsh
set -eu
cd /Users/lyuhongwang/Developer/SEC_metrics
nohup env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:scripts \
  ORDINARY_ISOLATED_PUBLICATION_PREPARATION=/private/tmp/issue28-d04-unified-release-current-enphase-070f-20260928 \
  ORDINARY_ISOLATED_PUBLICATION_ROOT=/private/tmp/issue28-d04-enphase-private-publication-070f-20260928 \
  /private/tmp/issue28_py314_venv/bin/python -u -m unittest -v \
  tests.vnext.test_ordinary_isolated_publication.OrdinaryIsolatedPublicationMaterialTest.test_stage_switch_rollback_restore_and_interrupted_recovery \
  > docs/evidence/issue28_continuous/d04-unified-release-20260928/publication-current.log 2>&1 < /dev/null &
pid=$!
set +e
wait $pid
code=$?
set -e
print -r -- "$code" > docs/evidence/issue28_continuous/d04-unified-release-20260928/publication-current.exit
exit "$code"
