"""Read-only heuristic current-tree/all-reachable-Git-blob inspection.

Only paths, categories and line numbers are reported, never matched values.
Not a credential revocation, vulnerability scan or exhaustive security proof.
"""
import json
from pathlib import Path
import re
import subprocess
from tools.repository import git_context, git_output

PATTERNS = {
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'aws_access_id': re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'github_token': re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'personal_path': re.compile(rb'(?:/home/[^/\s]+/|/Users/[^/\s]+/|[A-Z]:\\Users\\)'),
    'credential_literal': re.compile(rb'''(?i)(?:api[_-]?key|api[_-]?secret|password|access[_-]?token)\s*=\s*["'][A-Za-z0-9/+_=.-]{16,}["']'''),
}


def inspect_bytes(data, location, findings):
    for category, pattern in PATTERNS.items():
        for match in pattern.finditer(data):
            findings.append(dict(location=location, category=category,
                                 line=data[:match.start()].count(b'\n')+1))


def audit(root=None):
    root = Path(root or Path.cwd()).resolve()
    findings = []
    current = 0
    for directory in ('schemas', 'ingestion', 'storage_engine', 'streaming', 'ai_op',
                      'execution_engine', 'tools', 'tests', 'docs', 'docker', '.github'):
        for path in sorted((root / directory).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                inspect_bytes(path.read_bytes(), str(path.relative_to(root)), findings)
                current += 1
    for name in ('README.md', '.gitignore', '.env.example', 'pyproject.toml'):
        path = root / name
        if path.exists():
            inspect_bytes(path.read_bytes(), name, findings)
            current += 1
    seen = set()
    historical = None
    large = []
    history = git_context(root)
    suspicious = None
    if history['status'] == 'AVAILABLE':
        historical = 0
        try:
            for entry in git_output(root, 'rev-list', '--objects', '--all').splitlines():
                parts = entry.split(b' ', 1)
                if len(parts) != 2:
                    continue
                oid, raw_path = parts
                if oid in seen or git_output(root, 'cat-file', '-t', oid.decode()).strip() != b'blob':
                    continue
                seen.add(oid)
                data = git_output(root, 'cat-file', 'blob', oid.decode())
                location = 'git:' + oid.decode()[:12] + ':' + raw_path.decode(errors='replace')
                inspect_bytes(data, location, findings)
                historical += 1
                if len(data) > 1_000_000:
                    large.append(dict(location=location, bytes=len(data)))
            tracked = git_output(root, 'ls-files').decode().splitlines()
            suspicious = [p for p in tracked if Path(p).name == '.env' or p.endswith(
                ('.pem', '.key', '.pkl', '.parquet', '.csv', 'wal.log'))]
            history['status'] = 'COMPLETED'
        except (OSError, subprocess.CalledProcessError):
            history = dict(status='INCOMPLETE', reason='Git history scan failed; partial results only')
    local_env_files = []
    # Inspect ignored local env files too, without entering private metadata,
    # database, dependency or research-data directories. Never print values.
    import os
    for directory, directories, names in os.walk(root):
        directories[:] = [d for d in directories if d not in (
            '.git', '.aws', '.codex', '.agents', 'data', 'runtime', 'artifacts',
            'review_artifacts', '__pycache__', 'node_modules') and 'venv' not in d]
        for name in names:
            if name == '.env' or name.startswith('.env.') and name != '.env.example':
                path = Path(directory) / name
                if path.is_symlink():
                    continue
                location = str(path.relative_to(root))
                local_env_files.append(location)
                inspect_bytes(path.read_bytes(), location, findings)
    return dict(current_files_scanned=current, unique_git_blobs_scanned=historical,
                git_history=history, security_clearance='INCOMPLETE: heuristic scan; owner review required',
                findings=findings, large_historical_blobs=large, sensitive_tracked_paths=suspicious,
                local_env_files=local_env_files,
                limitations=['heuristic scan only; unreferenced Git objects excluded',
                             'runtime/private metadata directories excluded',
                             'dependency vulnerabilities not assessed; optional packages unavailable',
                             'Git author metadata requires owner review'])


def main():
    print(json.dumps(audit(), indent=2))


if __name__ == '__main__':
    main()
