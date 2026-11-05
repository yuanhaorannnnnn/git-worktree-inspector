import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from git_worktree_inspector import inspect
import git_worktree_inspector.core as core


def git(repo, *args, check=True):
    return subprocess.run(['git', '-C', str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-b', 'main')
        git(self.repo, 'config', 'user.name', 'Test')
        git(self.repo, 'config', 'user.email', 'test@example.invalid')
        (self.repo / 'file.txt').write_text('base\n')
        git(self.repo, 'add', '.')
        git(self.repo, 'commit', '-m', 'base')
        self.worktree = Path(self.tmp.name) / 'work tree'
        git(self.repo, 'worktree', 'add', '-b', 'feature', str(self.worktree))

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self, **kwargs):
        result = inspect(str(self.repo), **kwargs)
        return result, {r['path']: r for r in result['worktrees']}

    def test_dirty_same_tree_different_history_and_upstream_absent(self):
        git(self.worktree, 'commit', '--allow-empty', '-m', 'empty')
        (self.worktree / 'file.txt').write_text('changed\n')
        (self.worktree / 'new file').write_text('new')
        result, rows = self.rows(base='main')
        self.assertTrue(result['complete'])
        row = rows[str(self.worktree)]
        self.assertFalse(row['git_visible_clean'])
        self.assertEqual({e['path'] for e in row['git_status']}, {'file.txt', 'new file'})
        self.assertTrue(row['comparison']['committed_trees_equal'])
        self.assertFalse(row['comparison']['includes_working_changes'])
        self.assertEqual(row['comparison']['head_only_commits'], 1)
        self.assertEqual(row['upstream']['state'], 'not_configured')
        self.assertEqual(row['task_ownership'], 'unknown')

    def test_upstream_pinned_ahead_behind(self):
        base = git(self.repo, 'rev-parse', 'HEAD').stdout.decode().strip()
        git(self.repo, 'remote', 'add', 'origin', 'https://example.invalid/example.git')
        git(self.repo, 'update-ref', 'refs/remotes/origin/main', base)
        git(self.repo, 'config', 'branch.feature.remote', 'origin')
        git(self.repo, 'config', 'branch.feature.merge', 'refs/heads/main')
        git(self.worktree, 'commit', '--allow-empty', '-m', 'ahead')
        result, rows = self.rows()
        self.assertTrue(result['complete'])
        upstream = rows[str(self.worktree)]['upstream']
        self.assertEqual((upstream['state'], upstream['ahead'], upstream['behind']), ('configured', 1, 0))
        self.assertEqual(upstream['commit'], base)

    def test_missing_configured_upstream_is_partial(self):
        git(self.repo, 'config', 'branch.feature.remote', 'origin')
        git(self.repo, 'config', 'branch.feature.merge', 'refs/heads/missing')
        result, rows = self.rows()
        self.assertFalse(result['complete'])
        self.assertIn('upstream', rows[str(self.worktree)]['error'])
        self.assertIsNone(rows[str(self.worktree)]['git_visible_clean'])

    def test_detached_and_different_tree(self):
        (self.worktree / 'other').write_text('other')
        git(self.worktree, 'add', '.')
        git(self.worktree, 'commit', '-m', 'other')
        git(self.worktree, 'checkout', '--detach')
        result, rows = self.rows(base='main')
        row = rows[str(self.worktree)]
        self.assertTrue(result['complete'])
        self.assertTrue(row['detached'])
        self.assertFalse(row['comparison']['committed_trees_equal'])
        self.assertEqual(row['upstream']['state'], 'detached')

    def test_rename_original_and_conflict(self):
        git(self.worktree, 'mv', 'file.txt', 'renamed file')
        _, rows = self.rows()
        entry = rows[str(self.worktree)]['git_status'][0]
        self.assertEqual((entry['path'], entry['original_path']), ('renamed file', 'file.txt'))
        git(self.worktree, 'reset', '--hard', 'HEAD')
        (self.worktree / 'file.txt').write_text('feature\n')
        git(self.worktree, 'commit', '-am', 'feature')
        (self.repo / 'file.txt').write_text('main\n')
        git(self.repo, 'commit', '-am', 'main')
        self.assertNotEqual(git(self.worktree, 'merge', 'main', check=False).returncode, 0)
        _, rows = self.rows()
        self.assertTrue(rows[str(self.worktree)]['has_conflicts'])
        self.assertEqual(rows[str(self.worktree)]['git_status'][0]['status'], 'UU')

    def test_unavailable_worktree_partial(self):
        import shutil
        shutil.rmtree(self.worktree)
        result, rows = self.rows()
        self.assertFalse(result['complete'])
        self.assertIsNone(rows[str(self.worktree)]['git_status'])
        self.assertIn('error', rows[str(self.worktree)])

    def test_change_during_observation_partial(self):
        original = core.read_status
        calls = 0
        def changed(path, timeout):
            nonlocal calls
            calls += 1
            value = original(path, timeout)
            if calls == 2:
                return value + [{'status': '??', 'path': 'appeared'}]
            return value
        with patch.object(core, 'read_status', changed):
            result, rows = self.rows()
        self.assertFalse(result['complete'])
        self.assertFalse(rows[str(self.repo)]['snapshot_stable'])

    def test_cli_error_json_no_personal_dependencies(self):
        proc = subprocess.run([sys.executable, '-B', '-m', 'git_worktree_inspector', str(self.repo), '--base', 'nonexistent'], cwd=ROOT, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        result = json.loads(proc.stdout)
        self.assertFalse(result['complete'])
        self.assertIn('error', result)

    def test_cli_version_available_without_repository(self):
        from git_worktree_inspector import __version__
        proc = subprocess.run([sys.executable, '-B', '-m', 'git_worktree_inspector', '--version'],
                              cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(proc.stdout.strip().endswith(__version__))


if __name__ == '__main__':
    unittest.main()
