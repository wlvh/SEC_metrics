"""Native rate locking at a canonical system tmp path, no HTTP or real ledger."""
import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from vnext import company_local_acquisition as acquisition

class NativeRatePathTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.real=self.root/'real';self.real.mkdir()
        self.alias=self.root/'system-tmp-alias';self.alias.symlink_to(self.real,target_is_directory=True)
        self.rate=self.real/('sec-metrics-sec-rate-'+str(os.getuid()))

    def redirect_system_tmp(self,path):
        return self.alias if path=='/tmp' else Path(path)

    def test_system_alias_uses_same_physical_uid_gate_and_preserves_wait(self):
        with patch.object(acquisition,'Path',side_effect=self.redirect_system_tmp), \
             patch.object(acquisition.time,'time',side_effect=[100.0,100.25,101.0]), \
             patch.object(acquisition.time,'sleep') as sleep:
            with acquisition.rate_scope():pass
            with acquisition.rate_scope():pass
        self.assertTrue((self.rate/'last-request.json').is_file())
        self.assertEqual(sleep.call_args.args,(0.75,))
        self.assertEqual(self.alias.resolve(),self.real)

    def test_child_rate_directory_alias_is_still_rejected(self):
        target=self.root/'other';target.mkdir();self.rate.symlink_to(target,target_is_directory=True)
        with patch.object(acquisition,'Path',side_effect=self.redirect_system_tmp), \
             self.assertRaisesRegex(ValueError,'LOCAL_SEC_RATE_ALIAS'):
            with acquisition.rate_scope():self.fail('Must reject a replaced user gate')

    def test_same_uid_and_system_location_remain_shared_across_aliases_and_tmpdir(self):
        second=self.root/'second-system-alias';second.symlink_to(self.real,target_is_directory=True)
        with patch.object(acquisition,'Path',side_effect=[self.alias,second]), \
             patch.dict(os.environ,{'TMPDIR':str(self.root/'unrelated-tmp')}), \
             patch.object(acquisition.time,'time',side_effect=[100.0,100.25,101.0]), \
             patch.object(acquisition.time,'sleep') as sleep:
            with acquisition.rate_scope():pass
            with acquisition.rate_scope():pass
        sleep.assert_called_once_with(0.75)
        self.assertEqual(len(list(self.real.iterdir())),1)

    def test_wrong_uid_owner_is_still_rejected(self):
        original=Path.stat
        def different_owner(path,*args,**kwargs):
            record=original(path,*args,**kwargs)
            if path==self.rate:
                values=list(record);values[4]=os.getuid()+1;return os.stat_result(values)
            return record
        with patch.object(acquisition,'Path',side_effect=self.redirect_system_tmp), \
             patch.object(Path,'stat',different_owner), \
             self.assertRaisesRegex(ValueError,'LOCAL_SEC_RATE_OWNER_CHANGED'):
            with acquisition.rate_scope():self.fail('Wrong owner must not get a lock')
