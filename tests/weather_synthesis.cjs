const assert=require('node:assert/strict');
global.window={};global.document={getElementById:()=>null};require('../web/weather-synthesis.js');
const {presentation,currentStats,valid}=window.WeatherSynthesis;
const now=Date.now(),until=new Date(now+3600000).toISOString();
const d={schema_version:1,kind:'araquari_multisource_weather_not_institutional_level',location_id:'araquari',formal_level:null,station_registry:[],observations:[],signals:[],notices:[],statistics:{},selected_forecast:{sources_by_variable:{}}};
assert(valid(d));assert.equal(presentation(d,now).title,'Sem referências atuais suficientes');
const notice=source=>({source,valid_until:until,title:'Temporal',severity:'Perigo',start_at:new Date(now).toISOString(),end_at:until});
for(const source of ['INMET','Epagri/Ciram']){d.notices=[notice(source)];assert.equal(presentation(d,now).color,'amarelo');assert(presentation(d,now).reason.includes(source));}
d.notices=[];d.signals=[{band:1,nature:'observation',variable:'gust_kmh',valid_until:until,value:50,unit:'km/h',name:'IFC Araquari',end_at:until}];
assert.equal(presentation(d,now).title,'Atenção a vento');assert.equal(presentation(d,now+7200000).title,'Sem referências atuais suficientes');
d.statistics.rain_24h_mm={members:[0,0,0,80].map(value=>({value,unit:'mm',valid_until:until}))};
assert.equal(currentStats(d,'rain_24h_mm',now).mean,20);assert.equal(currentStats(d,'rain_24h_mm',now).median,0);assert.equal(currentStats(d,'rain_24h_mm',now).max,80);
d.normative_assessment={valid_until:until,suggested_level:'vermelho',title:'Alerta máximo',reason:'Correspondência explícita'};
assert.equal(presentation(d,now).color,'vermelho');assert.notEqual(presentation(d,now+7200000).color,'vermelho');
console.log('Multisource presentation: equal notices, individual expiry, preserved extremes and normative separation passed.');
