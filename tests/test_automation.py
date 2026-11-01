import datetime as dt
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import automation as a

class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime.fromisoformat('2026-11-01T10:00:00+00:00')
        self.report={'generated_at':'2026-11-01T06:00:00+00:00','channels':10,'programmes':100,'xml_sha256':'abc','gz_sha256':'def'}
        self.release={'assets':[
            {'name':'Sport.xml','size':100,'updated_at':'2026-11-01T06:01:00Z','digest':'sha256:abc'},
            {'name':'Sport.xml.gz','size':50,'updated_at':'2026-11-01T06:02:00Z','digest':'sha256:def'},
            {'name':'status.json','size':30,'updated_at':'2026-11-01T06:03:00Z'}]}
    def test_current_complete_release_skips(self):
        self.assertTrue(a.complete_release(self.report,self.release,self.now))
    def test_friday_release_is_due_on_sunday(self):
        self.report['generated_at']='2026-10-30T06:00:00+00:00'
        self.assertFalse(a.complete_release(self.report,self.release,self.now))
    def test_missed_sunday_catches_up_on_monday(self):
        self.assertEqual(a.due_date(dt.datetime.fromisoformat('2026-11-02T12:00:00+00:00')),dt.date(2026,11,1))
    def test_month_and_year_boundary(self):
        for day in (dt.date(2026,11,1),dt.date(2026,12,31),dt.date(2027,1,1),dt.date(2027,3,29)):
            now=dt.datetime.combine(day,dt.time(12),dt.timezone.utc)
            due=a.due_date(now)
            self.assertIn((day-due).days,(0,1))
            self.assertEqual((due-a.ANCHOR).days%2,0)
    def test_before_first_slot_does_not_require_today(self):
        self.assertEqual(a.due_date(dt.datetime.fromisoformat('2026-11-01T04:00:00+00:00')),dt.date(2026,10,30))
    def test_partial_publication_is_not_current(self):
        self.release['assets'][1]['updated_at']='2026-10-30T06:02:00Z'
        self.assertFalse(a.complete_release(self.report,self.release,self.now))
    def test_hash_mismatch_is_not_current(self):
        self.release['assets'][1]['digest']='sha256:wrong'
        self.assertFalse(a.complete_release(self.report,self.release,self.now))
    def test_success_marker_older_than_upload_is_not_current(self):
        self.release['assets'][0]['updated_at']='2026-11-01T06:04:00Z'
        self.assertFalse(a.complete_release(self.report,self.release,self.now))
    def test_missing_legacy_gzip_hash_rebuilds_once(self):
        del self.report['gz_sha256']
        self.assertFalse(a.complete_release(self.report,self.release,self.now))
    def test_upload_failure_restores_backup_including_marker_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in a.ASSETS:(root/name).write_text('new')
            uploads=[]
            def fake_gh(*args,**kwargs):
                if args[:2]==('release','download'):
                    dest=Path(args[args.index('--dir')+1]);name=args[args.index('--pattern')+1];(dest/name).write_text('old')
                return b''
            def fake_upload(repo,directory,name):
                uploads.append((directory==root,name))
                if directory==root and name=='Sport.xml.gz':raise RuntimeError('upload failed')
            with patch.object(a,'release_info',return_value=self.release),patch.object(a,'gh',side_effect=fake_gh),patch.object(a,'upload',side_effect=fake_upload),patch.object(a,'verify'):
                with self.assertRaises(RuntimeError):a.publish('owner/repo',root)
            self.assertEqual(uploads[-3:],[(False,n) for n in a.ASSETS])

if __name__=='__main__':unittest.main()
