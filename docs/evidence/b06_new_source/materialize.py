"""Restore a hash-indexed B06 review package into a new directory (offline)."""
import argparse,hashlib,json
from pathlib import Path,PurePosixPath


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);a=p.parse_args()
    root=Path(__file__).resolve().parent;dest=a.directory.absolute()
    if dest.exists():raise ValueError('Choose a new output directory')
    index=json.loads((root/'INDEX.json').read_text());objects=root/'objects'
    dest.mkdir(parents=True)
    for row in index['files']:
        rel=PurePosixPath(row['path'])
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe package path')
        body=(objects/row['sha256']).read_bytes()
        if len(body)!=row['size'] or hashlib.sha256(body).hexdigest()!=row['sha256']:raise ValueError('Package object differs: '+str(rel))
        out=dest/str(rel);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(body)
    print(json.dumps({'status':'MATERIALIZED_AND_HASH_VERIFIED','files':len(index['files']),'directory':str(dest)}))

if __name__=='__main__':main()
