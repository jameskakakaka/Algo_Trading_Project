"""Portable offline verification; --release additionally requires Git and owner review."""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest

from tools.benchmark import benchmark
from tools.demo import run_demo
from tools.review_archive import source_digest
from tools.security_audit import audit


def release_gate(security, root, owner_review=None):
    """An explicit local attestation is required; this does not publish anything.

    Owner JSON: approved=true, reviewer=<nonempty>, head=<actual HEAD>,
    source_sha256=<source_digest>. It is not an authenticated signature.
    """
    reasons = []
    history = security['git_history']
    if history['status'] != 'COMPLETED':
        reasons.append('Actual Git history verification is required')
    if any(f['category'] != 'personal_path' for f in security['findings']):
        reasons.append('Credential-pattern findings require resolution')
    if owner_review is None:
        reasons.append('Owner review attestation required; none was supplied')
    else:
        try:
            review = json.loads(Path(owner_review).read_text())
            if (review.get('approved') is not True or not isinstance(review.get('reviewer'), str)
                    or not review['reviewer'].strip()
                    or review.get('head') != history.get('head')
                    or review.get('source_sha256') != source_digest(root)):
                reasons.append('Owner review does not approve the current HEAD/source')
        except (OSError, ValueError, TypeError, AttributeError):
            reasons.append('Owner review attestation is unreadable or invalid')
    return dict(status='BLOCKED' if reasons else 'SATISFIED', reasons=reasons,
                publication_authorized=False)


def _run_unit_tests():
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover('tests')
    start = time.monotonic()
    with contextlib.redirect_stdout(io.StringIO()):
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    return result, log.getvalue(), time.monotonic()-start


def _verify(root, *, release=False, owner_review=None):
    evidence = root/'docs'/'verification'
    evidence.mkdir(parents=True, exist_ok=True)
    result, log, elapsed = _run_unit_tests()
    (evidence/'unittest.txt').write_text(log)
    commands = []
    for command in ([sys.executable, '-B', '-m', 'tools.check'],
                    [sys.executable, '-m', 'compileall', '-q',
                     'ai_op', 'execution_engine', 'ingestion', 'schemas', 'storage_engine',
                     'streaming', 'tools', 'tests']):
        env = dict(os.environ, PYTHONPYCACHEPREFIX='/tmp/algo-completion-pycache')
        process = subprocess.run(command, capture_output=True, text=True, env=env, timeout=60)
        commands.append(dict(command=command, returncode=process.returncode,
                             stdout=process.stdout, stderr=process.stderr))
    core_ok = result.wasSuccessful() and all(c['returncode'] == 0 for c in commands)
    if core_ok:
        for name, function in [('demo', run_demo), ('benchmark', lambda: benchmark(200))]:
            (evidence/(name+'.txt')).write_text(json.dumps(function(), indent=2)+'\n')
    security = audit(root)
    (evidence/'security.txt').write_text(json.dumps(security, indent=2)+'\n')
    gate = (release_gate(security, root, owner_review) if release else
            dict(status='NOT_RUN', reasons=['Strict release review not requested; owner approval still required'],
                 publication_authorized=False))
    status = dict(python=platform.python_version(), platform=platform.platform(),
                  mode='release' if release else 'offline',
                  source_kind='repository' if security['git_history']['status'] == 'COMPLETED' else 'archive/incomplete',
                  tests=result.testsRun, passed=result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
                  failures=len(result.failures), errors=len(result.errors),
                  skipped=len(result.skipped), skip_reasons=[reason for _, reason in result.skipped],
                  seconds=elapsed, commands=commands, git_history=security['git_history'],
                  security_clearance=security['security_clearance'], release_review=gate,
                  review_source_sha256=source_digest(root),
                  limitations=['Kafka real broker unverified', 'Real-market ML evaluation unavailable',
                               'Production readiness unsupported', 'Single-writer storage only',
                               'No hardware power-loss certification', 'Remote CI not run'])
    if security['git_history']['status'] != 'COMPLETED':
        status['limitations'].append('Git history NOT RUN or INCOMPLETE; no full security clearance')
    (evidence/'results.txt').write_text(json.dumps(status, indent=2)+'\n')
    print(json.dumps(status, indent=2))
    if not core_ok:
        print(log)
    if not core_ok or release and gate['status'] != 'SATISFIED':
        return 1
    print('Offline demo, benchmark and scoped security evidence written to docs/verification/')
    return 0


def run_verification(root, *, release=False, owner_review=None):
    root = Path(root).resolve()
    # Resolve attestation relative to the caller, before entering the source root.
    owner_review = Path(owner_review).resolve() if owner_review is not None else None
    previous = Path.cwd()
    try:
        os.chdir(root)
        return _verify(root, release=release, owner_review=owner_review)
    finally:
        os.chdir(previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', action='store_true', help='require actual Git history and bound owner attestation')
    parser.add_argument('--owner-review', type=Path, help='owner-provided review JSON; never generated automatically')
    args = parser.parse_args()
    if args.owner_review and not args.release:
        parser.error('--owner-review requires --release')
    raise SystemExit(run_verification(Path(__file__).resolve().parents[1],
                                      release=args.release, owner_review=args.owner_review))


if __name__ == '__main__':
    main()
