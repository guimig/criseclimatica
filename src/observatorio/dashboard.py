"""Compact Araquari dashboard, co-timed gauge distributions and bounded history."""
from __future__ import annotations

from datetime import timedelta
from statistics import median

from .analysis import fresh, hourly_bins, iso, local, moment, valid_number
from .protocol import assess, reference
from .objective_analysis import summarize as summarize_objective, integrate

KIND = 'araquari_weather_dashboard_not_official_decision'
HISTORY_KIND = 'araquari_point_observation_history_not_climatology'
RETENTION_DAYS = 7
MAX_HISTORY = 6000


def gauge_distribution(observed):
    stations = observed.get('stations', []) if observed.get('status') == 'available' else []
    valid = [s for s in stations if moment(s.get('observed_at')) and valid_number(s.get('rain_24h_mm'),0,1500)]
    result = {'status':'unavailable','station_count':0,'excluded_time_count':0,'median_mm':None,
              'minimum_mm':None,'maximum_mm':None,'latest_at':None,'earliest_at':None,
              'stations':[],'method':'same_24h_accumulation_endpoints_within_30_minutes_no_municipal_average'}
    if not valid:
        return result
    latest = max(moment(s['observed_at']) for s in valid)
    cohort = [s for s in valid if latest-moment(s['observed_at'])<=timedelta(minutes=30)]
    by_code = {}
    conflicts = set()
    for s in cohort:
        old = by_code.get(s['code'])
        if old and moment(old['observed_at']) == moment(s['observed_at']) and old['rain_24h_mm'] != s['rain_24h_mm']:
            conflicts.add((s['code'], s['observed_at']))
        if old is None or moment(s['observed_at']) >= moment(old['observed_at']):
            by_code[s['code']] = s
    cohort = [s for code,s in by_code.items() if (code,s['observed_at']) not in conflicts]
    if not cohort:
        return result
    latest = max(moment(s['observed_at']) for s in cohort)
    values = [s['rain_24h_mm'] for s in cohort]
    result.update(status='available',station_count=len(cohort),excluded_time_count=len(valid)-len(cohort),
                  median_mm=round(median(values),2) if len(values)>=3 else None,
                  minimum_mm=min(values), maximum_mm=max(values),latest_at=iso(latest),
                  earliest_at=iso(min(moment(s['observed_at']) for s in cohort)),
                  stations=[{'code':s['code'],'observed_at':s['observed_at'],'rain_24h_mm':s['rain_24h_mm']} for s in sorted(cohort,key=lambda s:s['code'])])
    return result


def merge_observations(previous, primary, stamp):
    now = moment(stamp)
    candidates = []
    status = 'first_publication'
    if isinstance(previous,dict) and previous.get('kind')==HISTORY_KIND and previous.get('schema_version')==1 and previous.get('location_id')=='araquari':
        if isinstance(previous.get('records'),list) and len(previous['records'])<=MAX_HISTORY:
            candidates = previous['records'][:]
            status = 'previous_recovered'
    if previous is not None and status != 'previous_recovered':
        raise ValueError('Invalid previous Araquari observation history; refusing loss')
    # Retain raw station references, never concatenate cumulative windows.
    for station in primary.get('observed_rain',{}).get('stations',[]):
        if fresh(station.get('observed_at'),now,6):
            candidates.append({'source':'cemaden-rain','station':station['code'],'observed_at':station['observed_at'],
                'distance_km':None, 'scope':'municipal_ibge_station_point',
                **{k:station.get(k) for k in ('rain_1h_mm','rain_24h_mm')}})
    for r in primary.get('recent_observations',[]):
        if valid_number(r.get('distance_km'),0,25) and fresh(r.get('observed_at'),now,6 if r['source']=='NOAA/METAR' else 3+20/60):
            candidates.append({'source':'metar' if r['source']=='NOAA/METAR' else 'cemaden-temperature',
                'station':r['code'],'observed_at':r['observed_at'],'distance_km':r['distance_km'],
                'scope':'nearby_station_not_municipal_measurement',
                **{k:r.get(k) for k in ('temperature_c','wind_kmh','gust_kmh')}})
    bounds = {'rain_1h_mm':(0,500),'rain_24h_mm':(0,1500),'temperature_c':(-80,65),'wind_kmh':(0,400),'gust_kmh':(0,450)}
    unique, conflicts = {}, set()
    if status == 'previous_recovered' and isinstance(previous.get('conflicts', []), list):
        for r in previous.get('conflicts', [])[:MAX_HISTORY]:
            if not isinstance(r, dict): continue
            dt = moment(r.get('observed_at'))
            if dt and now-timedelta(days=RETENTION_DAYS) <= dt <= now+timedelta(minutes=10):
                if r.get('source') in ('cemaden-rain','metar','cemaden-temperature') and isinstance(r.get('station'), str):
                    conflicts.add((r['source'],r['station'],iso(dt)))
    for r in candidates:
        if not isinstance(r,dict) or r.get('source') not in ('cemaden-rain','metar','cemaden-temperature'):
            continue
        dt = moment(r.get('observed_at'))
        if dt is None or not now-timedelta(days=RETENTION_DAYS)<=dt<=now+timedelta(minutes=10) or not isinstance(r.get('station'),str) or len(r['station'])>30:
            continue
        if r.get('source')!='cemaden-rain' and not valid_number(r.get('distance_km'),0,25):
            continue
        row = {k:r.get(k) for k in ('source','station','observed_at','distance_km','scope')}
        row['observed_at'] = iso(dt)
        for k,(lo,hi) in bounds.items():
            if valid_number(r.get(k),lo,hi): row[k]=r[k]
        if not any(k in row for k in bounds): continue
        key = (row['source'],row['station'],row['observed_at'])
        if key in unique and any(k in row and k in unique[key] and row[k]!=unique[key][k] for k in bounds):
            conflicts.add(key)
        else:
            unique[key] = {**unique.get(key,{}),**row}
    rows = sorted((r for key,r in unique.items() if key not in conflicts),key=lambda r:(r['observed_at'],r['source'],r['station']))[-MAX_HISTORY:]
    return {'schema_version':1,'kind':HISTORY_KIND,'location_id':'araquari','generated_at':stamp,
            'retention_days':RETENTION_DAYS,'recovery_status':status,'records':rows,
            'conflicting_records_discarded':len(conflicts),
            'conflicts':[{'source':key[0],'station':key[1],'observed_at':key[2]} for key in sorted(conflicts)[-MAX_HISTORY:]],
            'note':'Irregular station samples across publications; cumulative rain is not summed; gaps are not interpolated.'}


