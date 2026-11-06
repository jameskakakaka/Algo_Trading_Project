"""Allowlisted source review bundle, with completeness and SHA-256 inventories."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

from tools.repository import git_context, git_output
from tools.security_audit import inspect_bytes

PROJECT_DIRS = ('schemas', 'ingestion', 'storage_engine', 'streaming', 'ai_op',
                'execution_engine', 'tools', 'tests', 'docs', 'docker', '.github')
SUFFIXES = {'.py', '.md', '.toml', '.yml', '.yaml', '.txt', '.ini', '.cfg'}
ROOT_FILES = {'README.md', 'LICENSE', 'pyproject.toml', '.gitignore', '.gitattributes', '.env.example'}
EXCLUDED_PARTS = {'.git', '__pycache__', '.aws', '.codex', '.agents', '.venv', 'venv',
                  'node_modules', 'data', 'datasets', 'runtime', 'artifacts', 'secrets',
                  'credentials', 'review_artifacts', '.pytest_cache', '.ruff_cache'}


def _relevant(path):
    return (not EXCLUDED_PARTS.intersection(path.parts)
            and path.name != 'PHASE2D_TEST_OUTPUT.txt'
            and not (path.name.startswith('.env') and path != Path('.env.example'))
            and ((len(path.parts) == 1 and (path.name in ROOT_FILES or path.suffix in SUFFIXES))
                 or (path.parts[0] in PROJECT_DIRS and path.suffix in SUFFIXES)))


def validate_env_example(path):
    """Only the reviewed, credential-free loopback example is allowed."""
    data = path.read_bytes()
    assignments = [line.strip() for line in data.decode('utf-8').splitlines()
                   if line.strip() and not line.lstrip().startswith('#')]
    if assignments not in (['KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:9092'],
                           ['KAFKA_BOOTSTRAP_SERVERS=localhost:9092']):
        raise ValueError('.env.example must contain only the reviewed loopback placeholder')
    findings = []
    inspect_bytes(data, '.env.example', findings)
    if findings:
        raise ValueError('.env.example needs security review before inclusion')


def collect_files(root, *, include_evidence=True):
    root = Path(root).resolve()
    files = set()
    candidates = [p for directory in PROJECT_DIRS for p in (root/directory).rglob('*')]
    candidates += list(root.iterdir())
    for path in candidates:
        relative = path.relative_to(root)
        if not path.is_file() or not _relevant(relative):
            continue
        if not include_evidence and relative.parts[:2] == ('docs', 'verification'):
            continue
        if any(part.is_symlink() for part in [path, *path.parents] if part != root):
            raise ValueError(f'symlink requires explicit archive review: {relative}')
        files.add(relative)
    if Path('.env.example') not in files:
        raise ValueError('required safe configuration example missing')
    validate_env_example(root/'.env.example')
    return sorted(files)


def source_digest(root):
    """Bind owner review to source/config/docs, excluding generated evidence."""
    root = Path(root)
    inventory = [(str(p), hashlib.sha256((root/p).read_bytes()).hexdigest())
                 for p in collect_files(root, include_evidence=False)]
    return hashlib.sha256(json.dumps(inventory, separators=(',', ':')).encode()).hexdigest()


def check_completeness(root, files):
    context = git_context(root)
    if context['status'] != 'AVAILABLE':
        return dict(status='NOT_RUN', reason='Git change inventory unavailable; full allowlist collected')
    raw = git_output(root, 'diff', '--name-only', '-z', 'HEAD')
    raw += git_output(root, 'ls-files', '--others', '--exclude-standard', '-z')
    changed = {Path(name.decode()) for name in raw.split(b'\0') if name}
    expected = {p for p in changed if _relevant(p) and (Path(root)/p).is_file()}
    missing = sorted(str(p) for p in expected-set(files))
    if missing:
        raise ValueError('archive missing relevant changes: ' + ', '.join(missing))
    return dict(status='COMPLETED', relevant_changed_files=len(expected), missing=[])


def build_archive(root, *, name='final-release-review'):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', name):
        raise ValueError('archive name must be a simple basename')
    root = Path(root).resolve()
    output = root/'review_artifacts'
    output.mkdir(exist_ok=True)
    files = collect_files(root)
    coverage = check_completeness(root, files)
    # Refuse known credential patterns in selected content. Personal-path findings
    # remain review items; scanner regex definitions are not credentials.
    findings = []
    for path in files:
        inspect_bytes((root/path).read_bytes(), str(path), findings)
    if any(item['category'] != 'personal_path' for item in findings):
        raise ValueError('credential-pattern findings require review; archive not created')
    context = git_context(root)
    if context['status'] == 'AVAILABLE':
        status = git_output(root, 'status', '--short').decode()
        diff = git_output(root, 'diff', '--stat', 'HEAD').decode()
    else:
        status = 'NOT RUN: source has no usable Git metadata; history/change review INCOMPLETE\n'
        diff = ''
    summary = Path('review_artifacts/CHANGE_SUMMARY.md')
    (root/summary).write_text('# Review change inventory\n\n'
        'Owner review required; no security clearance or release approval is implied.\n\n'
        'Archive coverage: '+json.dumps(coverage)+'\n\n```text\n'+status+'\n'+diff+'```\n\n'
        'All project files are listed in MANIFEST.txt; SHA256SUMS.txt also covers the manifest.\n')
    files.append(summary)
    inventory = [dict(path=str(p), bytes=(root/p).stat().st_size,
                      sha256=hashlib.sha256((root/p).read_bytes()).hexdigest()) for p in files]
    manifest = Path('review_artifacts/MANIFEST.txt')
    (root/manifest).write_text(json.dumps(inventory, indent=2)+'\n')
    sums = Path('review_artifacts/SHA256SUMS.txt')
    (root/sums).write_text(''.join(hashlib.sha256((root/p).read_bytes()).hexdigest()+'  '+str(p)+'\n'
                                 for p in files+[manifest]))
    archive = output/(name+'.tar.gz')
    members = files+[manifest, sums]
    with tarfile.open(archive, 'w:gz') as bundle:
        for path in members:
            bundle.add(root/path, arcname=str(path), recursive=False)
    with tarfile.open(archive) as bundle:
        names = bundle.getnames()
        if len(names) != len(set(names)) or set(names) != {str(p) for p in members}:
            raise RuntimeError('archive member inventory mismatch')
        for member in bundle.getmembers():
            if not member.isfile() or '..' in Path(member.name).parts or Path(member.name).is_absolute():
                raise RuntimeError('unsafe archive member')
        for line in (root/sums).read_text().splitlines():
            digest, path = line.split('  ', 1)
            if hashlib.sha256(bundle.extractfile(path).read()).hexdigest() != digest:
                raise RuntimeError('archive hash mismatch')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/(name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
    return dict(archive=str(archive.relative_to(root)), members=len(members),
                bytes=archive.stat().st_size, sha256=digest, coverage=coverage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='final-release-review')
    args = parser.parse_args()
    print(json.dumps(build_archive(Path.cwd(), name=args.name), indent=2))


if __name__ == '__main__':
    main()
