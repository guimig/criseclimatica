"""Additional traceable evidence; heterogeneous products never become votes."""
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .analysis import fresh, hourly_bins, iso, moment, valid_number
from .inmet import haversine_km
from .inmet_periods import normalized, HAZARDS
from .objective_analysis import band

TZ = ZoneInfo('America/Sao_Paulo')
# Official CPTEC XML legend: https://servicos.cptec.inpe.br/XML/
CPTEC = {'ec':'Encoberto com chuvas isoladas','ci':'Chuvas isoladas','c':'Chuva','in':'Instável',
         'pp':'Possibilidade de pancadas de chuva','cm':'Chuva pela manhã','cn':'Chuva à noite',
         'pt':'Pancadas de chuva à tarde','pm':'Pancadas de chuva pela manhã','np':'Nublado e pancadas de chuva',
         'pc':'Pancadas de chuva','pn':'Parcialmente nublado','cv':'Chuvisco','ch':'Chuvoso','t':'Tempestade',
         'ps':'Predomínio de sol','e':'Encoberto','n':'Nublado','cl':'Céu claro','nv':'Nevoeiro','g':'Geada','ne':'Neve'}
QUIET_CPTEC = {'pn','ps','e','n','cl','cv','ci','ec'}


def eligible(feed, stamp, clock='retrieved_at', hours=6):
    now = moment(stamp); t = moment(feed.get(clock))
    return (feed.get('status') in ('available','cached','partial') and t is not None
            and t <= now < t+timedelta(hours=hours))


def cptec_days(comparison, stamp):
    feed = comparison.get('cptec', {}); now = moment(stamp)
    if not eligible(feed, stamp, 'checked_at') or normalized(feed.get('locality')) != 'araquari': return []
    try:
        updated = datetime.strptime(feed.get('updated_day',''), '%Y-%m-%d').date()
    except ValueError: return []
    if not now.astimezone(TZ).date()-timedelta(days=1) <= updated <= now.astimezone(TZ).date(): return []
    out=[]
    for day in feed.get('days', []):
        code=day.get('condition_code'); summary=CPTEC.get(code)
        if not summary: continue
        out.append({**day, 'source':'CPTEC/INPE','location_id':'araquari',
                    'collected_at':feed['checked_at'],'valid_until':iso(moment(feed['checked_at'])+timedelta(hours=6)),
                    'periods':[{'period':'dia','summary':summary,'wind_intensity_text':'',
                                'quiet_rain_documented':code in QUIET_CPTEC}],
                    'role':'municipal_daily_qualitative_and_numeric_temperature'})
    return out


