"""Local Git worktree inspection for agent tools."""
from .core import GitError, SCHEMA_VERSION, inspect

__version__ = '0.1.0'

__all__ = ['GitError', 'SCHEMA_VERSION', '__version__', 'inspect']
