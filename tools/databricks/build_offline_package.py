#!/usr/bin/env python3
"""Build an offline package for Databricks: SEC_metrics program + one company's saved SEC originals.

Run on a machine that can reach github.com (Python 3.8+, standard library only):

    python3 build_offline_package.py --list-companies          # saved companies and sizes
    python3 build_offline_package.py --company <company_id>    # program at the tested commit

It makes no SEC request. The SEC originals were captured earlier through the project's
SEC client and are archived in the public repository together with the request ledger.
Every file is checked against the pinned commit's git blob hash; each SEC body is also
checked against the SHA-256 and length the ledger recorded when SEC returned it.
Upload the resulting zip to Databricks and run company_metrics_notebook.py there
(steps and expected results: docs/databricks_offline_run.md).
"""
import argparse
import concurrent.futures
import csv
import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPOSITORY = "wlvh/SEC_metrics"
# Program commit verified end to end with this builder; a newer --ref may need more PROGRAM_FILES.
DEFAULT_REF = "681b35d865af9660ad03ffbbb20ec93cd499d9cd"
PROGRAM_TREES = ("scripts", "config", "catalog")
PROGRAM_FILES = ("tools/vnext_company.py", "tools/check_main_scalability.py", "tools/probe_securegpt.py",
                 "docs/evidence/issue28_continuous/known_result_defects.json")
SOURCE_FILES = ("evidence/requests_log.csv", "evidence/requests_log_manifest.json", "config/company_registry.csv")
ROOT = "sec_metrics_package"
TIMEOUT = 60


class PackageError(Exception):
    """A download or integrity check failed; nothing is written."""


def _get(url, *, api=False):
    headers = {"User-Agent": "sec-metrics-package-builder"}
    if api:
        headers["Accept"] = "application/vnd.github+json"
        if os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        hint = (" (GitHub API rate limit: wait an hour or set GITHUB_TOKEN)"
                if api and error.code in (403, 429) else "")
        raise PackageError(f"HTTP {error.code} for {url}{hint}") from None
    except urllib.error.URLError as error:
        raise PackageError(f"Cannot reach {url}: {error.reason}. Behind a proxy, set HTTPS_PROXY; "
                           "for certificate errors, set SSL_CERT_FILE to your company CA bundle.") from None


def _tree(ref, path, recursive):
    """Map full repository path -> git blob SHA-1 for one directory of the pinned commit."""
    url = (f"https://api.github.com/repos/{REPOSITORY}/git/trees/"
           f"{urllib.parse.quote(ref + ':' + path, safe=':')}" + ("?recursive=1" if recursive else ""))
    body = json.loads(_get(url, api=True))
    if body.get("truncated"):
        raise PackageError(f"GitHub truncated the listing of {path}")
    return {f"{path}/{entry['path']}": entry["sha"] for entry in body["tree"] if entry["type"] == "blob"}


def _raw(ref, path, blob_sha):
    data = _get(f"https://raw.githubusercontent.com/{REPOSITORY}/{ref}/{urllib.parse.quote(path)}")
    actual = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    if actual != blob_sha:
        raise PackageError(f"Content of {path} differs from commit {ref[:12]}")
    return data


def _company_ciks(registry_text, company_id):
    rows = [row for row in csv.DictReader(io.StringIO(registry_text)) if row["company_id"] == company_id]
    if len(rows) != 1:
        raise PackageError(f"Company {company_id!r} is not in config/company_registry.csv")
    return sorted({cik.lstrip("0") for cik in re.findall(r"\d+", rows[0]["primary_cik"] + " " + rows[0]["related_ciks"])})


def _company_rows(ledger_rows, ciks):
    return [row for row in ledger_rows
            if any(f"/{cik}/" in row["source_url"] or f"CIK{cik.zfill(10)}" in row["source_url"] for cik in ciks)]


def _ledger(ref, blobs):
    files = {path: _raw(ref, path, blobs[path]) for path in SOURCE_FILES}
    manifest = json.loads(files["evidence/requests_log_manifest.json"])
    ledger_bytes = files["evidence/requests_log.csv"]
    rows = list(csv.DictReader(io.StringIO(ledger_bytes.decode("utf-8"))))
    if hashlib.sha256(ledger_bytes).hexdigest() != manifest["content_sha256"] or len(rows) != manifest["row_count"]:
        raise PackageError("Request ledger does not match its manifest")
    return files, rows


def list_companies(ref):
    blobs = {**_tree(ref, "evidence", False), **_tree(ref, "config", False)}
    files, rows = _ledger(ref, blobs)
    registry = files["config/company_registry.csv"].decode("utf-8")
    for row in csv.DictReader(io.StringIO(registry)):
        selected = _company_rows(rows, _company_ciks(registry, row["company_id"]))
        size = sum(int(r["content_length"] or 0) for r in selected)
        print(f"{row['company_id']:<36} {row['industry_profile']:<34} {len(selected):>4} SEC requests  {size / 1e6:6.1f} MB")


