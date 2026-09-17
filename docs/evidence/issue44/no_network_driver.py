"""Run the reference check and tests with every network primitive disabled."""
import socket, sys, subprocess, urllib.request, unittest, os

def _blocked(*args, **kwargs):
    raise RuntimeError("NETWORK_DISABLED_BY_DRIVER")

socket.socket = _blocked  # type: ignore[assignment]
socket.create_connection = _blocked  # type: ignore[assignment]
socket.getaddrinfo = _blocked  # type: ignore[assignment]
urllib.request.urlopen = _blocked  # type: ignore[assignment]
subprocess.Popen = _blocked  # type: ignore[assignment]  # also blocks any git subprocess

root = os.getcwd()
sys.path.insert(0, root)
sys.argv = ["generate_metrics_reference", "--check"]
import importlib.util
spec = importlib.util.spec_from_file_location("gen", os.path.join(root, "tools", "generate_metrics_reference.py"))
gen = importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
rc = gen.main(["--check", "--repo-root", root])
print("check rc =", rc)
suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_metrics_reference")
result = unittest.TextTestRunner(verbosity=1).run(suite)
print("tests run =", result.testsRun, "failures =", len(result.failures), "errors =", len(result.errors))
sys.exit(0 if rc == 0 and result.wasSuccessful() else 1)
