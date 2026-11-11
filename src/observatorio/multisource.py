"""Local evidence synthesis; equal station relevance, no institutional decision."""
from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from statistics import mean, median
from zoneinfo import ZoneInfo

from .analysis import fresh, forecast_analysis, hourly_bins, iso, local, moment, valid_number
from .objective_analysis import band

VERSION = 'araquari-multisource-v1'
KIND = 'araquari_multisource_weather_not_institutional_level'
HISTORY_KIND = 'araquari_normalized_evidence_history'
STATIONS = {'420130701A': 'Rainha', '420130702A': 'Porto Grande',
            '420130704A': 'Centro', 'ifc-araquari': 'IFC Araquari'}
CAMPUS_FIELDS = {'temperature': ('temperature_c', '°C', -50, 65),
                 'humidity': ('humidity_pct', '%', 0, 100),
                 'pressure': ('pressure_hpa', 'hPa', 800, 1100),
                 'wind_avg': ('wind_kmh', 'km/h', 0, 400),
                 'wind_gust': ('gust_kmh', 'km/h', 0, 400),
                 'rain_daily': ('rain_daily_mm', 'mm', 0, 2000),
                 'rain_intensity': ('rain_intensity_mmh', 'mm/h', 0, 2000)}
LIFETIME = {'rain_1h_mm': 1, 'rain_24h_mm': 6}
MAX_HISTORY = 6000
TZ = ZoneInfo('America/Sao_Paulo')


def evidence(source, station, variable, value, end, *, hours=0, unit='', ttl=1.5, method='reported', **extra):
    t = moment(end)
    return {'source': source, 'station': station, 'name': STATIONS.get(station, station),
            'nature': 'observation', 'variable': variable, 'value': value, 'unit': unit,
            'start_at': iso(t-timedelta(hours=hours)), 'end_at': iso(t),
            'valid_until': iso(t+timedelta(hours=ttl)), 'method': method,
            'weight': 1, 'scope': 'araquari', **extra}


def local_observations(primary, campus, sensors, stamp):
    now = moment(stamp)
    rows, rejected = [], []
    rain = primary.get('observed_rain', {})
    if rain.get('status') == 'available':
        for s in rain.get('stations', []):
            if s.get('code') not in STATIONS: continue
            for hours in (1, 24):
                key = f'rain_{hours}h_mm'
                if valid_number(s.get(key), 0, 500 if hours == 1 else 1500) and fresh(s.get('observed_at'), now, LIFETIME[key]):
                    rows.append(evidence('cemaden', s['code'], key, s[key], s['observed_at'], hours=hours, unit='mm', ttl=LIFETIME[key]))
    if sensors.get('status') == 'available' and fresh(sensors.get('checked_at'), now, 6):
        for s in sensors.get('stations', []):
            if s.get('code') not in STATIONS: continue
            for r in s.get('readings', []):
                if r.get('sensor_id') == 60 and r.get('unit') == '°C' and valid_number(r.get('value'), -50, 65) and fresh(r.get('observed_at'), now, 1.5):
                    rows.append(evidence('cemaden', s['code'], 'temperature_c', r['value'], r['observed_at'], unit='°C'))
    if campus.get('status') == 'available' and fresh(campus.get('checked_at'), now, 1.5):
        metrics = campus.get('metrics', {})
        temp, humidity = (metrics.get(k, {}).get('latest') or {} for k in ('temperature', 'humidity'))
        # A simultaneous zero temperature/humidity is a known sensor failure
        # signature, not evidence of freezing weather or a reason to erase wind.
        suspect = (temp.get('value') == 0 and humidity.get('value') == 0 and temp.get('time') == humidity.get('time'))
        for key, (variable, unit, low, high) in CAMPUS_FIELDS.items():
            r = metrics.get(key, {}).get('latest') or {}
            reason = 'simultaneous_temperature_humidity_zero' if suspect and key in ('temperature', 'humidity') else None
            if not valid_number(r.get('value'), low, high) or not fresh(r.get('time'), now, 1.5):
                reason = reason or 'missing_invalid_or_stale'
            if reason:
                rejected.append({'station': 'ifc-araquari', 'variable': variable, 'reason': reason})
                continue
            rows.append(evidence('ifc', 'ifc-araquari', variable, r['value'], r['time'], unit=unit,
                                 method='reported_interval_unverified' if key.startswith('wind') else 'reported'))
    return rows, rejected


