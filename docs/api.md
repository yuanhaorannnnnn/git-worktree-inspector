# CLI and Python API — package 0.1.0 / JSON schema 1.0.0

## CLI

```
git-worktree-inspector --version
git-worktree-inspector --help
git-worktree-inspector REPOSITORY [--base REF] [--timeout SECONDS]
```

`REPOSITORY` may be a worktree path or a directory inside one. `--base` is an optional locally resolvable commit or ref used for committed-tree comparison; it has no default. `--timeout` is the timeout for **each** Git command, in seconds, and defaults to 30. This is not a whole-run time limit.

On success or an operational error, stdout is JSON. Exit `0`: complete; `2`: one or more worktrees failed or changed during observation; `1`: invalid repository, base or configuration. CLI argument parsing errors are reported by argparse on stderr. A consumer must check `complete` and `errors`, including per-worktree errors; process success does not prove the repo has no dirty files.

## Python

```python
from git_worktree_inspector import GitError, SCHEMA_VERSION, __version__, inspect

try:
    result = inspect('/path/to/repository', base='main', timeout=30)
except (GitError, ValueError) as exc:
    print(f'Unable to inspect: {exc}')
else:
    if not result['complete']:
        print('Partial observation:', result['errors'])
    for worktree in result['worktrees']:
        print(worktree['path'], worktree['git_visible_clean'])
```

A returned dictionary is equivalent to the CLI JSON. Invalid root, missing Git or invalid base raises `GitError`; invalid timeout raises `ValueError`. Individual worktree failures are returned in `errors`, not raised as a whole-repository error. `SCHEMA_VERSION` describes output shape, independent of the package version `__version__`.

## Interpretation

- `repository.root`, `git_common_dir`: observed local repository identity. Each worktree's common directory is checked against it.
- `worktrees[].git_status`: Git porcelain XY codes, including original path for renames. `git_visible_clean` excludes ignored files; `has_conflicts` covers unmerged index entries only.
- `upstream.state`: `configured`, `not_configured`, `detached`, or `unborn`. An unresolvable configured upstream returns a worktree error. For a configured upstream, `ahead_commits` contains exact commit IDs relative to its locally recorded commit; for detached/no-upstream worktrees it lists commits not found in local remote-tracking refs. These are not live remote checks.
- `comparison`: optional pinned base and HEAD commit/tree IDs, committed divergence and `committed_trees_equal`. This does not compare uncommitted or ignored files. For an unborn HEAD it is `null`.
- `task_ownership` and `active_writer` are `unknown`; ignored files are `not_inspected`. `snapshot_stable` checks HEAD and Git status twice but is not an atomic file snapshot or proof of writer inactivity.

## Boundaries

No fetch, remote verification, worktree modification, cleanup, submission, ownership inference, or closeout decision is performed. Bare repositories are unsupported. An unborn worktree is supported only when no local or remote refs exist. Output contains local paths and filenames; treat it as potentially sensitive. Git failures, timeout, unavailable worktrees, inconsistent state and partial results are not evidence that a worktree is clean.
