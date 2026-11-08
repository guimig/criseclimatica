"""Regression for safe destination checks and rollback before replacing output."""
import sys
import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'src')]
from build_site import build,checked_output,replace_output
from validate_site import validate


class BuildTransactionTests(unittest.TestCase):
    def test_source_and_parent_destinations_are_rejected_before_collection(self):
        for target in [ROOT,ROOT.parent,ROOT/'src',ROOT/'web'/'nested',ROOT/'.git']:
            with self.subTest(target=target),patch('build_site.collect') as collect:
                with self.assertRaises(ValueError):build(target)
                collect.assert_not_called()

    def test_file_and_symbolic_link_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'file';file.write_text('keep')
            link=Path(directory)/'linked';link.symlink_to(ROOT,target_is_directory=True)
            for target in [file,link]:
                with self.assertRaises(ValueError):checked_output(target)
            self.assertEqual(file.read_text(),'keep')
            self.assertTrue(link.is_symlink())

    def test_failed_directory_swap_restores_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'dist';output.mkdir();(output/'index.html').write_text('previous')
            staged=root/'transaction'/'site';staged.mkdir(parents=True);(staged/'index.html').write_text('new')
            original=Path.replace
            def fail_stage(path,target):
                if path==staged:raise OSError('simulated rename failure')
                return original(path,target)
            with patch.object(Path,'replace',fail_stage):
                with self.assertRaises(OSError):replace_output(staged,output)
            self.assertEqual((output/'index.html').read_text(),'previous')
            self.assertTrue(staged.is_dir())

    def test_invalid_artifact_never_replaces_existing_site(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'dist';output.mkdir();(output/'index.html').write_text('previous')
            with patch('build_site.validate_staged_site',side_effect=ValueError('invalid artifact')):
                with self.assertRaisesRegex(ValueError,'invalid artifact'):
                    build(output,fixture=ROOT/'tests/fixtures/open_meteo.json')
            self.assertEqual((output/'index.html').read_text(),'previous')
            self.assertEqual(sorted(p.name for p in output.iterdir()),['index.html'])

    def test_successful_repeated_build_replaces_only_valid_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'dist'
            for _ in range(2):
                build(output,fixture=ROOT/'tests/fixtures/open_meteo.json')
                self.assertTrue((output/'index.html').is_file())
                self.assertTrue((output/'data/dashboard.json').is_file())

    def test_missing_declared_script_blocks_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'dist';build(output,fixture=ROOT/'tests/fixtures/open_meteo.json')
            (output/'forecasts.js').unlink()
            with self.assertRaisesRegex(ValueError,'frontend asset'):
                validate(output,fixture=True)

    def test_publication_identity_is_shared_without_replacing_source_clocks(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'dist';build(output,fixture=ROOT/'tests/fixtures/open_meteo.json')
            overview=json.loads((output/'data/latest.json').read_text())
            for path in (output/'data').rglob('*.json'):
                payload=json.loads(path.read_text())
                self.assertEqual(payload['publication_at'],overview['generated_at'])
            model=json.loads((output/'data/places/araquari.json').read_text())
            self.assertNotEqual(model['current']['time'],model['publication_at'])

    def test_mixed_secondary_publication_blocks_artifact_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'dist';build(output,fixture=ROOT/'tests/fixtures/open_meteo.json')
            source=output/'data/cemaden.json';payload=json.loads(source.read_text())
            payload['publication_at']='2000-01-01T00:00:00Z';source.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,'Mixed publication artifact'):
                validate(output,fixture=True)


if __name__=='__main__':unittest.main()