def merge_history(previous, observations, campus, stamp):
    now = moment(stamp)
    if previous is not None and (previous.get('kind') != HISTORY_KIND or previous.get('schema_version') != 1
                                or not isinstance(previous.get('records'), list) or len(previous['records']) > MAX_HISTORY):
        raise ValueError('Invalid multisource history; refusing history loss')
    candidates = list((previous or {}).get('records', [])) + observations
    # Counter history is necessary to derive rolling windows, never sum counters.
    if campus.get('status') in ('available', 'stale'):
        for p in campus.get('metrics', {}).get('rain_daily', {}).get('series', []):
            if moment(p.get('time')) and valid_number(p.get('value'), 0, 2000):
                candidates.append(evidence('ifc', 'ifc-araquari', 'rain_daily_mm', p['value'], p['time'], unit='mm', method='five_minute_counter_max'))
    unique, conflicts = {}, set()
    for r in candidates:
        t = moment(r.get('end_at')) if isinstance(r, dict) else None
        if (not t or not now-timedelta(days=7) <= t <= now or r.get('station') not in STATIONS
                or r.get('nature') != 'observation' or not valid_number(r.get('value'))): continue
        key = (r['station'], r['variable'], r['end_at'], r['method'])
        if key in unique and unique[key]['value'] != r['value']: conflicts.add(key)
        unique[key] = r
    for r in (previous or {}).get('conflicts', []):
        if moment(r.get('end_at')) and moment(r['end_at']) >= now-timedelta(days=7):
            conflicts.add((r['station'], r['variable'], r['end_at'], r['method']))
    records = sorted((r for k, r in unique.items() if k not in conflicts), key=lambda r: (r['end_at'], r['station'], r['variable']))[-MAX_HISTORY:]
    return {'schema_version': 1, 'kind': HISTORY_KIND, 'generated_at': stamp, 'retention_days': 7,
            'method_version': VERSION, 'records': records,
            'conflicts': [dict(zip(('station', 'variable', 'end_at', 'method'), k)) for k in sorted(conflicts)[-MAX_HISTORY:]]}


def counter_window(records, hours, stamp):
    """Counter differences only over continuous, monotonic, same-day samples.

    Do not reconstruct rain across an unverified reset; gaps >12 min invalidate
    the window. A rolling 24h window may consequently remain unavailable.
    """
    now = moment(stamp)
    points = {moment(r['end_at']): r['value'] for r in records
              if r['station'] == 'ifc-araquari' and r['variable'] == 'rain_daily_mm' and r['method'] == 'five_minute_counter_max'}
    if not points: return None
    end = max(points)
    start = end-timedelta(hours=hours)
    if not fresh(iso(end), now, 1 if hours == 1 else 1.5) or start not in points: return None
    selected = sorted(t for t in points if start <= t <= end)
    if any((b-a).total_seconds() > 720 or points[b] < points[a] for a, b in zip(selected, selected[1:])): return None
    if start.astimezone(TZ).date() != end.astimezone(TZ).date(): return None
    # MAX buckets provide an interval approximation, explicitly excluded from
    # institutional threshold matching until the source reset/interval is known.
    return evidence('ifc', 'ifc-araquari', f'rain_{hours}h_mm', round(points[end]-points[start], 3), iso(end),
                    hours=hours, unit='mm', ttl=LIFETIME[f'rain_{hours}h_mm'], method='counter_difference_5min_approximation',
                    interval_uncertainty_minutes=5, threshold_eligible=False)


