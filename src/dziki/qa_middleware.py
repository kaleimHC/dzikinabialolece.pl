"""
QA correlation middleware — active only when QA_SESSION=1 env var is set.

Logs: timestamp | qa_id | METHOD path | status | ms | user
to stdout (and optionally /tmp/qa_session_<date>.log).
"""

import logging
import os
import time
from datetime import datetime

logger = logging.getLogger("qa")

_QA_ACTIVE = os.environ.get("QA_SESSION", "0") == "1"
_LOG_FILE = None

if _QA_ACTIVE:
    log_path = f"/tmp/qa_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    try:
        _LOG_FILE = open(log_path, "a", buffering=1)  # line-buffered
        print(f"[QA-MW] Session log: {log_path}", flush=True)
    except OSError:
        pass


def _write(line):
    print(line, flush=True)
    if _LOG_FILE:
        try:
            _LOG_FILE.write(line + "\n")
        except OSError:
            pass


class QaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not _QA_ACTIVE:
            return self.get_response(request)

        qa_id = request.headers.get("X-QA-Id", "-")
        t0 = time.monotonic()
        response = self.get_response(request)
        ms = round((time.monotonic() - t0) * 1000)

        user = "-"
        if hasattr(request, "user") and request.user and request.user.is_authenticated:
            user = str(request.user.pk)

        _write(
            f"QA| {datetime.utcnow().isoformat()} | {qa_id} |"
            f" {request.method} {request.path} | {response.status_code} | {ms}ms | {user}"
        )
        return response