def build(ref, company_id, output):
    blobs = {}
    for path in PROGRAM_TREES:
        blobs.update(_tree(ref, path, True))
    for path in ("tools", "docs/evidence/issue28_continuous", "evidence"):
        blobs.update(_tree(ref, path, False))
    source_files, rows = _ledger(ref, blobs)
    ciks = _company_ciks(source_files["config/company_registry.csv"].decode("utf-8"), company_id)
    selected = _company_rows(rows, ciks)
    if not selected:
        raise PackageError(f"No saved SEC requests for {company_id}")
    # A body path can be written by several captures; keep the file only if its bytes are
    # exactly one recorded SEC response. Immutable request_attempts always are; an older
    # working copy that a later capture overwrote is left out and listed.
    recorded, headers_of = {}, {}
    for row in selected:
        if row["repo_relative_path"]:
            recorded.setdefault(row["repo_relative_path"], set()).add((row["content_sha256"], int(row["content_length"] or 0)))
            if row["headers_repo_relative_path"]:
                headers_of.setdefault(row["repo_relative_path"], set()).add(row["headers_repo_relative_path"])
    wanted = set(recorded) | {h for paths in headers_of.values() for h in paths}
    for top in sorted({"/".join(path.split("/")[:2]) for path in wanted}):
        blobs.update(_tree(ref, top, True))
    missing = sorted(path for path in wanted if path not in blobs)
    if missing:
        raise PackageError(f"{len(missing)} ledger files are not in the commit, first: {missing[0]}")

    program_paths = sorted(p for p in blobs if p.split("/")[0] in PROGRAM_TREES) + list(PROGRAM_FILES)
    jobs = {("program", p): p for p in program_paths}
    jobs.update({("source", p): p for p in wanted})
    print(f"Downloading {len(jobs)} files from github.com/{REPOSITORY} at {ref[:12]} ...", flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = {key: pool.submit(_raw, ref, path, blobs[path]) for key, path in jobs.items()}
        contents = {key: future.result() for key, future in futures.items()}
    skipped = []
    for path, captures in recorded.items():
        data = contents[("source", path)]
        if (hashlib.sha256(data).hexdigest(), len(data)) not in captures:
            skipped.append(path)
            del contents[("source", path)]
            for header in headers_of.get(path, ()):
                contents.pop(("source", header), None)
    for (side, path), data in contents.items():
        named = re.search(r"\.([0-9a-f]{64})\.headers\.json$", path)
        if side == "source" and named and hashlib.sha256(data).hexdigest() != named.group(1):
            raise PackageError(f"{path} differs from the hash in its name")
    for path in SOURCE_FILES:
        contents[("source", path)] = source_files[path]

    files = {f"{side}/{path}": hashlib.sha256(data).hexdigest() for (side, path), data in contents.items()}
    package = {"record_type": "SEC_METRICS_OFFLINE_PACKAGE", "schema_version": 1, "repository": REPOSITORY,
               "ref": ref, "company_id": company_id, "ciks": ciks, "sec_requests": len(selected),
               "sec_bodies": len(recorded) - len(skipped), "skipped_overwritten_working_copies": sorted(skipped),
               "new_sec_requests": 0, "files": dict(sorted(files.items()))}
    entries = sorted((f"{ROOT}/{side}/{path}", data) for (side, path), data in contents.items())
    entries.append((f"{ROOT}/PACKAGE.json", json.dumps(package, indent=1).encode("utf-8")))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    with open(output, "wb") as stream:
        stream.write(buffer.getvalue())
    print(json.dumps({"status": "PACKAGE_READY", "zip": os.path.abspath(output), "zip_sha256":
                      hashlib.sha256(buffer.getvalue()).hexdigest(), "zip_mb": round(len(buffer.getvalue()) / 1e6, 1),
                      "company_id": company_id, "ref": ref, "sec_requests": len(selected),
                      "sec_bodies": package["sec_bodies"], "skipped_overwritten_working_copies": len(skipped),
                      "files": len(files), "new_sec_requests": 0}, indent=1))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--company", help="company_id from config/company_registry.csv")
    parser.add_argument("--ref", default=DEFAULT_REF, help="Pinned SEC_metrics commit (default is the tested one)")
    parser.add_argument("--out", help="Output zip path")
    parser.add_argument("--list-companies", action="store_true")
    args = parser.parse_args(argv)
    if not args.list_companies and not args.company:
        parser.error("--company is required; --list-companies shows the choices")
    try:
        if args.list_companies:
            list_companies(args.ref)
        else:
            build(args.ref, args.company, args.out or f"sec_metrics_{args.company}_{args.ref[:8]}.zip")
    except PackageError as error:
        print("PACKAGE_FAILED: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
