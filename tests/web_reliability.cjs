// Run browser behavior with a small DOM harness; no network or third-party packages.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.textContent = ''; this.className = ''; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; this.textContent = ''; }
  setAttribute() {}
  addEventListener() {}
  get childElementCount() { return this.children.length; }
  get text() { return this.textContent + this.children.map(n => n.text ?? n.textContent ?? String(n)).join(' '); }
}
const elements = new Map();
const document = {
  getElementById(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); },
  createElement(tag) { return new Element(tag); }, createElementNS(ns, tag) { return new Element(tag); },
  querySelectorAll() { return []; }, addEventListener() {}, hidden: false,
};
let clock = Date.parse('2026-11-06T12:30:00Z');
class Clock extends Date { static now() { return clock; } }
const context = vm.createContext({ document, Date: Clock, Intl, console, AbortController,
  setTimeout() { return 1; }, clearTimeout() {}, setInterval() {},
  fetch() { return new Promise(() => {}); } });
vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8'), context);
const run = code => vm.runInContext(code, context);
const text = id => document.getElementById(id).text;

assert.equal(run("freshAt('2026-11-06T12:00:00Z')"), true);
assert.equal(run("freshAt('2026-11-05T12:00:00Z')"), false);
assert.equal(run("freshAt('2026-11-07T12:00:00Z')"), false);
assert.equal(run("freshAt('invalid')"), false);
assert.equal(run("effectiveStatus('available', '2026-11-05T12:00:00Z')"), 'stale');
assert.equal(run("effectiveStatus('not_configured', null)"), 'not_configured');

run(`state.slug = 'araquari'; state.cemaden = {status:'available',checked_at:'2026-11-06T12:00:00Z',
locations:[{location_id:'araquari',status:'unavailable',diagnostic:'unavailable',stations:[]}]}; renderCemaden();`);
assert.match(text('cemaden-data'), /não respondeu/);
assert.doesNotMatch(text('cemaden-data'), /Nenhum pluviômetro/);

run(`state.cemaden.locations[0] = {location_id:'araquari',status:'available',stations:[
{code:'12345',observed_at:'2026-11-06T12:00:00Z',rain_24h_mm:17}]}; renderCemaden();`);
assert.match(text('cemaden-data'), /17,0 mm/);
clock = Date.parse('2026-11-06T20:00:00Z');
run('renderCemaden();');
assert.match(text('cemaden-data'), /desatualizadas/);
assert.doesNotMatch(text('cemaden-data'), /17,0 mm/);

clock = Date.parse('2026-11-06T12:30:00Z');
run(`state.cemadenSensors = {status:'available',checked_at:'2026-11-06T12:00:00Z',
locations:[{location_id:'araquari',stations:[{code:'12345',distance_km:2}]}],
stations:[{code:'12345',name:'Estação',municipality:'Araquari',readings:[
{sensor_id:60,sensor_name:'Temperatura',unit:'°C',value:25,observed_at:'2026-11-06T08:00:00Z'}]}]};
renderCemadenSensors();`);
assert.match(text('cemaden-sensors-data'), /vencidas/);
assert.doesNotMatch(text('cemaden-sensors-data'), /25,00/);

run(`state.overview = {generated_at:'2026-11-06T12:00:00Z',available_locations:0,total_locations:10,locations:[]};
refreshPublicationStatus();`);
assert.match(text('system-status'), /Open-Meteo indisponível/);
clock = Date.parse('2026-11-07T12:30:00Z');
run('refreshPublicationStatus();');
assert.match(text('system-status'), /desatualizada/);
console.log('Browser reliability scenarios passed: freshness, municipal failure, expired readings, partial publication.');
