"""Qualitative municipal evidence; never hourly interpolation or numeric limits."""
from datetime import datetime, timedelta, timezone
import re
import unicodedata
from zoneinfo import ZoneInfo

from .analysis import fresh, iso, moment

TZ = ZoneInfo('America/Sao_Paulo')
# Operational display buckets, not exact event times supplied by INMET.
BOUNDS = {'manha': (0, 12), 'tarde': (12, 18), 'noite': (18, 24), 'dia': (0, 24)}
WEATHER = re.compile(r'(?:ceu claro|claro|poucas nuvens|muitas nuvens|parcialmente nublado|'
                     r'nublado|encoberto)(?: com (?:possibilidade de )?(?:chuva isolada|'
                     r'chuvas isoladas|chuvisco|nevoa umida|nevoa seca|nevoeiro|pancadas de chuva(?: isoladas)?))?')
HAZARDS = (('trovoadas', r'\btrovoadas?\b'),
           ('tempestade', r'\b(?:tempestades?|temporais|temporal)\b'),
           ('granizo', r'\bgranizo\b'),
           ('vento forte/intenso', r'\b(?:ventos?|rajadas)\b.{0,35}\b(?:fortes?|intensos?)\b'),
           ('chuva forte/intensa', r'\b(?:chuva|chuvas|pancadas de chuva)\b.{0,35}\b(?:fortes?|intensas?)\b'))


def normalized(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD', text or '') if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', text.casefold()).strip(' .;')


def assess(context, stamp):
    """Read original texts and cover [now,now+24h) without inventing samples.

    Unknown/negated text cannot certify quiet conditions. Any recognized hazard
    supports attention only, never a severe observation/model coincidence.
    """
    now = moment(stamp); end = now+timedelta(hours=24)
    rows = []; seen = set(); conflicts = set()
    for day in context.get('days', []):
        if day.get('source') not in ('INMET','CPTEC/INPE') or day.get('location_id') != 'araquari': continue
        expiry = moment(day.get('valid_until')); collected = moment(day.get('collected_at'))
        if not expiry or not collected or not collected <= now < expiry: continue
        if not fresh(day['collected_at'], now, 6): continue
        expiry = min(expiry, collected+timedelta(hours=6))
        if expiry <= now: continue
        try:
            start = datetime.strptime(day['day'], '%Y-%m-%d').replace(tzinfo=TZ).astimezone(timezone.utc)
        except (ValueError, TypeError, KeyError):
            continue
        periods = day.get('periods', [])
        labels = [p.get('period') for p in periods]
        if len(set(labels)) != len(labels) or ('dia' in labels and len(labels) > 1): continue
        for period in periods:
            label = period.get('period')
            if label not in BOUNDS: continue
            a, b = (start+timedelta(hours=h) for h in BOUNDS[label])
            if b <= now or a >= end: continue
            key = (day['source'], day['day'], label)
            if key in seen: conflicts.add(key)
            seen.add(key)
            summary = normalized(period.get('summary')); wind = normalized(period.get('wind_intensity_text'))
            # A negation prevents both automatic positive matching and a quiet
            # certificate; retain the source text for human interpretation.
            negated = bool(re.search(r'\b(?:sem|nao)\b', summary+' '+wind))
            phenomena = []
            for name, pattern in HAZARDS:
                for match in re.finditer(pattern, summary):
                    if not re.search(r'\b(?:sem|nao)\b', summary[max(0, match.start()-30):match.start()]):
                        phenomena.append(name); break
            if not re.search(r'\b(?:sem|nao)\b', wind) and re.search(r'\b(?:fortes?|intensos?)\b', wind):
                phenomena.append('vento forte/intenso')
            phenomena=list(dict.fromkeys(phenomena))
            hazard = bool(phenomena)
            rows.append({'source': day['source'], 'location_id': 'araquari', 'day': day['day'], 'period': label,
                         'summary': period.get('summary'), 'wind_intensity_text': period.get('wind_intensity_text'),
                         'collected_at': day['collected_at'], 'cached': day.get('cached', False),
                         'start_at': iso(a), 'end_at': iso(b), 'valid_until': iso(min(expiry, b)),
                         'time_basis': 'operational_period_bucket_not_exact_event_time',
                         'hazard': hazard, 'phenomena': phenomena, 'quiet_rain': not negated and not hazard and bool(WEATHER.fullmatch(summary) or (day['source']=='CPTEC/INPE' and period.get('quiet_rain_documented') is True)),
                         'quiet_wind': not negated and not hazard and wind in ('fraco', 'fracos', 'calmo', 'calmos')})
    rows = [r for r in rows if (r['source'], r['day'], r['period']) not in conflicts]
    coverage = {}
    for field in ('rain', 'wind'):
        cursor = now; used = []
        while cursor < end:
            choices = [r for r in rows if r['quiet_'+field] and moment(r['start_at']) <= cursor < moment(r['end_at'])]
            if not choices: break
            # Prefer the longer matching period; preserve actual source and
            # expiry. A positive cue from any source is handled separately.
            row = max(choices,key=lambda r:(moment(r['end_at']),moment(r['valid_until'])))
            used.append(row); cursor = moment(row['end_at'])
        complete = cursor >= end
        coverage[field] = {'available': complete, 'valid_until': min((r['valid_until'] for r in used), default=None) if complete else None,
                           'evidence': used if complete else [], 'resolution': 'qualitative_daily_or_period'}
    return {'periods': rows, 'coverage': coverage, 'horizon_start_at': stamp, 'horizon_end_at': iso(end)}
