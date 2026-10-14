
import socket, sys, runpy
def _blocked(*a, **k):
    raise OSError("NETWORK_DISABLED_BY_RECEIVER_PROBE")
socket.socket.connect = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
