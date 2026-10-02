// Full-page regression fixtures; no production API or saved data is accessed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');
const names = ['Auditorio Nacional de Música', 'Auditorio Nacional de Musica', ' AUDITORIO  NACIONAL DE MÚSICA '];
const venues = names.map((name, i) => ({id:`m${i}`,name,city:'Madrid',country_code:'es',organization:`Org ${i}`,organization_id:`o${i}`}));
venues.push({id:'b',name:'Berliner Philharmonie',city:'Berlin',country_code:'de',organization:'Berliner Philharmoniker'},
  {id:'u',name:'Munich Hall',city:'Munich',country_code:'de',organization:'Munich Orchestra'});
const requests = [];
const server = http.createServer(async (req, res) => {
  const filename = new URL(req.url,'http://localhost').pathname.slice(1);
  if(filename==='api') {
    let body='';for await(const chunk of req)body+=chunk;
    const query=JSON.parse(body||'{}');requests.push(query);
    let result={};
    if(query.action==='schedule_options')result={cities:['Berlin','Madrid','Munich'],venues,organizations:[],event_types:[],country_names:{de:['Germany','Deutschland','德国'],es:['Spain','España','西班牙']}};
    if(query.action==='combined_entity_events')result={events:[{event_id:'saved',title:'Saved concert',date:'2026-10-01',venue:'Madrid Hall',organization:'Saved orchestra'}]};
    res.writeHead(200,{'Content-Type':'application/json'});return res.end(JSON.stringify(result));
  }
  if(!['schedule.html','shared-header.js','shared-i18n.js'].includes(filename)){res.writeHead(404);return res.end()}
  res.writeHead(200,{'Content-Type':filename.endsWith('.js')?'text/javascript':'text/html; charset=utf-8'});
  res.end(fs.readFileSync(path.join(__dirname,filename)));
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));let browser;
  try{
    browser=await chromium.launch({headless:true,...(process.env.SCHEDULE_CHROME_PATH?{executablePath:process.env.SCHEDULE_CHROME_PATH}:{})});
    const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('https://**/*',route=>route.fulfill({contentType:'text/javascript',body:''}));
    await page.goto(`http://127.0.0.1:${server.address().port}/schedule.html`);
    await page.waitForFunction(()=>events.length===1);
    await page.evaluate(()=>{selected_event_ids.add('saved');renderLiveSchedule()});
    const saved=await page.evaluate(()=>document.querySelector('.my-schedule-list').textContent);
    await page.locator('#locationSearch').fill('Madrid');
    assert.deepEqual(await page.locator('[data-progress-city]').evaluateAll(nodes=>nodes.map(n=>n.dataset.progressCity)),['Madrid']);
    assert.equal(await page.locator('[data-progress-venue]').count(),1);
    await page.locator('[data-progress-venue]').check();
    await page.locator('#entitySearchButton').click();
    await page.waitForFunction(()=>events.length===1);
    const payload=requests.filter(q=>q.action==='combined_entity_events').at(-1);
    assert.deepEqual(payload.venues,names);assert.deepEqual(payload.venue_keys,['auditorio nacional de musica|madrid']);
    assert.deepEqual(await page.evaluate(()=>dedupeVenues(options.venues)[0].ids),['m0','m1','m2']);
    await page.locator('[data-progress-organization]').first().check();
    assert.equal(await page.locator('[data-progress-venue]:checked').count(),1);
    await page.locator('#venueSearch').fill('old Madrid filter');
    let releaseOldSearch;
    const oldSearchStarted=new Promise(resolve=>{
      page.route('**/api',async route=>{
        const query=route.request().postDataJSON();
        if(query.action!=='combined_entity_events'||query.location_query!=='Madrid')return route.continue();
        await new Promise(release=>{releaseOldSearch=release;resolve()});
        await route.fulfill({contentType:'application/json',body:JSON.stringify({events:[{event_id:'stale',title:'Stale Madrid result'}]})});
      });
    });
    await page.evaluate(()=>{void runEntitySearch()});await oldSearchStarted;
    await page.locator('#locationSearch').fill('Berlin');
    const oldResponse=page.waitForResponse(response=>response.request().postDataJSON()?.location_query==='Madrid');
    releaseOldSearch();await oldResponse;await page.waitForLoadState('networkidle');
    assert.deepEqual(await page.evaluate(()=>({cities:[...selectedCities],orgs:[...selectedOrganizations],venues:[...selectedVenues],events:events.length})),{cities:['Berlin'],orgs:[],venues:[],events:0});
    assert.equal(await page.locator('#venueSearch').inputValue(),'');
    assert.deepEqual(await page.locator('[data-progress-city]').evaluateAll(nodes=>nodes.map(n=>n.dataset.progressCity)),['Berlin']);
    assert.equal(await page.evaluate(()=>document.querySelector('.my-schedule-list').textContent),saved);
    assert.deepEqual(await page.evaluate(()=>[...selected_event_ids]),['saved']);
    await page.locator('#entitySearchButton').click();await page.waitForFunction(()=>events.length===1);
    assert.deepEqual(requests.filter(q=>q.action==='combined_entity_events').at(-1).cities,['Berlin']);
    await page.locator('#locationSearch').fill('Deutschland');
    assert.deepEqual(await page.locator('[data-progress-city]').evaluateAll(nodes=>nodes.map(n=>n.dataset.progressCity)),['Berlin','Munich']);
    await page.locator('[data-progress-city="Berlin"]').check();
    await page.locator('[data-progress-organization]').check();
    await page.locator('[data-progress-venue]').check();
    await page.locator('[data-progress-organization]').uncheck();
    assert.deepEqual(await page.evaluate(()=>[...selectedCities]),['Berlin']);
    assert.equal(await page.locator('[data-progress-venue]:checked').count(),1);
    await page.locator('#locationSearch').fill('Berlin');
    await page.locator('[data-progress-organization]').check();
    await page.locator('[data-progress-venue]').check();
    await page.locator('#locationSearch').fill(' BERLIN ');
    assert.deepEqual(await page.evaluate(()=>[...selectedOrganizations]),['Berliner Philharmoniker']);
    assert.equal(await page.locator('[data-progress-venue]:checked').count(),1);
    assert.equal(await page.evaluate(()=>normalizeVenueKey({name:'Háll— A.',city:'Madrid'})===normalizeVenueKey({name:'HALL A',city:'MADRID'})),true);
    assert.deepEqual(errors,[]);
    console.log('Schedule location regressions passed (reset, city/country scope, venue aliases, saved schedule, checkbox filters).');
  }finally{await browser?.close();await new Promise(resolve=>server.close(resolve))}
})().catch(error=>{console.error(error);process.exitCode=1});
