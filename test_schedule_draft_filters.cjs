// Full-page regression: restored entity IDs must have visible selections and clear with the fields.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const ids={composer:'61f9bd52-8cc4-4752-bfbd-76c7a8d55f85',work:'c7b6cef4-fe70-48a8-a7a2-710058c2861f',character:'33333333-3333-4333-8333-333333333333',artist:'44444444-4444-4444-8444-444444444444'};
const labels={composer:'Richard Wagner',work:'Siegfried',character:'Wotan',artist:'Fixture Artist'};
const rows=Array.from({length:31},(_,i)=>({event_id:`event-${i+1}`,title:i?'Fixture performance':'Richard Wagner: Siegfried',date:'2027-05-06',start_time:'16:00',organization:'Wiener Konzerthaus',venue:'Wiener Konzerthaus',city:'Vienna',event_type:'opera'}));
const requests=[];
const server=http.createServer(async(req,res)=>{
 const name=new URL(req.url,'http://localhost').pathname.slice(1);
 if(name==='api'){
  let body='';for await(const chunk of req)body+=chunk;const q=JSON.parse(body||'{}');requests.push(q);let result={};
  if(q.action==='schedule_options')result={cities:['Vienna'],organizations:['Wiener Konzerthaus'],venues:[{name:'Wiener Konzerthaus',city:'Vienna',country_code:'AT',organization:'Wiener Konzerthaus'}],event_types:['opera']};
  if(q.action==='combined_entity_events')result={events:Object.keys(ids).some(type=>q[`${type}_id`])?rows.slice(0,1):rows};
  if(q.action==='entity_options')result={composers:[],works:[],characters:[],artists:[]};
  res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(result));
 }
 if(!/^[-\w]+\.(html|js|css)$/.test(name)||!fs.existsSync(path.join(__dirname,name))){res.writeHead(404);return res.end()}
 res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(path.join(__dirname,name)));
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.SCHEDULE_CHROME_PATH?{executablePath:process.env.SCHEDULE_CHROME_PATH}:{})});
  const context=await browser.newContext(),errors=[];await context.route('https://**/*',r=>r.fulfill({contentType:'text/javascript',body:''}));
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  const base=`http://127.0.0.1:${server.address().port}/schedule.html`;
  const conditions=Object.fromEntries(Object.keys(ids).map(type=>[type,{type,id:ids[type],label:labels[type]}]));
  const fields={locationSearch:'Vienna',venueSearch:'',dateFrom:'',dateTo:'',eventType:'',composerCondition:'',workCondition:'',characterCondition:'',artistCondition:''};
  async function seed(search){await page.addInitScript(search=>{if(!sessionStorage.getItem('seeded')){localStorage.setItem('byelinguaUiLanguage','en');localStorage.setItem('byelinguaPlannerDraft:v1',JSON.stringify({search,selected:[]}));sessionStorage.setItem('seeded','1')}},search);}
  await seed({fields,conditions,cities:[],organizations:[],venues:[]});await page.goto(base);
  await page.waitForFunction(()=>document.querySelector('#filterStatus').textContent==='');await page.locator('#entitySearchButton').click();
  await page.waitForFunction(()=>document.querySelector('#resultHint').textContent.includes('31'));
  let q=requests.filter(q=>q.action==='combined_entity_events').at(-1);
  for(const type of Object.keys(ids))assert.equal(q[`${type}_id`],undefined,`empty restored ${type} must not send a hidden ID`);
  assert.equal(await page.locator('#events [data-event]').count(),15,'normal15-card page retained');assert.equal(await page.locator('#eventPagination [data-page-last]').count(),1);
  // Old drafts never saved composerCondition: recover that valid selection as a visible chip, not a hidden ID.
  await page.evaluate(({fields,conditions})=>{const legacy={...fields};delete legacy.composerCondition;window.ByelinguaPlannerState.write({search:{fields:legacy,conditions:{composer:conditions.composer,work:conditions.work},cities:[],organizations:[],venues:[]}})}, {fields,conditions});
  await page.reload();await page.locator('#composerCondition').locator('..').locator('.selected-chip button').waitFor();
  assert.equal(await page.locator('#workCondition').isVisible(),true,'cleared legacy work stays clear');
  assert.equal(await page.evaluate(()=>conditionState.work),null);
  await page.locator('#composerCondition').locator('..').locator('.selected-chip button').click();
  await page.waitForFunction(()=>window.ByelinguaPlannerState.read().search.conditions.composer===null);
  await page.reload();await page.waitForFunction(()=>document.querySelector('#resultHint').textContent.includes('31'));
  // Valid selections survive a reload as existing removable chips, including the previously omitted composer field.
  await page.evaluate(({fields,conditions})=>{const saved={...fields};for(const type of Object.keys(conditions))saved[`${type}Condition`]=conditions[type].label;window.ByelinguaPlannerState.write({search:{fields:saved,conditions,cities:[],organizations:[],venues:[]}})}, {fields,conditions});
  await page.reload();await page.locator('#composerCondition').locator('..').locator('.selected-chip button').waitFor();
  for(const type of Object.keys(ids)){assert.equal(await page.locator(`#${type}Condition`).isHidden(),true);assert.match(await page.locator(`#${type}Condition`).locator('..').textContent(),new RegExp(labels[type]));}
  for(const type of Object.keys(ids))await page.locator(`#${type}Condition`).locator('..').locator('.selected-chip button').click();
  await page.locator('#composerCondition').fill('Mozart');await page.locator('#entitySearchButton').click();
  q=requests.filter(q=>q.action==='combined_entity_events').at(-1);assert.equal(q.composer_query,'Mozart');for(const type of Object.keys(ids))assert.equal(q[`${type}_id`],undefined);
  await page.reload();assert.equal(await page.locator('#composerCondition').inputValue(),'Mozart','typed composer text restored');await page.locator('#composerCondition').fill('');await page.locator('#entitySearchButton').click();
  await page.waitForFunction(()=>document.querySelector('#resultHint').textContent.includes('31'));q=requests.filter(q=>q.action==='combined_entity_events').at(-1);assert.equal(q.composer_id,undefined);assert.equal(q.composer_query,undefined);
  await page.reload();await page.waitForFunction(()=>document.querySelector('#resultHint').textContent.includes('31'));
  assert.deepEqual(errors,[]);console.log('PASS: legacy empty fields drop stale IDs; valid draft selections render removable chips; clearing stays cleared across reload; typed composer persists;15-card pagination preserved.');
 }finally{await browser?.close();await new Promise(resolve=>server.close(resolve))}
})().catch(error=>{console.error(error);process.exitCode=1});