def chart_rows(detail, stamp):
    now=moment(stamp)
    if not detail or not fresh(detail.get('collected_at'),now,8) or not fresh(detail.get('current',{}).get('time'),now,8):
        return []
    fields = {key:hourly_bins(detail.get('hourly',[]),key) for key in ('precipitation_mm','temperature_c','wind_kmh','gust_kmh')}
    start=now.replace(minute=0,second=0,microsecond=0)
    return [{'time':iso(start+timedelta(hours=i)),**{key:values.get(start+timedelta(hours=i)) for key,values in fields.items()}}
            for i in range(241) if any(start+timedelta(hours=i) in values for values in fields.values())]


def summarize(analysis, details, epagri, bulletins, defesa, stamp, previous_history=None, sensors=None):
    primary=local(analysis,'araquari')
    if not primary:
        raise ValueError('Araquari analysis is required')
    policy=assess(epagri,analysis,stamp)
    history=merge_observations(previous_history,primary,stamp)
    forecast=primary.get('forecast',{})
    detail=details.get('araquari',{})
    policy=integrate(policy,summarize_objective(primary,detail,epagri,stamp,sensors=sensors))
    source_status = [
        {'source':'Epagri/Ciram · avisos','role':'prioritária','status':epagri.get('status','unavailable'),'reference_at':epagri.get('retrieved_at')},
        {'source':'Defesa Civil SC · publicações','role':'complementar','status':defesa.get('status','unavailable'),'reference_at':defesa.get('last_successful_check')},
        {'source':'INMET · avisos','role':'complementar','status':primary.get('official_notices',{}).get('status','unavailable'),'reference_at':primary.get('official_notices',{}).get('retrieved_at')},
        {'source':'Open-Meteo · previsão','role':'modelo','status':forecast.get('status','unavailable'),'reference_at':forecast.get('reference_at')},
        {'source':'Cemaden · chuva local','role':'observação','status':primary.get('observed_rain',{}).get('status','unavailable'),'reference_at':primary.get('observed_rain',{}).get('checked_at')},
    ]
    expiry=min(moment(primary['valid_until']),moment(policy['valid_until']))
    alerts=primary.get('official_notices',{})
    dashboard={'schema_version':1,'kind':KIND,'location_id':'araquari','generated_at':stamp,'valid_until':iso(expiry),
        'assessment':policy,'protocol':reference(),'gauge_distribution':gauge_distribution(primary.get('observed_rain',{})),
        'forecast':forecast,'forecast_series':chart_rows(detail,stamp),'revision':primary.get('revision',{}),
        'recent_observations':primary.get('recent_observations',[]),'temperature_context':primary.get('temperature_context',{}),
        'suggestions':primary.get('suggestions',[]),'limitations':primary.get('limitations',[]),
        'complementary_notices':alerts,'source_status':source_status,
        'editorial_context':{'status':bulletins.get('status','unavailable'),'bulletins':bulletins.get('bulletins',[])[:4]},
        'decision_automated':False}
    return dashboard,history