def model_evidence(comparison, archive, stamp, *, observed_signals=(), matches=None, selected=None):
    from .multisource import select_forecast
    now=moment(stamp); start=now.replace(minute=0,second=0,microsecond=0)
    signals=[]; ranges=[]; temperatures=[]
    for identifier in ('best_match','ecmwf_ifs025','ncep_gfs_global'):
        old=None
        if archive:
            old={**archive,'publications':[{**p,'records':[r for r in p.get('records',[]) if r.get('id')==identifier]}
                                          for p in archive.get('publications',[])]}
        f,detail=select_forecast({'records':[r for r in comparison.get('records',[]) if r.get('id')==identifier]},stamp,old)
        for field,variable in (('precipitation_mm','rain_1h_mm'),('wind_kmh','wind_kmh'),('gust_kmh','gust_kmh')):
            source=f['sources_by_variable'][field]
            if source['status']!='available': continue
            bins=hourly_bins(detail['hourly'],field)
            slots=[start+timedelta(hours=i) for i in (range(1,25) if field=='precipitation_mm' else range(24))]
            peak=max(slots,key=lambda t:bins[t]); value=bins[peak]
            signals.append({'source':source['name'],'station':'araquari','name':source['name'],'model_id':identifier,
                            'nature':'forecast','variable':variable,'value':value,'unit':'mm' if field=='precipitation_mm' else 'km/h',
                            'start_at':iso(peak-timedelta(hours=1)) if field=='precipitation_mm' else iso(peak),
                            'end_at':iso(peak),'valid_until':source['valid_until'],'band':band(value,variable),
                            'collected_at':source['collected_at'],'retained_previous':source['retained_previous']})
        if matches is not None:
            for observation in observed_signals:
                variable=observation['variable']
                if observation.get('nature')!='observation' or observation.get('band',0)<2 or variable=='rain_24h_mm':continue
                if observation.get('method')=='reported_interval_unverified':continue
                if observation.get('scope')=='regional_not_araquari_station' and observation.get('distance_km',999)>25:continue
                field='precipitation_mm' if variable=='rain_1h_mm' else variable
                source=f['sources_by_variable'].get(field,{})
                primary=(selected or {}).get('sources_by_variable',{}).get(field,{})
                if source.get('status')!='available' or (source.get('id'),source.get('collected_at'))==(primary.get('id'),primary.get('collected_at')):continue
                measured=moment(observation.get('end_at')); deadline=moment(observation.get('valid_until'))
                if not measured or not deadline or not measured<=now<deadline:continue
                bins=hourly_bins(detail['hourly'],field)
                near=[t for t in bins if abs((t-measured).total_seconds())<=3600]
                if not near:continue
                t=min(near,key=lambda t:abs((t-measured).total_seconds()))
                if (band(bins[t],variable) or 0)<2:continue
                if field=='precipitation_mm' and not (t>moment(observation['start_at']) and t-timedelta(hours=1)<measured):continue
                matches.append({'variable':variable,'observation':observation,'model_id':identifier,
                                'forecast':{'source':source['name'],'collected_at':source['collected_at'],'at':iso(t),'value':bins[t]},
                                'valid_until':iso(min(deadline,moment(source['valid_until'])))})
        s=f['sources_by_variable']['temperature_c']
        if s['status']=='available':
            bins=hourly_bins(detail['hourly'],'temperature_c')
            # A civil-day comparison requires every hour of that same day.
            for offset in (0,1):
                day=(now.astimezone(TZ)+timedelta(days=offset)).date()
                midnight=datetime.combine(day,datetime.min.time(),TZ)
                slots=[(midnight+timedelta(hours=i)).astimezone(timezone.utc) for i in range(24)]
                if all(t in bins for t in slots):
                    temperatures.append({'source':s['name'],'day':day.isoformat(),'minimum_c':min(bins[t] for t in slots),
                                         'maximum_c':max(bins[t] for t in slots),'valid_until':s['valid_until'],
                                         'kind':'extremes_of_24_hourly_samples','collected_at':s['collected_at']})
    for variable in ('rain_1h_mm','wind_kmh','gust_kmh'):
        rows=[r for r in signals if r['variable']==variable]
        if rows:
            ranges.append({'variable':variable,'minimum':min(r['value'] for r in rows),'maximum':max(r['value'] for r in rows),
                           'attention_disagreement':len({r['band']>0 for r in rows})>1,'members':rows,
                           'independent_provider_count':1,'interpretation':'different_forecasts_not_probability_or_votes'})
    return signals,ranges,temperatures


