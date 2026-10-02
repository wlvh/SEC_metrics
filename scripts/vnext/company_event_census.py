"""Bind the frozen event census to independently admitted company headers.

Installed programs contain rules, never SEC originals. The preparer checks the
complete acquisition history before enrolling the exact company file closure.
That external record, rather than a second scan of the program checkout, owns
the computing-side census. Event parsing and all window/supplement rules stay
in the original zero-AI route.
"""
from pathlib import Path

from .company_source_authority import need, require_company
from .sources import resolve_repository_file
from .traits import repository_company_ciks
from .zero_ai_r2 import _acquired_event_filings


def installed_event_filings(*, source_root, company_id, allowed_ciks,
                            period_start, period_end):
    """Replay the original census only after authenticating its exact inputs."""
    source = Path(source_root)
    admission = require_company(source_root=source, company_id=company_id)
    registered = {str(int(cik)) for cik in repository_company_ciks(
        repo_root=source, company_id=company_id)}
    requested = {str(int(cik)) for cik in allowed_ciks}
    need(bool(requested) and requested <= registered,
         'COMPANY_EVENT_CENSUS_WRONG_CIK')
    prefix = 'evidence/accession_materials/'
    expected = {relative for relative in admission['files']
                if relative.startswith(prefix) and relative.endswith('.hdr.sgml')}
    for relative in expected:
        path = resolve_repository_file(repo_root=source, repo_relative_path=relative)
        parts = path.parent.name.rsplit('_', 2)
        need(len(parts) == 3 and parts[1].isdigit()
             and str(int(parts[1])) in registered,
             'COMPANY_EVENT_CENSUS_FOREIGN_DECLARED_HEADER')
    directory = source/'evidence/accession_materials'
    need(directory.is_dir() and not directory.is_symlink(),
         'COMPANY_EVENT_CENSUS_DIRECTORY_REQUIRED')
    actual = set()
    for child in directory.iterdir():
        need(child.is_dir() and not child.is_symlink(),
             'COMPANY_EVENT_CENSUS_UNSAFE_DIRECTORY')
        for header in child.glob('*.hdr.sgml'):
            resolve_repository_file(repo_root=source,
                                    repo_relative_path=header.relative_to(source).as_posix())
            actual.add(header.relative_to(source).as_posix())
    # Missing, added and foreign headers are all rejected. require_company
    # above has checked every declared hash and the independent trust record;
    # a locally rehashed package cannot become its own census authority.
    need(actual == expected, 'COMPANY_EVENT_CENSUS_FILE_SET_DIFFERS_FROM_TRUST')
    return _acquired_event_filings(repo_root=source, company_id=company_id,
        allowed_ciks=allowed_ciks, period_start=period_start, period_end=period_end)
