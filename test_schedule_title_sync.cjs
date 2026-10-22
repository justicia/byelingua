const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const old='wiener_konzerthaus:fca41a07686f5f96449be2f4',kept='wiener_konzerthaus:pdf:53779919bb8487728696ebec';
const fresh={event_id:kept,title:'Symphonien Nr. 1, 2 & 3',date:'2027-06-02',start_time:'18:30:00',event_type:'concert',venue:'Wiener Konzerthaus',organization:'Wiener Konzerthaus',city:'Vienna'};
let release=null,pending=false,fail=false,activeRelations=[];const requests=[];
const server=http.createServer(async(req,res)=>{
 const name=new URL(req.url,'http://localhost').pathname.slice(1);
 if(name==='api'){
  let body='';for await(const chunk of req)body+=chunk;const q=JSON.parse(body||'{}');requests.push(q);let data={};
  if(q.action==='schedule_options')data={cities:['Vienna'],organizations:[],venues:[],event_types:['concert']};
  if(q.action==='combined_entity_events')data={events:[fresh]};
  if(q.action==='get_event_relations')data={relations:activeRelations};
  if(q.action==='resolve_event_keys'){
   pending=true;if(release!==null)await new Promise(r=>release=r);
   if(fail){res.writeHead(503,{'Content-Type':'application/json'});return res.end(JSON.stringify({error_code:'network_error'}));}
   data={resolutions:q.event_keys.filter(k=>[old,kept].includes(k)).map(k=>({requested_event_id:k,event:fresh}))};
  }
  res.writeHead(200,{'Content-Type':'application/json'});return res.end(JSON.stringify(data));
 }
 if(!/^[-\w]+\.(html|js|css)$/.test(name)||!fs.existsSync(path.join(__dirname,name))){res.writeHead(404);return res.end()}
 res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(__dirname,name)));
});
(async()=>{await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;try{
 browser=await chromium.launch({headless:true,executablePath:process.env.SCHEDULE_CHROME_PATH});const context=await browser.newContext({viewport:{width:1440,height:1100}});await context.route('https://**/*',r=>r.fulfill({contentType:'text/javascript',body:''}));
 const errors=[];context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));const base=`http://127.0.0.1:${server.address().port}/schedule.html`;
 async function pageWith(selected){activeRelations=selected.filter(row=>[old,kept].includes(row.event_id)).map(row=>({event_key:row.event_id,intent_status:row.planner_intent,is_planned:true}));const page=await context.newPage();await page.addInitScript(selected=>{if(!sessionStorage.getItem('seeded')){localStorage.setItem('byelinguaUiLanguage','en');localStorage.setItem('byelinguaPlannerDraft:v1',JSON.stringify({search:{fields:{locationSearch:'Vienna'},conditions:{},cities:[],organizations:[],venues:[]},selected}));sessionStorage.setItem('seeded','1')}},selected);await page.goto(base);return page;}
 const legacy={...fresh,event_id:old,title:'Beethovens',start_time:null,planner_intent:'must_go'},canonical={...fresh,title:'stale title',planner_intent:'optional'},unknown={event_id:'unknown:key',title:'unresolved selection',planner_intent:'optional'};
 const page=await pageWith([legacy,canonical,unknown]);await page.waitForFunction(()=>window.ByelinguaPlannerState.read().selected.length===2);
 let selected=await page.evaluate(()=>window.ByelinguaPlannerState.read().selected);assert.equal(selected[0].event_id,kept);assert.equal(selected[0].title,fresh.title);assert.equal(selected[0].start_time,'18:30:00');assert.equal(selected[0].planner_intent,'must_go');assert.equal(selected[1].event_id,'unknown:key');
 assert.equal(await page.locator('#liveSchedulePanel').getByText('Beethovens',{exact:true}).count(),0);assert.deepEqual(await page.evaluate(()=>[...selected_event_ids]),[kept,'unknown:key']);
 // Resolve a fresh pending lookup after the user removes the old selection and adds the kept one.
 pending=false;release=()=>{};await page.close();const racing=await pageWith([legacy]);await racing.waitForSelector('#liveSchedulePanel [data-live-remove]');assert.equal(pending,true);
 await racing.locator(`#liveSchedulePanel [data-live-remove="${old}"]`).click();await racing.locator(`#events [data-add="${kept}"]`).click();const before=await racing.evaluate(()=>window.ByelinguaPlannerState.read().selected);release();release=null;
 await racing.waitForFunction(()=>window.ByelinguaPlannerState.read().selected[0]?.title==='Symphonien Nr. 1, 2 & 3');selected=await racing.evaluate(()=>window.ByelinguaPlannerState.read().selected);assert.equal(selected.length,1);assert.equal(selected[0].event_id,kept);assert.equal(selected[0].planner_intent,before[0].planner_intent,'pending refresh preserves the new user choice');
 await racing.close();fail=true;const failed=await pageWith([legacy,unknown]);await failed.waitForSelector('#liveSchedulePanel [data-live-remove]');await failed.locator('#entitySearchButton').click();selected=await failed.evaluate(()=>window.ByelinguaPlannerState.read().selected);assert.deepEqual(selected.map(x=>x.event_id),[old,'unknown:key']);
 assert.deepEqual(errors,[]);assert.ok(requests.filter(q=>q.action==='resolve_event_keys').every(q=>q.event_keys.length<=200));console.log('PASS: saved titles/times refresh, reviewed duplicate IDs collapse with strongest intent, unresolved/offline selections survive, pending lookup does not restore removed selections.');
}finally{await browser?.close();await new Promise(r=>server.close(r))}})().catch(e=>{console.error(e);process.exitCode=1});
