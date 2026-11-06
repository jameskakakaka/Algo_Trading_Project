"""Explicit Git boundary: a source extraction must not inherit a parent repo."""
import os
from pathlib import Path
import subprocess


def git_output(root, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    return subprocess.run(['git', '-C', str(Path(root).resolve()), *args], env=env,
                          capture_output=True, check=True).stdout


def git_context(root):
    root = Path(root).resolve()
    if not (root / '.git').exists():
        return dict(status='NOT_RUN', reason='No .git metadata at source root; history unavailable')
    try:
        toplevel = Path(git_output(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
        if toplevel != root:
            return dict(status='INCOMPLETE', reason='Git root does not match source root')
        head = git_output(root, 'rev-parse', '--verify', 'HEAD').decode().strip()
        return dict(status='AVAILABLE', head=head)
    except (OSError, subprocess.CalledProcessError):
        return dict(status='INCOMPLETE', reason='Git metadata/HEAD could not be inspected')
