"""Regression coverage: official validity cannot expire with collection freshness."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observatorio.alerts import merge_active_notices, normalize_alerts, retain_valid_notices
from observatorio.notice_time import normalize_window, lifecycle
from observatorio.notice_territory import classify as territorial
from observatorio.epagri_notices import _window
from observatorio.protocol import assess, territorial_scope
from observatorio.multisource import notices as classified_notices

NOW = datetime(2026, 11, 15, 21, 0, tzinfo=timezone.utc)
STAMP = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
PLACE = {"id": "araquari", "name": "Araquari", "ibge_code": "4201307"}


def payload(*, cancelled=False, date_only=False):
    return {"hoje": [{"id_aviso": 2026, "id_sequencia": 1, "geocodes": "4201307",
                      "descricao": "Tempestade", "riscos": ["Vento forte"],
                      "data_inicio": "2026-11-15T00:00:00.000Z",
                      "data_fim": "2026-11-15T00:00:00.000Z",
                      **({} if date_only else {"hora_inicio": "08:00", "hora_fim": "23:00"}),
                      "encerrado": cancelled}], "futuro": []}


def source_notice():
    return {"kind": "epagri_ciram_official_advisories_not_civil_defense_alerts",
            "status": "stale", "retrieved_at": "2026-11-15T08:00:00Z",
            "notices": [{
                "notice_kind": "epagri_meteorological_advisory_not_civil_defense_alert",
                "title": "Tempestades no litoral", "url": "https://ciram.epagri.sc.gov.br/index.php/aviso/",
                "regions_text": "Todas, especialmente Litoral e Grande Florianópolis",
                "valid_from": "2026-11-15T11:00:00Z",
                "valid_until": "2026-11-16T02:00:00Z",
                "assessment_text": "Previsão de temporais no litoral norte com possibilidade de alagamento."}]}


class NoticeTimeTests(unittest.TestCase):
    def test_brasilia_without_offset(self):
        self.assertEqual(
            normalize_window("2026-11-15", "08:00", "2026-11-15", "23:00"),
            ("2026-11-15T11:00:00Z", "2026-11-16T02:00:00Z",
             "brasilia_assumed_when_offset_absent"))

    def test_date_only_includes_entire_final_day(self):
        self.assertEqual(
            normalize_window("2026-11-14", None, "2026-11-15", None),
            ("2026-11-14T03:00:00Z", "2026-11-16T03:00:00Z",
             "brasilia_full_day_when_clock_absent"))

    def test_explicit_offsets_are_respected(self):
        start, end, basis = normalize_window(
            "2026-11-15", "10:00-02:00", "2026-11-15", "21:00-02:00")
        self.assertEqual((start, end, basis),
                         ("2026-11-15T12:00:00Z", "2026-11-15T23:00:00Z",
                          "source_explicit_offset"))

    def test_exact_end_boundary_and_future(self):
        self.assertEqual(lifecycle("2026-11-15T11:00:00Z", "2026-11-16T02:00:00Z",
                                   datetime(2026, 11, 16, 1, 59, tzinfo=timezone.utc)), "ongoing")
        self.assertEqual(lifecycle("2026-11-15T11:00:00Z", "2026-11-16T02:00:00Z",
                                   datetime(2026, 11, 16, 2, 0, tzinfo=timezone.utc)), "expired")

    def test_inmet_serialized_day_without_clock(self):
        row = normalize_alerts(payload(date_only=True), [PLACE], STAMP)["locations"][0]["alerts"][0]
        self.assertEqual(row["start_at"], "2026-11-15T03:00:00Z")
        self.assertEqual(row["end_at"], "2026-11-16T03:00:00Z")

    def test_epagri_date_only_text(self):
        self.assertEqual(_window("Início: 15/11/2026\nFim: 16/11/2026"),
                         ("2026-11-15T03:00:00Z", "2026-11-17T03:00:00Z"))


class NoticeRetentionTests(unittest.TestCase):
    def test_notice_retained_after_sixteen_hours(self):
        old = normalize_alerts(payload(), [PLACE], "2026-11-15T08:00:00Z")
        recovered = retain_valid_notices(old, [PLACE], "2026-11-16T01:00:00Z")
        self.assertTrue(recovered["retained_previous"])
        self.assertEqual(len(recovered["retained_locations"][0]["alerts"]), 1)

    def test_absence_from_new_feed_not_cancellation(self):
        old = normalize_alerts(payload(), [PLACE], "2026-11-15T08:00:00Z")
        current = normalize_alerts({"hoje": [], "futuro": []}, [PLACE], STAMP)
        merged = merge_active_notices(current, old, [PLACE], STAMP)
        self.assertTrue(merged["locations"][0]["alerts"][0]["retained_previous"])
        self.assertEqual(merged["locations"][0]["alerts"][0]["end_at"], "2026-11-16T02:00:00Z")

    def test_explicit_cancellation_overrides_previous(self):
        old = normalize_alerts(payload(), [PLACE], "2026-11-15T08:00:00Z")
        current = normalize_alerts(payload(cancelled=True), [PLACE], STAMP)
        self.assertEqual(merge_active_notices(current, old, [PLACE], STAMP)["locations"][0]["alerts"], [])

    def test_expired_not_retained(self):
        old = normalize_alerts(payload(), [PLACE], "2026-11-15T08:00:00Z")
        self.assertFalse(retain_valid_notices(old, [PLACE], "2026-11-16T02:00:00Z")["retained_previous"])


class TerritoryTests(unittest.TestCase):
    def test_broad_state_expressions(self):
        for text in ("Todas, especialmente Litoral", "Todas as regiões do estado",
                     "Todo o estado", "Toda Santa Catarina", "Litoral Norte",
                     "Litoral catarinense", "Norte catarinense",
                     "Região Metropolitana de Joinville", "AMUNESC", "Araquari/SC"):
            with self.subTest(text=text):
                scope, reason = territorial(text)
                self.assertIn(scope, ("municipality_explicit", "regional_reference_not_municipal_confirmation"), reason)

    def test_exclusions_and_other_municipalities(self):
        for text in ("Todas, exceto Litoral Norte", "Todas, excluindo Araquari",
                     "Somente Joinville", "Planalto Norte"):
            with self.subTest(text=text):
                self.assertIsNone(territorial(text)[0])

    def test_geography_ambiguous_not_lost(self):
        for text in ("Nordeste catarinense", "Faixa leste"):
            with self.subTest(text=text):
                self.assertEqual(territorial(text)[0], "territory_needs_review")

    def test_temporally_different_regions_flagged(self):
        scope, reason = territorial("Litoral Norte na sexta-feira, Oeste no sábado")
        self.assertEqual((scope, reason), ("territory_needs_review", "different_regions_by_weekday"))

    def test_scope_from_protocol(self):
        self.assertEqual(territorial_scope({"regions_text": "Todas, especialmente Litoral"}),
                         "regional_reference_not_municipal_confirmation")


class ClassificationTests(unittest.TestCase):
    def test_stale_source_does_not_end_validity(self):
        report = assess(source_notice(), {}, STAMP)
        evidence = report["evidence"][0]
        self.assertEqual(evidence["status"], "eligible")
        self.assertEqual(report["valid_until"], "2026-11-16T02:00:00Z")
        self.assertEqual(evidence["scope"], "regional_reference_not_municipal_confirmation")

    def test_synthesis_notices_use_official_end(self):
        feed = source_notice()
        report = assess(feed, {}, STAMP)
        dashboard = {"assessment": {"base_assessment": report},
                     "inmet_context": {"status": "unavailable", "notices": []}}
        rows = classified_notices(dashboard, STAMP)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["valid_until"], "2026-11-16T02:00:00Z")


if __name__ == "__main__":
    unittest.main()
