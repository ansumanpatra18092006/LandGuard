/* Every interactive element must change visibly on hover and show a focus ring on
   keyboard focus. Compares computed styles before and after. */
const { chromium } = require('playwright');

const TARGETS = [
  ['/', '.clickable-stat', 'KPI card'],
  ['/', '.bottleneck-row', 'Bottleneck row'],
  ['/', '.district-panel > summary', 'District panel summary'],
  ['/', '.chart-data summary', 'Chart values summary'],
  ['/projects', '.project-table tbody tr', 'Table row'],
  ['/projects', '.project-link', 'Project name link'],
  ['/projects', '.view-link', 'Quick view link'],
  ['/projects', '.sort-header', 'Sort header'],
  ['/projects', '.pagination-controls button:not([disabled])', 'Pagination button'],
  ['/projects', '.filters button', 'Filters button'],
  ['/projects?state=Maharashtra', '.filter-chips .chip', 'Filter chip'],
  ['/projects/P1042', '.detail-tabs button', 'Detail tab'],
  ['/projects/P1042', '.back', 'Back link'],
  ['/', '.app-nav a', 'Sidebar nav link'],
  ['/', '.collapse-button', 'Collapse sidebar'],
  ['/', '.global-search input', 'Global search input'],
  ['/', '.header-menu > summary', 'Profile menu'],
];

const snapshot = el => {
  const s = getComputedStyle(el);
  return [s.backgroundColor, s.color, s.borderColor, s.transform, s.textDecorationLine, s.boxShadow, s.opacity].join('|');
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  const rows = [];

  for (const [url, selector, label] of TARGETS) {
    await page.goto('http://127.0.0.1:4173' + url);
    try { await page.waitForSelector(selector, { timeout: 8000 }); } catch { rows.push(`  MISSING  ${label} (${selector})`); continue; }
    await page.waitForTimeout(500);
    const el = page.locator(selector).first();

    await page.mouse.move(5, 5);
    await page.waitForTimeout(120);
    const before = await el.evaluate(snapshot);
    await el.hover();
    await page.waitForTimeout(200);
    const after = await el.evaluate(snapshot);
    const hoverChanged = before !== after;

    // Focus ring: outline, or a box-shadow ring for inputs.
    const focus = await el.evaluate(node => {
      node.focus();
      const target = document.activeElement.closest('button, a, input, select, summary, tr, [tabindex]') || document.activeElement;
      const s = getComputedStyle(target);
      return { outline: s.outlineStyle + ' ' + s.outlineWidth, shadow: s.boxShadow, tag: target.tagName.toLowerCase() };
    });
    const focusable = await el.evaluate(node => {
      const t = node.tagName.toLowerCase();
      return ['button', 'a', 'input', 'select', 'summary'].includes(t) || node.hasAttribute('tabindex');
    });
    const ring = focus.outline !== 'none 0px' || /rgba?\([^)]*\)\s+0px\s+0px\s+0px\s+3px/.test(focus.shadow);

    rows.push(`  ${hoverChanged ? 'hover OK ' : 'HOVER —  '} ${focusable ? (ring ? 'focus OK ' : 'FOCUS —  ') : 'n/a      '} ${label}`);
  }

  console.log(rows.join('\n'));
  await browser.close();
})().catch(e => { console.error('FAILED ' + e.message); process.exit(1); });
