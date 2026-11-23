"""HTTP with a per-host rate limit, retries and exponential backoff."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import __version__


class HttpError(Exception):
    """Network failure or persistent server error (never a 'not found')."""


# Hosts that publish a stricter etiquette than the default rate.
MIN_INTERVAL = {"export.arxiv.org": 3.0}
RETRY_STATUS = {429, 500, 502, 503, 504}


class Http:
    def __init__(self, rate: float = 1.0, mailto: str | None = None, retries: int = 3,
                 timeout: float = 20.0, opener=None, sleep=time.sleep, clock=time.monotonic):
        self.interval = 1.0 / rate if rate and rate > 0 else 0.0
        self.mailto = mailto
        self.retries = max(1, retries)
        self.timeout = timeout
        self._open = opener or urllib.request.urlopen
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        ua = f"hallucinated-citation-checker/{__version__}"
        if mailto:
            ua += f" (mailto:{mailto})"
        self.user_agent = ua

    def _wait(self, host: str):
        gap = max(self.interval, MIN_INTERVAL.get(host, 0.0))
        last = self._last.get(host)
        if last is not None:
            delay = gap - (self._clock() - last)
            if delay > 0:
                self._sleep(delay)
        self._last[host] = self._clock()

    def get(self, url: str, headers: dict | None = None) -> tuple[int, bytes]:
        """Return (status, body). 4xx other than 429 is returned, not raised.
        Raises HttpError after the retries are used up."""
        host = urlsplit(url).netloc
        hdrs = {"User-Agent": self.user_agent}
        hdrs.update(headers or {})
        last_err = "unknown error"
        for attempt in range(1, self.retries + 1):
            self._wait(host)
            try:
                req = urllib.request.Request(url, headers=hdrs)
                with self._open(req, timeout=self.timeout) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as e:
                try:
                    body = e.read()
                except Exception:
                    body = b""
                e.close()
                if e.code not in RETRY_STATUS:
                    return e.code, body
                last_err = f"HTTP {e.code} from {host}"
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                last_err = f"{type(e).__name__} from {host}: {e}"
            if attempt < self.retries:
                self._sleep(2 ** attempt)
        raise HttpError(f"{last_err} after {self.retries} attempts")
