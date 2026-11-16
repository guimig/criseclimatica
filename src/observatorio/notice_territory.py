"""Conservative territorial recognition for Epagri/Ciram notices near Araquari.

A broad warning covering Santa Catarina or the litoral norte includes Araquari.
A warning for a neighboring city alone does NOT. Clauses with different days or
ambiguous geography require human review instead of being silently discarded.
"""
from __future__ import annotations

import re
import unicodedata


def fold(value: object) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "").casefold())
                   if not unicodedata.combining(c))


LOCAL = re.compile(r"\baraquari\b|\b4201307\b")
STATE = re.compile(
    r"^(?:todas?|todo\s+o\s+territorio)(?:\s*[,.;]|$)|"
    r"^(?:santa\s+catarina|sc)(?:\s*[,.;]|$)|"
    r"\b(?:todas?(?:\s+as)?\s+regioes|todo\s+o\s+estado|estado\s+inteiro|"
    r"toda\s+santa\s+catarina|todo\s+territorio\s+catarinense|"
    r"todo\s+territorio\s+de\s+sc|sc\s+inteira|"
    r"todas?\s*,\s*especialmente|todas?\s+as?\s+areas)\b"
)
COAST = re.compile(
    r"^(?:litoral|todo\s+o\s+litoral)(?:\s*[,.;]|$|\s+e\b)|"
    r"\blitoral\s+(?:norte|catarinense|de\s+santa\s+catarina|de\s+sc|do\s+estado)\b|"
    r"\bcosta\s+(?:norte|catarinense)\b|\bfaixa\s+leste\s+(?:do\s+estado|de\s+sc)\b"
)
JOINVILLE = re.compile(
    r"\b(?:regiao\s+(?:metropolitana|imediata|geografica\s+imediata)\s+de\s+joinville|"
    r"amunesc|norte\s+catarinense)\b"
)
AMBIGUOUS = re.compile(
    r"\b(?:norte\s+de\s+sc|nordeste\s+catarinense|litoral\s+(?:de\s+sc|do\s+estado)|"
    r"faixa\s+leste|regiao\s+norte|regiao\s+de\s+joinville|"
    r"leste\s+catarinense|extremo\s+norte|norte\s+do\s+estado|"
    r"norte\s+de\s+santa\s+catarina|planicie\s+costeira)\b"
)
EXCLUSION = re.compile(r"\b(?:exceto|excluind[oa]s?|menos|nao\s+inclui|fora\s+d[ao]s?)\b")
LOCAL_EXCLUDED = re.compile(
    r"\b(?:exceto|excluindo|menos|nao\s+inclui)\b.{0,100}"
    r"(?:araquari|litoral\s+norte|norte\s+catarinense|regiao\s+de\s+joinville)"
)
MULTI_DAY = re.compile(r"\b(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)?\b")


def classify(regions: object, *, full_text: object = "") -> tuple[str | None, str]:
    """Return (scope, explanation), without turning adjacent cities into local notices."""
    text = fold(regions)
    if not text:
        # A free-text reference may be useful for manual triage; it is not
        # sufficient evidence of official territorial coverage.
        summary = fold(full_text)
        if LOCAL.search(summary) or STATE.search(summary) or COAST.search(summary):
            return "territory_needs_review", "territory_only_in_body"
        return None, "no_territorial_statement"
    if len(text) > 1600:
        return "territory_needs_review", "territorial_statement_too_long"
    if LOCAL_EXCLUDED.search(text):
        return None, "explicit_local_exclusion"
    positive = LOCAL.search(text) or STATE.search(text) or COAST.search(text) or JOINVILLE.search(text)
    if EXCLUSION.search(text) and not positive:
        return None, "not_included"
    # Distinct day/region clauses must be evaluated against each event window,
    # not flattened into an unsupported claim for all its days.
    if len(set(MULTI_DAY.findall(text))) > 1 and re.search(r"\b(?:em|no|na|para)\b", text):
        return "territory_needs_review", "different_regions_by_weekday"
    if positive:
        if EXCLUSION.search(text):
            # Exclusions of OTHER areas do not negate the named local region,
            # but free-text scopes are safest to present for confirmation.
            return "territory_needs_review", "mixed_inclusions_and_exclusions"
        return ("municipality_explicit", "araquari_named") if LOCAL.search(text) else (
            "regional_reference_not_municipal_confirmation", "broad_region_includes_araquari"
        )
    if AMBIGUOUS.search(text):
        return "territory_needs_review", "ambiguous_regional_reference"
    if LOCAL.search(fold(full_text)):
        return "territory_needs_review", "municipality_only_in_body"
    return None, "territory_does_not_include_araquari"
