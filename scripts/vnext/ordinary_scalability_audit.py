"""Source-aware scalability audit for the explicit ordinary release route.

The frozen annual scanner treats every literal like a possible company value.
This successor keeps that default and excludes only syntax that proves a
single-letter literal is a typed source-reference prefix, or that a date is
an authorization transcription date rather than a financial period.
"""
import ast

from sec_pipeline import (audit_python_literal, folded_ast_literal_value,
    literal_value_matches_identity, load_company_registry_from_path)

from .canonical import sha256_file, strict_json_file
from .normal_source_authority import ROOT
from .sources import resolve_repository_file


_SOURCE_MARKERS = {
    'VISIBLE_BLOCK': 'B',
    'NATIVE_FACT': 'F',
    'NATIVE_SUPPLEMENT': 'S',
}
POLICY_PATH = 'config/ordinary_scalability_exemptions_v1.json'


def _approved_exemptions(runtime_root):
    """An exception is valid only for the exact reviewed source-file bytes."""
    path = runtime_root / POLICY_PATH
    if not path.exists():
        return {}
    policy = strict_json_file(path=resolve_repository_file(
        repo_root=runtime_root, repo_relative_path=POLICY_PATH))
    if (set(policy) != {'record_type', 'schema_version', 'scope', 'entries'}
            or policy['record_type'] != 'ORDINARY_SCALABILITY_EXACT_SOURCE_EXEMPTIONS'
            or policy['schema_version'] != 1 or type(policy['entries']) is not list):
        raise ValueError('ORDINARY_SCALABILITY_EXEMPTION_POLICY_INVALID')
    approved = {}
    for row in policy['entries']:
        if (type(row) is not dict or set(row) != {'file', 'line', 'literal',
                'type', 'source_sha256', 'source_size', 'context_kind'}
                or type(row['file']) is not str
                or not row['file'].startswith(('scripts/', 'tools/'))
                or not row['file'].endswith('.py')
                or type(row['line']) is not int or row['line'] < 1
                or type(row['literal']) is not str
                or row['type'] not in {'ticker', 'fixed_fiscal_date'}
                or row['context_kind'] not in {'NATIVE_FACT_REFERENCE_PREFIX',
                                               'AUTHORIZATION_TRANSCRIPTION_DATE'}
                or type(row['source_sha256']) is not str
                or len(row['source_sha256']) != 64
                or type(row['source_size']) is not int or row['source_size'] < 1):
            raise ValueError('ORDINARY_SCALABILITY_EXEMPTION_FIELDS_INVALID')
        source = resolve_repository_file(repo_root=runtime_root,
                                         repo_relative_path=row['file'])
        if (sha256_file(path=source) != row['source_sha256']
                or source.stat().st_size != row['source_size']):
            raise ValueError('ORDINARY_SCALABILITY_APPROVED_SOURCE_CHANGED')
        key = (row['file'], row['line'], row['literal'], row['type'])
        if key in approved:
            raise ValueError('ORDINARY_SCALABILITY_EXEMPTION_DUPLICATE')
        approved[key] = row['context_kind']
    return approved


def _parents(tree):
    return {child: parent for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)}


def _source_reference_prefix(node, parents):
    """Recognize a kind-to-reference marker, never an arbitrary ticker value."""
    if not isinstance(node, ast.Constant) or node.value not in _SOURCE_MARKERS.values():
        return False
    parent = parents.get(node)
    if isinstance(parent, ast.Dict):
        for key, value in zip(parent.keys, parent.values):
            if value is node and folded_ast_literal_value(node=key) in _SOURCE_MARKERS:
                return _SOURCE_MARKERS[folded_ast_literal_value(node=key)] == node.value
    if not (isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add)
            and parent.left is node and isinstance(parent.right, ast.Call)
            and isinstance(parent.right.func, ast.Name)
            and parent.right.func.id == 'str'
            and len(parent.right.args) == 1 and not parent.right.keywords):
        return False
    cursor = parents.get(parent)
    while cursor is not None and not isinstance(cursor, (ast.Assign, ast.Return,
            ast.Expr, ast.Call, ast.FunctionDef, ast.IfExp)):
        cursor = parents.get(cursor)
    while isinstance(cursor, ast.IfExp):
        kinds = {part.value for part in ast.walk(cursor.test)
                 if isinstance(part, ast.Constant) and type(part.value) is str}
        if any(_SOURCE_MARKERS.get(kind) == node.value for kind in kinds):
            return True
        cursor = parents.get(cursor)
    return False


