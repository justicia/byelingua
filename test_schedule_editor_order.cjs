const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const event=(key,date,time,city='Vienna')=>({event_key:key,event:{event_id:key,title:key,date,start_time:time,city,venue:'Wiener Konzerthaus'}});
let members=[event('late','2027-06-03','19:30'),event('unknown-time','2027-06-02',null),event('early','2027-06-02','18:30'),event('other-city','2027-05-31','20:00','Paris'),event('same-time','2027-06-03','19:30'),event('unknown-date',null,null)];
const requests=[],schedule={id:'fixture',title:'Chronological fixture',status:'draft'};
const server=http.createServer(async(req,res)=>{
 const name=new URL(req.url,'http://localhost').pathname.slice(1);
 if(name==='api'){
  let body='';for await(const chunk of req)body+=chunk;const q=JSON.parse(body||'{}');requests.push(q);let data={};
  if(q.action==='get_schedule')data={schedule,events:members};
  if(q.action==='schedule_options')data={cities:['Vienna','Paris'],venues:[]};
  if(q.action==='get_event_relations')data={relations:[]};
  if(q.action==='schedule_events')data={events:[{event_id:'new-earliest',title:'new-earliest',date:'2027-05-31',start_time:'19:00',city:'Vienna',venue:'Wiener Konzerthaus'}]};
  if(q.action==='add_event_to_schedule'){members.push(event('new-earliest','2027-05-31','19:00'));data={schedule,events:members};}
  if(q.action==='reorder_schedule_events'){members=q.ordered_event_keys.map(k=>members.find(r=>r.event_key===k));data={schedule,events:members};}
  if(q.action==='remove_event_from_schedule'){members=members.filter(r=>r.event_key!==q.event_key);data={schedule,events:members};}
  res.writeHead(200,{'Content-Type':'application/json'});return res.end(JSON.stringify(data));
 }
 if(!/^[-\w]+\.(html|js|css)$/.test(name)||!fs.existsSync(path.join(__dirname,name))){res.writeHead(404);return res.end()}
 res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(__dirname,name)));
});
(async()=>{await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;try{
 browser=await chromium.launch({headless:true,executablePath:process.env.SCHEDULE_CHROME_PATH});const context=await browser.newContext({viewport:{width:1440,height:1100}});
 await context.route('https://**/*',r=>r.fulfill({contentType:'text/javascript',body:''}));const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>localStorage.setItem('byelinguaUiLanguage','en'));
 await page.goto(`http://127.0.0.1:${server.address().port}/schedule-editor.html?schedule_id=fixture`);
 const keys=()=>page.locator('#scheduleList [data-row]').evaluateAll(els=>els.map(e=>e.dataset.row));
 await page.waitForSelector('#scheduleList [data-row]');assert.deepEqual(await keys(),['other-city','early','unknown-time','late','same-time','unknown-date']);
 assert.equal(requests.some(q=>q.action==='reorder_schedule_events'),false,'viewing must not mutate saved order');
 await page.locator('#cityFilter').selectOption('Vienna');assert.deepEqual(await keys(),['early','unknown-time','late','same-time','unknown-date']);
 await page.locator('#clearFilters').click();assert.equal((await keys())[0],'other-city');
 // A manual drop cannot pull a later day ahead of an earlier day; tied performances remain draggable.
 await page.locator('[data-row="same-time"]').dragTo(page.locator('[data-row="late"]'));
 await page.waitForFunction(()=>document.querySelector('#status').textContent==='Saved');
 assert.deepEqual(await keys(),['other-city','early','unknown-time','same-time','late','unknown-date']);
 assert.deepEqual(requests.filter(q=>q.action==='reorder_schedule_events').at(-1).ordered_event_keys,await keys());
 await page.locator('[data-row="late"]').dragTo(page.locator('[data-row="other-city"]'));
 await page.waitForFunction(()=>document.querySelector('#status').textContent==='Saved');assert.deepEqual((await keys()).slice(0,3),['other-city','early','unknown-time']);
 await page.locator('[data-select="other-city"]').click();await page.locator('[data-add="new-earliest"]').click();await page.waitForSelector('[data-row="new-earliest"]');assert.equal((await keys())[0],'new-earliest');
 await page.reload();await page.waitForSelector('[data-row="new-earliest"]');assert.equal((await keys())[0],'new-earliest');
 await page.locator('[data-remove="new-earliest"]').click();await page.waitForSelector('[data-row="new-earliest"]',{state:'detached'});assert.equal((await keys())[0],'other-city');
 const dir=path.join(require('node:os').tmpdir(),'byelingua-ui-checks');fs.mkdirSync(dir,{recursive:true});await page.screenshot({path:path.join(dir,'schedule-editor-date-order.png'),fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS: editor sorts dates/times, puts unknown values last, preserves tied-event drag order, filters/add/remove/reload and does not write on load.');
}finally{await browser?.close();await new Promise(r=>server.close(r))}})().catch(e=>{console.error(e);process.exitCode=1});
