"""Dependency-free syntax, whitespace and recommended/legacy import smoke check."""
import ast
import importlib
from pathlib import Path
from tools.repository import git_context, git_output

PACKAGES = ('schemas', 'ingestion', 'storage_engine', 'streaming', 'ai_op', 'execution_engine', 'tools')


def check(root=None):
    root = Path(root or Path.cwd()).resolve()
    count = 0
    for package in PACKAGES:
        for path in sorted((root / package).rglob('*.py')):
            ast.parse(path.read_text(), filename=str(path))
            importlib.import_module('.'.join(path.relative_to(root).with_suffix('').parts))
            count += 1
    context = git_context(root)
    if context['status'] == 'AVAILABLE':
        git_output(root, 'diff', '--check', 'HEAD')
        whitespace = 'COMPLETED'
    else:
        whitespace = 'NOT_RUN'
    return dict(modules=count, git_whitespace=whitespace, git=context)


def main():
    result = check()
    count = result['modules']
    print(f'Parsed and imported {count} modules without optional dependencies or application startup')
    print(f"Git whitespace: {result['git_whitespace']}; Git metadata: {result['git']['status']}")


if __name__ == '__main__':
    main()
