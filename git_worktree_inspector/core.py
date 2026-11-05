"""Read-only Git worktree observation, independent of repository policy."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import subprocess
from typing import Any

SCHEMA_VERSION = '1.0.0'


class GitError(Exception):
    pass


def git(repo: str, *args: str, timeout: float = 30) -> bytes:
    env = os.environ.copy()
    env.update(GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GIT_PAGER='cat')
    command = ['git', '--no-optional-locks', '-c', 'core.fsmonitor=false', '-C', repo, *args]
    try:
        p = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           env=env, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(f'git execution failed: {exc}') from exc
    if p.returncode:
        detail = p.stderr.decode('utf-8', 'replace').strip()
        raise GitError(f'git {args[0]} failed ({p.returncode}): {detail}')
    return p.stdout


def decode(data: bytes) -> str:
    return os.fsdecode(data)


def resolve_commit(repo: str, ref: str, timeout: float) -> str:
    return git(repo, 'rev-parse', '--verify', '--end-of-options', ref + '^{commit}', timeout=timeout).decode('ascii').strip()


def common_dir(repo: str, timeout: float) -> str:
    result = git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir', timeout=timeout)
    return str(Path(decode(result.rstrip(b'\n'))).resolve())


def list_worktrees(repo: str, timeout: float) -> list[dict[str, Any]]:
    data = git(repo, 'worktree', 'list', '--porcelain', '-z', timeout=timeout)
    rows: list[dict[str, Any]] = []
    row: dict[str, Any] = {}
    for item in data.split(b'\0'):
        if not item:
            if row:
                rows.append(row)
                row = {}
            continue
        key, sep, value = item.partition(b' ')
        row[key.decode('ascii')] = decode(value) if sep else True
    if row:
        rows.append(row)
    return rows


def read_status(repo: str, timeout: float) -> list[dict[str, str]]:
    parts = git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all', timeout=timeout).split(b'\0')
    entries = []
    i = 0
    while i < len(parts) and parts[i]:
        record = parts[i]
        i += 1
        if len(record) < 4 or record[2:3] != b' ':
            raise GitError('malformed git status record')
        code = record[:2].decode('ascii')
        entry = {'status': code, 'path': decode(record[3:])}
        if 'R' in code or 'C' in code:
            if i >= len(parts) or not parts[i]:
                raise GitError('incomplete rename/copy status record')
            entry['original_path'] = decode(parts[i])
            i += 1
        entries.append(entry)
    return entries


def branch_upstream(repo: str, branch: str | None, timeout: float) -> dict[str, Any]:
    if not branch:
        return {'state': 'detached', 'ref': None, 'commit': None, 'ahead': None, 'behind': None}
    full = git(repo, 'for-each-ref', '--format=%(upstream)', branch, timeout=timeout).decode('utf-8', 'replace').strip()
    if not full:
        # Resolve configuration separately: a configured but missing ref must not look unconfigured.
        short = branch.removeprefix('refs/heads/')
        # rev-parse distinguishes an unset upstream from a configured but missing upstream.
        try:
            full = git(repo, 'rev-parse', '--symbolic-full-name', '@{upstream}', timeout=timeout).decode('utf-8', 'replace').strip()
        except GitError:
            # Inspect branch configuration without treating Git's not-found exit as success for other commands.
            p = subprocess.run(['git', '--no-optional-locks', '-C', repo, 'config', '--get', f'branch.{short}.remote'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0'), timeout=timeout)
            if p.returncode not in (0, 1):
                raise GitError('unable to read upstream configuration')
            if p.returncode == 0 and p.stdout.strip():
                return {'state': 'configured_unresolved', 'ref': None, 'commit': None, 'ahead': None, 'behind': None}
            return {'state': 'not_configured', 'ref': None, 'commit': None, 'ahead': None, 'behind': None}
    commit = resolve_commit(repo, full, timeout)
    return {'state': 'configured', 'ref': full, 'commit': commit, 'ahead': None, 'behind': None}


def comparison(repo: str, base_sha: str, head: str, timeout: float) -> dict[str, Any]:
    counts = git(repo, 'rev-list', '--left-right', '--count', base_sha + '...' + head, timeout=timeout).decode('ascii').split()
    base_tree = git(repo, 'rev-parse', base_sha + '^{tree}', timeout=timeout).decode('ascii').strip()
    head_tree = git(repo, 'rev-parse', head + '^{tree}', timeout=timeout).decode('ascii').strip()
    return {'base_commit': base_sha, 'head_commit': head, 'base_only_commits': int(counts[0]),
            'head_only_commits': int(counts[1]), 'base_tree': base_tree, 'head_tree': head_tree,
            'committed_trees_equal': base_tree == head_tree, 'includes_working_changes': False}


def inspect(repo: str, *, base: str | None = None, timeout: float = 30) -> dict[str, Any]:
    if timeout <= 0:
        raise ValueError('timeout must be positive')
    repo_path = str(Path(repo).resolve())
    root = decode(git(repo_path, 'rev-parse', '--show-toplevel', timeout=timeout).rstrip(b'\n'))
    root = str(Path(root).resolve())
    shared = common_dir(root, timeout)
    base_sha = resolve_commit(root, base, timeout) if base is not None else None
    listed = list_worktrees(root, timeout)
    rows, errors = [], []
    for item in listed:
        path = item.get('worktree')
        row: dict[str, Any] = {'path': path, 'branch': item.get('branch'), 'head': item.get('HEAD'),
            'detached': bool(item.get('detached')), 'locked': item.get('locked', False),
            'prunable': item.get('prunable', False), 'git_status': None, 'git_visible_clean': None,
            'has_conflicts': None, 'upstream': None, 'comparison': None, 'snapshot_stable': False,
            'active_writer': 'unknown', 'task_ownership': 'unknown', 'ignored_files': 'not_inspected'}
        try:
            if not isinstance(path, str):
                raise GitError('worktree record has no path')
            if common_dir(path, timeout) != shared:
                raise GitError('worktree Git common directory mismatch')
            enumerated_head = item.get('HEAD')
            unborn = isinstance(enumerated_head, str) and not enumerated_head.strip('0')
            if unborn:
                git(path, 'symbolic-ref', '-q', 'HEAD', timeout=timeout)
                if git(path, 'for-each-ref', '--format=%(refname)', 'refs/heads/', 'refs/remotes/', timeout=timeout).strip():
                    raise GitError('HEAD missing while local or remote refs exist')
                head = None
            else:
                head = resolve_commit(path, 'HEAD', timeout)
            if not unborn and head != enumerated_head:
                raise GitError('HEAD changed after worktree enumeration')
            before = read_status(path, timeout)
            upstream = ({'state': 'unborn', 'ref': None, 'commit': None, 'ahead': None, 'behind': None}
                        if unborn else branch_upstream(path, item.get('branch'), timeout))
            if upstream['state'] == 'configured_unresolved':
                raise GitError('configured upstream could not be resolved')
            if upstream['state'] == 'configured' and head is not None:
                counts = git(path, 'rev-list', '--left-right', '--count', upstream['commit'] + '...' + head, timeout=timeout).decode('ascii').split()
                upstream['behind'], upstream['ahead'] = int(counts[0]), int(counts[1])
                upstream['ahead_commits'] = git(path, 'rev-list', upstream['commit'] + '..' + head, timeout=timeout).decode('ascii').splitlines()
            elif head is not None:
                # A local-only result cannot establish remote publication.
                commits = git(path, 'rev-list', head, '--not', '--remotes', timeout=timeout).decode('ascii').splitlines()
                upstream['commits_not_in_local_remote_refs'] = len(commits)
                upstream['ahead_commits'] = commits
            else:
                upstream['ahead_commits'] = []
            cmp = comparison(root, base_sha, head, timeout) if base_sha and head else None
            after = read_status(path, timeout)
            if unborn:
                current_items = list_worktrees(root, timeout)
                end_entry = next((v for v in current_items if v.get('worktree') == path), None)
                end_head = None if end_entry and not str(end_entry.get('HEAD', '')).strip('0') else 'changed'
            else:
                end_head = resolve_commit(path, 'HEAD', timeout)
            stable = before == after and head == end_head
            conflicts = any(e['status'] in ('DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU') for e in before)
            row.update(head=head, git_status=before, git_visible_clean=not before, has_conflicts=conflicts,
                       upstream=upstream, comparison=cmp, snapshot_stable=stable)
            if not stable:
                errors.append({'path': path, 'error': 'HEAD or Git-visible status changed during observation'})
        except (GitError, ValueError, UnicodeError, subprocess.TimeoutExpired) as exc:
            row['error'] = str(exc)
            errors.append({'path': path, 'error': str(exc)})
        rows.append(row)
    return {'schema_version': SCHEMA_VERSION, 'observed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'repository': {'root': root, 'git_common_dir': shared},
            'base': {'requested': base, 'commit': base_sha} if base is not None else None,
            'worktrees': rows, 'errors': errors, 'complete': not errors,
            'limitations': ['Local refs only; no fetch or remote verification.',
                'Ignored files, active writers, ownership, and safe-to-remove state are not determined.',
                'Observations are non-atomic; unchanged status does not prove file contents or upstream did not change.']}