def statistics(rows, variable, stamp):
    now = moment(stamp)
    selected = [r for r in rows if r['variable'] == variable and now < moment(r['valid_until']) and moment(r['end_at']) <= now]
    if not selected: return {'variable': variable, 'status': 'unavailable', 'members': [], 'station_count': 0}
    latest = max(moment(r['end_at']) for r in selected)
    cohort = [r for r in selected if latest-moment(r['end_at']) <= timedelta(minutes=30)]
    unique, conflicts = {}, set()
    for r in sorted(cohort, key=lambda r: r['end_at']):
        key = r['station']
        if key in unique and unique[key]['end_at'] == r['end_at'] and unique[key]['value'] != r['value']: conflicts.add(key)
        unique[key] = r
    members = [r for k, r in sorted(unique.items()) if k not in conflicts]
    if not members: return {'variable': variable, 'status': 'unavailable', 'members': [], 'station_count': 0}
    values = [r['value'] for r in members]
    return {'variable': variable, 'status': 'available', 'station_count': len(members), 'unit': members[0]['unit'],
            'mean': round(mean(values), 3), 'median': round(median(values), 3), 'minimum': min(values), 'maximum': max(values),
            'members': members, 'weighting': 'equal_per_station', 'excluded_time_count': len(selected)-len(cohort),
            'period_note': 'Same nominal interval; endpoints within 30 min. Counter-derived intervals retain 5 min uncertainty.'}


def select_forecast(comparison, stamp):
    """Select a complete product per variable; never splice hourly sources."""
    now = moment(stamp); start = now.replace(minute=0, second=0, microsecond=0)
    selections, combined = {}, {}
    records = comparison.get('records', [])
    for field in ('precipitation_mm', 'wind_kmh', 'gust_kmh', 'temperature_c'):
        slots = [start+timedelta(hours=i) for i in (range(1, 25) if field == 'precipitation_mm' else range(24))]
        candidates = []
        for record in records:
            if record.get('status') != 'available' or not fresh(record.get('collected_at'), now, 8): continue
            bins = hourly_bins(record.get('hourly', []), field)
            if not all(t in bins for t in slots): continue
            candidates.append((record, bins))
        if not candidates:
            selections[field] = {'status': 'unavailable', 'reason': 'no_complete_24h_product'}
            continue
        record, bins = candidates[0]
        selections[field] = {'status': 'available', 'id': record['id'], 'name': record['name'],
            'provider': record.get('provider', 'Open-Meteo'), 'collected_at': record['collected_at'],
            'valid_until': iso(moment(record['collected_at'])+timedelta(hours=8)),
            'fallback': record['id'] != 'best_match', 'reason': 'first_fresh_complete_product_not_skill_ranking',
            'requested_point': record.get('requested_point'), 'grid_point': record.get('grid_point')}
        for t, value in bins.items():
            combined.setdefault(t, {'time': iso(t)})[field] = value
    available = [s for s in selections.values() if s['status'] == 'available']
    detail = {'collected_at': min((s['collected_at'] for s in available), default=None),
              'current': {'time': min((s['collected_at'] for s in available), default=None)},
              'hourly': [r for _, r in sorted(combined.items())]}
    result = forecast_analysis(detail, now) if available else forecast_analysis({}, now)
    result['sources_by_variable'] = selections
    if selections['precipitation_mm'].get('id') != selections['gust_kmh'].get('id'):
        result['rain_wind_overlap'] = None
    return result, detail


def forecast_context(comparison, inmet, bulletins, stamp):
    now = moment(stamp); today = now.astimezone(TZ).date().isoformat()
    days = []
    if inmet.get('status') in ('available', 'cached') and fresh(inmet.get('retrieved_at'), now, 6) and moment(inmet.get('valid_until')) and now < moment(inmet['valid_until']):
        for day in inmet.get('days', []):
            if today <= day['day']:
                days.append({'source': 'INMET', 'day': day['day'], 'minimum_c': day.get('minimum_c'), 'maximum_c': day.get('maximum_c'),
                             'periods': day.get('periods', []), 'valid_until': inmet['valid_until'], 'collected_at': inmet['retrieved_at'],
                             'cached': inmet['status'] == 'cached', 'role': 'daily_and_period_synthesis'})
    cptec = comparison.get('cptec', {})
    if cptec.get('status') == 'available' and fresh(cptec.get('checked_at'), now, 6):
        for day in cptec.get('days', []):
            if day.get('day', '') >= today:
                days.append({'source': 'CPTEC/INPE', **day, 'locality': cptec.get('locality'),
                             'role': 'daily_context_boundaries_not_conciliated', 'collected_at': cptec['checked_at'],
                             'valid_until': iso(moment(cptec['checked_at'])+timedelta(hours=6))})
    editorial = []
    if bulletins.get('status') in ('available', 'cached') and fresh(bulletins.get('retrieved_at'), now, 6):
        editorial = [{'source': 'Epagri/Ciram', 'title': b.get('title'), 'url': b.get('url'),
                      'valid_until': iso(moment(bulletins['retrieved_at'])+timedelta(hours=6))} for b in bulletins.get('bulletins', [])[:4]]
    return {'days': days, 'editorial': editorial, 'comparison': inmet.get('daily_comparison', []),
            'shared_dependencies': ['best_match, ECMWF and GFS use Open-Meteo and may share model ancestry'],
            'hourly_product_priority': ['best_match', 'ecmwf_ifs025', 'ncep_gfs_global'],
            'priority_basis': 'operational_coverage_not_validated_local_skill',
            'other_sources': [{'source': 'OpenWeather', 'status': 'not_configured', 'reason': 'no_active_adapter_or_credentials_in_current_application'}]}


