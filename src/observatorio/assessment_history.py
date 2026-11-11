"""Sampled assessment episodes and Epagri validity windows; not disaster durations."""
from datetime import timedelta
from hashlib import sha256
from .analysis import iso,moment

KIND='araquari_assessment_episodes_and_epagri_notice_history'
MAX_EPISODES=3000
MAX_NOTICES=500


def merge(previous,dashboard,stamp):
    now=moment(stamp);stamp=iso(now);cutoff=now-timedelta(days=366);episodes=[];notices={}
    if previous is not None:
        if (not isinstance(previous,dict) or previous.get('kind')!=KIND or previous.get('schema_version')!=1
            or not isinstance(previous.get('episodes'),list) or len(previous['episodes'])>MAX_EPISODES
            or not isinstance(previous.get('notices'),list) or len(previous['notices'])>MAX_NOTICES):
            raise ValueError('Invalid previous assessment history; preserving publication')
        for old in previous['episodes']:
            first,last=moment(old.get('first_seen_at')),moment(old.get('last_seen_at'))
            if first is None or last is None or first>last or last>now:raise ValueError('Invalid assessment episode clock')
            if last>=cutoff:episodes.append(dict(old))
        for old in previous['notices']:
            if moment(old.get('last_seen_at')) is None:raise ValueError('Invalid notice history clock')
            if moment(old['last_seen_at'])>=cutoff:notices[old['id']]=dict(old)
    policy=dashboard['assessment'];state=policy.get('suggested_level') or policy.get('monitoring_state','partial')
    classification=dashboard.get('risk_classification')
    if classification:state=classification.get('level') or 'partial'
    version=classification['method_version'] if classification else policy.get('rule_version');last=episodes[-1] if episodes else None
    same=last and last['state']==state and last.get('rule_version')==version and now-moment(last['last_seen_at'])<=timedelta(hours=6)
    if same:
        if last['last_seen_at']!=stamp:last['samples']+=1
        last['last_seen_at']=stamp;last['last_sample_is_current']=True
    else:
        if last:
            last['last_sample_is_current']=False
            last['next_sample_at']=stamp
            last['transition_kind']='collection_gap' if now-moment(last['last_seen_at'])>timedelta(hours=6) else 'different_state_sampled'
        episodes.append({'state':state,'label':classification.get('name') if classification else policy.get('title'),'first_seen_at':stamp,'last_seen_at':stamp,
                         'samples':1,'rule_version':version,'last_sample_is_current':True})
    for e in episodes:
        e['sampled_span_hours']=round((moment(e['last_seen_at'])-moment(e['first_seen_at'])).total_seconds()/3600,3)
    for notice in policy.get('evidence',[]):
        if notice.get('status')!='eligible':continue
        identifier=sha256(notice['url'].encode()).hexdigest()[:20]
        first=notices.get(identifier,{}).get('first_seen_at',stamp)
        start,end=moment(notice.get('valid_from')),moment(notice.get('valid_until'))
        notices[identifier]={'id':identifier,'source':'Epagri/Ciram','title':notice.get('title'),'url':notice['url'],
            'start_at':notice.get('valid_from'),'end_at':notice.get('valid_until'),
            'validity_hours':round((end-start).total_seconds()/3600,3) if start and end and end>=start else None,
            'duration_kind':'explicit_instants','first_seen_at':first,'last_seen_at':stamp,
            'scope':notice.get('scope'),'regions_text':notice.get('regions_text')}
    return {'schema_version':1,'kind':KIND,'location_id':'araquari','generated_at':stamp,'retention_days':366,
            'episodes':episodes[-MAX_EPISODES:],
            'notices':sorted(notices.values(),key=lambda r:(r['last_seen_at'],r['id']))[-MAX_NOTICES:],
            'duration_note':'Span between observed samples is not continuous alert or weather-event duration. Validity windows describe the source notice, not an observed disaster.'}
