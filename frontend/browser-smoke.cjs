// Run against the local demo: NODE_PATH must resolve an installed Playwright package.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ reducedMotion: 'reduce', viewport: { width: 1440, height: 1050 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const id = `SMOKE_${Date.now()}`;
  try {
    await page.goto('http://127.0.0.1:5173');
    await page.getByRole('link', { name: 'Illustrative Eastern Connector' }).waitFor();
    await page.getByLabel('Search projects').fill('P1042');
    await page.getByText('1 matching records', { exact: false }).waitFor();
    await page.getByRole('link', { name: 'Illustrative Eastern Connector' }).click();
    await page.getByRole('heading', { name: 'Acquisition progress' }).waitFor();
    await page.getByRole('tab', { name: 'AI Intelligence' }).click();
    await page.getByRole('heading', { name: 'Model not yet trained' }).waitFor();
    await page.goto('http://127.0.0.1:5173/projects/new');
    const values = {
      'Project ID': id, 'Project name': 'Fictional browser smoke record', State: 'Test state', District: 'Test district',
      Latitude: '18.52', Longitude: '73.85', 'Land area (hectares)': '120', 'Affected families': '80',
      'Compensation completed (%)': '35', 'Possession (%)': '20', 'Rehabilitation completed (%)': '30',
      'Pending approvals': '2', 'Legal disputes': '1', 'Stakeholder response (days)': '14', 'Elapsed acquisition (days)': '90',
    };
    for (const [label, value] of Object.entries(values)) await page.getByLabel(label, { exact: true }).fill(value);
    await page.getByRole('button', { name: 'Save project' }).click();
    await page.getByRole('heading', { name: 'Fictional browser smoke record' }).waitFor();
    await page.getByRole('link', { name: 'Edit project' }).click();
    await page.getByLabel('Project name', { exact: true }).fill('Fictional browser edited record');
    await page.getByRole('button', { name: 'Save project' }).click();
    await page.getByRole('heading', { name: 'Fictional browser edited record' }).waitFor();
    await page.reload();
    await page.getByRole('heading', { name: 'Fictional browser edited record' }).waitFor();
    await page.getByRole('link', { name: 'Edit project' }).click();
    await page.getByRole('button', { name: 'Delete project' }).click();
    await page.getByRole('button', { name: 'Confirm deletion' }).click();
    await page.getByRole('heading', { name: 'All projects' }).waitFor();
    await page.goto('http://127.0.0.1:5173');
    await page.getByRole('link', { name: 'Illustrative Eastern Connector' }).waitFor();
    await page.screenshot({ path: 'desktop-smoke.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: 'Toggle navigation' }).click();
    await page.getByRole('dialog').getByRole('link', { name: 'Projects', exact: true }).click();
    await page.getByRole('heading', { name: 'All projects' }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: 'mobile-smoke.png', fullPage: true });
    assert.deepEqual(errors, []);
    console.log('PASS: filtering, details, create, edit, reload persistence, delete, mobile navigation; no browser errors.');
  } finally {
    await page.request.delete(`http://127.0.0.1:8000/api/v1/projects/${id}`);
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
