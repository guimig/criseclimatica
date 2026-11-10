'use strict';
const assert=require('node:assert/strict');
const {validComparison,current,validInmet}=require('../web/forecasts.js');
const stamp=new Date().toISOString(),end=new Date(Date.now()+3*3600000).toISOString();
const data={schema_version:1,kind:'araquari_comparable_forecasts_not_probability',location_id:'araquari',generated_at:stamp,valid_until:end,
 records:[{id:'best_match',hourly:[]}],cptec:{days:[]},limitations:[],windows:[24,72].map(hours=>({hours,start_at:stamp,end_at:end,
 metrics:['precipitation_mm','temperature_c','gust_kmh','wind_kmh'].map(variable=>({variable,members:[{id:'best_match',value:null}],highest_sources:[]}))}))};
assert.equal(validComparison(data),true);assert.equal(current(data),true);
for(const mutation of [{windows:{}},{records:[{hourly:[null]}]},{cptec:{days:[null]}},{fixture_mode:true},
 {windows:[...data.windows,data.windows[0]]},
 {windows:data.windows.map(w=>({...w,metrics:w.metrics.map(m=>({...m,members:[null]}))}))}]){
 assert.equal(validComparison({...data,...mutation}),false);
}
assert.equal(current({...data,generated_at:new Date(Date.now()-24*3600000).toISOString()}),false);
assert.equal(current({...data,generated_at:new Date(Date.now()+3600000).toISOString()}),false);
assert.equal(current(null),false);
console.log('Comparison contract passed: malformed structures fail closed without breaking page, fresh/future/expired/test publications remain distinct.');

const inmet={schema_version:1,kind:'inmet_araquari_municipal_forecast_not_observations_or_risk_criteria',location_id:'araquari',ibge_code:'4201307',issued_at:null,risk_criteria:false,numeric_rain_or_gust_inferred:false,status:'available',retrieved_at:stamp,valid_until:end,days:[],daily_comparison:[]};
assert.equal(validInmet(inmet),true);
for(const change of [{risk_criteria:true},{days:[null]},{valid_until:'invalid'},{issued_at:stamp},{daily_comparison:[null]}])assert.equal(validInmet({...inmet,...change}),false);
console.log('INMET contract passed: malformed periods, validity and risk isolation.');
