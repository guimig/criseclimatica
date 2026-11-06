"""Server-side SGAA login for Cemaden PED.

Only short-lived JWTs are kept in memory for one Actions run. Credentials and
JWTs must never be persisted to the static site or written to job logs.
"""
from __future__ import annotations

import json
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

SGAA_TOKEN_URL = "https://sgaa.cemaden.gov.br/SGAA/rest/controle-token/tokens"
MAX_RESPONSE_BYTES = 16_384


class SgaaAuthError(RuntimeError):
    """Error without potentially sensitive request/response contents."""

    def __init__(self, reason: str):
        super().__init__(f"SGAA authentication: {reason}")
        self.reason = reason


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_token(email: str, password: str, *, timeout: int = 15) -> str:
    """Request a token using the official SGAA POST JSON interface.

    Swagger documents response status 201 and `timeToExp` in milliseconds;
    the earlier PDF manual calls that duration seconds. We do not depend on
    the inconsistent field: request a token once per run, retry after 401.
    """
    if (not isinstance(email, str) or not isinstance(password, str) or
            not 3 <= len(email) <= 254 or "@" not in email or
            not 1 <= len(password) <= 2048):
        raise SgaaAuthError("invalid_configuration")
    body = json.dumps({"email": email, "password": password}, ensure_ascii=False).encode("utf-8")
    request = Request(
        SGAA_TOKEN_URL, data=body, method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json",
                 "User-Agent": "criseclimatica/1.0 (+https://github.com/guimig/criseclimatica)"},
    )
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            if response.status not in (200, 201):
                raise SgaaAuthError("service_unavailable")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise SgaaAuthError("invalid_response")
        data = json.loads(payload.decode("utf-8"))
    except HTTPError as exc:
        if exc.code in (400, 401, 403):
            raise SgaaAuthError("access_restricted") from None
        if exc.code == 429:
            raise SgaaAuthError("rate_limited") from None
        raise SgaaAuthError("service_unavailable") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise SgaaAuthError("service_unavailable") from None
    except (ValueError, UnicodeError) as exc:
        raise SgaaAuthError("invalid_response") from None
    if not isinstance(data, dict):
        raise SgaaAuthError("invalid_response")
    token = data.get("token")
    if (not isinstance(token, str) or not 10 <= len(token) <= 8192 or
            any(char.isspace() for char in token)):
        raise SgaaAuthError("invalid_response")
    return token


class SgaaSession:
    """One in-memory token per build; bounded, synchronized refresh on expiry."""

    def __init__(self, email: str, password: str, *, token_requester=request_token):
        self._email = email
        self._password = password
        self._requester = token_requester
        self._lock = Lock()
        self._token: str | None = None
        self._rejected_token: str | None = None

    def token(self, *, rejected: str | None = None) -> str:
        """If `rejected` is stale, reuse a token refreshed by another worker."""
        with self._lock:
            # If SGAA returned the same rejected token, never flood PED with
            # more known-bad requests or repeatedly log in for each city.
            if self._token is not None and self._token == self._rejected_token:
                raise SgaaAuthError("access_restricted")
            if self._token is not None and (rejected is None or self._token != rejected):
                return self._token
            new_token = self._requester(self._email, self._password)
            self._token = new_token
            if rejected is not None and new_token == rejected:
                self._rejected_token = rejected
                raise SgaaAuthError("access_restricted")
            self._rejected_token = None
            return self._token
