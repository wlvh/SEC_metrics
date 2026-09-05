"""R4 schema and shared publication hook boundaries, without release credit.

The small bundle fixtures exercise the real envelope/file/hash validators.
Only the separate R4 semantic hooks are stubs; these fixtures do not stand in
for qualification, native projection, or a publication rehearsal.
"""

import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tests.vnext.common import REPO_ROOT  # establishes the repository import path
from vnext import publication as publication
from vnext.canonical import atomic_write_bytes, atomic_write_json, content_hash, sha256_bytes
from vnext.records import R4_PUBLICATION_MANIFEST_TYPE, RecordError, validate_record


def _hashes(*, successor):
    fields = (publication.PROFILE_REQUIREMENT_HASH_FIELDS if successor
              else publication.REQUIREMENT_HASH_FIELDS)
    return {field: ("sha256:" if field in publication.REQUIREMENT_CONTENT_HASH_FIELDS else "")
            + "a" * 64 for field in sorted(fields)}


def _resign(manifest):
    body = {key: value for key, value in manifest.items()
            if key not in {"record_type", "publication_id"}}
    manifest["publication_id"] = "publication_" + content_hash(value=body)[7:]
    return manifest


def _bundle(*, root, r4=True, previous=None, extra_files=None):
    files = {relative: b"test-fixture-only\n" for relative in publication.REQUIRED_BUNDLE_FILES}
    files.update(extra_files or {})
    files[("internal/r4_release_receipt.json" if r4 else publication.INTERNAL_CLOSURE_MANIFEST)] = (
        b'{"test_fixture_only":true}\n')
    hashes = _hashes(successor=r4)
    ledger = {**publication._empty_legacy_ledger_binding(),
              "request_locator_tier": publication.RECORDED_VALIDATION_MODE}
    manifest = {"record_type": R4_PUBLICATION_MANIFEST_TYPE if r4 else "PUBLICATION_MANIFEST",
        "candidate_status": "PUBLISHABLE", "requirement_hashes": hashes,
        "batch_manifest_id": "sha256:" + "b" * 64,
        "projection_manifest_id": "sha256:" + "c" * 64,
        "validation_receipt_id": "sha256:" + "d" * 64,
        "files": [{"path": relative, "sha256": sha256_bytes(content=content), "size": len(content)}
                  for relative, content in sorted(files.items())],
        "ledger_binding": ledger, "previous_publication_id": previous}
    if r4:
        manifest.update(artifact_requirement_generation="EXPLICIT_REQUIREMENT_V1",
            requirement_id="issue_28_v2", requirement_closure_hash=content_hash(value=hashes),
            projection_requirement_hashes=dict(hashes),
            r4_release_receipt_id=content_hash(value={"test_fixture_only": True}),
            publication_credit="NONE_RECORDED_REHEARSAL")
    _resign(manifest)
    validate_record(record=manifest)
    directory = root / "outputs/publications" / manifest["publication_id"]
    for relative, content in files.items():
        atomic_write_bytes(path=directory / relative, content=content)
    atomic_write_json(path=directory / "publication_manifest.json", value=manifest)
    return directory, manifest, files


def _pointer(*, root, directory, manifest, previous=None, previous_switch=None):
    pointer = {"publication_id": manifest["publication_id"],
        "bundle_manifest_sha256": sha256_bytes(content=(directory / "publication_manifest.json").read_bytes()),
        "previous_publication_id": previous, "committed_at_utc": "2026-09-04T00:00:00Z"}
    path = root / "outputs/active_publication.json"
    atomic_write_json(path=path, value=pointer)
    receipt = publication._write_switch_receipt(pointer_path=path, pointer=pointer,
        switch_mode="COMMIT", previous_switch_receipt_id=previous_switch)
    return pointer, receipt["switch_receipt_id"]


