import json, os, pathlib, subprocess, time
root=pathlib.Path(__file__).resolve().parent
start=time.monotonic()
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONPATH="scripts",B13_REFERENCE_CONTEXT="1",B13_NATIVE_RUN_MATERIAL_ROOT="/tmp/sec_metrics_ci_program_20260922")
command=["/tmp/sec_metrics_ci_20260922_venv/bin/python","-m","unittest","-v","tests.vnext.test_capacity_program_run_material"]
result=subprocess.run(command,env=env)
(root/"result.json").write_text(json.dumps({"command":command,"exit_code":result.returncode,"seconds":round(time.monotonic()-start,3),"new_calls":[0,0,0],"material_root":env["B13_NATIVE_RUN_MATERIAL_ROOT"]},indent=2)+"\n")
raise SystemExit(result.returncode)
