"""Project canonical company traits from the existing registry/profile config.

The catalog declares profile-to-trait semantics but never duplicates company
identity. This module joins each registry row to its existing profile and
fails when the catalog/profile exact set drifts.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from .canonical import strict_json_file


class TraitError(ValueError):
    """Report registry, profile, or generated trait-catalog drift."""


def derive_company_traits(
    *, registry_path: Path, applicability_path: Path, trait_catalog_path: Path,
) -> Dict[str, List[str]]:
    """Return deterministic company traits without a second company registry.

    Args:
        registry_path: Canonical ``config/company_registry.csv``.
        applicability_path: Existing JSON-compatible profile configuration.
        trait_catalog_path: JSON-compatible profile-to-traits projection.

    Returns:
        Company ID to ordered unique traits.

    Raises:
        TraitError: On unsafe files, duplicate company/profile/trait, unknown
        profile, or catalog provenance drift.
    """
    for path in (registry_path, applicability_path, trait_catalog_path):
        if path.is_symlink() or not path.is_file():
            raise TraitError("Trait input must be a regular file")
    applicability = strict_json_file(path=applicability_path)
    catalog = strict_json_file(path=trait_catalog_path)
    if not isinstance(applicability, dict) or not isinstance(catalog, dict):
        raise TraitError("Trait configuration root must be an object")
    required_catalog = {
        "profile_traits",
        "projection_source",
        "schema_version",
    }
    if set(catalog) != required_catalog:
        raise TraitError("Trait catalog fields are not exact")
    expected_sources = {
        "company_registry": "config/company_registry.csv",
        "metric_applicability": "config/metric_applicability.yaml",
    }
    if catalog["projection_source"] != expected_sources:
        raise TraitError("Trait catalog provenance differs")
    profiles = applicability["profiles"]
    trait_profiles = catalog["profile_traits"]
    if not isinstance(profiles, dict) or not isinstance(trait_profiles, dict):
        raise TraitError("Profile traits must be objects")
    if set(profiles) != set(trait_profiles):
        raise TraitError("Trait catalog profile exact set differs")
    for profile in trait_profiles:
        traits = trait_profiles[profile]
        if (
            not isinstance(traits, list)
            or not traits
            or any(not isinstance(trait, str) or not trait for trait in traits)
            or len(traits) != len(set(traits))
        ):
            raise TraitError("Profile traits must be unique non-empty strings")
    with registry_path.open(
        mode="r", encoding="utf-8", newline=""
    ) as file_obj:
        reader = csv.DictReader(file_obj)
        if reader.fieldnames is None or not {
            "company_id",
            "industry_profile",
        }.issubset(reader.fieldnames):
            raise TraitError("Company registry lacks trait join fields")
        output: Dict[str, List[str]] = {}
        for row in reader:
            company_id = row["company_id"]
            profile = row["industry_profile"]
            if not company_id or company_id in output:
                raise TraitError(
                    "Company registry identity is empty or duplicated"
                )
            if profile not in trait_profiles:
                raise TraitError(
                    "Company registry profile has no trait mapping"
                )
            output[company_id] = list(trait_profiles[profile])
    if not output:
        raise TraitError("Company trait projection is empty")
    return output


def repository_company_traits(
    *, repo_root: Path, company_id: str
) -> List[str]:
    """Return one company's traits from the repository's canonical inputs.

    Args:
        repo_root: Repository containing config and the trait catalog.
        company_id: Logical company identity from the canonical registry.

    Returns:
        Ordered traits projected from registry profile configuration.

    Raises:
        TraitError: When inputs drift or the company is not registered.
    """
    traits_by_company = derive_company_traits(
        registry_path=repo_root / "config" / "company_registry.csv",
        applicability_path=(
            repo_root / "config" / "metric_applicability.yaml"
        ),
        trait_catalog_path=repo_root / "catalog" / "company_traits.yaml",
    )
    if company_id not in traits_by_company:
        raise TraitError("Company is absent from the canonical registry")
    return traits_by_company[company_id]


def repository_company_ciks(*, repo_root: Path, company_id: str) -> List[str]:
    """Return every registry-authorized CIK for one logical company.

    Args:
        repo_root: Repository containing the canonical company registry.
        company_id: Logical company identity from that registry.

    Returns:
        Ordered, unique, unpadded decimal CIK strings from the role mapping.

    Raises:
        TraitError: On an unsafe registry, missing company, malformed role,
            duplicate CIK, or primary-CIK disagreement.
    """
    path = repo_root / "config" / "company_registry.csv"
    if path.is_symlink() or not path.is_file():
        raise TraitError("Company registry must be a regular file")
    with path.open(mode="r", encoding="utf-8", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        required = {"company_id", "primary_cik", "roles"}
        if reader.fieldnames is None or not required.issubset(
            reader.fieldnames
        ):
            raise TraitError("Company registry lacks CIK identity fields")
        matches = [row for row in reader if row["company_id"] == company_id]
    if len(matches) != 1:
        raise TraitError("Company registry identity is absent or duplicated")
    row = matches[0]
    role_entries = row["roles"].split(";")
    if not role_entries or any(not entry for entry in role_entries):
        raise TraitError("Company registry CIK roles are empty")
    ciks = []
    for entry in role_entries:
        parts = entry.split(":", 1)
        if (
            len(parts) != 2
            or not parts[0]
            or not parts[1].isdigit()
            or int(parts[1]) <= 0
        ):
            raise TraitError("Company registry CIK role is malformed")
        ciks.append(str(int(parts[1])))
    if len(ciks) != len(set(ciks)):
        raise TraitError("Company registry CIK roles are duplicated")
    if not row["primary_cik"].isdigit() or str(
        int(row["primary_cik"])
    ) not in ciks:
        raise TraitError("Company registry primary CIK lacks a role")
    return ciks