def antecedent_rain(primary, stamp):
    now=moment(stamp); groups=[]; lower_bounds=[]
    for h in (3,6,12,48,72):
        field=f'rain_{h}h_mm'; rows=[]
        for s in primary.get('observed_rain',{}).get('stations',[]):
            from .multisource import STATIONS
            t=moment(s.get('observed_at')); value=s.get(field)
            if s.get('code') not in STATIONS or not t or not t<=now<t+timedelta(hours=6) or not valid_number(value,0,5500):continue
            # Inconsistent nested accumulations are retained only in raw source.
            known=[(k,s.get(f'rain_{k}h_mm')) for k in (1,3,6,12,24,48,72) if valid_number(s.get(f'rain_{k}h_mm'),0,5500)]
            if any(a>b for (_,a),(_,b) in zip(known,known[1:])):continue
            row={'source':'cemaden','station':s['code'],'variable':field,'value':value,'unit':'mm','hours':h,
                 'start_at':iso(t-timedelta(hours=h)),'end_at':iso(t),'valid_until':iso(t+timedelta(hours=6)),'weight':1}
            rows.append(row)
            if h<=12 and (band(value,'rain_24h_mm') or 0)>0 and not valid_number(s.get('rain_24h_mm'),0,5500):
                lower_bounds.append({**row,'kind':'lower_bound_of_24h_not_reconstructed_total'})
        if rows:
            groups.append({'hours':h,'members':rows,'maximum':max(r['value'] for r in rows),
                           'station_count':len({r['station'] for r in rows}),'equal_station_weight':True})
    return {'windows':groups,'attention_lower_bounds':lower_bounds,
            'interpretation':'antecedent_accumulations_not_new_normative_thresholds'}


def regional_inmet_rain(feed, point, stamp):
    now=moment(stamp); out=[]
    if not eligible(feed,stamp,'checked_at') or not all(valid_number(point.get(k)) for k in ('latitude','longitude')):return out
    for s in feed.get('stations',[]):
        if not all(valid_number(s.get(k)) for k in ('latitude','longitude')):continue
        distance=haversine_km(point['latitude'],point['longitude'],s['latitude'],s['longitude'])
        t=moment(s.get('observed_at'))
        if distance>25 or not t or t>now:continue
        for field,key,h,ttl in (('rain_1h_mm','rain_last_hour_mm',1,1),('rain_24h_mm','rain_last_24_readings_mm',24,6)):
            value=s.get(key)
            if not valid_number(value,0,500 if h==1 else 1500) or now>=t+timedelta(hours=ttl):continue
            if h==24 and (not s.get('rain_24h_complete') or s.get('hourly_coverage_24')!=24):continue
            out.append({'source':'INMET · pluviometria','station':s['code'],'name':s.get('name') or s['code'],
                        'nature':'observation','scope':'regional_not_araquari_station','distance_km':round(distance,1),
                        'variable':field,'value':value,'unit':'mm','start_at':iso(t-timedelta(hours=h)),
                        'end_at':iso(t),'valid_until':iso(t+timedelta(hours=ttl)),'band':band(value,field),
                        'method':'reported_hourly_raw_not_homogenized'})
    return out


def scope(text):
    text=normalized(text)
    if re.search(r'\b(?:exceto|excecao|nao inclui)\b',text):return None
    if re.search(r'\baraquari\b',text):return 'municipality_explicit'
    if re.search(r'litoral norte|norte catarinense|faixa leste do estado|todo o estado|todas as regio|\bem sc\b|em santa catarina',text):
        return 'regional_reference_not_municipal_confirmation'
    return None


