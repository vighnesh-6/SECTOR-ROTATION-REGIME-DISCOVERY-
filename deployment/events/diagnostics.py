"""Sanitize event diagnostics before console, Actions, or execution-log output."""
from __future__ import annotations

import os
import re
import sys
import traceback
from urllib.parse import unquote, urlsplit


def redact(value):
    text = str(value)
    known = set()
    for key, candidate in os.environ.items():
        if candidate and re.search(r'PASSWORD|SECRET|TOKEN|DATABASE_URL|API_KEY|CONNECTION_STRING', key, re.I):
            known.add(candidate)
            if '://' in candidate:
                try:
                    parsed = urlsplit(candidate)
                    known.update([parsed.password or '', unquote(parsed.password or ''),
                                  parsed.username or '', unquote(parsed.username or '')])
                except ValueError:
                    pass
    for candidate in sorted((x for x in known if len(x) >= 4), key=len, reverse=True):
        text = text.replace(candidate, '[REDACTED]')
    text = re.sub(r'(?i)postgres(?:ql)?://[^\s\x22\x27<>]+', '[REDACTED_CONNECTION]', text)
    text = re.sub(r'(?i)(https?://)[^/\s:@]+:[^@\s]+@', r'\1[REDACTED]@', text)
    text = re.sub(r'(?i)(\b(?:Bearer|Basic)\s+)[^\s\x22\x27,;]+', r'\1[REDACTED]', text)
    # JSON/Python mapping keys have a closing quote before the separator.
    # Handle these independently of environment-known secret values, including
    # escaped quotes inside the value, without losing the useful error context.
    text = re.sub(
        r'''(?i)((["'])(?:password|passwd|pwd|username|user|secret|token|client_secret|access_token|refresh_token|api[_-]?key|authorization|database_url|connection_string)\2\s*:\s*)(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}]+)''',
        r'\1"[REDACTED]"', text)
    text = re.sub(r'(?i)((?:password|passwd|pwd|user(?:name)?|secret|token|api[_-]?key|authorization)\s*[=:]\s*)(?:\x22[^\x22]*\x22|\x27[^\x27]*\x27|[^\s&,;]+)', r'\1[REDACTED]', text)
    return re.sub(r'(?i)\bSECRET\b', '[REDACTED]', text)


def sanitize(value):
    if isinstance(value, dict):
        return {redact(key):sanitize(item) for key,item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    return redact(value) if isinstance(value, str) else value


def exception_details(exc, context):
    details = {'error_type':type(exc).__name__, 'error':redact(str(exc))[:2000]}
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        # No locals are captured. Redact the complete chained traceback, including
        # exception messages and source lines, before writing to Actions logs.
        trace = ''.join(traceback.TracebackException.from_exception(exc, capture_locals=False).format(chain=True))
        sys.stderr.write(redact(f'Event automation failure [{context}]\n'+trace).replace('::', ': :')+'\n')
    return details
