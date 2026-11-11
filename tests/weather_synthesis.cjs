const assert=require('node:assert/strict');
global.window={};global.document={getElementById:()=>null};require('../web/weather-synthesis.js');
const {riskLevel,currentStats,presentation}=window.WeatherSynthesis;
const now=Date.now(),stamp=new Date(now).toISOString(),until=new Date(now+3600000).toISOString();
const product={schema_version:1,method_version:'araquari-risk-v2',kind:'consultative_risk_level_not_official_decision',official_level:null,generated_at:stamp,candidates:[]};
assert.equal(riskLevel(product,now).active,null);
for(const [level,name] of Object.entries({verde:'Normalidade',azul:'Preparação',amarelo:'Atenção',laranja:'Alerta',vermelho:'Alerta máximo'})){
 const p={...product,candidates:[{level,reason:'Evidência identificada.',valid_until:until,evidence:[{source:'Fonte'}]}]};
 assert.equal(riskLevel(p,now).title,name);assert.equal(riskLevel(p,now).active,level);assert.equal(riskLevel(p,now+7200000).active,null);
}
const yellow={level:'amarelo',reason:'Rajada elevada.',valid_until:until,evidence:[{}]};
assert.equal(riskLevel({...product,candidates:[{...yellow,level:'verde'},yellow]},now).active,'amarelo');
assert.equal(riskLevel({...product,candidates:[{...yellow,level:'roxo'}]},now).active,null);
assert.equal(riskLevel({...product,official_level:'verde',candidates:[yellow]},now).active,null);
assert.equal(riskLevel({...product,candidates:[{...yellow,evidence:[]}]},now).active,null);
assert.equal(riskLevel({...product,generated_at:new Date(now+7200000).toISOString(),candidates:[yellow]},now).active,null);
assert.equal(presentation({},now),null);assert.equal(presentation({risk_classification:{...product,candidates:[yellow]}},now).title,'Atenção');
const data={statistics:{rain_24h_mm:{members:[0,0,0,80].map(value=>({value,unit:'mm',valid_until:until}))}}};
assert.equal(currentStats(data,'rain_24h_mm',now).mean,20);assert.equal(currentStats(data,'rain_24h_mm',now).max,80);
console.log('Six-level classification: real categories, expiry, no false normality, official separation and preserved station extremes passed.');
