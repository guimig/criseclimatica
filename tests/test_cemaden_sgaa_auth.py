"""Offline tests for secure SGAA login, token rotation and PED rainfall."""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observatorio.cemaden_auth import request_token, SgaaSession, SgaaAuthError
from observatorio.cemaden import collect, normalize, fetch, CemadenError
from observatorio.config import load_locations

NOW = datetime(2026, 11, 6, 13, 0, tzinfo=timezone.utc)
STAMP = "2026-11-06T13:00:00Z"
LOCATIONS = load_locations(ROOT / "config" / "locations.json")
TOKEN = "header.payload.signature_for_offline_testing"


class Reply:
    status = 201

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, count):
        return json.dumps({"token": TOKEN, "timeToExp": "600000"}).encode()[:count]


class SgaaAuthTests(unittest.TestCase):
    def test_login_post_json_does_not_put_password_in_url(self):
        requests = []
        class Opener:
            def open(self, req, timeout):
                requests.append(req)
                return Reply()
        with patch("observatorio.cemaden_auth.build_opener", return_value=Opener()):
            self.assertEqual(request_token("test@example.org", "TOP_SECRET_PASSWORD"), TOKEN)
        self.assertEqual(requests[0].get_method(), "POST")
        self.assertEqual(requests[0].full_url, "https://sgaa.cemaden.gov.br/SGAA/rest/controle-token/tokens")
        self.assertEqual(json.loads(requests[0].data)["password"], "TOP_SECRET_PASSWORD")
        self.assertNotIn("TOP_SECRET_PASSWORD", requests[0].full_url)

    def test_denied_login_error_does_not_expose_credentials(self):
        class Opener:
            def open(self, req, timeout):
                raise HTTPError(req.full_url, 401, "Unauthorized", {}, None)
        with patch("observatorio.cemaden_auth.build_opener", return_value=Opener()):
            with self.assertRaises(SgaaAuthError) as failure:
                request_token("private@example.org", "VERY_SECRET")
        self.assertEqual(failure.exception.reason, "access_restricted")
        self.assertNotIn("VERY_SECRET", str(failure.exception))
        self.assertNotIn("private@example.org", str(failure.exception))

    def test_sgaa_session_reuses_then_rotates_jwt_once(self):
        calls = []
        def login(*_):
            calls.append(1)
            return TOKEN if len(calls) == 1 else "new.token.signature"
        session = SgaaSession("x@example.org", "safe", token_requester=login)
        self.assertEqual(session.token(), TOKEN)
        self.assertEqual(session.token(), TOKEN)
        self.assertEqual(session.token(rejected=TOKEN), "new.token.signature")
        self.assertEqual(session.token(rejected=TOKEN), "new.token.signature")
        self.assertEqual(len(calls), 2)

    def test_sgaa_same_bad_jwt_is_not_repeated_indefinitely(self):
        session = SgaaSession("x@example.org", "safe", token_requester=lambda *_: TOKEN)
        self.assertEqual(session.token(), TOKEN)
        with self.assertRaises(SgaaAuthError):
            session.token(rejected=TOKEN)
        with self.assertRaises(SgaaAuthError):
            session.token()

    def test_seven_cities_use_sgaa_and_publish_no_credentials(self):
        session = SgaaSession("x@example.org", "safe", token_requester=lambda *_: TOKEN)
        calls = []
        def fetcher(ibge, received_token):
            calls.append((ibge, received_token))
            return [{"codibge":int(ibge), "codestacao":ibge+"A", "datahora":STAMP,
                     "acc1hr":0, "acc3hr":2, "acc6hr":4, "acc12hr":6,
                     "acc24hr":8, "acc48hr":10, "acc72hr":12,
                     "acc96hr":14, "acc120hr":16}]
        with patch.dict(os.environ, {"CEMADEN_PED_EMAIL":"PRIVATE_EMAIL@example.org",
                                     "CEMADEN_PED_PASSWORD":"PRIVATE_PASSWORD",
                                     "CEMADEN_PED_TOKEN":"STALE_OLD_JWT"}):
            data = collect(LOCATIONS, STAMP, now=NOW, fetcher=fetcher, session=session)
        self.assertEqual(data["status"], "available")
        self.assertEqual(len(calls), 7)
        self.assertTrue(all(value == TOKEN for _, value in calls))
        self.assertEqual(data["locations"][0]["stations"][0]["rain_120h_mm"], 16)
        public = json.dumps(data)
        for secret in ("PRIVATE_EMAIL@example.org", "PRIVATE_PASSWORD", TOKEN, "STALE_OLD_JWT"):
            self.assertNotIn(secret, public)
        self.assertIn("DADOS DA REDE OBSERVACIONAL DO CEMADEN/MCTIC", public)

    def test_expired_token_refreshed_once_and_not_reused_for_next_city(self):
        calls = []
        def login(*_):
            calls.append("login")
            return TOKEN if len(calls) == 1 else "updated.token.signature"
        session = SgaaSession("x@example.org", "safe", token_requester=login)
        requests = []
        def fetcher(ibge, token):
            requests.append(token)
            if token == TOKEN:
                raise CemadenError("Expired", "token_expired")
            return [{"codibge":int(ibge), "codestacao":ibge+"A",
                     "datahora":STAMP, "acc24hr":3}]
        with patch.dict(os.environ, {"CEMADEN_PED_EMAIL":"x@example.org",
                                     "CEMADEN_PED_PASSWORD":"safe"}):
            result = collect(LOCATIONS[:2], STAMP, now=NOW, fetcher=fetcher, session=session)
        self.assertEqual(result["status"], "available")
        self.assertEqual(requests, [TOKEN, "updated.token.signature", "updated.token.signature"])
        self.assertEqual(len(calls), 2)

    def test_partial_secrets_do_not_fall_back_to_old_jwt(self):
        with patch.dict(os.environ, {"CEMADEN_PED_EMAIL":"x@example.org",
                                     "CEMADEN_PED_PASSWORD":"", "CEMADEN_PED_TOKEN":"old"}):
            out = collect(LOCATIONS, STAMP, now=NOW,
                          fetcher=lambda *_: self.fail("No queries allowed"))
        self.assertEqual(out["status"], "not_configured")
        self.assertEqual(out["diagnostic"], "incomplete_sgaa_credentials")

    def test_all_precipitation_windows_validate_missing_values(self):
        rows = [{"codibge":4201307, "codestacao":"420130701A",
                 "datahora": STAMP, "acc1hr":None, "acc3hr":0,
                 "acc6hr":-999, "acc12hr":4, "acc24hr":15,
                 "acc48hr":20, "acc72hr":30, "acc96hr":45, "acc120hr":55}]
        result = normalize(rows, "4201307", NOW)[0]
        self.assertIsNone(result["rain_1h_mm"])
        self.assertIsNone(result["rain_6h_mm"])
        self.assertEqual(result["rain_3h_mm"], 0)
        self.assertEqual(result["rain_120h_mm"], 55)

    def test_ped_401_400_429_are_classified_without_jwt_leak(self):
        for code, reason in ((401,"token_expired"), (400,"bad_request"), (429,"rate_limited")):
            class Opener:
                def open(self, req, timeout):
                    raise HTTPError(req.full_url, code, "", {}, None)
            with self.subTest(code=code), patch("observatorio.cemaden.build_opener", return_value=Opener()):
                with self.assertRaises(CemadenError) as failure:
                    fetch("4201307", "PRIVATE_JWT")
                self.assertEqual(failure.exception.reason, reason)
                self.assertNotIn("PRIVATE_JWT", str(failure.exception))


if __name__ == "__main__":
    unittest.main()