def publication_evidence(bulletins, defesa, stamp):
    from .epagri_notices import _window
    now=moment(stamp); rows=[]; pending=[]
    for feed,source,key in ((bulletins,'Epagri/Ciram','bulletins'),(defesa,'Defesa Civil SC','publications')):
        clock='retrieved_at' if source=='Epagri/Ciram' else 'last_successful_check'
        if not eligible(feed,stamp,clock):continue
        query_end=moment(feed[clock])+timedelta(hours=6)
        for p in feed.get(key,[])[:4]:
            url=urlparse(p.get('url',''))
            hosts=('ciram.epagri.sc.gov.br',) if source=='Epagri/Ciram' else ('defesacivil.sc.gov.br','www.defesacivil.sc.gov.br')
            if url.scheme!='https' or url.hostname not in hosts or url.username or url.password:continue
            text=p.get('assessment_text') or p.get('summary','')
            published=moment(p.get('published_at'))
            if not published or published>now:continue
            start,end=_window(text)
            blocks=[]
            if start and end and moment(start)<moment(end):
                # Explicit windows require an explicit regional scope label.
                region=re.search(r'(?:Regi[oõ]es|Regi[aã]o|Munic[ií]pios|Abrang[eê]ncia)\s*:\s*([^\n.;]{1,220})',text,re.I)
                if region and scope(region[1]):blocks=[(start,end,text,scope(region[1]))]
            if not blocks and source=='Epagri/Ciram':
                # Editorial civil dates, never publication time as event time.
                headers=list(re.finditer(r'\((\d{2})/(\d{2})(?:/(\d{4}))?\)\s*:',text))
                for i,m in enumerate(headers):
                    try:
                        a=datetime(int(m[3] or published.astimezone(TZ).year),int(m[2]),int(m[1]),tzinfo=TZ).astimezone(timezone.utc)
                    except ValueError:continue
                    block=text[m.end():headers[i+1].start() if i+1<len(headers) else len(text)]
                    for clause in re.split(r'[.;\n]',block):
                        if scope(clause):blocks.append((iso(a),iso(a+timedelta(days=1)),clause,scope(clause)))
            emitted=False
            for a,b,text,territory in blocks:
                if moment(b)<=now or moment(a)>=now+timedelta(hours=24):continue
                folded=normalized(text)
                phenomena=[]
                for clause in re.split(r'[.;\n]',folded):
                    if re.search(r'\b(?:oeste|sul|planalto)\b|vale do itajai|florianopolis',clause) and not scope(clause):continue
                    if re.search(r'\b(?:sem|nao|descartad[oa])\b',clause):continue
                    phenomena += [name for name,pattern in HAZARDS if re.search(pattern,clause)]
                phenomena=list(dict.fromkeys(phenomena))
                impact=re.search(r'\b(?:foram|foi)\s+(?:registrad[oa]s?|confirmad[oa]s?).{0,50}(?:alagamentos?|inundac|destelhamento|interrupcao de energia)',folded)
                if impact and re.search(r'\b(?:oeste|sul|planalto)\b',folded) and not scope(impact.group(0)):impact=None
                if not phenomena and not impact:continue
                rows.append({'source':source,'title':p.get('title'),'url':p['url'],'summary':text[:900],
                             'scope':territory,'start_at':a,'end_at':b,'valid_until':iso(min(query_end,moment(b))),
                             'phenomena':phenomena or ['impactos relatados'],'level':'amarelo','collected_at':feed[clock],
                             'kind':'scoped_dated_publication_attention_not_verified_disaster'})
                emitted=True
            if not emitted:pending.append({'source':source,'title':p.get('title'),'url':p['url'],
                                           'reason':'missing_applicable_window_scope_or_positive_cue'})
    # Same announcement may be present in multiple categories; do not multiply it.
    unique={(r['source'],r['url'],r['start_at'],r['summary']):r for r in rows}
    bounded=[]
    for source in ('Epagri/Ciram','Defesa Civil SC'):
        bounded += sorted((r for r in unique.values() if r['source']==source),key=lambda r:(r['scope']!='municipality_explicit',r['start_at'],r['url']))[:8]
    return bounded,pending[:8]


def sensor_inventory(sensors, stamp):
    now=moment(stamp); rows=[]
    if not eligible(sensors,stamp,'checked_at'):return rows
    for s in sensors.get('stations',[]):
        from .multisource import STATIONS
        if s.get('code') not in STATIONS:continue
        for r in s.get('readings',[]):
            t=moment(r.get('observed_at'))
            if not t or not t<=now<t+timedelta(minutes=90):continue
            use='temperature_observation' if r.get('sensor_id')==60 and r.get('unit')=='°C' else 'context_only'
            rows.append({'station':s['code'],'sensor_id':r.get('sensor_id'),'name':r.get('sensor_name'),
                         'value':r.get('value'),'unit':r.get('unit'),'use':use,
                         'reason':None if use!='context_only' else 'unit_or_interval_or_risk_reference_not_confirmed'})
    return rows
