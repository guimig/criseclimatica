"""Transparent numeric context, using INMET references without issuing INMET alerts.

No weighted risk score or source vote. Different periods and station locations
remain explicit. Coincidence is contextual, not forecast skill or causality.
"""
from datetime import timedelta
from .inmet import haversine_km
from .analysis import fresh, hourly_bins, iso, moment, valid_number

REFERENCE_URLS = ['https://avisos.inmet.gov.br/54644',
                  'https://avisos.inmet.gov.br/56310',
                  'https://portal.inmet.gov.br/uploads/notastecnicas/Tabela-MS_tempo-severo_23-e-24-10-2021.pdf']


def band(value, variable):
    upper={'rain_1h_mm':500,'rain_24h_mm':1500,'wind_kmh':400,'gust_kmh':450}.get(variable,0)
    if not valid_number(value,0,upper): return None
    if variable == 'rain_1h_mm':
        return 3 if value>60 else 2 if value>=30 else 1 if value>=20 else 0
    if variable == 'rain_24h_mm':
        return 3 if value>100 else 2 if value>=50 else 0
    return 3 if value>100 else 2 if value>=60 else 1 if value>=40 else 0


def summarize(primary, detail, epagri, stamp, sensors=None):
    now=moment(stamp);signals=[];coincidences=[]
    def add(source, station, variable, value, start, end, kind, distance=None):
        b=band(value,variable)
        if b is None or moment(start) is None or moment(end) is None:return
        signals.append({'source':source,'station':station,'variable':variable,'value':value,
            'unit':'mm' if variable.startswith('rain') else 'km/h','band':b,'start_at':start,'end_at':end,
            'kind':kind,'distance_km':distance,'period_proxy':variable=='rain_24h_mm'})
    forecast=primary.get('forecast',{})
    rows=detail.get('hourly',[]) if forecast.get('status')=='available' else []
    rain=forecast.get('rain') or {}
    forecast_rain_valid=False
    if rain.get('status')=='complete':
        bins=hourly_bins(rows,'precipitation_mm');start=moment(rain['start_at']);end=moment(rain['end_at'])
        selected={t:v for t,v in bins.items() if start<t<=end}
        forecast_rain_valid=len(selected)==24 and valid_number(rain.get('total_mm'),0,24000) and abs(sum(selected.values())-rain['total_mm'])<=.11
        if forecast_rain_valid:
            t=max(selected,key=selected.get)
            add('open-meteo','araquari','rain_1h_mm',bins[t],iso(t-timedelta(hours=1)),iso(t),'forecast')
            add('open-meteo','araquari','rain_24h_mm',rain['total_mm'],rain['start_at'],rain['end_at'],'forecast')
    for field in ('wind_kmh','gust_kmh'):
        peak=forecast.get('wind',{}).get(field,{})
        if peak.get('status')=='complete' and peak.get('at'):
            add('open-meteo','araquari',field,peak['maximum'],peak['at'],peak['at'],'forecast')
    for s in primary.get('observed_rain',{}).get('stations',[]) if primary.get('observed_rain',{}).get('status')=='available' else []:
        distance=None
        point=detail.get('location',{})
        for ref in (sensors or {}).get('stations',[]):
            if (ref.get('code')==s['code'] and all(valid_number(x,-180,180) for x in (point.get('latitude'),point.get('longitude'),ref.get('latitude'),ref.get('longitude')))):
                distance=round(haversine_km(point['latitude'],point['longitude'],ref['latitude'],ref['longitude']),2)
                break
        end=moment(s.get('observed_at'))
        if end is None:continue
        for hours in (1,24):
            if fresh(s['observed_at'],now,1 if hours==1 else 6):
                add('cemaden',s['code'],f'rain_{hours}h_mm',s.get(f'rain_{hours}h_mm'),iso(end-timedelta(hours=hours)),iso(end),'observation',distance)
    for s in primary.get('recent_observations',[]):
        if s.get('source')!='NOAA/METAR' or not valid_number(s.get('distance_km'),0,25) or not fresh(s.get('observed_at'),now,2):continue
        for field in ('wind_kmh','gust_kmh'):
            add('metar',s['code'],field,s.get(field),s['observed_at'],s['observed_at'],'observation',s['distance_km'])
    # Compare each recent point to the model reference for THAT time, not to a
    # future 24-hour maximum. No numeric model-error statistic is produced.
    for s in [s for s in signals if s['kind']=='observation' and not s['period_proxy'] and s['band']]:
        field='precipitation_mm' if s['variable']=='rain_1h_mm' else s['variable']
        bins=hourly_bins(rows,field);end=moment(s['end_at'])
        near=[t for t in bins if abs((t-end).total_seconds())<=3600]
        if not near:continue
        t=min(near,key=lambda t:abs((t-end).total_seconds()))
        model_band=band(bins[t],s['variable'])
        if not model_band:continue
        if s['variable']=='rain_1h_mm' and not (t>moment(s['start_at']) and t-timedelta(hours=1)<end):continue
        coincidences.append({'variable':s['variable'],'station':s['station'],'observed_at':s['end_at'],
            'model_at':iso(t),'time_gap_minutes':abs((t-end).total_seconds())/60,
            'observed_band':s['band'],'model_band':model_band,'distance_km':s['distance_km'],
            'spatial_match_verified':valid_number(s['distance_km'],0,25),
            'interpretation':'coincident_attention_references_not_independent_confirmation'})
    numeric=[s for s in signals if s['band']>0]
    # Rolling 24h proxies do not alone establish a suggested institutional level.
    direct=[s for s in numeric if not s['period_proxy']]
    proposed='laranja' if any(c['observed_band']>=2 and c['model_band']>=2 and c['spatial_match_verified'] for c in coincidences) else 'amarelo' if any(s['band']>=2 for s in direct) or coincidences else None
    notices=primary.get('official_notices',{})
    pending_notices=[n for n in notices.get('notices',[]) if n.get('lifecycle')!='expired'] if notices.get('status')=='available' else []
    epagri_ok=epagri.get('status') in ('available','cached','no_recent_notices') and fresh(epagri.get('retrieved_at'),now,6)
    coverage_checks=[
        (forecast.get('status')=='available','Previsão Open-Meteo atual'),
        (forecast_rain_valid,'Chuva prevista: 24 horas completas'),
        (all(forecast.get('wind',{}).get(k,{}).get('status')=='complete' for k in ('wind_kmh','gust_kmh')),'Vento e rajadas previstos: 24 horas completas'),
        (any(s['source']=='cemaden' and s['variable']=='rain_1h_mm' for s in signals),'Chuva Cemaden local em 1 hora'),
        (any(s['source']=='cemaden' and s['variable']=='rain_24h_mm' for s in signals),'Chuva Cemaden local em 24 horas'),
        (epagri_ok,'Consulta Epagri/Ciram atual'),
    ]
    coverage_gaps=[label for valid,label in coverage_checks if not valid]
    core_complete=not coverage_gaps
    expiry=[now+timedelta(hours=3)]
    for signal in numeric:
        if signal['kind']=='observation':
            lifetime=1 if signal['variable']=='rain_1h_mm' else 6 if signal['variable']=='rain_24h_mm' else 2
            expiry.append(moment(signal['end_at'])+timedelta(hours=lifetime))
    return {'valid_until':iso(min(expiry)), 'method_version':'numeric-support-v1','reference_source':'INMET · referência auxiliar, não emissão de aviso',
        'reference_urls':REFERENCE_URLS,'signals':signals,'coincidences':coincidences,'proposed_level':proposed,
        'maximum_band':max((s['band'] for s in signals),default=None),'core_complete':core_complete,'coverage_gaps':coverage_gaps,
        'has_complementary_notices':bool(pending_notices),
        'period_note':'Acumulados móveis de 24h são aproximação comparativa da referência diária; não têm necessariamente os mesmos limites do dia.',
        'boundary_note':'Chuva horária: 20–<30 / 30–60 / >60 mm; vento: 40–<60 / 60–100 / >100 km/h. Limites compartilhados usam a faixa superior. Chuva 24h: ≥50–100 / >100 mm; valores abaixo de 50 não recebem faixa diária.',
        'interpretation':'Faixas técnicas não equivalem automaticamente aos níveis institucionais nem comprovam impactos locais.'}


