'use strict';
const assert=require('node:assert/strict');
const {validComparison,current}=require('../web/forecasts.js');
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