def notices(dashboard, stamp):
    now = moment(stamp); rows = []
    for n in dashboard.get('assessment', {}).get('base_assessment', {}).get('evidence', []):
        if n.get('status') != 'eligible' or not moment(n.get('valid_until')) or now >= moment(n['valid_until']): continue
        checked = moment(n.get('checked_at'))
        if not checked or not fresh(n['checked_at'], now, 6): continue
        rows.append({'source': 'Epagri/Ciram', 'id': n.get('url'), 'title': n.get('title'), 'url': n.get('url'),
                     'scope': n.get('scope'), 'start_at': n.get('valid_from'), 'end_at': n['valid_until'],
                     'valid_until': iso(min(moment(n['valid_until']), checked+timedelta(hours=6))),
                     'severity': n.get('supports_level') or 'Consultar texto original', 'weight': 1})
    feed = dashboard.get('inmet_context', {})
    if fresh(feed.get('retrieved_at'), now, 6) and (feed.get('status') == 'available' or feed.get('retained_previous')):
        for n in feed.get('notices', []):
            # Unverified windows remain accessible in details, not promoted to active evidence.
            start, end = moment(n.get('start_at')), moment(n.get('end_at'))
            if not start or not end or not start < end or end <= now or start > now+timedelta(days=14): continue
            if not any(m.get('location_id') == 'araquari' for m in n.get('municipalities', [])): continue
            rows.append({'source': 'INMET', 'id': n.get('id'), 'title': n.get('type'), 'url': n.get('url'),
                         'scope': 'municipality_explicit', 'start_at': n['start_at'], 'end_at': n['end_at'],
                         'valid_until': iso(min(end, moment(feed['retrieved_at'])+timedelta(hours=6))),
                         'severity': n.get('severity'), 'retained_previous': n.get('retained_previous', False), 'weight': 1})
    return sorted(rows, key=lambda n: (n['start_at'], n['source'], n['id'] or ''))


