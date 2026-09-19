/* Visual QA capture: every screen at every required width, plus an automated scan for
   overflow, clipping and touch-target problems. Screenshots land in /home/claude/work/qa. */
const { chromium } = require('playwright');
const fs = require('node:fs');

const BASE = 'http://127.0.0.1:4173';
const OUT = '/home/claude/work/qa';
const WIDTHS = [1440, 1280, 1024, 768, 430, 390];

const SCREENS = [
  { name: 'dashboard', url: '/', ready: '.stat' },
  { name: 'projects', url: '/projects', ready: '.pagination' },
  { name: 'details', url: '/projects/P1042', ready: '.detail-tabs' },
  { name: 'details-issues', url: '/projects/P1042?tab=issues', ready: '.admin-indicators' },
  { name: 'details-ai', url: '/projects/P1042?tab=ai', ready: '.intelligence-slots' },
  { name: 'details-gis', url: '/projects/P1042?tab=gis', ready: '.geographic-placeholder' },
  { name: 'details-history', url: '/projects/P1042?tab=history', ready: '.timeline' },
  { name: 'form', url: '/projects/new', ready: '.form-grid' },
  { name: 'empty', url: '/projects?search=zzzzzznomatch', ready: '.empty' },
  { name: 'filters-open', url: '/projects?state=Maharashtra&project_type=ROAD', ready: '.filter-chips' },
  { name: 'notfound', url: '/nowhere', ready: '.empty' },
];

// Elements whose box escapes its scroll container, or whose text is clipped.
const SCAN = () => {
  const problems = [];
  const docWidth = document.documentElement.clientWidth;
  for (const el of document.querySelectorAll('body *')) {
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || !el.getClientRects().length) continue;
    const rect = el.getBoundingClientRect();
    const tag = el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).join('.') : '');

    // Horizontal escape past the viewport.
    if (rect.width > 0 && (rect.right > docWidth + 1.5 || rect.left < -1.5)) {
      const scrollParent = el.closest('.table-wrap, .chart-scroll, .pagination-controls, .detail-tabs, dialog, .command-results');
      if (!scrollParent) problems.push(`OVERFLOW ${tag} left=${rect.left.toFixed(0)} right=${rect.right.toFixed(0)} vw=${docWidth}`);
    }
    // Text clipped by a fixed-height or hidden-overflow box.
    if (style.overflow !== 'visible' && el.scrollWidth > el.clientWidth + 2 && el.children.length === 0 && el.textContent.trim()) {
      const scrollable = style.overflowX === 'auto' || style.overflowX === 'scroll';
      if (!scrollable) problems.push(`CLIPPED-X ${tag} scrollW=${el.scrollWidth} clientW=${el.clientWidth} "${el.textContent.trim().slice(0, 40)}"`);
    }
    if (style.overflowY === 'hidden' && el.scrollHeight > el.clientHeight + 2 && el.children.length === 0 && el.textContent.trim()) {
      problems.push(`CLIPPED-Y ${tag} scrollH=${el.scrollHeight} clientH=${el.clientHeight} "${el.textContent.trim().slice(0, 40)}"`);
    }
  }
  // Page-level horizontal scroll.
  if (document.documentElement.scrollWidth > docWidth + 1) {
    problems.push(`PAGE-SCROLL-X scrollWidth=${document.documentElement.scrollWidth} vw=${docWidth}`);
  }
  return [...new Set(problems)];
};

const TOUCH_SCAN = () => {
  const small = [];
  for (const el of document.querySelectorAll('button, a[href], select, input, summary, [role="tab"], [role="option"]')) {
    const style = getComputedStyle(el);
    if (style.display === 'none' || !el.getClientRects().length) continue;
    const r = el.getBoundingClientRect();
    if (r.height > 0 && r.height < 30) {
      const label = (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30);
      small.push(`${el.tagName.toLowerCase()}.${(el.className || '').toString().trim().split(/\s+/)[0]} h=${r.height.toFixed(0)} w=${r.width.toFixed(0)} "${label}"`);
    }
  }
  return [...new Set(small)];
};


