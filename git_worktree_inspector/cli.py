"""Machine-readable command-line entry point."""
import argparse
import json
import sys
from .core import GitError, SCHEMA_VERSION, inspect
from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspect local Git worktrees without modifying them.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('repository', help='Path within a non-bare Git worktree')
    parser.add_argument('--base', help='Optional local Git commit/ref for committed-tree comparison')
    parser.add_argument('--timeout', type=float, default=30, help='Timeout in seconds per Git command (default 30)')
    args = parser.parse_args()
    try:
        result = inspect(args.repository, base=args.base, timeout=args.timeout)
    except (GitError, ValueError) as exc:
        print(json.dumps({'schema_version': SCHEMA_VERSION, 'complete': False, 'error': str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['complete'] else 2
