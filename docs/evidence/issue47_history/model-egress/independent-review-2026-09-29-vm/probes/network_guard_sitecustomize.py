# Review network guard: every Python process started with this on PYTHONPATH refuses
# to resolve names or open inet sockets. Unix sockets are left alone.
import socket as _s
def _refuse(*a, **k):
    raise OSError("REVIEW_NETWORK_FORBIDDEN")
_orig_connect = _s.socket.connect
_orig_connect_ex = _s.socket.connect_ex
def _connect(self, address, *a, **k):
    if self.family in (_s.AF_INET, _s.AF_INET6):
        raise OSError("REVIEW_NETWORK_FORBIDDEN:" + str(address))
    return _orig_connect(self, address, *a, **k)
def _connect_ex(self, address, *a, **k):
    if self.family in (_s.AF_INET, _s.AF_INET6):
        raise OSError("REVIEW_NETWORK_FORBIDDEN:" + str(address))
    return _orig_connect_ex(self, address, *a, **k)
_s.socket.connect = _connect
_s.socket.connect_ex = _connect_ex
_s.getaddrinfo = _refuse
_s.gethostbyname = _refuse
_s.create_connection = _refuse