// Scroll-reveal panels only appear once they intersect the viewport, and a fullPage
// screenshot resizes the viewport mid-capture — which fires the observers and photographs
// the transition halfway. Walking the page first reveals everything and lets it settle.
async function settle(page) {
  await page.evaluate(async () => {
    const step = Math.round(window.innerHeight * 0.8);
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise(r => setTimeout(r, 120));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(700);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const report = [];

  for (const width of WIDTHS) {
    const mobile = width <= 430;
    const page = await browser.newPage({ viewport: { width, height: mobile ? 900 : 1000 }, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1, reducedMotion: 'reduce' });
    page.on('pageerror', e => report.push(`[${width}] PAGEERROR ${e.message}`));

    for (const screen of SCREENS) {
      await page.goto(BASE + screen.url, { waitUntil: 'load' });
      try { await page.waitForSelector(screen.ready, { timeout: 8000 }); }
      catch { report.push(`[${width}] ${screen.name}: never reached ready state ${screen.ready}`); continue; }
      await page.waitForTimeout(900);
      await settle(page);
      await page.screenshot({ path: `${OUT}/${screen.name}-${width}.png`, fullPage: true });
      for (const p of await page.evaluate(SCAN)) report.push(`[${width}] ${screen.name}: ${p}`);
      if (mobile) for (const t of await page.evaluate(TOUCH_SCAN)) report.push(`[${width}] ${screen.name}: SMALL-TARGET ${t}`);
    }

    // Overlays
    await page.goto(BASE + '/projects?search=P1042');
    await page.getByRole('button', { name: 'Quick view P1042' }).first().click();
    await page.waitForSelector('dialog.quick-view[open]');
    await page.waitForTimeout(900);
    await page.screenshot({ path: `${OUT}/quickview-${width}.png` });
    for (const p of await page.evaluate(SCAN)) report.push(`[${width}] quickview: ${p}`);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);

    await page.keyboard.press('Control+k');
    await page.waitForSelector('dialog.command-palette[open]');
    await page.waitForTimeout(500);
    await page.keyboard.type('illus');
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/palette-${width}.png` });
    for (const p of await page.evaluate(SCAN)) report.push(`[${width}] palette: ${p}`);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);

    await page.getByRole('button', { name: 'Notification status' }).click();
    await page.waitForSelector('dialog.notice-center[open]');
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `${OUT}/notices-${width}.png` });
    for (const p of await page.evaluate(SCAN)) report.push(`[${width}] notices: ${p}`);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);

    // Expanded desktop filter panel / mobile filter sheet
    await page.goto(BASE + '/projects');
    await page.waitForSelector('.pagination');
    await page.getByRole('button', { name: /^Filters/ }).click();
    await page.waitForTimeout(700);
    if (!mobile) await settle(page);
    await page.screenshot({ path: `${OUT}/filters-${width}.png`, fullPage: !mobile });
    for (const p of await page.evaluate(SCAN)) report.push(`[${width}] filters: ${p}`);

    // Mobile navigation drawer
    if (width <= 768) {
      await page.goto(BASE + '/');
      await page.getByRole('button', { name: 'Toggle navigation' }).click();
      await page.waitForSelector('dialog.nav-drawer[open]');
      await page.waitForTimeout(700);
      await page.screenshot({ path: `${OUT}/navdrawer-${width}.png` });
      for (const p of await page.evaluate(SCAN)) report.push(`[${width}] navdrawer: ${p}`);
    }

    // Collapsed sidebar (desktop only)
    if (width > 900) {
      await page.goto(BASE + '/');
      await page.waitForSelector('.stat');
      await page.getByRole('button', { name: 'Collapse sidebar' }).click();
      await page.waitForTimeout(700);
      await page.screenshot({ path: `${OUT}/collapsed-${width}.png` });
      for (const p of await page.evaluate(SCAN)) report.push(`[${width}] collapsed: ${p}`);
    }

    await page.close();
  }

  // Loading and error states at one representative width each.
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: width <= 430 ? 900 : 1000 }, isMobile: width <= 430, hasTouch: width <= 430, reducedMotion: 'reduce' });
    // Loading: stall the API so skeletons stay up.
    await page.route('**/api/v1/**', route => setTimeout(() => route.abort(), 12000));
    await page.goto(BASE + '/');
    await page.waitForTimeout(1500);
    await settle(page);
    await page.screenshot({ path: `${OUT}/loading-${width}.png`, fullPage: true });
    for (const p of await page.evaluate(SCAN)) report.push(`[${width}] loading: ${p}`);
    await page.unroute('**/api/v1/**');

    // Error: fail the API outright.
    await page.route('**/api/v1/**', route => route.abort());
    await page.goto(BASE + '/');
    await page.waitForTimeout(2500);
    await settle(page);
    await page.screenshot({ path: `${OUT}/error-${width}.png`, fullPage: true });
    for (const p of await page.evaluate(SCAN)) report.push(`[${width}] error: ${p}`);
    await page.goto(BASE + '/projects/P1042');
    await page.waitForTimeout(2500);
    await page.screenshot({ path: `${OUT}/error-detail-${width}.png`, fullPage: true });
    for (const p of await page.evaluate(SCAN)) report.push(`[${width}] error-detail: ${p}`);
    await page.close();
  }

  await browser.close();
  fs.writeFileSync(`${OUT}/report.txt`, report.join('\n') || 'no automated issues found');
  console.log(report.length ? report.join('\n') : 'no automated issues found');
  console.log('\n--- ' + report.length + ' automated findings; screenshots in ' + OUT);
})().catch(e => { console.error('FAILED ' + e.message); process.exit(1); });
