"""Fail-closed isolation guard used only by opt-in persistence verification."""
import os
from urllib.parse import urlparse

PRODUCTION_ENDPOINT = 'ep-calm-rain-a1emw9d9'


def isolated_test_url():
    value = os.environ.get('EVENT_TEST_DATABASE_URL', '')
    parsed = urlparse(value)
    production = urlparse(os.environ.get('DATABASE_URL', ''))
    if (os.environ.get('EVENT_TEST_BRANCH_CONFIRMED') != 'true'
            or parsed.scheme not in ('postgres', 'postgresql')
            or not parsed.hostname or not parsed.hostname.endswith('.neon.tech')
            or not parsed.username or not parsed.password or not parsed.path.strip('/')
            or PRODUCTION_ENDPOINT in parsed.hostname
            or (production.hostname and parsed.hostname.replace('-pooler.', '.') == production.hostname.replace('-pooler.', '.'))):
        raise ValueError('A separately confirmed isolated Neon branch is required')
    return value
