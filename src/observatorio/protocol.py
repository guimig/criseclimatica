"""PN 13/2026 and PN 14/2026: transparent assistance, not an official level.

These norms define qualitative categories, not rainfall/wind thresholds.
Only primary Epagri advisories with explicit territory and validity support
an exploratory level. Missing warnings never establish normality.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import timedelta
from urllib.parse import urlparse

from .analysis import fresh, iso, moment

LEVELS = [
    {"id":"verde", "name":"Normalidade", "criterion":"Condições meteorológicas normais.",
     "reference":"PN 13/2026, art. 6º, I", "orientation":"Atividades presenciais em normalidade; acompanhar os canais oficiais.", "automatic":"requires_explicit_normality_not_absence_of_notices"},
    {"id":"azul", "name":"Preparação", "criterion":"Previsão de desastre com sete dias ou mais de antecedência, com potencial evolução.",
     "reference":"PN 13/2026, art. 6º, II", "orientation":"Monitorar a evolução e preparar as equipes; manutenção das atividades presenciais.", "automatic":"requires_explicit_event_window_at_least_seven_days_ahead"},
    {"id":"amarelo", "name":"Atenção", "criterion":"Possibilidade de impactos pontuais, como alagamentos, destelhamentos ou interrupção de energia.",
     "reference":"PN 13/2026, art. 6º, III", "orientation":"Acompanhar atentamente os canais oficiais e preparar-se para possíveis alterações.", "automatic":"exploratory_primary_advisory_with_localized_impact"},
    {"id":"laranja", "name":"Alerta", "criterion":"Potencial impacto na mobilidade e segurança; alta probabilidade de tempestades e eventos associados.",
     "reference":"PN 13/2026, art. 6º, IV", "orientation":"Avaliar mitigação e possíveis alterações; manutenção preferencial das atividades presenciais, conforme decisão competente.", "automatic":"exploratory_explicit_high_risk_in_primary_advisory"},
    {"id":"vermelho", "name":"Alerta Máximo", "criterion":"Perigo concreto e excepcional, ocorrência severa iminente ou ameaça à vida, conforme avaliação competente.",
     "reference":"PN 13/2026, art. 6º, V", "orientation":"A norma recomenda suspensão presencial no dia; a decisão, abrangência e vigência competem à autoridade responsável.", "automatic":"requires_explicit_imminent_severe_danger_not_numeric_peak"},
    {"id":"roxo", "name":"Calamidade", "criterion":"Desastre prolongado, danos e prejuízos ou declaração de emergência/calamidade, conforme avaliação competente.",
     "reference":"PN 13/2026, art. 6º, VI", "orientation":"A norma prevê suspensão por mais de um dia letivo, com período definido pela autoridade competente.", "automatic":"not_inferred_without_verified_impacts_or_decrees"},
]
DOCUMENTS = [
    {"number":13,"year":2026,"date":"2026-11-04","url":"./references/pn-13-2026.pdf",
     "title":"Protocolo institucional para situações de desastres", "verification_code":"4d5c6aed24"},
    {"number":14,"year":2026,"date":"2026-11-04","url":"./references/pn-14-2026.pdf",
     "title":"Reorganização e reposição das atividades acadêmicas", "verification_code":"6fb1144f73"},
]


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text).casefold()) if not unicodedata.combining(c))


def safe_official_url(value):
    try:
        url = urlparse(value)
        return url.scheme == 'https' and url.hostname == 'ciram.epagri.sc.gov.br' and not url.username and not url.password
    except (TypeError, ValueError):
        return False


def territorial_scope(notice):
    regions = fold(notice.get('regions_text') or '')
    if re.search(r'\b(exceto|excecao|menos|nao inclui)\b', regions):
        return None
    if re.search(r'\baraquari\b', regions):
        return 'municipality_explicit'
    if any(term in regions for term in ('litoral norte','todas as regio','todo o estado')):
        return 'regional_reference_not_municipal_confirmation'
    return None


def _applicable_clause(text, match):
    """A higher-risk phrase for another region must not escalate Araquari."""
    left = max(text.rfind(sep, 0, match.start()) for sep in ('.', ';', '\n')) + 1
    positions = [p for sep in ('.', ';', '\n') if (p := text.find(sep, match.end())) >= 0]
    clause = text[left:min(positions) if positions else len(text)]
    if re.search(r'exceto|excecao|menos (?:o )?litoral norte', clause):
        return False
    local = re.search(r'araquari|litoral norte|todas as regio|todo o estado', clause)
    other = re.search(r'\boeste\b|\bsul\b|planalto|vale do itajai|florianopolis', clause)
    return not other or bool(local)


def qualitative_match(text, lead_days):
    """Literal affirmative cues, never color conversion or free numeric scores."""
    text = fold(text)
    if re.search(r'\b(sem|nao ha|nao existe|descartad[oa])\b.{0,55}(risco|perigo|temporal|tempestade|impacto)', text):
        return None, None
    event_pattern = r'tempestade|temporais|temporal|alagamento|inundac|enxurrad|deslizamento|vento forte|chuva intensa|calor extremo|frio extremo|seca extrema'
    events = [m for m in re.finditer(event_pattern, text) if _applicable_clause(text, m)]
    if not events:
        return None, None
    if lead_days >= 7:
        return 'azul', events[0].group(0)
    patterns = [
        ('vermelho', r'ameaca (?:a|as) vida|ameaca a integridade|perigo concreto|(?:tempestade|temporal) sever[oa].{0,60}iminente|iminente.{0,60}(?:tempestade|temporal) sever[oa]'),
        ('laranja', r'risco (?:alto|muito alto|elevado)|alto risco|alta probabilidade'),
        ('amarelo', r'alagamento|destelhamento|queda de (?:arvore|galho)|interrupcao de energia|corte de energia'),
    ]
    for level, pattern in patterns:
        for match in re.finditer(pattern, text):
            if _applicable_clause(text, match):
                return level, match.group(0)
    return None, None


def assess(epagri, analysis, checked_at):
    now = moment(checked_at)
    if now is None:
        raise ValueError('Protocol assessment requires an aware timestamp')
    result = {"status":"insufficient_evidence", "suggested_level":None, "official_level":None,
              "title":"Enquadramento a verificar", "reason":"As categorias dependem de avaliação qualitativa e avisos oficiais aplicáveis a Araquari.",
              "evidence":[], "pending":[], "primary_source":"Epagri/Ciram",
              "valid_until":iso(now+timedelta(hours=3)), "rule_version":"pn13-14-2026-v1",
              "mapping_kind":"exploratory_qualitative_correspondence_not_official_classification"}
    if epagri.get('kind') != 'epagri_ciram_official_advisories_not_civil_defense_alerts' or epagri.get('status') not in ('available','cached','no_recent_notices') or not fresh(epagri.get('retrieved_at'),now,6):
        result['pending'].append('Avisos prioritários Epagri/Ciram indisponíveis ou desatualizados; conferir o canal oficial.')
    else:
        expirations = [now+timedelta(hours=3), moment(epagri['retrieved_at'])+timedelta(hours=6)]
        candidates = []
        for n in epagri.get('notices', [])[:8]:
            if not isinstance(n,dict) or n.get('notice_kind') != 'epagri_meteorological_advisory_not_civil_defense_alert' or not safe_official_url(n.get('url')):
                continue
            scope = territorial_scope(n)
            start,end = moment(n.get('valid_from')),moment(n.get('valid_until'))
            active = bool(start and end and start < end and end > now and start <= now+timedelta(days=14))
            entry = {"source":"Epagri/Ciram", "title":n.get('title'), "url":n['url'],
                     "scope":scope or 'not_verified', "regions_text":n.get('regions_text'),
                     "valid_from":n.get('valid_from'), "valid_until":n.get('valid_until'),
                     "published_at":n.get('published_at'), "checked_at":epagri.get('retrieved_at'),
                     "status":'eligible' if scope and active else 'expired' if end and end<=now else 'needs_territorial_or_temporal_check',
                     "supports_level":None,"matched_cue":None}
            if scope and active:
                lead = max(0,(start-now).total_seconds()/86400)
                text = str(n.get('assessment_text') or n.get('summary') or '')
                level,cue = qualitative_match(text,lead)
                entry.update(supports_level=level,matched_cue=cue)
                expirations.append(end)
                if level:
                    candidates.append(level)
            result['evidence'].append(entry)
        if candidates:
            order = {l['id']:i for i,l in enumerate(LEVELS)}
            chosen = max(candidates,key=lambda level:order[level])
            result.update(status='suggested_for_review',suggested_level=chosen,
                          title=f"{chosen.capitalize()} · {next(l['name'] for l in LEVELS if l['id']==chosen)}",
                          reason='Correspondência exploratória com trechos explícitos de aviso Epagri/Ciram aplicável ao período e à região; confirmar a avaliação local.')
        elif any(n['status']=='eligible' for n in result['evidence']):
            result.update(status='official_advisory_under_review',reason='Há aviso prioritário aplicável à região, mas o texto disponível não sustenta um nível específico com os critérios qualitativos da norma.')
        else:
            result['pending'].append('Ausência de aviso aplicável não comprova normalidade; não se atribui verde automaticamente.')
        result['valid_until'] = iso(min(expirations))
    result['pending'].append('Nível formal e decisões sobre atividades dependem da autoridade competente; não são determinados por este painel.')
    result['pending'].append('Danos locais, ameaça concreta e decretos não são verificados automaticamente; o nível roxo requer verificação externa.')
    return result


def reference():
    return {"status":"current_reference", "basis":"PN 13/2026 e PN 14/2026 — ASSINST/REI",
            "levels":LEVELS, "documents":DOCUMENTS, "priority_source":"Epagri/Ciram (PN 13, art. 4º)",
            "complementary_sources":"Defesa Civil estadual/municipal e demais órgãos (PN 13, art. 5º)",
            "decision_authority":"Direção-Geral (PN 13, art. 13)",
            "communication_deadlines":[{"shift":"Matutino","deadline":"22h do dia anterior"},
                                       {"shift":"Vespertino","deadline":"12h do dia"},
                                       {"shift":"Noturno","deadline":"17h do dia"}],
            "sudden_aggravation":"Emergência ou agravamento súbito permitem comunicação a qualquer momento (art. 12, parágrafo único).",
            "academic_rules":["PN 14, art. 1º: abrangência de até 10 dias letivos; acima disso, reavaliação pelo Conselho Superior.",
                              "PN 14, art. 6º, §7º: prazo mínimo de uma semana para atividades disponibilizadas, considerando condições de acesso.",
                              "PN 13, art. 10, I veda avaliações a partir do laranja; PN 14, art. 8º, III sugere suspensão no laranja e veda no vermelho. Divergência textual requer orientação institucional; não é resolvida pelo aplicativo."],
            "automatic_numeric_thresholds":False, "supersedes":"protocolo local anteriormente utilizado"}
