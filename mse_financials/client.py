"""HTTP клиент: дахин оролдлого, backoff, ойлгомжтой алдаа."""
from __future__ import annotations

import logging
import time
import warnings
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

from .config import BASE_URL, INSECURE_FALLBACK_DOMAINS, USER_AGENT

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    """Хуудас/файл татаж чадаагүй."""


class Client:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 60, retries: int = 3,
                 delay: float = 0.5, session: requests.Session | None = None,
                 strict_ssl: bool = False, insecure_domains: tuple[str, ...] = INSECURE_FALLBACK_DOMAINS):
        self.base_url = base_url.rstrip("/")
        self.strict_ssl = strict_ssl
        self.insecure_domains = insecure_domains
        self._unverified_hosts: set[str] = set()   # гэрчилгээний алдаатай, баталгаажуулалтгүй татдаг хостууд
        self.timeout = timeout
        self.delay = delay
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        retry = Retry(total=retries, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",), raise_on_status=False)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _url(self, path_or_url: str) -> str:
        return path_or_url if path_or_url.startswith("http") else self.base_url + path_or_url

    def _may_skip_verify(self, host: str) -> bool:
        """Зөвхөн жагсаасан домэйн (болон дэд домэйн) дээр, `strict_ssl` унтраалттай үед л зөвшөөрнө."""
        return not self.strict_ssl and any(host == d or host.endswith("." + d) for d in self.insecure_domains)

    def _get_unverified(self, url: str, hops: int = 5) -> requests.Response:
        """verify=False таталт. Redirect-ийг гараар дагаж, зөвшөөрсөн домэйнээс гарвал зогсооно."""
        for _ in range(hops):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", InsecureRequestWarning)
                resp = self.session.get(url, timeout=self.timeout, verify=False, allow_redirects=False)
            if not resp.is_redirect:
                return resp
            url = urljoin(url, resp.headers.get("Location", ""))
            if not self._may_skip_verify(urlparse(url).hostname or ""):
                raise FetchError(f"{url}: баталгаажаагүй холболтоор өөр домэйн руу шилжүүлэх гэсэн тул зогсоолоо")
        raise FetchError(f"{url}: хэт олон redirect")

    def get(self, path_or_url: str) -> requests.Response:
        url = self._url(path_or_url)
        host = urlparse(url).hostname or ""
        try:
            if host in self._unverified_hosts:
                resp = self._get_unverified(url)
            else:
                try:
                    resp = self.session.get(url, timeout=self.timeout)
                except requests.exceptions.SSLError:
                    if not self._may_skip_verify(host):
                        raise
                    log.warning("%s: SSL гэрчилгээний гинж дутуу — энэ хост дээр баталгаажуулалтгүйгээр татна "
                                "(--strict-ssl өгвөл болиулна)", host)
                    self._unverified_hosts.add(host)
                    resp = self._get_unverified(url)
        except requests.RequestException as exc:
            raise FetchError(f"{url}: {exc}") from exc
        if not resp.ok:
            raise FetchError(f"{url}: HTTP {resp.status_code}")
        return resp

    def text(self, path_or_url: str) -> str:
        return self.get(path_or_url).text

    def sleep(self) -> None:
        if self.delay:
            time.sleep(self.delay)
