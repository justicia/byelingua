const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const { chromium } = require('playwright');
const ids = ['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222','33333333-3333-4333-8333-333333333333'];
const server = http.createServer(async (req,res) => {
  const name = new URL(req.url,'http://localhost').pathname.slice(1);
  if(name==='api') {
    let body=''; for await(const chunk of req) body+=chunk;
    const q=JSON.parse(body||'{}');
    const result=q.action==='entity_options'?{
      composers:[{type:'composer',id:ids[0],label:'Richard Wagner',composer:'Richard Wagner'}],
      works:[{type:'work',id:ids[1],label:'Die Walküre',composer:'Richard Wagner'}],
      characters:[{type:'character',id:ids[2],label:'Wotan',work_title:'Die Walküre'},
        {type:'character',id:'44444444-4444-4444-8444-444444444444',label:'Wotan',work_title:'Das Rheingold'}]
    }:{events:[],cities:[],organizations:[],venues:[]};
    res.setHeader('Content-Type','application/json');res.end(JSON.stringify(result));return;
  }
  if(!/^[\w.-]+$/.test(name)||!fs.existsSync(name)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':'text/html');
  res.end(fs.readFileSync(name));
});
(async()=>{
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  let browser;
  try {
    browser=await chromium.launch({headless:true,...(process.env.SCHEDULE_CHROME_PATH?{executablePath:process.env.SCHEDULE_CHROME_PATH}:{})});
    const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>localStorage.setItem('byelinguaUiLanguage','en'));
    await page.route('https://**/*',r=>r.fulfill({contentType:'text/javascript',body:''}));
    await page.goto(`http://127.0.0.1:${server.address().port}/schedule.html`);
    await page.locator('#composerCondition').fill('wagner');
    await page.locator('#composerConditionChoices button').waitFor();
    assert.equal(await page.locator('#composerConditionChoices').textContent(),'Richard Wagner');
    await page.locator('#composerConditionChoices button').click();
    await page.locator('#workCondition').fill('walkure');
    await page.locator('#workConditionChoices button').waitFor();
    await page.locator('#workConditionChoices button').click();
    await page.locator('#characterCondition').fill('wotan');
    await page.locator('#characterConditionChoices button').first().waitFor();
    assert.match(await page.locator('#characterConditionChoices').textContent(),/Wotan · Die Walküre/);
    assert.match(await page.locator('#characterConditionChoices').textContent(),/Wotan · Das Rheingold/);
    await page.locator('#characterConditionChoices button').first().click();
    assert.match(await page.locator('#characterCondition').locator('..').textContent(),/Wotan · Die Walküre/);
    const pending=page.waitForRequest(r=>r.url().endsWith('/api')&&r.postDataJSON()?.action==='combined_entity_events');
    await page.locator('#entitySearchButton').click();
    const payload=(await pending).postDataJSON();
    assert.equal(payload.composer_id,ids[0]);assert.equal(payload.work_id,ids[1]);assert.equal(payload.character_id,ids[2]);
    assert.deepEqual(errors,[]);
    console.log('PASS: separate composer/work searches, character work labels, selected chips and combined request.');
  } finally {await browser?.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1;});
