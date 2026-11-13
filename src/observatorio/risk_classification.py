"""Traceable consultative classification using the six PN 13/2026 categories.

Operational numeric references remain auxiliary, not thresholds written in the
norm. Each candidate and the normality requirements retain individual validity.
"""
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo
from .analysis import fresh, hourly_bins, iso, moment
from .protocol import qualitative_match, LEVELS

VERSION = 'araquari-risk-v4'
ORDER = {level['id']: i for i, level in enumerate(LEVELS)}
NAMES = {level['id']: level['name'] for level in LEVELS}
VARIABLES = {'rain_1h_mm': 'Chuva em 1 h', 'rain_24h_mm': 'Chuva em 24 h',
             'wind_kmh': 'Vento', 'gust_kmh': 'Rajadas'}

RULES = {
    'verde': 'Chuva local de 1 h e 24 h e consulta atual de avisos; previsão horária completa ou cobertura qualitativa de 24 h com medições locais ou referências regionais identificadas de vento/rajadas para os campos substituídos; nenhum sinal de atenção.',
    'azul': 'Aviso aplicável com evento previsto para sete dias ou mais.',
    'amarelo': 'Faixa auxiliar atingida, aviso aplicável ou previsão municipal com trovoadas, tempestade, granizo, chuva forte/intensa ou vento forte/intenso; boletim/publicação com região e período explícitos ou acumulado curto que já atinge a referência de 24 h também sustentam atenção.',
    'laranja': 'Aviso com indicação explícita de risco alto/alta probabilidade ou medição e previsão compatíveis nas faixas intermediárias/superiores.',
    'vermelho': 'Aviso válido com indicação explícita de perigo concreto, tempestade severa iminente ou ameaça à vida; não resulta de um pico numérico isolado.',
    'roxo': 'Exige verificação de danos, desastre prolongado ou decreto aplicável. Não é atribuído automaticamente por esta versão.',
}


def evaluate(product, stamp):
    now = moment(stamp)
    valid = [c for c in product['candidates'] if moment(c.get('valid_until')) and now < moment(c['valid_until'])]
    chosen = max(valid, key=lambda c: ORDER[c['level']]) if valid else None
    if chosen:
        return {'level': chosen['level'], 'name': NAMES[chosen['level']], 'reason': chosen['reason'],
                'basis': chosen['basis'], 'valid_until': chosen['valid_until']}
    return {'level': None, 'name': 'Sem classificação', 'reason': 'Faltam referências atuais para definir o nível.',
            'basis': 'insufficient_current_evidence', 'valid_until': None}