class R4PublicationBoundaryTest(unittest.TestCase):
    def test_explicit_identity_and_credit_are_hashed_and_not_legacy_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            _path, original, _files = _bundle(root=Path(directory))
            for field in ("r4_release_receipt_id", "publication_credit"):
                changed = copy.deepcopy(original)
                changed[field] = "sha256:" + "e" * 64 if field.endswith("_id") else "LIVE"
                with self.subTest(field=field), self.assertRaises(RecordError):
                    validate_record(record=changed)
                validate_record(record=_resign(changed))
            for field in ("artifact_requirement_generation", "requirement_id", "requirement_closure_hash",
                          "requirement_hashes", "projection_requirement_hashes", "r4_release_receipt_id",
                          "publication_credit"):
                changed = copy.deepcopy(original)
                del changed[field]
                with self.subTest(missing=field), self.assertRaises(RecordError):
                    validate_record(record=_resign(changed))
            for field, value in (("publication_credit", "FORMAL"),
                                 ("r4_release_receipt_id", "caller-grant"),
                                 ("projection_requirement_hashes", {"forged": "nonempty"})):
                changed = {**original, field: value}
                with self.subTest(invalid=field), self.assertRaises(RecordError):
                    validate_record(record=_resign(changed))
            changed = {**original, "record_type": "SUCCESSOR_PUBLICATION_MANIFEST"}
            with self.assertRaises(RecordError):
                validate_record(record=changed)

    def test_native_envelope_checks_run_before_the_r4_semantic_hook(self):
        for mutation in ("bytes", "extra", "symlink", "identity"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                bundle, manifest, files = _bundle(root=Path(directory))
                verifier = mock.Mock()
                with mock.patch.object(publication, "_r4_publication_hooks",
                        return_value=SimpleNamespace(verify_r4_bundle=verifier)):
                    self.assertEqual(publication.verify_publication_bundle(bundle_dir=bundle), manifest)
                    verifier.assert_called_once_with(bundle_dir=bundle, manifest=manifest)
                    verifier.reset_mock()
                    target = bundle / "metrics_matrix.csv"
                    if mutation == "bytes":
                        target.write_bytes(b"different fixture\n")
                    elif mutation == "extra":
                        (bundle / "extra.txt").write_bytes(b"extra\n")
                    elif mutation == "symlink":
                        target.unlink()
                        target.symlink_to(bundle / "metric_evidence.csv")
                    else:
                        changed = {**manifest, "publication_credit": "LIVE"}
                        atomic_write_json(path=bundle / "publication_manifest.json", value=changed)
                    with self.assertRaises(publication.PublicationError):
                        publication.verify_publication_bundle(bundle_dir=bundle)
                    verifier.assert_not_called()

    def test_rebound_historical_marker_grafts_never_select_legacy_authority(self):
        for marker in (publication.LEGACY_BASELINE_IMPORT_MANIFEST, publication.ZERO_AI_FORMAL_MANIFEST):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                bundle, _manifest, _files = _bundle(root=Path(directory), extra_files={marker: b"{}\n"})
                with mock.patch.object(publication, "_r4_publication_hooks") as hooks:
                    with self.assertRaisesRegex(publication.PublicationError, "Historical release"):
                        publication.verify_publication_bundle(bundle_dir=bundle)
                    hooks.assert_not_called()

    def test_shared_persistence_uses_real_file_verification_and_exact_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _source, manifest, files = _bundle(root=root / "source")
            destination = root / "destination/publications"
            with mock.patch.object(publication, "_r4_publication_hooks",
                    return_value=SimpleNamespace(verify_r4_bundle=mock.Mock())):
                first = publication._persist_prepared_publication_bundle(
                    publications_dir=destination, files=files, manifest=manifest)
                second = publication._persist_prepared_publication_bundle(
                    publications_dir=destination, files=files, manifest=manifest)
                self.assertEqual(first, manifest)
                self.assertEqual(second, manifest)
                self.assertEqual([path.name for path in destination.iterdir()], [manifest["publication_id"]])
                (destination / manifest["publication_id"] / "metrics_matrix.csv").write_bytes(b"drift\n")
                with self.assertRaises(publication.PublicationError):
                    publication._persist_prepared_publication_bundle(
                        publications_dir=destination, files=files, manifest=manifest)

    def test_r4_commit_authority_is_typed_and_legacy_paths_do_not_load_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, manifest, _files = _bundle(root=root / "r4")
            classify = mock.Mock(return_value=publication.RECORDED_COMMIT_AUTHORITY)
            with mock.patch.object(publication, "_r4_publication_hooks",
                    return_value=SimpleNamespace(commit_authority=classify)):
                self.assertEqual(publication._publication_commit_authority(bundle_dir=bundle), "RECORDED")
                classify.assert_called_once_with(bundle_dir=bundle, manifest=manifest)
                classify.return_value = "caller-approved"
                with self.assertRaises(publication.PublicationError):
                    publication._publication_commit_authority(bundle_dir=bundle)
            legacy, _manifest, _files = _bundle(root=root / "legacy", r4=False,
                extra_files={publication.LEGACY_BASELINE_IMPORT_MANIFEST: b"{}\n"})
            with mock.patch.object(publication, "_r4_publication_hooks") as hooks:
                self.assertEqual(publication._publication_commit_authority(bundle_dir=legacy), "LEGACY_BASELINE")
                hooks.assert_not_called()

    def test_locked_switch_guards_target_or_active_r4_before_any_intent(self):
        for target_r4 in (True, False):
            with self.subTest(target_r4=target_r4), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                legacy_dir, legacy, _files = _bundle(root=root, r4=False)
                prior, prior_switch = _pointer(root=root, directory=legacy_dir, manifest=legacy)
                r4_dir, r4, _files = _bundle(root=root, previous=legacy["publication_id"])
                if target_r4:
                    target_dir, target, mode = r4_dir, r4, "COMMIT"
                else:
                    prior, _tip = _pointer(root=root, directory=r4_dir, manifest=r4,
                        previous=legacy["publication_id"], previous_switch=prior_switch)
                    target_dir, target, mode = legacy_dir, legacy, "ROLLBACK"
                layout = publication.publication_layout(publication_root=root)
                before = layout["pointer_path"].read_bytes()
                guard = mock.Mock(side_effect=publication.PublicationError("R4 guard blocked"))
                with mock.patch.object(publication, "_r4_publication_hooks",
                        return_value=SimpleNamespace(guard_switch=guard)):
                    with self.assertRaisesRegex(publication.PublicationError, "R4 guard blocked"):
                        publication._switch_publication_locked(
                            publications_dir=layout["publications_dir"], pointer_path=layout["pointer_path"],
                            bundle_dir=target_dir, manifest=target, publication_id=target["publication_id"],
                            expected_previous_publication_id=prior["publication_id"],
                            committed_at_utc="2026-09-04T01:00:00Z", mirror_paths=layout["mirror_paths"],
                            switch_mode=mode)
                guard.assert_called_once_with(pointer_path=layout["pointer_path"], manifest=target,
                    expected_active_id=prior["publication_id"], switch_mode=mode)
                self.assertEqual(before, layout["pointer_path"].read_bytes())
                self.assertFalse(layout["switch_intents_dir"].exists())
                self.assertFalse(any(path.exists() for path in layout["mirror_paths"].values()))

    def test_recovery_guards_r4_on_either_intent_side_before_mutation(self):
        for proposed_r4 in (True, False):
            with self.subTest(proposed_r4=proposed_r4), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                old_dir, old, _files = _bundle(root=root, r4=not proposed_r4)
                old_pointer, old_switch = _pointer(root=root, directory=old_dir, manifest=old)
                new_dir, new, _files = _bundle(root=root, r4=proposed_r4, previous=old["publication_id"])
                proposed = {"publication_id": new["publication_id"],
                    "bundle_manifest_sha256": sha256_bytes(content=(new_dir / "publication_manifest.json").read_bytes()),
                    "previous_publication_id": old["publication_id"], "committed_at_utc": "2026-09-04T01:00:00Z"}
                layout = publication.publication_layout(publication_root=root)
                intent = publication._write_switch_intent(pointer_path=layout["pointer_path"],
                    previous_pointer=old_pointer, proposed_pointer=proposed, switch_mode="COMMIT",
                    previous_switch_receipt_id=old_switch,
                    previous_mirror_state={name: None for name in layout["mirror_paths"]})
                if not proposed_r4:
                    atomic_write_json(path=layout["pointer_path"], value=proposed)
                before_pointer = layout["pointer_path"].read_bytes()
                guard = mock.Mock(side_effect=publication.PublicationError("R4 recovery blocked"))
                with mock.patch.object(publication, "_r4_publication_hooks",
                        return_value=SimpleNamespace(guard_recovery=guard)):
                    with self.assertRaisesRegex(publication.PublicationError, "R4 recovery blocked"):
                        publication._recover_switch_intent_locked(publications_dir=layout["publications_dir"],
                            pointer_path=layout["pointer_path"], mirror_paths=layout["mirror_paths"])
                guard.assert_called_once_with(pointer_path=layout["pointer_path"], intent=intent)
                self.assertEqual(before_pointer, layout["pointer_path"].read_bytes())
                self.assertEqual(publication._load_switch_intent(pointer_path=layout["pointer_path"]), intent)
                self.assertFalse(any(path.exists() for path in layout["mirror_paths"].values()))

    def test_plain_mirror_repair_guards_an_r4_view_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle, manifest, _files = _bundle(root=root)
            _pointer(root=root, directory=bundle, manifest=manifest)
            layout = publication.publication_layout(publication_root=root)
            guard = mock.Mock(side_effect=publication.PublicationError("R4 mirror repair blocked"))
            hooks = SimpleNamespace(verify_r4_bundle=mock.Mock(), guard_mirror_repair=guard)
            with mock.patch.object(publication, "_r4_publication_hooks", return_value=hooks):
                with self.assertRaisesRegex(publication.PublicationError, "R4 mirror repair blocked"):
                    publication.recover_publication_mirrors(publication_root=root)
            guard.assert_called_once_with(publication_root=root)
            self.assertFalse(any(path.exists() for path in layout["mirror_paths"].values()))


if __name__ == "__main__":
    unittest.main()
