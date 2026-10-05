"""Copy the transported legacy SEC root and add only baseline working mirrors.

The transported ``legacy-source-input`` stays unchanged. A fresh preparation
root receives exact bytes for repository-relative paths named on the command
line, and only when the fixed trusted saved-source baseline
(``config/normal_candidate_sources_v1.json`` of the consuming program) binds
that path to a git blob and size. Bytes come from that blob object, never from
an attempt with another identity, so the original immutable D04 input
(147714 bytes, e3eeefe3) stays at its own locator and is not replaced.

No ledger row, manifest, checkpoint or trust record is created or edited.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def git_blob_id(raw):
    return hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest()


def checked_relative(value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Unsafe repository-relative path: ' + value)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True,
                        help='Clone containing the baseline blob objects')
    parser.add_argument('--program-root', type=Path, required=True,
                        help='Consuming fixed program checkout (owns the baseline config)')
    parser.add_argument('--legacy-source', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--path', action='append', required=True,
                        help='Declared baseline locator to add; repeat')
    args = parser.parse_args()
    output = args.output_root
    if not output.is_absolute() or output.exists():
        raise ValueError('A fresh absolute output root is required')
    config_path = args.program_root / 'config/normal_candidate_sources_v1.json'
    baseline = json.loads(config_path.read_text())
    if (baseline.get('record_type') != 'TRUSTED_SAVED_SOURCE_BASELINE'
            or baseline.get('schema_version') != 1):
        raise ValueError('Unexpected baseline config')
    legacy = args.legacy_source.resolve(strict=True)
    shutil.copytree(legacy, output, symlinks=False)
    added = []
    for value in args.path:
        relative = checked_relative(value)
        entry = baseline['files'].get(relative.as_posix())
        if entry is None:
            raise ValueError('Not bound by the trusted baseline: ' + value)
        target = output / relative
        if target.exists():
            raise ValueError('Refusing to overwrite carried member: ' + value)
        raw = subprocess.check_output(
            ['git', 'cat-file', 'blob', entry['git_blob_id']], cwd=args.repository)
        if len(raw) != entry['size'] or git_blob_id(raw) != entry['git_blob_id']:
            raise ValueError('Baseline blob mismatch: ' + value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        added.append({'path': relative.as_posix(), 'size': len(raw),
                      'git_blob_id': entry['git_blob_id'],
                      'sha256': hashlib.sha256(raw).hexdigest()})
    print(json.dumps({
        'record_type': 'D04_BASELINE_WORKING_MIRROR_PREPARATION',
        'legacy_source_input_unchanged': str(legacy),
        'output_root': str(output),
        'baseline_config_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'baseline_commit': baseline['baseline_commit'],
        'added': added,
        'ledger_or_trust_written': False,
        'calls': [0, 0, 0]}, indent=2))


if __name__ == '__main__':
    main()
