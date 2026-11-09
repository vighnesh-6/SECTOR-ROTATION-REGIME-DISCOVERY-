"""Fail-closed isolation guard used only by opt-in persistence verification."""
import os
from deployment.events.database import validate_event_connection, EventDatabaseError

def isolated_test_url():
    value = os.environ.get('EVENT_TEST_DATABASE_URL', '').strip().strip('\'"')
    confirmed = os.environ.get('EVENT_TEST_BRANCH_CONFIRMED', '').strip().strip('\'"')
    if confirmed != 'true':
        raise ValueError('A separately confirmed isolated Neon branch is required: EVENT_TEST_BRANCH_CONFIRMED must be "true"')
    try:
        validate_event_connection(value, 'eod_ops_test')
    except EventDatabaseError:
        raise ValueError('Isolated endpoint must match test branch and database eod_ops_test; website neondb is forbidden for tests') from None
    return value
