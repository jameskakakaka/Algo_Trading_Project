"""Legacy direct-library network calls need deliberate operator opt-in."""
import os


def require_network_opt_in():
    if os.environ.get('ALLOW_LEGACY_NETWORK') != '1':
        raise RuntimeError('Legacy network access disabled; use finalized-bar injected transport')
