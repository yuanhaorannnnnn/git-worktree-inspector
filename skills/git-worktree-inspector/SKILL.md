---
name: git-worktree-inspector
description: Inspect local Git worktrees, uncommitted changes, conflicts and local upstream divergence using the read-only git-worktree-inspector CLI. Use when an agent needs a structured worktree inventory; it does not infer ownership or perform Git closeout.
---

# Git Worktree Inspector

Use the installed `git-worktree-inspector` CLI for local, read-only worktree observations. It requires Python and Git; installing this skill alone does not install the CLI.

1. Check `git-worktree-inspector --version` and `git-worktree-inspector --help`. If unavailable, report the missing CLI. Installation instructions are in https://github.com/yuanhaorannnnnn/git-worktree-inspector; the skill does not install the CLI.
2. Run `git-worktree-inspector /path/to/repository` and add `--base <local-ref>` only when a specific committed baseline is relevant. Never substitute an assumed branch for the user's intended baseline.
3. Parse JSON stdout. Exit 0 means collection completed; exit 2 means partial or unstable; exit 1 means invalid input or repository. Argument-parser errors use stderr. Check `schema_version`, `complete`, `errors` and each worktree's `snapshot_stable` before relying on the result.
4. Explain `git_status`, `has_conflicts`, upstream state and optional committed-tree comparison as separate facts. `committed_trees_equal` does not cover uncommitted or ignored files. `ahead_commits` and divergence compare local refs only; they do not prove remote publication.

`task_ownership` and `active_writer` are unknown. Ignored files are not inspected and the snapshot is non-atomic. Do not infer that a worktree is unused or safe to remove, merge, reset, or publish. Do not treat tool use as authorization for a write. Paths and filenames can be sensitive; avoid sharing raw JSON unless appropriate to the request.
