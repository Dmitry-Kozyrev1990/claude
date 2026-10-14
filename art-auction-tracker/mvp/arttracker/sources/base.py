"""Общая инфраструктура сборщиков: реестр источников и «вежливый» HTTP-клиент.

Правила, которые клиент соблюдает всегда:
- источник должен быть одобрен в реестре (registry.py), домен — в его списке;
- robots.txt проверяется до первого запроса к хосту;
- не чаще одного запроса в min_interval секунд на хост, повтор с паузой при 429/5xx;
- бот представляется в User-Agent с контактом;
- каждый ответ сохраняется в сыром виде (data/raw/<источник>/…), чтобы при смене
  парсера перепарсить историю без повторного скачивания.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

USER_AGENT = "LotlineBot/0.1 (+https://github.com/Dmitry-Kozyrev1990/claude; research prototype)"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


class SourceNotAllowed(Exception):
    """Источник не одобрен, домен не в списке или robots.txt запрещает адрес."""


@dataclass
class SourcePolicy:
    id: str
    name: str
    kind: str                    # reference | fx | auction
    status: str                  # approved | pending_review | blocked
    license: str
    terms_url: str
    domains: list[str]
    min_interval: float = 1.0
    note: str = ""
    extra_headers: dict = field(default_factory=dict)


@dataclass
class Response:
    url: str
    status: int
    body: bytes
    fetched_at: float
    from_cache: bool = False

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


Transport = Callable[[str, dict], tuple[int, bytes]]


def urllib_transport(url: str, headers: dict) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b""


class PoliteClient:
    def __init__(self, policy: SourcePolicy, transport: Transport | None = None,
                 raw_dir: Path | None = None, sleep: Callable[[float], None] = time.sleep,
                 check_robots: bool = True, max_retries: int = 3):
        if policy.status != "approved":
            raise SourceNotAllowed(f"{policy.name}: статус «{policy.status}». {policy.note}".strip())
        self.policy = policy
        self.transport = transport or urllib_transport
        self.raw_dir = (raw_dir or RAW_DIR) / policy.id
        self.sleep = sleep
        self.check_robots = check_robots
        self.max_retries = max_retries
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last: dict[str, float] = {}

    @property
    def headers(self) -> dict:
        return {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9",
                **self.policy.extra_headers}

    def _check_domain(self, url: str) -> str:
        host = urlparse(url).hostname or ""
        if not any(host == d or host.endswith("." + d) for d in self.policy.domains):
            raise SourceNotAllowed(f"{host} не входит в домены источника {self.policy.name}")
        return host

    def _robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            status, body = self._throttled(base + "/robots.txt", parsed.hostname)
            if status >= 400:
                rp.parse([])          # нет robots.txt — ограничений не объявлено
            else:
                rp.parse(body.decode("utf-8", errors="replace").splitlines())
            self._robots[base] = rp
        return self._robots[base].can_fetch(USER_AGENT, url)

    def _throttled(self, url: str, host: str) -> tuple[int, bytes]:
        wait = self.policy.min_interval - (time.monotonic() - self._last.get(host, -1e9))
        if wait > 0:
            self.sleep(wait)
        self._last[host] = time.monotonic()
        return self.transport(url, self.headers)

    def cache_path(self, url: str) -> Path:
        return self.raw_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")

    def get(self, url: str, use_cache: bool = True) -> Response:
        host = self._check_domain(url)
        path = self.cache_path(url)
        if use_cache and path.exists():
            meta = json.loads(path.read_text(encoding="utf-8"))
            return Response(url, meta["status"], meta["body"].encode("utf-8"), meta["fetched_at"], True)
        if self.check_robots and not self._robots_allows(url):
            raise SourceNotAllowed(f"robots.txt запрещает {url}")
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            status, body = self._throttled(url, host)
            if status not in (429, 500, 502, 503, 504) or attempt == self.max_retries:
                break
            self.sleep(delay)
            delay *= 2
        resp = Response(url, status, body, time.time())
        if status == 200:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"url": url, "status": status, "fetched_at": resp.fetched_at,
                                        "body": body.decode("utf-8", errors="replace")}, ensure_ascii=False),
                            encoding="utf-8")
        return resp
