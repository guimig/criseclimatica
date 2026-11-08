import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_refresh import refresh_needed, main, KIND

NOW=datetime(2026,11,8,14,tzinfo=timezone.utc)


class RefreshScheduleTests(unittest.TestCase):
    def sample(self,age=10):
        return {'schema_version':1,'kind':KIND,'generated_at':(NOW-timedelta(minutes=age)).isoformat(),
                'valid_until':(NOW+timedelta(hours=2)).isoformat()}

    def test_fresh_publication_skips_but_missed_triggers_are_reconciled(self):
        self.assertFalse(refresh_needed(self.sample(),NOW))
        self.assertTrue(refresh_needed(self.sample(35),NOW))
        self.assertTrue(refresh_needed(self.sample(300),NOW))

    def test_missing_invalid_synthetic_or_expired_never_skip(self):
        for d in [None,{},self.sample(-11),{**self.sample(),'fixture_mode':True},
                  {**self.sample(),'generated_at':'2026-11-08T13:55:00'},
                  {**self.sample(),'valid_until':NOW.isoformat()}]:
            with self.subTest(data=d):self.assertTrue(refresh_needed(d,NOW))

    def test_failed_probe_collects_and_force_does_not_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'output'
            with patch('sys.argv',['check_refresh','--github-output',str(path)]), patch('check_refresh.urlopen',side_effect=OSError('network')):
                main()
            self.assertEqual(path.read_text(),'refresh=true\n')
            path.unlink()
            with patch('sys.argv',['check_refresh','--force','true','--github-output',str(path)]),patch('check_refresh.urlopen') as fetch:
                main();fetch.assert_not_called()
            self.assertEqual(path.read_text(),'refresh=true\n')

    def test_successful_fresh_probe_outputs_skip(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'output'
            response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps(self.sample()).encode()
            with patch('sys.argv',['check_refresh','--github-output',str(path)]),patch('check_refresh.urlopen',return_value=response),patch('check_refresh.datetime') as clock:
                clock.now.return_value=NOW;clock.fromisoformat.side_effect=datetime.fromisoformat
                main()
            self.assertEqual(path.read_text(),'refresh=false\n')


if __name__=='__main__':unittest.main()