def build(dashboard, primary, campus, sensors, comparison, inmet, bulletins, stamp, previous=None):
    observations, rejected = local_observations(primary, campus, sensors, stamp)
    observations = [r for r in observations if moment(r["end_at"]) <= moment(stamp)]
    history = merge_history(previous, observations, campus, stamp)
    for hours in (1, 24):
        derived = counter_window(history['records'], hours, stamp)
        if derived: observations.append(derived)
    history = merge_history(history, observations, campus, stamp)
    variables = ('rain_1h_mm', 'rain_24h_mm', 'rain_daily_mm', 'rain_intensity_mmh', 'wind_kmh', 'gust_kmh', 'temperature_c', 'humidity_pct', 'pressure_hpa')
    stats = {k: statistics(observations, k, stamp) for k in variables}
    forecast, detail = select_forecast(comparison, stamp)
    advisory = notices(dashboard, stamp)
    signals = []
    for r in observations:
        b = band(r['value'], r['variable']) if r['variable'] in ('rain_1h_mm', 'rain_24h_mm', 'wind_kmh', 'gust_kmh') else None
        if b is not None and r.get('threshold_eligible', True): signals.append({**r, 'band': b})
    regional = []
    for r in primary.get('recent_observations', []):
        if r.get('source') != 'NOAA/METAR' or not valid_number(r.get('distance_km'), 0, 25) or not fresh(r.get('observed_at'), moment(stamp), 2): continue
        for variable in ('wind_kmh', 'gust_kmh', 'temperature_c'):
            value = r.get(variable)
            if not valid_number(value, -80 if variable == 'temperature_c' else 0, 65 if variable == 'temperature_c' else 450): continue
            row = evidence('NOAA/METAR', r['code'], variable, value, r['observed_at'], unit='°C' if variable == 'temperature_c' else 'km/h', ttl=2,
                           name=r.get('name') or r['code'], scope='regional_not_araquari_station', distance_km=r['distance_km'])
            regional.append(row)
            if variable != 'temperature_c': signals.append({**row, 'band': band(value, variable)})
    # Retain valid forecast evidence from each selected variable, no vote counting.
    for field, variable in (('precipitation_mm', 'rain_1h_mm'), ('wind_kmh', 'wind_kmh'), ('gust_kmh', 'gust_kmh')):
        source = forecast.get('sources_by_variable', {}).get(field, {})
        if source.get('status') != 'available': continue
        bins = hourly_bins(detail['hourly'], field); start = moment(forecast['start_at'])
        slots = [start+timedelta(hours=i) for i in (range(1, 25) if field == 'precipitation_mm' else range(24))]
        peak = max(slots, key=lambda t: bins[t])
        signals.append({'source': source['name'], 'station': 'araquari', 'name': source['name'], 'nature': 'forecast',
                        'variable': variable, 'value': bins[peak], 'unit': 'mm' if field == 'precipitation_mm' else 'km/h',
                        'start_at': iso(peak-timedelta(hours=1)) if field == 'precipitation_mm' else iso(peak),
                        'end_at': iso(peak), 'valid_until': source['valid_until'], 'band': band(bins[peak], variable)})
    coverage = {}
    for name, observed_fields, forecast_fields in (('rain', ('rain_1h_mm','rain_24h_mm'), ('precipitation_mm',)),
           ('wind', ('wind_kmh','gust_kmh'), ('wind_kmh','gust_kmh')), ('temperature', ('temperature_c',), ('temperature_c',))):
        obs = [r for r in observations if r['variable'] in observed_fields]
        pred = [forecast['sources_by_variable'][f] for f in forecast_fields if forecast['sources_by_variable'][f]['status'] == 'available']
        coverage[name] = {'status': 'observed_and_forecast' if obs and pred else 'observations_only' if obs else 'forecast_only' if pred else 'unavailable',
                          'observed_stations': sorted({r['station'] for r in obs}), 'forecast_sources': sorted({s['name'] for s in pred})}
    result = {'schema_version': 1, 'kind': KIND, 'method_version': VERSION, 'location_id': 'araquari', 'generated_at': stamp,
              'station_registry': [{'id': k, 'name': v, 'weight': 1} for k, v in STATIONS.items()],
              'observations': observations, 'regional_observations': regional, 'statistics': stats, 'rejected': rejected, 'signals': signals,
              'coverage': coverage, 'notices': advisory, 'forecast_context': forecast_context(comparison, inmet, bulletins, stamp),
              'selected_forecast': forecast, 'observation_history': [r for r in history['records'] if r['variable'] in ('rain_1h_mm','rain_24h_mm','temperature_c','wind_kmh','gust_kmh')],
              'formal_level': None, 'notice_weighting': 'equal_meteorological_relevance_not_institutional_color_conversion',
              'normative_assessment': deepcopy(dashboard['assessment']), 'institutional_decision_automated': False}
    return result, history, detail


def validate_product(data):
    if (data.get('kind') != KIND or data.get('method_version') != VERSION or data.get('location_id') != 'araquari'
            or data.get('formal_level') is not None or data.get('institutional_decision_automated') is not False
            or {s['id']:s['weight'] for s in data.get('station_registry', [])} != {k:1 for k in STATIONS}
            or len(data.get('observation_history', [])) > MAX_HISTORY):
        raise ValueError('Invalid multisource synthesis')
    for r in data.get('observations', []):
        if (r['station'] not in STATIONS or r['weight'] != 1 or not valid_number(r.get('value'))
                or not moment(r.get('end_at')) or not moment(r.get('valid_until'))):
            raise ValueError('Invalid local evidence')
    for stat in data.get('statistics', {}).values():
        members = stat.get('members', [])
        if stat['station_count'] != len({r['station'] for r in members}): raise ValueError('Duplicate stations in statistics')
        if members and abs(stat['mean']-mean(r['value'] for r in members)) > .001: raise ValueError('Unequal station weighting')