def integrate(policy, objective):
    result={**policy,'numeric_support':objective,'rule_version':'pn13-14-2026-multisource-v3'}
    result['valid_until']=iso(min(moment(policy['valid_until']),moment(objective['valid_until'])))
    levels={'amarelo':2,'laranja':3,'vermelho':4,'azul':1,'verde':0}
    proposal=objective['proposed_level'];current=policy.get('suggested_level')
    if proposal and levels.get(proposal,0)>levels.get(current,0):
        result.update(suggested_level=proposal,status='suggested_for_review',basis_kind='complementary_numeric_evidence',
            title=proposal.capitalize()+' · '+('Alerta' if proposal=='laranja' else 'Atenção'),
            reason='Sugestão para avaliação com apoio em referências quantitativas identificadas. Epagri/Ciram permanece prioritária; este resultado não é uma classificação oficial do INMET ou uma decisão institucional.')
    elif current:result['basis_kind']='primary_epagri_advisory'
    else:result['basis_kind']='monitoring_state'
    if result.get('suggested_level'):
        state,label='heightened','Acompanhamento reforçado'
    elif objective['maximum_band'] and objective['maximum_band']>0:
        state,label='technical_attention','Referências de atenção'
    elif any(e.get('status')=='eligible' for e in policy.get('evidence',[])):
        state,label='official_context','Acompanhamento reforçado'
    elif any(e.get('status')=='needs_territorial_or_temporal_check' and (e.get('scope')!='not_verified' or not e.get('regions_text')) for e in policy.get('evidence',[])):
        state,label='partial','Monitoramento parcial'
    elif objective['core_complete']:
        state,label='routine','Monitoramento de rotina'
    else:state,label='partial','Monitoramento parcial'
    result.update(monitoring_state=state,monitoring_label=label)
    if not result.get('suggested_level'):
        result['title']=label
        result['reason']=('As referências monitoradas não foram superadas nas séries válidas. O acompanhamento continua, sem atribuição automática de normalidade institucional.' if state=='routine' else
            'Há dados disponíveis, mas a cobertura ainda é parcial. Consulte as referências válidas e as lacunas identificadas.' if state=='partial' else
            'Há referências ou avisos que justificam acompanhamento reforçado, sem elementos suficientes para sugerir um nível institucional específico.')
    return result
