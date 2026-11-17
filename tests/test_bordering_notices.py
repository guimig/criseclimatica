"""Bordering INMET danger regression: municipality codes, lifecycle and local isolation."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from observatorio.alerts import normalize_alerts, retain_valid_notices
from observatorio.bordering_notices import (
    KIND, load_bordering, severity_rank, append_bordering, summarize_bordering)
from observatorio.dashboard import regional_notice_context
from observatorio.risk_classification import classify

STAMP = "2026-11-17T18:00:00Z"
ARAQUARI = {"id": "araquari", "name": "Araquari", "ibge_code": "4201307"}
CONFIG = ROOT / "config" / "araquari_limitrofes.json"


def notice(identifier, severity, codes, *, start="2026-11-17", end="2026-11-17", closed=False):
    return {"id_aviso": identifier, "id_sequencia": 1, "descricao": "Tempestade",
            "severidade": severity, "geocodes": ",".join(codes),
            "data_inicio": start, "hora_inicio": "08:00",
            "data_fim": end, "hora_fim": "23:59", "encerrado": closed}


def data(*items):
    return {"hoje": list(items), "futuro": []}


def make(feed, *, previous=None, fixture=True):
    places = load_bordering(CONFIG)
    local = normalize_alerts(feed, [ARAQUARI], STAMP)
    local = append_bordering(local, previous=previous, places=places, stamp=STAMP, raw=feed)
    return local, summarize_bordering(local, places, STAMP)


class BorderingTests(unittest.TestCase):
    def test_exact_codes_and_severity(self):
        self.assertEqual(len(load_bordering(CONFIG)), 7)
        self.assertEqual([severity_rank(x) for x in ("Perigo Potencial", "Perigo", "Grande Perigo", "grande PERIGO", "Não informada")], [1,2,3,3,0])
        for row in load_bordering(CONFIG):
            self.assertEqual(len(row["ibge_code"]), 7)

    def test_local_and_border_notice_separated(self):
        local, context = make(data(notice("51", "Perigo", ["4209102", "4210605"]),
                                   notice("52", "Grande Perigo", ["4201307", "4209102"])))
        self.assertEqual(len(local["locations"][0]["alerts"]), 1)
        self.assertEqual([row["id"] for row in context["notices"]], ["51"])
        self.assertEqual({m["name"] for m in context["notices"][0]["municipalities"]}, {"Joinville", "Massaranduba"})
        self.assertFalse(context["notices"][0]["araquari_included"])
        self.assertEqual(context["effect_on_local_risk"], "none")
        self.assertEqual(context["kind"], KIND)

    def test_perigo_and_potencial_are_not_equivalent(self):
        _, context = make(data(notice("53", "Perigo Potencial", ["4209102"]),
                               notice("54", "Perigo", ["4202107"]),
                               notice("55", "Grande Perigo", ["4216354"])))
        self.assertEqual([r["id"] for r in context["notices"]], ["55", "54", "53"])
        self.assertEqual([r["severity_rank"] for r in context["notices"]], [3, 2, 1])

    def test_non_adjacent_ignored_and_windows_confirmed(self):
        _, context = make(data(notice("56", "Perigo", ["4208450"]),  # Itapoá is regional, not a border registry entry.
                               notice("57", "Perigo", ["4209102"], end="2026-11-16"),
                               notice("58", "Perigo", ["4209102"], start="2026-11-18", end="2026-11-18")))
        self.assertEqual([r["id"] for r in context["notices"]], ["58"])

    def test_cancelled_notice_not_displayed(self):
        _, context = make(data(notice("59", "Grande Perigo", ["4209102"], closed=True)))
        self.assertEqual(context["notices"], [])

    def test_network_failure_preserves_official_end_but_not_freshness(self):
        previous, _ = make(data(notice("60", "Perigo", ["4209102"])))
        old = retain_valid_notices(previous, [ARAQUARI], STAMP)
        recovered = append_bordering(old, previous=previous, places=load_bordering(CONFIG),
                                   stamp=STAMP, raw=None)
        context = summarize_bordering(recovered, load_bordering(CONFIG), STAMP)
        self.assertEqual(context["status"], "retained_unconfirmed")
        self.assertTrue(context["notices"][0]["retained_previous"])
        self.assertEqual(context["notices"][0]["id"], "60")

    def test_no_local_risk_classification_input(self):
        _, context = make(data(notice("61", "Grande Perigo", ["4209102"])))
        self.assertNotIn("risk_classification", context)
        self.assertEqual(context["role"], "regional_context_only_not_official_warning_for_araquari")

    def test_bad_config_fails_closed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "bad.json"
            content = json.loads(CONFIG.read_text(encoding="utf-8"))
            content["municipalities"][0]["ibge_code"] = "4201307"
            file.write_text(json.dumps(content), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_bordering(file)


if __name__ == "__main__":
    unittest.main()
