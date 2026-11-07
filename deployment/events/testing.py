"""Fail-closed isolation guard used only by opt-in persistence verification."""
import os
from urllib.parse import urlparse

PRODUCTION_ENDPOINT = 'ep-calm-rain-a1emw9d9'
EXPECTED_TEST_ENDPOINT = 'ep-cold-wind-a14dq44q'


def isolated_test_url():
    value = os.environ.get('EVENT_TEST_DATABASE_URL', '').strip().strip('\'"')
    parsed = urlparse(value)
    production = urlparse(os.environ.get('DATABASE_URL', '').strip().strip('\'"'))
    if os.environ.get('EVENT_TEST_BRANCH_CONFIRMED') != 'true':
        raise ValueError('A separately confirmed isolated Neon branch is required: EVENT_TEST_BRANCH_CONFIRMED must be "true"')
    if parsed.scheme not in ('postgres', 'postgresql'):
        raise ValueError('A separately confirmed isolated Neon branch is required: scheme must be postgres or postgresql')
    if not parsed.hostname or not parsed.hostname.endswith('.neon.tech'):
        raise ValueError('A separately confirmed isolated Neon branch is required: host must end with .neon.tech')
    if not parsed.username or not parsed.password or not parsed.path.strip('/'):
        raise ValueError('A separately confirmed isolated Neon branch is required: username, password, and database path required')
    if PRODUCTION_ENDPOINT in parsed.hostname:
        raise ValueError('CRITICAL: Production endpoint detected. A separately confirmed isolated Neon branch is required')
    if production.hostname and parsed.hostname.replace('-pooler.', '.') == production.hostname.replace('-pooler.', '.'):
        raise ValueError('CRITICAL: Target matches production database. A separately confirmed isolated Neon branch is required')
    if EXPECTED_TEST_ENDPOINT not in parsed.hostname:
        raise ValueError(f'A separately confirmed isolated Neon branch is required: endpoint must match test branch {EXPECTED_TEST_ENDPOINT}')
    return value
