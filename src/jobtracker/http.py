"""Polite HTTP client: rate limiting, retries with backoff, robots.txt, clear UA."""
from __future__ import annotations
import time, logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import requests

log = logging.getLogger("jobtracker.http")

class PoliteSession:
    def __init__(self, cfg: dict):
        s = cfg["scraping"]
        self.delay = float(s["request_delay_seconds"])
        self.timeout = int(s["timeout_seconds"])
        self.max_retries = int(s["max_retries"])
        self.backoff = float(s["backoff_factor"])
        self.respect_robots = bool(s.get("respect_robots_txt", True))
        self.session = requests.Session()
        self.session.headers["User-Agent"] = s["user_agent"]
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}

    def _robots_ok(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        host = urlparse(url).netloc
        if host not in self._robots:
            rp = RobotFileParser()
            try:
                rp.set_url(f"https://{host}/robots.txt"); rp.read()
            except Exception:
                rp = None  # unreadable robots -> allow, stay polite
            self._robots[host] = rp
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(self.session.headers["User-Agent"], url)

    def _throttle(self, url: str):
        host = urlparse(url).netloc
        wait = self.delay - (time.time() - self._last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self._last_hit[host] = time.time()

    def get(self, url: str, **kw) -> requests.Response | None:
        if not self._robots_ok(url):
            log.warning("robots.txt disallows %s — skipping", url)
            return None
        for attempt in range(self.max_retries):
            self._throttle(url)
            try:
                r = self.session.get(url, timeout=self.timeout, **kw)
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(f"{r.status_code}")
                return r
            except Exception as e:
                sleep = self.backoff ** attempt
                log.info("retry %d for %s (%s), sleeping %.1fs", attempt + 1, url, e, sleep)
                time.sleep(sleep)
        log.error("giving up on %s", url)
        return None

    def get_json(self, url: str, **kw):
        r = self.get(url, **kw)
        if r is None or r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None
