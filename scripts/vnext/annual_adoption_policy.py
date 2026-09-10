"""Resolve only repository-known immutable adoption rules, never permissions."""
from pathlib import Path
from .canonical import sha256_file, strict_json_file, content_hash
from .sources import resolve_repository_file

ROOT = Path(__file__).resolve().parents[2]
V1 = 'annual_candidate_adoption_v1'
V2 = 'annual_candidate_adoption_v2'
V3 = 'annual_candidate_adoption_v3'
REHEARSAL_CREDIT = 'NONE_ISOLATED_ADOPTION_REHEARSAL'
PENDING_CREDIT = 'CANDIDATE_SPECIFIC_PENDING_PRODUCTION_AUTHORITY'
CONTINUITY_CREDIT = 'NONE_ISOLATED_CONTINUOUS_UPDATE'
POLICIES = {
    V1: ('config/annual_candidate_adoption_v1.json',
         'fb3ec5f09a5870d840cc970c1bcf46cdb09e6a2314263daec5f5cc64f33c2f12'),
    V2: ('config/annual_candidate_adoption_v2.json',
         'dd6f00aa361363cf12b8015f37c7eee5756df2dddb1b92964edb031f72bd5fff'),
    V3: ('config/annual_candidate_adoption_v3.json',
         'df84d19d751e8d78d6d883781fc1f7866276b5f3a534350df0cc395c9d0a1735'),
}


def policy(root=ROOT, policy_id=V1):
    if type(policy_id) is not str or policy_id not in POLICIES:
        raise ValueError('ANNUAL_UNKNOWN_ADOPTION_POLICY')
    relative, digest = POLICIES[policy_id]
    path = resolve_repository_file(repo_root=root, repo_relative_path=relative)
    value = strict_json_file(path=path)
    if sha256_file(path=path) != digest or value.get('policy_id') != policy_id:
        raise ValueError('ANNUAL_ADOPTION_POLICY_ID_OR_BYTES_CHANGED')
    return value


def resolve_embedded(value, *, root=ROOT):
    if type(value) is not dict or content_hash(value=value) != content_hash(value=policy(root, value.get('policy_id'))):
        raise ValueError('ANNUAL_ADOPTION_POLICY_CHANGED')
    return value


def credit(value):
    return {V1: REHEARSAL_CREDIT, V2: PENDING_CREDIT, V3: CONTINUITY_CREDIT}[value['policy_id']]


def pending_decision(value):
    """A proposal descriptor has no approval author, time, or active effect."""
    return {'decision_id': 'S-ANNUAL-ADOPTION', 'status': 'PENDING_EXTERNAL_APPROVAL',
        'effect': 'Candidate-specific rule requires an exact Requirement transition and distinct publication-plan approval.',
        'evidence': POLICIES[value['policy_id']][0],
        'required_choice_fields': ['policy_id', 'policy_hash', 'requirement_closure_hash', 'plan_id']}
