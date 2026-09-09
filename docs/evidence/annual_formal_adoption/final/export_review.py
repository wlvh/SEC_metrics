"""Copy an immutable pending bundle and audit evidence, then verify the archive."""
import hashlib,json,shutil,sys,zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parent;WORK=BASE/'attempt-02'
binding=json.loads((WORK/'run-binding.json').read_text())
assert binding['status']=='VERIFIED_IMPLEMENTATION_EXECUTION_PACKAGE_AND_PENDING_PLAN'
destination=BASE/'final-review-package'
destination.mkdir(exist_ok=False)
source=Path(binding['package']['directory']);package=destination/'outputs/publications'/source.name
shutil.copytree(source,package)
review=destination/'review';review.mkdir()
for name in ['prepare.json','prepare-execution.json','read.json','read-execution.json','integration.json','integration.log',
    'integration-execution.json','deep-negatives.json','deep-negatives.log','deep-negatives-execution.json',
    'pending-production-plan.json','pending-production-plan.log','PENDING_EXECUTION_PLAN.md','repeat-prepare.json','repeat-prepare.log','approval-templates.json','approval-templates.log','run-binding.json']:
    shutil.copyfile(WORK/name,review/name)
for name in ['independent-final-review.json','core-review-implementation.json','test-fix-review.json','content-review.json','test-fix-diff.json',
    'pending-plan-review.json','ci-implementation.json','ci-test-fix.json','ci-test-fix.log','run_b.py','run_b_final.py','bind_b_final.py']:
    shutil.copyfile(BASE/name,review/name)
shutil.copytree(BASE/'safety',review/'safety')
old=review/'prior-failed-suite';old.mkdir()
for name in ['prepare.json','integration.json','integration.log','integration-execution.json',
             'deep-negatives.json','deep-negatives.log','deep-negatives-execution.json']:
    shutil.copyfile(BASE/'attempt-01'/name,old/name)
(destination/'README.md').write_text('''# Complete pending annual adoption package

This is an audit-only export. It contains the complete immutable candidate
publication, including its exact embedded R3 predecessor and original native
inputs, Runs, model response, execution and content review. It does not contain
a production grant or activation. The plan targets the actual original root;
do not reinterpret this relocated export as that authorized destination.

Use trusted repository code, never Python from inside the bundle:

    manifest = verify_publication_bundle(bundle_dir=the_named_bundle_directory)
    view = PublicationView(publication_id=manifest['publication_id'],
                           bundle_dir=the_named_bundle_directory, manifest=manifest)
    view.read_bytes(relative_path='metrics_matrix.csv')
    view.read_bytes(relative_path='metric_evidence.csv')

The source locations in review/read.json are bundle-relative and can be read
through this same view. The supplied repository must contain the reviewed Git
history, because implementation ancestry is verified rather than fabricated.
The original unrelocated workspace also supports the ordinary CLI read command.

review/pending-production-plan.json and approval-templates.json are inert,
fully populated pending artifacts. Approval comment URLs/times do not yet exist.
TEST_ONLY fixtures in test logs are not Owner approvals. The prior failed suite
is preserved; its policy-mix JSON self-reported PASS conflicted with native test
ERROR and receives no credit. The final binding uses actual method log status.

The safety incident is explicit: one standalone semantic checker transiently
overwrote the actual-root compatibility receipt, then exact prior bytes were
restored. Actual active and historical packages were never switched. Subsequent
executions used OS-level write denial. Do not call the entire stage zero-write.

New business provider/paid/SEC calls are 0/0/0; prior PR38 remains 2/2/0. This is
same-year source/execution adoption, not unseen-source qualification, a new-year
production transition or completion of all 39 metrics.
''')
def proof(path):
    raw=path.read_bytes();return {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
files={p.relative_to(destination).as_posix():proof(p) for p in sorted(destination.rglob('*')) if p.is_file()}
(destination/'EXPORT_MANIFEST.json').write_text(json.dumps({'purpose':'AUDIT_ONLY_PENDING_NOT_AUTHORITY','files':files},indent=2)+'\n')
archive=BASE/'annual-formal-adoption-review.zip'
assert not archive.exists()
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in sorted(destination.rglob('*')):
        if path.is_file():z.write(path,path.relative_to(destination))
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for relative,p in files.items():
        raw=z.read(relative)
        assert {'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}==p
    names=z.namelist()
receipt={'archive':str(archive),**proof(archive),'zip_test':'PASS','file_count':len(names),
         'unpacked_directory':str(destination),'publication_id':source.name,'export_manifest':proof(destination/'EXPORT_MANIFEST.json')}
(BASE/'export-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