def classify(dashboard, detail, stamp):
    now = moment(stamp); synthesis = dashboard['synthesis']; candidates = []; requirements = []
    def add(level, reason, basis, expires, refs):
        times = [moment(t) for t in expires]
        if times and all(t is not None and t > now for t in times):
            candidates.append({'level': level, 'reason': reason, 'basis': basis,
                               'valid_until': iso(min(times)), 'evidence': refs})

    signals = [r for r in synthesis['signals'] if moment(r.get('valid_until')) and now < moment(r['valid_until'])]
    # Every positive technical signal retains its own maximum; no station vote.
    for s in signals:
        if s['band'] <= 0: continue
        value = f"{s['value']:g}".replace('.', ',')
        forms = ('previstas','observadas') if s['variable']=='gust_kmh' else ('previsto','observado') if s['variable']=='wind_kmh' else ('prevista','observada')
        nature = forms[0 if s['nature']=='forecast' else 1]
        variable = VARIABLES[s['variable']]
        add('amarelo', f"{variable}{' no entorno' if s.get('scope') == 'regional_not_araquari_station' else ''}: {value} {s['unit']} ({nature}).", 'numeric_attention', [s['valid_until']], [s])

    # An approximate counter interval cannot support a severe coincidence, but
    # a high value must not be hidden behind a green average from other stations.
    from .objective_analysis import band
    for s in synthesis['observations']:
        if s.get('threshold_eligible') is not False or s['variable'] not in ('rain_1h_mm','rain_24h_mm'): continue
        if (band(s['value'],s['variable']) or 0)>0:
            add('amarelo','Chuva elevada na estação IFC; intervalo aproximado.','approximate_local_observation',[s['valid_until']],[s])

    # Reuse the established observation/model coincidence rule. Match the SAME
    # variable/time, never an unrelated future maximum or an unverified interval.
    forecast = synthesis['selected_forecast']
    for s in signals:
        if s['nature'] != 'observation' or s['band'] < 2 or s['variable'] == 'rain_24h_mm' or s.get('method') == 'reported_interval_unverified': continue
        field = 'precipitation_mm' if s['variable'] == 'rain_1h_mm' else s['variable']
        source = forecast.get('sources_by_variable', {}).get(field, {})
        if source.get('status') != 'available': continue
        if s.get('scope') == 'regional_not_araquari_station' and not 0 <= s.get('distance_km', 999) <= 25: continue
        bins = hourly_bins(detail.get('hourly', []), field)
        near = [t for t in bins if abs((t-moment(s['end_at'])).total_seconds()) <= 3600]
        if not near: continue
        t = min(near, key=lambda t: abs((t-moment(s['end_at'])).total_seconds()))
        if (band(bins[t], s['variable']) or 0) < 2: continue
        if field == 'precipitation_mm' and not (t > moment(s['start_at']) and t-timedelta(hours=1) < moment(s['end_at'])): continue
        add('laranja', f"{VARIABLES[s['variable']]}: medição elevada e previsão compatível no mesmo período.",
            'compatible_observation_and_forecast', [s['valid_until'], source['valid_until']],
            [s, {'source': source['name'], 'variable': field, 'at': iso(t), 'value': bins[t]}])

    warning_sources = []
    for source in dashboard.get('source_status', []):
        if source['source'] not in ('Epagri/Ciram · avisos', 'INMET · avisos'): continue
        if source.get('status') in ('available', 'cached', 'no_recent_notices') and fresh(source.get('reference_at'), now, 6):
            warning_sources.append({'source': source['source'], 'valid_until': iso(moment(source['reference_at'])+timedelta(hours=6))})

    for n in synthesis.get('notices', []):
        if not moment(n.get('valid_until')) or now >= moment(n['valid_until']): continue
        text = n.get('assessment_text') or n.get('title', '')
        start = moment(n.get('start_at'))
        lead = max(0, (start-now).total_seconds()/86400) if start else 0
        level, cue = qualitative_match(text, lead)
        level = n.get('normative_correspondence') or level or 'amarelo'
        expiry = [n['valid_until']]
        if level == 'azul' and start: expiry.append(iso(start-timedelta(days=7)+timedelta(seconds=1)))
        add(level, f"{n['source']}: {n.get('title') or 'aviso para Araquari'}.", 'applicable_official_notice', expiry, [{**n, 'matched_cue': cue}])

    # A positive, freshly queried municipal notice with an unverified window
    # prevents green; it supports attention, not a fabricated severe level.
    feed = dashboard.get('inmet_context', {})
    if feed.get('status') == 'available' and fresh(feed.get('retrieved_at'), now, 6):
        eligible_ids = {n.get('id') for n in synthesis.get('notices', []) if n['source'] == 'INMET'}
        for n in feed.get('notices', []):
            if n.get('id') in eligible_ids or n.get('lifecycle') == 'expired': continue
            if not any(m.get('location_id') == 'araquari' for m in n.get('municipalities', [])): continue
            reported_dates=re.findall(r'\d{2}/\d{2}/\d{4}',n.get('window_as_reported') or '')
            if reported_dates:
                try:
                    if datetime.strptime(reported_dates[-1],'%d/%m/%Y').date()<now.astimezone(ZoneInfo('America/Sao_Paulo')).date():continue
                except ValueError:continue
            end = moment(n.get('end_at')); start = moment(n.get('start_at'))
            if end and start and start < end and end <= now: continue
            # Date-only source clocks are not shifted to an invented timezone.
            add('amarelo', f"INMET: {n.get('type') or 'aviso para Araquari'}; validade a confirmar.",
                'positive_notice_pending_time_verification', [iso(moment(feed['retrieved_at'])+timedelta(hours=6))], [n])

    base = dashboard.get('assessment', {}).get('base_assessment', {})
    for n in base.get('evidence', []):
        if n.get('status') != 'eligible' or not n.get('supports_level'): continue
        if not fresh(n.get('checked_at'), now, 6): continue
        expiry=[n.get('valid_until'),iso(moment(n['checked_at'])+timedelta(hours=6))]
        if n['supports_level']=='azul' and moment(n.get('valid_from')):
            expiry.append(iso(moment(n['valid_from'])-timedelta(days=7)+timedelta(seconds=1)))
        add(n['supports_level'], f"Epagri/Ciram: {n.get('title') or 'aviso para a região'}.",
            'qualitative_epagri_evidence', expiry, [n])

    from .inmet_periods import assess as assess_inmet_periods
    qualitative = assess_inmet_periods(synthesis.get('forecast_context', {}), stamp)
    for row in qualitative['periods']:
        if row['hazard']:
            label = {'manha': 'manhã', 'tarde': 'tarde', 'noite': 'noite', 'dia': 'dia'}[row['period']]
            short_date = datetime.strptime(row['day'], '%Y-%m-%d').strftime('%d/%m')
            phenomena = ', '.join(row['phenomena'][:3])
            add('amarelo', f"{row['source']}: previsão de {phenomena} ({short_date}, {label}).",
                'inmet_qualitative_forecast_attention' if row['source']=='INMET' else 'cptec_qualitative_forecast_attention', [row['valid_until']], [row])

    for row in synthesis.get('observation_model_matches', []):
        add('laranja', f"{VARIABLES[row['variable']]}: medição elevada e previsão compatível no mesmo período.",
            'compatible_observation_and_additional_model', [row['valid_until']], [row['observation'],row['forecast']])
    for row in synthesis.get('publication_evidence', []):
        where = '' if row['scope']=='municipality_explicit' else ' na região'
        add('amarelo', f"{row['source']}: {', '.join(row['phenomena'][:2])}{where}.",
            'scoped_dated_publication_attention', [row['valid_until']], [row])
    for row in synthesis.get('antecedent_rain', {}).get('attention_lower_bounds', []):
        value = f"{row['value']:g}".replace('.', ',')
        add('amarelo', f"Chuva observada: {value} mm em {row['hours']} h.",
            'observed_shorter_window_lower_bound_24h', [row['valid_until']], [row])

    # Green requires positive coverage, not merely an empty warning list.
    for variable in ('rain_1h_mm', 'rain_24h_mm'):
        refs = [r for r in synthesis['observations'] if r['variable'] == variable and r.get('threshold_eligible', True)
                and moment(r.get('valid_until')) and now < moment(r['valid_until'])]
        requirements.append({'id': variable, 'label': VARIABLES[variable]+' observada', 'available': bool(refs),
                             'valid_until': max((r['valid_until'] for r in refs), default=None)})
    for field, label in (('precipitation_mm', 'Chuva prevista'), ('wind_kmh', 'Vento previsto'), ('gust_kmh', 'Rajadas previstas')):
        r = forecast.get('sources_by_variable', {}).get(field, {})
        hourly = r.get('status') == 'available' and moment(r.get('valid_until')) and now < moment(r['valid_until'])
        q = qualitative['coverage']['rain' if field == 'precipitation_mm' else 'wind']
        # Textual wind cannot replace a gust maximum. The qualitative route
        # additionally requires a real current local measurement of that field.
        observations = [o for o in synthesis['observations'] if o['variable'] == field
                        and o.get('scope') == 'araquari' and moment(o.get('valid_until'))
                        and moment(o.get('end_at')) and moment(o['end_at']) <= now < moment(o['valid_until'])]
        if not observations and field in ('wind_kmh','gust_kmh'):
            observations = [o for o in synthesis.get('regional_observations', []) if o['variable']==field
                            and o.get('source')=='NOAA/METAR' and 0<=o.get('distance_km',999)<=25
                            and moment(o.get('end_at')) and moment(o.get('valid_until'))
                            and moment(o['end_at'])<=now<moment(o['valid_until'])]
        regional = bool(observations) and all(o.get('scope')=='regional_not_araquari_station' for o in observations)
        alternative = q['available'] and (field == 'precipitation_mm' or bool(observations))
        expires = r.get('valid_until') if hourly else q['valid_until'] if alternative else None
        if alternative and not hourly and observations:
            expires = iso(min(moment(expires), max(moment(o['valid_until']) for o in observations)))
        if alternative and not hourly:
            label = {'precipitation_mm': 'Chuva prevista por período', 'wind_kmh': 'Vento qualitativo e observado',
                     'gust_kmh': 'Vento qualitativo e rajadas observadas'}[field]
        requirements.append({'id': field, 'label': label, 'available': bool(hourly or alternative), 'valid_until': expires,
                             'resolution': 'hourly_quantitative' if hourly else 'qualitative_daily_or_period' if alternative else None,
                             'spatial_scope':'regional_reference' if alternative and not hourly and regional else 'araquari',
                             'evidence': [r] if hourly else q['evidence']+observations if alternative else []})
    requirements.append({'id': 'warnings', 'label': 'Consulta de avisos', 'available': bool(warning_sources),
                         'valid_until': max((r['valid_until'] for r in warning_sources), default=None)})
    pending_epagri = [n for n in base.get('evidence', []) if n.get('status') == 'needs_territorial_or_temporal_check'
                      and n.get('scope') != 'not_verified' and fresh(n.get('checked_at'), now, 6)]
    requirements.append({'id': 'epagri_pending', 'label': 'Abrangência e validade dos avisos', 'available': not pending_epagri,
                         'valid_until': iso(now+timedelta(hours=8)) if not pending_epagri else None})
    if all(r['available'] and moment(r['valid_until']) and now < moment(r['valid_until']) for r in requirements) and not candidates:
        add('verde', 'Sem sinais de atenção nas referências monitoradas.', 'qualitative_monitored_coverage' if any(r.get('resolution') == 'qualitative_daily_or_period' for r in requirements) else 'complete_monitored_coverage',
            [r['valid_until'] for r in requirements], requirements)
    product = {'schema_version': 1, 'method_version': VERSION, 'generated_at': stamp,
               'kind': 'consultative_risk_level_not_official_decision', 'official_level': None,
               'candidates': sorted(candidates, key=lambda c: ORDER[c['level']], reverse=True),
               'quantitative_context': synthesis.get('daily_quantitative', []),
               'requirements': requirements, 'warning_sources': warning_sources, 'qualitative_forecast': qualitative,
               'coverage': {'forecast_resolution': 'mixed_or_qualitative' if any(r.get('resolution') == 'qualitative_daily_or_period' for r in requirements) else 'hourly' if all(r.get('available') for r in requirements if r['id'] in ('precipitation_mm', 'wind_kmh', 'gust_kmh')) else 'incomplete',
                            'regional_reference_used':any(r.get('spatial_scope')=='regional_reference' for r in requirements),
                            'retained_hourly_variables': [k for k, r in forecast.get('sources_by_variable', {}).items() if r.get('retained_previous')]},
               'levels': [{'id': k, 'name': NAMES[k], 'criterion': RULES[k]} for k in ORDER],
               'limitations': ['Calamidade exige evidências verificadas de impacto ou decreto; não é inferida dos sensores.',
                              'Faixas numéricas são referências auxiliares do aplicativo, não limites definidos pela portaria.',
                              'Previsão diária/por turno é qualitativa; não comprova chuva ou rajadas abaixo de limites numéricos.']}
    product.update(evaluate(product, stamp))
    return product


