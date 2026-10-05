"""One-time transport recipe for the already authenticated Marriott LIVE input.

This does not grant calls, register a new assessment, or alter its identity.
Run from a clone containing the fixed commits listed by the locator files.
The old program, SEC/proofs, processing packet and original export trust stay
separate. No new archive or provider request is made.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent


def checked_relative(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Unsafe transport member: ' + value)
    return path


def restore(repository, target, rows):
    for row in rows:
        if 'carried_path' in row:
            raw = (HERE / checked_relative(row['carried_path'])).read_bytes()
        else:
            source = checked_relative(row['source_path']).as_posix()
            raw = subprocess.check_output(
                ['git', 'show', row['commit'] + ':' + source], cwd=repository)
        if (len(raw) != row['size'] or
                hashlib.sha256(raw).hexdigest() != row['sha256']):
            raise ValueError('Original byte mismatch: ' + row['path'])
        path = target / checked_relative(row['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve(strict=True)
    output = args.output_root
    if not output.is_absolute() or output.exists():
        raise ValueError('A fresh absolute output root is required')
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('Output aliases are forbidden')
    output.mkdir(parents=True)
    program = output / 'processing-runtime'
    old_source = output / 'legacy-source-input'
    locators = json.loads((HERE/'d04-runtime-object-locators.json').read_text())
    if locators['missing']:
        raise ValueError('Incomplete original program transport')
    restore(repository, program, locators['files'])
    # Existing export-processing inventories a private Git program. Recreate
    # that inventory only; its Requirement and all program bytes remain exact.
    for command in (['init'], ['add', '.'],
                    ['-c', 'user.name=Saved program transport',
                     '-c', 'user.email=saved-program@localhost',
                     'commit', '-m', 'Inventory unchanged saved program']):
        subprocess.run(['git', *command], cwd=program, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.copytree(program, old_source, ignore=shutil.ignore_patterns('.git'))
    sources = json.loads((HERE/'d04-source-object-locators.json').read_text())
    restore(repository, old_source, sources['files'])
    mirrors = json.loads((HERE/'d04-legacy-baseline-mirrors.json').read_text())
    # These legacy working mirrors belong to the trusted baseline. In
    # particular its submissions bytes are distinct from the original D04
    # immutable e3 acquisition; neither is used to overwrite the other.
    restore(repository, old_source, mirrors['files'])
    for part in ('processing', 'processing-trust'):
        shutil.copytree(HERE/'d04-transfer'/part, output/part)
    metadata = json.loads((output/'processing/processing.json').read_text())
    # The authenticated trust member is transported from the original export;
    # it is not generated from incoming processing metadata.
    trusted = json.loads((output/'processing-trust'/
        (metadata['processing_id'][7:]+'.json')).read_text())
    if trusted != metadata:
        raise ValueError('Original export trust differs')
    print(json.dumps({'processing_id':metadata['processing_id'],
        'output_root':str(output), 'original_source_members':len(sources['files']),
        'program_members':len(locators['files']), 'calls':[0,0,0],
        'scope':'Transport only; run the fixed83 authenticator before consumption',
        'legacy_working_locators':len(mirrors['files']),
        'source_package_export':'Baseline mirrors restored; consumer verifies export/admission',
        'production_authorized':False}, indent=2))


if __name__ == '__main__':
    main()
