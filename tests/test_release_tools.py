"""Portable tooling and release gates; no repositories/services are created."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.check import check
from tools.repository import git_context
from tools.review_archive import build_archive, check_completeness, collect_files, source_digest
from tools.security_audit import audit
from tools.verify import release_gate, run_verification

ROOT = Path(__file__).resolve().parents[1]


class ReleaseToolTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root/'.env.example').write_text('KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092\n')
        (self.root/'README.md').write_text('test source\n')

    def test_no_git_does_not_use_parent_or_environment_repository(self):
        with patch('tools.repository.git_output', side_effect=AssertionError('Git must not run')):
            self.assertEqual(git_context(self.root)['status'], 'NOT_RUN')
            result = audit(self.root)
            self.assertEqual(result['git_history']['status'], 'NOT_RUN')
            self.assertIsNone(result['unique_git_blobs_scanned'])
            self.assertIsNone(result['sensitive_tracked_paths'])
            self.assertIn('INCOMPLETE', result['security_clearance'])
            self.assertEqual(check(self.root)['git_whitespace'], 'NOT_RUN')

    def test_corrupt_metadata_is_incomplete(self):
        (self.root/'.git').mkdir()
        with patch('tools.repository.git_output', side_effect=OSError('invalid')):
            self.assertEqual(git_context(self.root)['status'], 'INCOMPLETE')

    def test_repository_context_and_history_are_actually_requested(self):
        (self.root/'.git').mkdir()
        with patch('tools.repository.git_output', side_effect=[str(self.root).encode(), b'head']):
            self.assertEqual(git_context(self.root), dict(status='AVAILABLE', head='head'))
        context = dict(status='AVAILABLE', head='head')
        with patch('tools.security_audit.git_context', return_value=context), \
                patch('tools.security_audit.git_output', side_effect=[b'oid README.md\n', b'blob\n',
                                                                     b'safe source', b'README.md\n']) as git:
            result = audit(self.root)
        self.assertEqual(result['git_history']['status'], 'COMPLETED')
        self.assertEqual(result['unique_git_blobs_scanned'], 1)
        self.assertEqual(git.call_count, 4)

    def test_repository_check_keeps_git_diff_strict(self):
        with patch('tools.check.git_context', return_value=dict(status='AVAILABLE')), \
                patch('tools.check.git_output', side_effect=subprocess.CalledProcessError(2, 'git')):
            with self.assertRaises(subprocess.CalledProcessError):
                check(self.root)

    def test_archive_contains_safe_example_and_complete_hash_inventory(self):
        for name in ('ai_op/new.py', 'tests/new.py', 'docs/new.md', '.github/new.yaml',
                     'extra.cfg', 'runtime/wal.log', 'data/private.csv', 'tools/__pycache__/bad.py'):
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# fixture\n')
        (self.root/'.env').write_text('not an example\n')
        result = build_archive(self.root)
        with tarfile.open(self.root/result['archive']) as archive:
            names = archive.getnames()
            self.assertIn('.env.example', names)
            for name in ('ai_op/new.py', 'tests/new.py', 'docs/new.md', '.github/new.yaml', 'extra.cfg'):
                self.assertIn(name, names)
            for name in ('runtime/wal.log', 'data/private.csv', 'tools/__pycache__/bad.py', '.env'):
                self.assertNotIn(name, names)
            for line in archive.extractfile('review_artifacts/SHA256SUMS.txt').read().decode().splitlines():
                digest, path = line.split('  ', 1)
                self.assertEqual(hashlib.sha256(archive.extractfile(path).read()).hexdigest(), digest)
        self.assertEqual(result['coverage']['status'], 'NOT_RUN')

    def test_unsafe_example_is_not_packaged(self):
        (self.root/'.env.example').write_text('API_KEY=unreviewed-value\n')
        with self.assertRaisesRegex(ValueError, 'loopback placeholder'):
            build_archive(self.root)

    def test_changed_untracked_file_coverage_cannot_be_silently_omitted(self):
        path = self.root/'new.yaml'
        path.write_text('safe: true\n')
        with patch('tools.review_archive.git_context', return_value=dict(status='AVAILABLE')), \
                patch('tools.review_archive.git_output', side_effect=[b'README.md\0', b'new.yaml\0']):
            with self.assertRaisesRegex(ValueError, 'missing relevant changes'):
                check_completeness(self.root, [Path('README.md')])
        with patch('tools.review_archive.git_context', return_value=dict(status='AVAILABLE')), \
                patch('tools.review_archive.git_output', side_effect=[b'README.md\0', b'new.yaml\0']):
            self.assertEqual(check_completeness(self.root, collect_files(self.root))['status'], 'COMPLETED')

    def test_symlink_is_not_followed_into_archive(self):
        path = self.root/'tools/link.py'
        path.parent.mkdir()
        path.symlink_to(self.root/'README.md')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            collect_files(self.root)

    def test_release_requires_history_and_bound_owner_review(self):
        security = audit(self.root)
        gate = release_gate(security, self.root)
        self.assertEqual(gate['status'], 'BLOCKED')
        self.assertEqual(len(gate['reasons']), 2)
        security['git_history'] = dict(status='COMPLETED', head='test-head')
        self.assertEqual(release_gate(security, self.root)['status'], 'BLOCKED')
        review = self.root/'owner-review.json'
        review.write_text(json.dumps(dict(approved=True, reviewer='test fixture owner',
                                         head='test-head', source_sha256=source_digest(self.root))))
        self.assertEqual(release_gate(security, self.root, review)['status'], 'SATISFIED')
        (self.root/'README.md').write_text('changed after review\n')
        self.assertEqual(release_gate(security, self.root, review)['status'], 'BLOCKED')

    def test_verification_portable_mode_and_strict_gate(self):
        # Exercise orchestration without recursively invoking this test suite.
        result = SimpleNamespace(testsRun=3, failures=[], errors=[], skipped=[], wasSuccessful=lambda: True)
        for release in (False, True):
            with patch('tools.verify._run_unit_tests', return_value=(result, 'fixture test runner\n', 0)), \
                    patch('tools.verify.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')), \
                    patch('tools.verify.run_demo', return_value={'fixture': True}), \
                    patch('tools.verify.benchmark', return_value={'fixture': True}), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = run_verification(self.root, release=release)
            report = json.loads((self.root/'docs/verification/results.txt').read_text())
            self.assertEqual(code, 1 if release else 0)
            self.assertEqual(report['git_history']['status'], 'NOT_RUN')
            self.assertIn('INCOMPLETE', report['security_clearance'])
            self.assertFalse(report['release_review']['publication_authorized'])

    def test_actual_archive_style_syntax_import_and_security_commands(self):
        for relative in collect_files(ROOT):
            destination = self.root/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/relative, destination)
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        env['PYTHONPATH'] = ''
        process = subprocess.run([sys.executable, '-B', '-m', 'tools.check'], cwd=self.root,
                                 capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn('Git metadata: NOT_RUN', process.stdout)
        process = subprocess.run([sys.executable, '-B', '-m', 'tools.security_audit'], cwd=self.root,
                                 capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)['git_history']['status'], 'NOT_RUN')
