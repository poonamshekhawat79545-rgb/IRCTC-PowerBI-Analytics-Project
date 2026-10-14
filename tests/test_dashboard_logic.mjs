import fs from 'node:fs/promises';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// Execute the actual inline application script against a minimal in-memory DOM.
// No browser, network, operating-system UI, or blocked URL access is involved.
// This checks logic and generated markup, not browser layout or native events.
const html=await fs.readFile(path.join(root,'dashboard/IRCTC_Dashboard.html'),'utf8');
const payload=html.match(/<script id="analytics-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script=html.match(/<script>\s*([\s\S]*?)<\/script><\/body>/)[1];
const nodes=new Map();
function node(id='',dataset={}){return {id,dataset,value:'',textContent:'',innerHTML:'',hidden:false,listeners:{},title:'',classList:{toggle(){}},addEventListener(t,f){this.listeners[t]=f},focus(){document.activeElement=this},click(){this.onclick?.()}}}
for(const match of html.matchAll(/\bid="([^"]+)"/g)) nodes.set(match[1],node(match[1]));
nodes.get('analytics-data').textContent=payload;
const pageButtons=['overview','explorer','quality'].map(page=>node('',{page}));
const trendButtons=['bookings','value'].map(trend=>node('',{trend}));
let lastBlob=null,lastDownload=null;
const document={activeElement:null,getElementById:id=>nodes.get(id),querySelectorAll:sel=>({'[data-page]':pageButtons,'[data-trend]':trendButtons,'.page':['overview','explorer','quality'].map(id=>nodes.get(id))}[sel]||[]),addEventListener(){},createElement:()=>{const n=node();n.click=()=>{lastDownload=n.download};return n}};
const context=vm.createContext({document,window:{},console,Intl,Date,Map,Set,JSON,Number,String,Object,Array,Math,Blob,URL:{createObjectURL(b){lastBlob=b;return 'memory:blob'},revokeObjectURL(){}},setTimeout:f=>f()});
vm.runInContext(script,context,{timeout:10000});
const expected=JSON.parse(await fs.readFile(path.join(root,'tests/fixtures/dashboard_expected.json'),'utf8'));
const checks=[];
for(const scenario of expected){
  nodes.get('reset-btn').click();
  for(const [key,val]of Object.entries(scenario.filters)){const n=nodes.get(key+'-filter');n.value=val;n.listeners.change()}
  const got=context.window.IRCTCState;
  for(const key of ['count','value','users','trains','invalid','validLeadCount','passengers'])if(got[key]!==scenario.expected[key])throw new Error(scenario.name+' '+key+' '+got[key]+' != '+scenario.expected[key]);
  if(got.occupancy!==null&&Math.abs(got.occupancy-scenario.expected.occupancy)>1e-8)throw new Error('Occupancy mismatch');
  if(got.count===0&&!nodes.get('trend-chart').innerHTML.includes('No bookings match'))throw new Error('Empty state missing');
  if(scenario.name==='Small-value single booking'){
    trendButtons[1].click();
    if(nodes.get('trend-chart').innerHTML.includes('0L'))throw new Error('Small amounts mislabeled as zero lakh');
    trendButtons[0].click();
  }
  checks.push({test:scenario.name,status:'PASS',bookings:got.count});
}
nodes.get('reset-btn').click();
trendButtons[1].click();
if((nodes.get('trend-chart').innerHTML.match(/<circle /g)||[]).length!==12)throw new Error('Monthly point count');
trendButtons[0].click();
for(const button of pageButtons){button.click();if(nodes.get(button.dataset.page).hidden)throw new Error('Navigation failed')}
nodes.get('route-search').value='Delhi';nodes.get('route-search').listeners.input();
if((nodes.get('route-table').innerHTML.match(/<tr>/g)||[]).length!==3)throw new Error('Search failed');
nodes.get('reset-btn').click();
nodes.get('method-btn').click();if(nodes.get('method-modal').hidden)throw new Error('Modal open');
nodes.get('close-modal').click();if(!nodes.get('method-modal').hidden)throw new Error('Modal close');
nodes.get('month-filter').value='2025-01';nodes.get('month-filter').listeners.change();
nodes.get('export-btn').click();
const csv=await lastBlob.text();
if(csv.trim().split('\n').length-1!==context.window.IRCTCState.count)throw new Error('Export count');
if(lastDownload!=='irctc_selected_bookings.csv')throw new Error('Export filename');

checks.push({test:'Generated CSV matches selected row count and filename',status:'PASS'});
checks.push({test:'Trend metric, page state, route search, reset and modal state logic',status:'PASS'});
nodes.get('reset-btn').click();

const report={status:'PASS',method:'Actual inline application script executed in Node with a minimal in-memory DOM; '+expected.length+' cohorts independently calculated from CSV',checks,browser_visual_validation:'NOT PERFORMED: local HTML navigation blocked by browser security policy; this test does not establish layout, native browser events, mobile appearance or download UI behavior.'};
await fs.writeFile(path.join(root,'reports/dashboard_logic_validation.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({status:report.status,checks:checks.length,browser_visual_validation:report.browser_visual_validation}));
