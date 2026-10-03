"""Delete a batch position's data root once its row and separate-process replay are recorded.

The coverage frame reads only the run directories and their row receipts; the
data root is needed while the driver installs, creates, renders and replays,
and after that only for diagnosis. Positions that failed, or whose replay did
not read back the same result, keep their data root.
"""
import json, shutil, sys, time
from pathlib import Path

OUT = Path(sys.argv[1])
removed = 0
while True:
    log = OUT / "progress.log"
    finished = log.exists() and "BATCH EXIT" in log.read_text()
    for matrix in sorted(OUT.glob("matrix-*.json")):
        try:
            data = json.loads(matrix.read_text())
        except (json.JSONDecodeError, OSError):
            continue  # the driver is rewriting it; the next pass reads it
        label = matrix.stem[len("matrix-"):]
        for row in data["positions"]:
            replay = row.get("separate_process_replay") or {}
            if not (row.get("stage") == "PUBLIC_ROW" and replay.get("status") == "FROZEN"
                    and replay.get("result_id") == row.get("result_id")):
                continue
            data_root = OUT / ("data-" + label + "-" + row["metric_id"])
            if data_root.exists():
                shutil.rmtree(data_root)
                removed += 1
    if finished:
        break
    time.sleep(60)
print(json.dumps({"removed_data_roots": removed}))
