import pytest
import requests

from mse_financials.client import Client, FetchError


class Resp:
    def __init__(self, status=200, headers=None, content=b"ok"):
        self.status_code, self.headers, self.content = status, headers or {}, content
        self.ok = status < 400
        self.is_redirect = status in (301, 302) and "Location" in self.headers
        self.text = content.decode()


class FakeSession(requests.Session):
    """Эхний (баталгаажуулалттай) дуудлага SSLError өгнө; verify=False дуудлагыг `script` дагуу хариулна."""

    def __init__(self, script=None, ssl_fail=True):
        super().__init__()
        self.calls = []
        self.script = list(script or [Resp()])
        self.ssl_fail = ssl_fail

    def get(self, url, **kw):
        self.calls.append((url, kw.get("verify", True)))
        if kw.get("verify", True) is not False and self.ssl_fail:
            raise requests.exceptions.SSLError("unable to get local issuer certificate")
        return self.script.pop(0)


def test_ssl_error_on_mse_domain_retries_unverified_and_remembers_host(caplog):
    s = FakeSession([Resp(), Resp()])
    c = Client(session=s, delay=0)
    with caplog.at_level("WARNING"):
        assert c.get("https://issuers.mse.mn/uploads/a.xlsx").content == b"ok"
    assert "гэрчилгээ" in caplog.text
    assert s.calls == [("https://issuers.mse.mn/uploads/a.xlsx", True),
                       ("https://issuers.mse.mn/uploads/a.xlsx", False)]
    c.get("https://issuers.mse.mn/uploads/b.xlsx")                    # дараагийн дуудлага шууд verify=False
    assert s.calls[-1] == ("https://issuers.mse.mn/uploads/b.xlsx", False) and len(s.calls) == 3


def test_ssl_error_on_other_domain_is_never_bypassed():
    s = FakeSession()
    with pytest.raises(FetchError):
        Client(session=s, delay=0).get("https://example.com/x")
    assert all(v is True for _, v in s.calls)                          # verify=False хэзээ ч ашиглаагүй


def test_strict_ssl_disables_fallback():
    s = FakeSession()
    with pytest.raises(FetchError):
        Client(session=s, delay=0, strict_ssl=True).get("https://open.mse.mn/securities")
    assert all(v is True for _, v in s.calls)


def test_lookalike_domain_is_not_trusted():
    s = FakeSession()
    with pytest.raises(FetchError):
        Client(session=s, delay=0).get("https://evilmse.mn/x")        # "mse.mn"-ээр дуусдаг боловч дэд домэйн биш


def test_unverified_redirect_to_foreign_domain_is_refused():
    s = FakeSession([Resp(302, {"Location": "https://evil.example.com/steal"})])
    with pytest.raises(FetchError, match="өөр домэйн"):
        Client(session=s, delay=0).get("https://open.mse.mn/x")
    assert all("evil.example.com" not in u for u, _ in s.calls)


def test_http_error_becomes_fetch_error():
    s = FakeSession([Resp(404)], ssl_fail=False)
    with pytest.raises(FetchError, match="404"):
        Client(session=s, delay=0).get("https://open.mse.mn/x")
