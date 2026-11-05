# Git Worktree Inspector

A local, read-only worktree inventory for agents and developers. Inspect registered worktrees, Git-visible changes and conflicts, local upstream divergence, and optionally compare committed trees. The same Python implementation powers the CLI and API. A separate skill explains how agents should interpret it.

## Install the CLI and Python API

Requirements: Python 3.9+, Git supporting `worktree list --porcelain -z` and `rev-parse --path-format=absolute`, and a copy of this source directory. No third-party runtime dependency or hosted service is required. Builds require setuptools; see `pyproject.toml`. The offline packaging test additionally needs `pip`, `setuptools` and `wheel` already installed.

Install from GitHub into your chosen Python environment:

```sh
python3 -m pip install "git+https://github.com/yuanhaorannnnnn/git-worktree-inspector.git"
git-worktree-inspector --version
git-worktree-inspector /path/to/repository --base main
```

Alternatively, without installing, run from the source directory:

```sh
python3 -B -m git_worktree_inspector /path/to/repository
```

The CLI/API is installed from GitHub; there is no PyPI or npm package for this project. Installation of the CLI/API is separate from installation of the skill.

## Give an agent the skill

The distributable skill is [`skills/git-worktree-inspector/SKILL.md`](skills/git-worktree-inspector/SKILL.md). For example, from the target project, the `skills` installer can install it from a local source directory:

```sh
npx skills add yuanhaorannnnnn/git-worktree-inspector --skill git-worktree-inspector --agent codex
```

Alternatively, copy that skill directory to the target agent's skill location. Follow that agent's instructions for discovery/reload. The skill is an instruction file; it does not install the CLI or its Python/Git prerequisites.

To install from an existing local source directory, replace the repository name with that directory path.

## Use the result

The CLI emits versioned JSON. Check process status, `complete`, `errors`, and each worktree's `snapshot_stable` before interpreting data. Local refs are not live remote verification; Git-visible cleanliness excludes ignored files. Equal committed trees do not include uncommitted changes. Task ownership, active writers and safe-to-remove state are not determined. Output can contain sensitive local paths and filenames.

[CLI and Python API reference](docs/api.md) covers options, exit codes, response fields and limits.

## Tests

```sh
python3 -B -m unittest discover -s tests -v
```

Tests create temporary local Git repositories and do not access the network. Bare repositories are unsupported; supported unborn worktrees report a null HEAD. Observations are non-atomic and do not authorize writes or closeout actions.

## License

Apache License 2.0. See [LICENSE](LICENSE). Git and Python remain separately licensed dependencies and are not bundled.