def _authorization_date(node, parents):
    """Exempt only a date value bound to a delegation provenance field."""
    parent = parents.get(node)
    if not isinstance(parent, ast.Dict):
        return False
    if not any(value is node and folded_ast_literal_value(node=key) ==
               'user_instruction_date' for key, value in zip(parent.keys, parent.values)):
        return False
    cursor = parents.get(parent)
    while cursor is not None and not isinstance(cursor, (ast.Compare, ast.Assign,
            ast.Return, ast.Expr, ast.FunctionDef)):
        cursor = parents.get(cursor)
    if not isinstance(cursor, ast.Compare) or not any(isinstance(op, ast.Eq)
                                                     for op in cursor.ops):
        return False
    return any(isinstance(part, ast.Constant)
               and part.value == 'delegation_source' for part in ast.walk(cursor))


def successor_scalability_snapshot(runtime_root):
    """Audit current code without treating source grammar as company routing."""
    approved = _approved_exemptions(runtime_root)
    used = set()
    registry = load_company_registry_from_path(
        path=runtime_root / 'config/company_registry.csv')
    identities = []
    for company in registry:
        candidates = [(str(company['company']), 'company_name'),
                      (str(company['primary_cik']), 'cik')]
        if company['ticker']:
            candidates.append((str(company['ticker']), 'ticker'))
        candidates.extend((str(role['cik']), 'cik') for role in company['roles'])
        for candidate in candidates:
            if candidate not in identities:
                identities.append(candidate)
    rows = []
    for prefix in ('scripts', 'tools'):
        for path in sorted((runtime_root / prefix).rglob('*.py')):
            relative = path.relative_to(runtime_root)
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            parents = _parents(tree)
            for node in ast.walk(tree):
                literal = folded_ast_literal_value(node=node)
                if literal is None:
                    continue
                marker = _source_reference_prefix(node, parents)
                for forbidden, kind in identities:
                    key = (relative.as_posix(), node.lineno, forbidden, kind)
                    if (kind == 'ticker' and marker and literal == forbidden
                            and approved.get(key) == 'NATIVE_FACT_REFERENCE_PREFIX'):
                        used.add(key)
                        continue
                    if literal_value_matches_identity(literal_value=literal,
                            forbidden_literal=forbidden, literal_type=kind):
                        rows.append({'file': relative.as_posix(),
                            'line': str(node.lineno), 'literal': forbidden,
                            'type': kind, 'allowed': '0',
                            'reason': 'identity literal appears in production Python',
                            'replacement_plan': 'Move identity to config or fixtures and branch on profile, SEC metadata, dimensions, or registry rules.'})
                for row in audit_python_literal(file_path=ROOT / relative,
                        line_number=node.lineno, literal_value=literal):
                    if row['type'] not in {'accession', 'fixed_fiscal_date'}:
                        continue
                    key = (relative.as_posix(), node.lineno,
                           row['literal'], row['type'])
                    if (row['type'] == 'fixed_fiscal_date'
                            and _authorization_date(node, parents)
                            and approved.get(key) == 'AUTHORIZATION_TRANSCRIPTION_DATE'):
                        used.add(key)
                        continue
                    rows.append(row)
    if used != set(approved):
        raise ValueError('ORDINARY_SCALABILITY_EXEMPTION_NOT_PRESENT_OR_NOT_PROVEN')
    return rows