def validate_product(data):
    if (data.get('method_version') != VERSION or data.get('kind') != 'consultative_risk_level_not_official_decision'
            or data.get('official_level') is not None or data.get('level') not in (None, *ORDER)
            or not isinstance(data.get('candidates'), list)):
        raise ValueError('Invalid consultative risk classification')
    for c in data['candidates']:
        if c['level'] not in ORDER or c['level'] == 'roxo' or not moment(c.get('valid_until')) or not c.get('evidence'):
            raise ValueError('Risk classification must have eligible supporting evidence')
    if evaluate(data, data['generated_at'])['level'] != data['level']:
        raise ValueError('Classification differs from its evidence')


def history_snapshot(product):
    """Bounded audit record; current dashboard keeps complete supporting data."""
    from copy import deepcopy
    keys=('generated_at','method_version','level','name','basis','valid_until','kind','official_level','coverage')
    result={k:deepcopy(product[k]) for k in keys if k in product}
    result['record_kind']='classification_summary_with_evidence_references'
    result['candidates']=[]
    for c in product['candidates']:
        row={k:deepcopy(c[k]) for k in ('level','reason','basis','valid_until')}
        row['evidence']=[{k:deepcopy(e[k]) for k in ('source','station','variable','value','unit','start_at','end_at','valid_until',
                         'url','day','period','phenomena','scope','method','id','available','resolution','spatial_scope') if k in e}
                         for e in c['evidence']]
        result['candidates'].append(row)
    return result
