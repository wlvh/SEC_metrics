"""Local worker audit boundary, separate from cluster/kernel enforcement."""
import os
from pathlib import Path
import sys


def install_worker_guards(program):
    program = Path(program).resolve()
    denied = [Path(p).resolve() for p in os.environ.get('COMPANY_DENY_READ_ROOTS', '').split(os.pathsep) if p]

    def audit(event, args):
        if event not in {'open', 'os.listdir', 'os.scandir'} or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        target = Path(os.fsdecode(args[0])).resolve()
        if any(target == root or root in target.parents for root in denied):
            raise PermissionError('COMPANY_WORKER_READ_OUTSIDE_BOUNDARY:'+str(target))
        if event == 'open':
            mode = args[1] if len(args) > 1 else ''
            flags = args[2] if len(args) > 2 else 0
            writing = isinstance(mode, str) and any(c in mode for c in 'wax+') or isinstance(flags, int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)
            if writing and (target == program or program in target.parents):
                raise PermissionError('COMPANY_WORKER_PROGRAM_WRITE_FORBIDDEN')

    sys.addaudithook(audit)
