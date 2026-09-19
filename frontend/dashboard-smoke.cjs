const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ reducedMotion: 'reduce', viewport: { width: 1440, height: 1050 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    const response = await page.request.get('http://127.0.0.1:8000/api/v1/dashboard/summary');
    assert.equal(response.status(), 200);
    const summary = await response.json();
    await page.route('**/dashboard/summary?*', async route => {
      await new Promise(resolve => setTimeout(resolve, 700));
      await route.continue();
    });
    await page.goto('http://127.0.0.1:5173');
    await page.getByLabel('Loading dashboard').waitFor();
    assert.equal(await page.getByTestId('Total projects').count(), 0);
    await page.getByTestId('Total projects').waitFor();
    assert.equal(await page.getByTestId('Total projects').locator('strong').innerText(), String(summary.total_projects));
    assert.equal(await page.getByTestId('Pending approvals').locator('strong').innerText(), String(summary.pending_approvals));
    assert.equal(await page.getByTestId('Projects with legal disputes').locator('strong').innerText(), String(summary.projects_with_legal_disputes));
    assert.equal(await page.getByTestId('Average compensation progress').locator('strong').innerText(), summary.avg_compensation_pct + '%');
    await page.getByRole('heading', { name: 'Administrative bottlenecks' }).waitFor();
    await page.unroute('**/dashboard/summary?*');
    await page.getByLabel('Search projects').fill('P1042');
    await page.getByText('1 matching records', { exact: false }).waitFor();
    await page.waitForFunction(() => document.querySelector('[data-testid="Total projects"] strong')?.textContent === '1');
    const filtered = await (await page.request.get('http://127.0.0.1:8000/api/v1/dashboard/summary?search=P1042')).json();
    assert.equal(await page.getByTestId('Pending approvals').locator('strong').innerText(), String(filtered.pending_approvals));
    await page.getByLabel('Search projects').fill('NO_SUCH_FICTIONAL_PROJECT');
    await page.getByRole('heading', { name: 'No projects are currently available.' }).waitFor();
    assert.equal(await page.getByTestId('Average compensation progress').locator('strong').innerText(), 'Unavailable');
    assert.equal(await page.locator('.chart-panel').count(), 0);
    await page.route('**/dashboard/**', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Private SQL stack trace should never reach the interface.' }) }));
    await page.getByLabel('Search projects').fill('');
    await page.getByRole('heading', { name: 'Dashboard data could not be loaded.' }).waitFor();
    assert.equal(await page.getByText('Private SQL stack trace', { exact: false }).count(), 0);
    await page.unroute('**/dashboard/**');
    await page.getByRole('button', { name: 'Try again' }).click();
    await page.getByRole('heading', { name: 'Administrative bottlenecks' }).waitFor();
    await page.getByRole('button', { name: 'Next', exact: true }).click();
    await page.getByText('Page 2 of', { exact: false }).waitFor();
    assert.equal(await page.getByTestId('Total projects').locator('strong').innerText(), String(summary.total_projects));
    await page.getByRole('button', { name: 'Previous', exact: true }).click();
    await page.getByText('Page 1 of', { exact: false }).waitFor();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: 'dashboard-desktop-smoke.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('heading', { name: 'Administrative bottlenecks' }).scrollIntoViewIfNeeded();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: 'dashboard-mobile-smoke.png', fullPage: true });
    assert.deepEqual(errors, []);
    console.log('PASS: database-derived metrics, shared filters, loading, empty, failure/retry, pagination, mobile layout; no JavaScript errors.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
