"""Target company context for ordinary updates, retaining registry integrity checks."""
import csv
from .company_registry import _registry_rows


def registered_company_row(*, repo_root, company_id):
    rows=_registry_rows(repo_root=repo_root)
    with (repo_root/"config"/"company_registry.csv").open(encoding="utf-8",newline="") as stream:
        fields=next(csv.reader(stream))
    if len(fields)!=len(set(fields)):
        raise ValueError("CURRENT_UPDATE_COMPANY_REGISTRY_FIELDS_AMBIGUOUS")
    for row in rows:
        if (None in row or not row.get('company_id') or not row.get('display_name')
                or not str(row.get('primary_cik','')).isdigit()
                or int(row['primary_cik'])<=0 or any(value is None for value in row.values())):
            raise ValueError('CURRENT_UPDATE_COMPANY_REGISTRY_ROW_INVALID')
    selected=[row for row in rows if row['company_id']==company_id]
    if len(selected)!=1:
        raise ValueError('CURRENT_UPDATE_COMPANY_REGISTRY_TARGET_NOT_UNIQUE')
    # All target fields remain relevant context; only other companies' rows
    # leave this task's change comparison. No old configuration is rewritten.
    return dict(selected[0])
