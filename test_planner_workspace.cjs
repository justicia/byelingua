// Browser integration: one controller and draft across News, embedded and full Planner.
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {chromium}=require('playwright');
const screenshotDir=path.join(require('node:os').tmpdir(),'byelingua-ui-checks');fs.mkdirSync(screenshotDir,{recursive:true});
const requests=[];
const rows=Array.from({length:31},(_,i)=>({event_id:`event-${i+1}`,title:`A very long performance title · 演出名称 ${i+1} — Mozart and friends`,date:'2026-10-18',start_time:'19:30',event_type:'opera',venue:'Madrid Hall',organization:'Fixture orchestra',city:'Madrid'}));
const articles=Array.from({length:12},(_,i)=>({id:`article-${i}`,title:`News headline ${i} 新闻标题`,titles:{en:`News headline ${i}`,zh:`新闻标题 ${i}`},excerpts:{en:'A real-data rendering fixture for the newspaper columns.',zh:'用于验证真实数据渲染路径的新闻摘要。'},country:'fr',source:'Fixture newspaper',url:`https://example.test/news/${i}`,published:`2026-10-${String(20-i).padStart(2,'0')}T10:00:00Z`}));
const server=http.createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');
 if(url.pathname==='/api'){
  let body='';for await(const chunk of req)body+=chunk;const q=JSON.parse(body||'{}');requests.push(q);let data={};
  if(req.method==='GET'||q.action==='get_public')data={articles,subscriptions:[],countries:{fr:'法国'}};
  if(q.action==='schedule_options')data={cities:['Madrid'],organizations:['Fixture orchestra'],venues:[{name:'Madrid Hall',city:'Madrid',country:'Spain',country_code:'ES',organization:'Fixture orchestra'}],event_types:['opera']};
  if(q.action==='combined_entity_events'){const start=((q.page||1)-1)*(q.page_size||15);data=q.page?{events:rows.slice(start,start+15),total:rows.length,page:q.page,page_size:15}:{events:rows};}
  if(q.action==='schedule_event_detail')data={event:{...rows.find(row=>row.event_id===q.event_id),source_url:'https://example.test/event',programme:[{title:'Don Giovanni',composer:'Mozart',order:1}],credits:[]}};
  if(q.action==='create_schedule')data={schedule:{id:'fixture-schedule'}};
  res.writeHead(200,{'Content-Type':'application/json'});return res.end(JSON.stringify(data));
 }
 const name=url.pathname==='/'?'index.html':url.pathname.slice(1);
 if(name.includes('..')||!/^[-\w]+\.(html|css|js)$/.test(name)||!fs.existsSync(path.join(__dirname,name))){res.writeHead(404);return res.end()}
 res.writeHead(200,{'Content-Type':name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html; charset=utf-8'});res.end(fs.readFileSync(path.join(__dirname,name)));
});
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
 try{
  browser=await chromium.launch({headless:true,...(process.env.SCHEDULE_CHROME_PATH?{executablePath:process.env.SCHEDULE_CHROME_PATH}:{})});
  const context=await browser.newContext({viewport:{width:1440,height:1100}}),errors=[];
  await context.route('https://**/*',route=>route.fulfill({contentType:'text/javascript',body:''}));
  context.on('page',page=>page.on('pageerror',error=>{errors.push(error.message);console.error('Browser error:',error.stack)}));
  const base=`http://127.0.0.1:${server.address().port}`,news=await context.newPage();
  await news.goto(base);await news.waitForSelector('.news-column');assert.equal(await news.locator('.news-column').count(),3);assert.equal(await news.locator('.article').count(),10);
  assert.match(await news.locator('.news-column').first().textContent(),/新闻标题 0/);assert.match(await news.locator('.news-column.featured').textContent(),/新闻标题 3/);
  await news.locator('.planner-launcher').click();const frame=news.frameLocator('#floatingPlanner iframe');await frame.locator('#events [data-add]').first().waitFor();await news.screenshot({path:path.join(screenshotDir,'byelingua-embedded-debug.png'),fullPage:true});
  assert.equal(await frame.locator('.planner-more').getAttribute('open'),null);
  await frame.locator('#events [data-add]').first().click();await news.waitForFunction(()=>document.querySelector('.planner-launcher').textContent.endsWith('1'));await frame.locator('#events [data-add]').first().click();await news.waitForFunction(()=>document.querySelector('.planner-launcher').textContent.endsWith('0'));await frame.locator('#events [data-add]').first().click();await news.waitForFunction(()=>document.querySelector('.planner-launcher').textContent.endsWith('1'));
  await news.locator('[data-floating-close]').click();await news.locator('.planner-launcher').click();assert.match(await frame.locator('.my-schedule-list').textContent(),/performance title/);
  const full=await context.newPage();await full.goto(base+'/schedule.html');await full.waitForSelector('#events [data-add]');assert.deepEqual(await full.evaluate(()=>[...selected_event_ids]),['event-1']);
  await full.screenshot({path:path.join(screenshotDir,'byelingua-planner-desktop.png'),fullPage:true});const columns=await full.locator('.schedule-builder-layout').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length);assert.equal(columns,3);assert.match(await full.locator('.planner-entity-panel h2').evaluate(el=>getComputedStyle(el).fontFamily),/system-ui/);assert.match(await full.locator('.byelingua-compact-brand').evaluate(el=>getComputedStyle(el).fontFamily),/Georgia/);
  await full.locator('#locationSearch').fill('Madrid');await full.locator('#entitySearchButton').click();await full.waitForFunction(()=>events.length===31);assert.deepEqual(await full.evaluate(()=>[...selected_event_ids]),['event-1']);
  await full.locator('[data-calendar-date]').first().click();await full.locator('[data-calendar-date]').nth(2).click();assert.ok(await full.locator('#dateFrom').inputValue());assert.ok(await full.locator('#dateTo').inputValue());
  await full.locator('#entitySearchButton').click();await full.waitForFunction(()=>document.querySelector('#filterStatus').textContent==='');assert.ok(requests.filter(q=>q.action==='combined_entity_events').at(-1).date_to);
  await full.locator('#events [data-detail]').first().click();await full.waitForSelector('#persistentEventDetail .details');assert.match(await full.locator('#persistentEventDetail').textContent(),/Don Giovanni/);
  await full.locator('[data-close-persistent]').click();await full.locator('#liveSchedulePanel [data-live-remove]').first().click();await news.waitForFunction(()=>document.querySelector('.planner-launcher').textContent.endsWith('0'));
  assert.deepEqual(await frame.locator('body').evaluate(()=>[...selected_event_ids]),[]);
  await frame.locator('#events [data-add]').nth(1).click();await full.waitForFunction(()=>selected_event_ids.has('event-2'));
  // Actual selection, detail, calendar and draft synchronization on narrow screens.
  for(const language of ['zh','en']){
   await full.evaluate(lang=>localStorage.setItem('byelinguaUiLanguage',lang),language);await full.reload();await full.waitForSelector('#events [data-add]');
   await full.setViewportSize({width:375,height:812});await full.evaluate(()=>{document.querySelector('.planner-filters').open=false});
   assert.equal(await full.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await full.locator('.mobile-schedule-trigger').click();await full.locator('#liveSchedulePanel').waitFor({state:'visible'});
   assert.equal(await full.locator('[data-generate-live]').isEnabled(),true);await full.screenshot({path:path.join(screenshotDir,`byelingua-planner-mobile-${language}.png`),fullPage:true});await full.locator('[data-close-schedule]').click();await full.locator('#events [data-detail]').first().click();await full.waitForSelector('#persistentEventDetail .details');assert.equal(await full.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await full.locator('[data-close-persistent]').click();
   await news.setViewportSize({width:375,height:812});assert.equal(await news.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   assert.equal(await news.locator('#floatingPlanner').evaluate(el=>Math.round(el.getBoundingClientRect().width)),375);await frame.locator('.planner-more>summary').click();assert.equal(await frame.locator('html').evaluate(el=>el.scrollWidth<=innerWidth),true);await frame.locator('.planner-more>summary').click();
  }
  await full.setViewportSize({width:1440,height:1100});await full.locator('[data-generate-live]').click();await full.waitForURL('**/schedule-editor.html?schedule_id=fixture-schedule');
  assert.deepEqual(requests.filter(q=>q.action==='add_event_to_schedule').map(q=>q.event_key),['event-2']);
  assert.deepEqual(errors,[]);
  await news.locator('[data-floating-close]').click();await news.screenshot({path:path.join(screenshotDir,'byelingua-news-mobile.png'),fullPage:true});
  await context.close();console.log('PASS: newspaper columns, full/embedded selection sync, retained filters, calendar, details, generation, desktop/mobile layouts and both languages.');
 }finally{await browser?.close();await new Promise(resolve=>server.close(resolve))}
})().catch(error=>{console.error(error);process.exitCode=1});
