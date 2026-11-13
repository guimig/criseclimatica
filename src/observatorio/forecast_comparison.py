"""Co-timed deterministic forecasts. Spread is not probability or model skill."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .analysis import fresh, hourly_bins, iso, local, moment, valid_number
from .open_meteo import URL

KIND = 'araquari_comparable_forecasts_not_probability'
ARCHIVE_KIND = 'araquari_forecasts_saved_before_verification'
MODELS = {'ecmwf_ifs025': 'ECMWF IFS · 0,25°', 'ncep_gfs_global': 'NOAA GFS · global'}
FIELDS = {'precipitation_mm': ('precipitation', 'mm', 0, 500),
          'temperature_c': ('temperature_2m', '°C', -80, 65),
          'wind_kmh': ('wind_speed_10m', 'km/h', 0, 400),
          'gust_kmh': ('wind_gusts_10m', 'km/h', 0, 450)}


def normalize(payload, model, location, stamp):
    if not isinstance(payload, dict) or payload.get('error') or payload.get('utc_offset_seconds') != 0:
        raise ValueError('Invalid model response or timezone')
    hourly, units = payload.get('hourly', {}), payload.get('hourly_units', {})
    if not isinstance(hourly, dict) or not isinstance(units, dict):
        raise ValueError('Invalid hourly response structure')
    times = hourly.get('time')
    if not isinstance(times, list) or not 1 <= len(times) <= 240:
        raise ValueError('Invalid model hourly series')
    for field, (key, unit, lo, hi) in FIELDS.items():
        if units.get(key) != unit or not isinstance(hourly.get(key), list) or len(hourly[key]) != len(times):
            raise ValueError('Invalid model units or array lengths')
    rows = []
    for index, value in enumerate(times):
        t = moment(value + 'Z' if isinstance(value, str) and len(value) == 16 else value)
        if t is None or t.minute or t.second:
            raise ValueError('Invalid model hourly timestamp')
        row = {'time': iso(t)}
        for field, (key, unit, lo, hi) in FIELDS.items():
            v = hourly[key][index]
            row[field] = v if valid_number(v, lo, hi) else None
        rows.append(row)
    lat, lon = payload.get('latitude'), payload.get('longitude')
    if not valid_number(lat, -90, 90) or not valid_number(lon, -180, 180):
        raise ValueError('Missing returned model grid')
    return {'id': model, 'name': MODELS[model], 'provider': 'Open-Meteo', 'status': 'available',
            'collected_at': stamp, 'model_run_at': None, 'location_id': location['id'],
            'requested_point': {k: location[k] for k in ('latitude', 'longitude')},
            'grid_point': {'latitude': lat, 'longitude': lon, 'elevation_m': payload.get('elevation')},
            'time_basis': 'UTC; rain at T covers (T-1h,T]; hourly provider output may be interpolated', 'hourly': rows}


def collect(location, stamp, *, fixture=False):
    records = []
    for model, name in MODELS.items():
        row = {'id': model, 'name': name, 'provider': 'Open-Meteo', 'status': 'unavailable', 'hourly': []}
        if fixture:
            row['diagnostic'] = 'fixture_mode_no_external_queries'
        else:
            params = {'latitude': location['latitude'], 'longitude': location['longitude'], 'models': model,
                      'hourly': ','.join(spec[0] for spec in FIELDS.values()), 'forecast_days': 7,
                      'timezone': 'UTC', 'wind_speed_unit': 'kmh', 'temperature_unit': 'celsius', 'precipitation_unit': 'mm'}
            try:
                request = Request(URL + '?' + urlencode(params), headers={'Accept': 'application/json', 'User-Agent': 'criseclimatica-model-comparison/1'})
                with urlopen(request, timeout=12) as response:
                    raw = response.read(1_000_001)
                    if len(raw) > 1_000_000:
                        raise ValueError('Forecast exceeds size limit')
                row = normalize(json.loads(raw), model, location, iso(datetime.now(timezone.utc)))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                row['diagnostic'] = type(exc).__name__
        records.append(row)
    return records


def _clean_series(row, now):
    if row.get('status') != 'available' or not fresh(row.get('collected_at'), now, 8):
        return {**row, 'status': 'unavailable', 'hourly': []}
    cleaned = []
    for item in row.get('hourly', []):
        if not isinstance(item, dict):
            continue
        t = moment(item.get('time'))
        if t is None or t.minute or t.second:
            continue
        cleaned.append({'time': iso(t), **{key: item.get(key) if valid_number(item.get(key), spec[2], spec[3]) else None
                                          for key, spec in FIELDS.items()}})
    bins = {key: hourly_bins(cleaned, key) for key in FIELDS}
    times = sorted({moment(r['time']) for r in cleaned})
    return {**row, 'hourly': [{'time': iso(t), **{key: values.get(t) for key, values in bins.items()}} for t in times]}


def summarize(detail, alternatives, cptec, stamp):
    now = moment(stamp)
    start = now.replace(minute=0, second=0, microsecond=0)
    reference = {'id': 'best_match', 'name': 'Open-Meteo · seleção automática', 'provider': 'Open-Meteo',
                 'status': 'available' if detail and fresh(detail.get('current', {}).get('time'), now, 8) else 'unavailable',
                 'location_id': 'araquari', 'collected_at': detail.get('collected_at'), 'reference_at': detail.get('current', {}).get('time'), 'model_run_at': None,
                 'grid_point': detail.get('grid_point'), 'requested_point': {k: detail.get('location', {}).get(k) for k in ('latitude', 'longitude')},
                 'hourly': detail.get('hourly', [])}
    records = [_clean_series(r, now) for r in [reference, *alternatives]]
    for row in records:
        row['hourly'] = [r for r in row['hourly'] if start <= moment(r['time']) <= start+timedelta(hours=168)]
    windows = []
    for hours in (24, 72):
        end = start + timedelta(hours=hours)
        metrics = []
        for field, (_, unit, _, _) in FIELDS.items():
            times = [start+timedelta(hours=i) for i in (range(1, hours+1) if field == 'precipitation_mm' else range(hours))]
            members = []
            for row in records:
                bins = hourly_bins(row['hourly'], field)
                values = [bins.get(t) for t in times]
                complete = all(v is not None for v in values)
                value = round(sum(values) if field == 'precipitation_mm' else max(values), 2) if complete else None
                peak_at = iso(times[values.index(max(values))]) if complete and field != 'precipitation_mm' else None
                members.append({'id': row['id'], 'name': row['name'], 'value': value, 'peak_at': peak_at,
                                'valid_hours': sum(v is not None for v in values), 'expected_hours': hours})
            eligible = [m for m in members if m['value'] is not None]
            low = min((m['value'] for m in eligible), default=None)
            high = max((m['value'] for m in eligible), default=None)
            comparable = len(eligible) >= 2
            metrics.append({'variable': field, 'unit': unit, 'statistic': 'sum' if field == 'precipitation_mm' else 'maximum',
                            'status': 'comparable' if comparable else 'insufficient_sources',
                            'minimum': low if comparable else None, 'maximum': high if comparable else None,
                            'spread': round(high-low, 2) if comparable else None,
                            'highest_sources': [m['id'] for m in eligible if m['value'] == high], 'members': members})
        windows.append({'hours': hours, 'start_at': iso(start), 'end_at': iso(end), 'metrics': metrics})
    cp = local(cptec or {}, 'araquari')
    cp_ready = cp.get('status') == 'available' and fresh((cptec or {}).get('checked_at'), now, 6)
    expirations=[now+timedelta(hours=3)]
    for record in records:
        if record['status']=='available':
            expirations.append(moment(record['collected_at'])+timedelta(hours=8))
    if records[0]['status']=='available':
        expirations.append(moment(detail['current']['time'])+timedelta(hours=8))
    return {'schema_version': 1, 'kind': KIND, 'location_id': 'araquari', 'generated_at': stamp,
            'valid_until': iso(min(expirations)), 'primary_id': 'best_match',
            'priority_reason': 'Operational hourly coverage; no demonstrated local skill ranking', 'records': records, 'windows': windows,
            'cptec': {'status': 'available' if cp_ready else 'unavailable', 'reported_status': cp.get('status', 'unavailable'),
                      'checked_at': (cptec or {}).get('checked_at'), 'updated_day': cp.get('updated_day'),
                      'locality': cp.get('nearest_cptec_locality'), 'days': cp.get('days', [])[:8],
                      'numeric_comparison': False, 'reason': 'daily_boundaries_and_locality_not_verified'},
            'limitations': ['Faixa entre previsões determinísticas; não é probabilidade nem intervalo de confiança.',
                           'A seleção automática pode compartilhar modelos com ECMWF e GFS; não são votos independentes.',
                           'Mesmo ponto solicitado, grades e resoluções diferentes. Comparação contextual, sem equivalência espacial comprovada.',
                           'Hora de coleta não é emissão do modelo. Horários de rodada não fornecidos por esta integração.',
                           'Nenhuma média, pontuação de confiança ou mudança automática do nível institucional.']}


def merge_archive(previous, comparison):
    now = moment(comparison['generated_at'])
    if previous is not None and (not isinstance(previous, dict) or previous.get('kind') != ARCHIVE_KIND
            or previous.get('schema_version') != 1 or previous.get('location_id') != 'araquari'
            or not isinstance(previous.get('publications'), list) or len(previous['publications']) > 64):
        raise ValueError('Invalid prior forecast archive; refusing loss')
    publications = {}
    for p in (previous or {}).get('publications', []):
        t = moment(p.get('saved_at')) if isinstance(p, dict) else None
        if t is None or not isinstance(p.get('records'), list):
            raise ValueError('Invalid prior forecast publication')
        if now-timedelta(days=7) <= t <= now:
            publications[p['saved_at']] = p
    rows = []
    for record in comparison['records']:
        # Keep the current forecast point for wind/temperature recovery as well
        # as future rainfall endpoints. These rows never become observations.
        hourly = [r for r in record['hourly'] if now.replace(minute=0, second=0, microsecond=0) <= moment(r['time']) <= now+timedelta(hours=72)]
        if hourly:
            rows.append({**record, 'hourly': hourly})
    publications[comparison['generated_at']] = {'saved_at': comparison['generated_at'], 'records': rows, 'cptec': comparison['cptec'], 'inmet': comparison.get('inmet')}
    return {'schema_version': 1, 'kind': ARCHIVE_KIND, 'location_id': 'araquari', 'generated_at': comparison['generated_at'],
            'retention_days': 7, 'verification_performed': False,
            'publications': sorted(publications.values(), key=lambda p: p['saved_at'])[-64:]}
