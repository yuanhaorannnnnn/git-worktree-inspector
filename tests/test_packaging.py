"""Exercise source packaging with the peer skills/ directory present."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackagingTest(unittest.TestCase):
    def test_offline_build_and_installed_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'source', root / 'site'
            source.mkdir()
            for name in ('pyproject.toml', 'README.md'):
                shutil.copy2(ROOT / name, source / name)
            for name in ('git_worktree_inspector', 'skills', 'docs'):
                shutil.copytree(ROOT / name, source / name,
                                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            install = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index',
                                      '--no-deps', '--no-build-isolation', '--target', str(target), str(source)],
                                     capture_output=True, text=True, timeout=90)
            self.assertEqual(install.returncode, 0, install.stderr)
            env = os.environ.copy()
            env['PYTHONPATH'] = str(target)
            probe = subprocess.run([sys.executable, '-B', '-m', 'git_worktree_inspector', '--version'],
                                   cwd=root, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertTrue(probe.stdout.strip().endswith('0.1.0'))


if __name__ == '__main__':
    unittest.main()
