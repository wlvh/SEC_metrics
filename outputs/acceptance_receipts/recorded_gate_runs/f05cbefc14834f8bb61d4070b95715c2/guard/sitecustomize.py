import sys


def _block_socket(event, _arguments):
    if event.startswith("socket."):
        raise PermissionError("RECORDED_SOCKET_BLOCKED")


sys.addaudithook(_block_socket)
