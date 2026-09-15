"""Restore the complete recorded/structural materials from verified unique bytes."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import sys
import tarfile


def main():
    here = Path(__file__).resolve().parent
    output = Path(sys.argv[1]).resolve()
    if output.exists():
        raise ValueError('RESTORE_REQUIRES_NEW_DIRECTORY')
    index = json.loads((here / 'native-material-index.json').read_text())
    archive = here / 'native-material.tar.xz'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != index['archive_sha256']:
        raise ValueError('ARCHIVE_CHANGED')
    targets = {}
    for relative, binding in index['files'].items():
        path = PurePosixPath(relative)
        if path.is_absolute() or '..' in path.parts or str(path) != relative:
            raise ValueError('UNSAFE_MEMBER')
        targets.setdefault(binding['sha256'], []).append((relative, binding['size']))
    output.mkdir(parents=True)
    seen = set()
    with tarfile.open(archive, 'r|xz') as source:
        for member in source:
            digest = member.name.removeprefix('blobs/')
            if not member.isfile() or digest not in targets or member.name != 'blobs/' + digest or digest in seen:
                raise ValueError('ARCHIVE_MEMBER_SET_CHANGED')
            raw = source.extractfile(member).read()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('ARCHIVE_MEMBER_BYTES_CHANGED')
            for relative, size in targets[digest]:
                if len(raw) != size:
                    raise ValueError('ARCHIVE_MEMBER_SIZE_CHANGED')
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(raw)
            seen.add(digest)
    if seen != set(targets):
        raise ValueError('ARCHIVE_MEMBER_MISSING')
    print(json.dumps({'restored_files': len(index['files']), 'verified_blobs': len(seen)}))


if __name__ == '__main__':
    main()
