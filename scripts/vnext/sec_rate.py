"""One shared Unix-user pacing lock for finite company SEC captures."""
from contextlib import contextmanager
from pathlib import Path
import fcntl,os,time
from .canonical import strict_json_file
from .company_handoff import _atomic_json


@contextmanager
def rate_scope():
    # /tmp is /private/tmp on macOS. Resolve this OS alias once; use the same
    # physical directory as the existing Linux/local company rate gate.
    root=Path('/tmp').resolve()/('sec-metrics-sec-rate-'+str(os.getuid()))
    root.mkdir(mode=0o700,exist_ok=True)
    fd=os.open(root,os.O_RDONLY)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        stamp=root/'last-request.json'
        if stamp.is_file():
            delay=1-(time.time()-float(strict_json_file(path=stamp)['at']))
            if delay>0:time.sleep(min(delay,1))
        _atomic_json(stamp,{'at':format(time.time(),'.6f')})
        yield
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)
