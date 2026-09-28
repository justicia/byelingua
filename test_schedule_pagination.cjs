// Run with Node and Playwright available on NODE_PATH.
// Load the complete page, including shared-header.js and its window.load hooks.
// The API fixture keeps this regression check independent of production data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require('playwright');

const files = new Set(['schedule.html', 'shared-header.js', 'shared-i18n.js']);
const rows = Array.from({ length: 1000 }, (_, i) => ({
  event_id: `pagination-${i + 1}`, title: `Pagination fixture ${i + 1}`,
  date: '2026-10-01', start_time: '19:00', event_type: 'opera',
  organization: 'Fixture orchestra', venue: 'Fixture hall', city: 'Paris'
}));
const server = http.createServer(async (req, res) => {
  const filename = new URL(req.url, 'http://localhost').pathname.slice(1);
  if (filename === 'api') {
    let body = ''; for await (const chunk of req) body += chunk;
    const query = JSON.parse(body || '{}');
    let result = {};
    if (query.action === 'schedule_options') result = { cities: [], organizations: [], venues: [], event_types: [] };
    if (query.action === 'combined_entity_events') {
      const counts = { empty: 0, single: 15, two: 16, seven: 105, eight: 106 };
      result = { events: rows.slice(0, counts[query.work_query] ?? 1000) };
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(result));
  }
  if (!files.has(filename)) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': filename.endsWith('.js') ? 'text/javascript' : 'text/html; charset=utf-8' });
  res.end(fs.readFileSync(path.join(__dirname, filename)));
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
      ...(process.env.SCHEDULE_CHROME_PATH ? { executablePath: process.env.SCHEDULE_CHROME_PATH } : {})
    });
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await page.addInitScript(() => {
      if (!localStorage.getItem('byelinguaUiLanguage')) localStorage.setItem('byelinguaUiLanguage', 'en');
    });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('https://**/*', route => route.fulfill({ contentType: 'text/javascript', body: '' }));
    const base = `http://127.0.0.1:${server.address().port}`;
    const waitForRows = async () => {
      await page.waitForLoadState('load');
      await page.waitForFunction(() => document.querySelectorAll('#events .event').length === 15);
    };
    const checkPages = async (count, current, language, visible, ellipses) => {
      const nav = page.locator('#eventPagination');
      assert.deepEqual(await nav.locator('[data-page-number]').allTextContents(), visible.map(String), 'Only endpoint and nearby page numbers should be visible');
      assert.equal(await nav.locator('.pagination-ellipsis').count(), ellipses, 'Distant middle pages should be abbreviated');
      assert.equal(await nav.locator('[aria-current="page"]').textContent(), String(current));
      const labels = language === 'zh' ? ['第一页', '上一页', '下一页', '最后一页'] : ['First page', 'Previous', 'Next', 'Last page'];
      for (const [i, action] of ['first', 'prev', 'next', 'last'].entries()) {
        const button = nav.locator(`[data-page-${action}]`);
        assert.equal(await button.textContent(), labels[i]);
        assert.equal(await button.isDisabled(), i < 2 ? current === 1 : current === count);
      }
    };
    await page.goto(`${base}/schedule.html`);
    await waitForRows();
    await checkPages(67, 1, 'en', [1, 2, 3, 67], 1);
    for (const [selector, current, firstId, visible, ellipses] of [
      ['[data-page-next]', 2, 'pagination-16', [1, 2, 3, 67], 1],
      ['[data-page-last]', 67, 'pagination-991', [1, 65, 66, 67], 1],
      ['[data-page-prev]', 66, 'pagination-976', [1, 65, 66, 67], 1],
      ['[data-page-first]', 1, 'pagination-1', [1, 2, 3, 67], 1]
    ]) {
      await page.locator(`#eventPagination ${selector}`).click();
      await checkPages(67, current, 'en', visible, ellipses);
      assert.equal(await page.locator('#events [data-event]').first().getAttribute('data-event'), firstId);
    }
    await page.evaluate(() => { eventPage = 34; renderEvents(); });
    await checkPages(67, 34, 'en', [1, 33, 34, 35, 67], 2);
    assert.equal(await page.locator('#events [data-event]').first().getAttribute('data-event'), 'pagination-496');
    await page.locator('#eventPagination [data-page-first]').click();
    await page.locator('[data-shared-language="zh"]').click();
    await page.waitForFunction(() => document.documentElement.lang === 'zh-CN');
    await waitForRows();
    await checkPages(67, 1, 'zh', [1, 2, 3, 67], 1);
    await page.reload(); await waitForRows(); await checkPages(67, 1, 'zh', [1, 2, 3, 67], 1);
    for (const width of [920, 375]) {
      await page.setViewportSize({ width, height: 1000 });
      await checkPages(67, 1, 'zh', [1, 2, 3, 67], 1);
      assert.equal(await page.locator('#eventPagination').evaluate(nav => {
        const box = nav.getBoundingClientRect();
        return [...nav.querySelectorAll('button')].every(button => {
          const b = button.getBoundingClientRect();
          return b.left >= box.left - 1 && b.right <= box.right + 1;
        });
      }), true, 'All page buttons must wrap inside the pagination area');
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    if (process.env.SCHEDULE_PAGINATION_SCREENSHOT) await page.locator('#eventPagination').screenshot({ path: process.env.SCHEDULE_PAGINATION_SCREENSHOT });
    for (const [query, count, pages, visible, ellipses] of [
      ['two', 16, 2, [1, 2], 0],
      ['seven', 105, 7, [1, 2, 3, 4, 5, 6, 7], 0],
      ['eight', 106, 8, [1, 2, 3, 8], 1],
      ['single', 15, 0, [], 0],
      ['empty', 0, 0, [], 0],
      ['', 1000, 67, [1, 2, 3, 67], 1]
    ]) {
      await page.locator('#workCondition').fill(query);
      await page.locator('#workCondition').press('Enter');
      await page.waitForFunction(n => document.querySelector('#resultHint').textContent.includes(String(n)), count);
      if (pages) await checkPages(pages, 1, 'zh', visible, ellipses);
      else assert.equal(await page.locator('#eventPagination button').count(), 0);
    }
    assert.deepEqual(errors, [], 'Complete page must load and paginate without script errors');
    console.log('PASS: full page load, compact dynamic pagination, four navigation controls, middle and endpoint pages, English/Chinese, reload, responsive wrapping, and changed search results.');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
