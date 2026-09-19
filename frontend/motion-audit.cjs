/* Motion audit: exercises every animated surface and asserts that each one moves, settles,
   and disappears entirely under prefers-reduced-motion. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

// Defaults to the production preview: the dashboard chunk only behaves realistically bundled.
const BASE = process.env.BASE || 'http://127.0.0.1:4173';
const checks = [];
const ok = (name, detail = '') => { const line = `  PASS  ${name}${detail ? ' — ' + detail : ''}`; checks.push(line); console.log(line); };


// Watching a single timed probe is unreliable: an exit lasts 250ms and headless scheduling
// jitters. This samples the element every frame across the whole exit instead, and reports
// whether the dialog was still *open* while the exit animation ran — which is the thing that
// actually matters. An exit that plays on an already-closed dialog is an invisible exit.
async function recordExit(page, selector, dismiss) {
  await page.evaluate(sel => {
    window.__exit = [];
    const sample = () => {
      const el = document.querySelector(sel);
      if (el) window.__exit.push({ phase: el.dataset.phase, open: el.open, anim: getComputedStyle(el).animationName });
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
  }, selector);
  await dismiss();
  await page.waitForTimeout(600);
  return page.evaluate(() => window.__exit);
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  // Polling over the wire is far too slow to catch a 500ms tween, so the counter is sampled
  // in-page on every animation frame instead.
  await page.addInitScript(() => {
    window.__counter = [];
    const tick = () => {
      const el = document.querySelector('.stat strong');
      if (el) window.__counter.push(el.textContent);
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  try {
    // ---------- KPI counters ----------
    await page.goto(BASE + '/');
    const kpi = page.locator('.stat').first();
    await kpi.waitFor();
    await page.waitForTimeout(1200);
    const readings = await page.evaluate(() => [...new Set(window.__counter)]);
    assert.ok(readings.length > 3, 'KPI counter did not tick through intermediate values: ' + readings.join(','));
    assert.equal(readings[0], '0', 'counter did not start from zero');
    assert.equal(readings[readings.length - 1], '12', 'counter did not land on the true figure');
    const numeric = readings.map(Number);
    assert.ok(numeric.every((n, i) => i === 0 || n >= numeric[i - 1]), 'counter went backwards: ' + readings.join(','));
    assert.ok(numeric.every(n => n >= 0 && n <= 12), 'counter left its range: ' + readings.join(','));
    ok('KPI counter ramps monotonically to the true figure', readings.join(' → '));

    // ---------- KPI stagger ----------
    const delays = await page.$$eval('.stats .stat', els => els.map(el => getComputedStyle(el).animationDelay));
    assert.deepEqual(delays, ['0s', '0.055s', '0.11s', '0.165s']);
    ok('KPI entrance staggers', delays.join(' '));

    // ---------- Spotlight ----------
    const box = await kpi.boundingBox();
    assert.equal(await kpi.getAttribute('data-spotlight'), 'on');
    await page.mouse.move(box.x + box.width * 0.25, box.y + box.height * 0.5);
    await page.waitForTimeout(120);
    const spotA = await kpi.evaluate(el => el.style.getPropertyValue('--spot-x'));
    await page.mouse.move(box.x + box.width * 0.8, box.y + box.height * 0.5);
    await page.waitForTimeout(120);
    const spotB = await kpi.evaluate(el => el.style.getPropertyValue('--spot-x'));
    assert.ok(spotA && spotB && spotA !== spotB, `spotlight did not track: ${spotA} / ${spotB}`);
    const spotOpacity = await kpi.evaluate(el => getComputedStyle(el, '::after').opacity);
    assert.equal(spotOpacity, '1');
    await page.mouse.move(box.x + box.width / 2, box.y - 60);
    await page.waitForTimeout(260);
    assert.equal(await kpi.evaluate(el => getComputedStyle(el, '::after').opacity), '0');
    ok('KPI spotlight tracks the pointer and fades out on leave', `${spotA} → ${spotB}`);

    // ---------- Process strip ----------
    const strip = page.locator('.process-strip');
    await strip.waitFor();
    assert.equal(await strip.getAttribute('data-animate'), 'true');
    const stepDelays = await page.$$eval('.process-track li .process-label', els => els.map(el => getComputedStyle(el).animationDelay));
    assert.deepEqual(stepDelays, ['0s', '0.11s', '0.22s', '0.33s', '0.44s']);
    const labels = await page.$$eval('.process-track .process-label', els => els.map(el => el.textContent));
    assert.deepEqual(labels, ['Predict', 'Explain', 'Recommend', 'Alert', 'Intervene']);
    await page.waitForTimeout(1300);
    const settled = await page.$$eval('.process-track li .process-label', els => els.map(el => getComputedStyle(el).opacity));
    assert.ok(settled.every(o => o === '1'), 'process steps did not settle visible: ' + settled);
    // Hovering replays the sequence, which remounts the list.
    const before = await page.$eval('.process-track', el => el.getAttribute('data-run') || el.firstElementChild.textContent);
    await strip.hover();
    await page.waitForTimeout(80);
    const replayOpacity = await page.$$eval('.process-track .process-label', els => els.map(el => Number(getComputedStyle(el).opacity)));
    assert.ok(replayOpacity[4] < 1, 'hover did not replay the sequence: ' + replayOpacity.join(','));
    await page.waitForTimeout(1300);
    assert.ok((await page.$$eval('.process-track .process-label', els => els.map(el => getComputedStyle(el).opacity))).every(o => o === '1'));
    ok('Process strip runs once, settles, and replays on hover', before ? 'steps ' + labels.length : '');

    // ---------- Section reveal ----------
    await page.mouse.move(700, 900);
    const revealed = await page.$$eval('.panel.reveal', els => els.map(el => el.classList.contains('is-revealed')));
    assert.ok(revealed.length > 0, 'no revealable panels found');
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(900);
    const afterScroll = await page.$$eval('.panel.reveal', els => els.map(el => getComputedStyle(el).opacity));
    assert.ok(afterScroll.every(o => o === '1'), 'a panel stayed hidden after scrolling: ' + afterScroll.join(','));
    ok('Section reveal fires for every panel', afterScroll.length + ' panels');
    await page.evaluate(() => window.scrollTo(0, 0));

    // ---------- Filter chips ----------
    await page.goto(BASE + '/projects?state=Maharashtra&project_type=ROAD');
    await page.locator('.filter-chips .chip').first().waitFor();
    assert.equal(await page.locator('.filter-chips .chip').count(), 2);
    const chipAnim = await page.$eval('.filter-chips .chip', el => getComputedStyle(el).animationName);
    assert.equal(chipAnim, 'chip-in');
    await page.locator('.filter-chips .chip').first().click();
    await page.waitForTimeout(50);
    const exiting = await page.locator('.filter-chips .chip.is-exiting').count();
    assert.equal(exiting, 1, 'removed chip did not animate out');
    const exitName = await page.$eval('.filter-chips .chip.is-exiting', el => getComputedStyle(el).animationName);
    assert.equal(exitName, 'chip-out');
    await page.waitForTimeout(400);
    assert.equal(await page.locator('.filter-chips .chip').count(), 1, 'exiting chip was not cleaned up');
    ok('Filter chips animate in and collapse out', 'chip-in / chip-out');

    // ---------- Row stagger ----------
    await page.goto(BASE + '/projects');
    await page.locator('.project-table tbody tr').first().waitFor();
    const rowDelays = await page.$$eval('.project-table tbody tr', els => els.map(el => getComputedStyle(el).animationDelay));
    assert.deepEqual(rowDelays.slice(0, 4), ['0s', '0.026s', '0.052s', '0.078s']);
    await page.waitForTimeout(600);
    assert.ok((await page.$$eval('.project-table tbody tr', els => els.map(el => getComputedStyle(el).opacity))).every(o => o === '1'));
    ok('Table rows stagger in and settle', rowDelays.length + ' rows');

    // Changing page must remount the row list — reordering alone would leave the entrance
    // keyframes already spent, so the new page would appear with no transition at all.
    // Tagging the current tbody and watching the tag disappear tests that mechanism directly,
    // without racing the fetch to catch a 220ms animation mid-flight.
    await page.$eval('.project-table tbody', el => { el.dataset.generation = 'first'; });
    await page.getByRole('button', { name: 'Page 2' }).click();
    await page.getByText('Page 2 of', { exact: false }).waitFor();
    await page.locator('.project-table tbody tr').first().waitFor();
    const generation = await page.$eval('.project-table tbody', el => el.dataset.generation);
    assert.equal(generation, undefined, 'row list was reused, so the stagger could not replay');
    assert.equal(await page.$eval('.project-table tbody tr', el => getComputedStyle(el).animationName), 'row-enter');
    ok('Row stagger replays when the scope changes', 'row list remounts');

    // ---------- Drawer open + close ----------
    await page.goto(BASE + '/projects?search=P1042');
    await page.getByRole('button', { name: 'Quick view P1042' }).first().click();
    const drawer = page.locator('dialog.quick-view[open]');
    await drawer.waitFor();
    assert.equal(await drawer.getAttribute('data-phase'), 'open');
    const inAnim = await drawer.evaluate(el => [getComputedStyle(el).animationName, getComputedStyle(el).animationDuration]);
    assert.deepEqual(inAnim, ['drawer-in', '0.3s']);
    await page.waitForTimeout(600);

    // Progress fill still reaches the recorded percentage.
    const ratio = await drawer.locator('.progress').first().evaluate(el =>
      el.querySelector('.progress-track i').getBoundingClientRect().width / el.querySelector('.progress-track').getBoundingClientRect().width);
    assert.ok(Math.abs(ratio - 0.28) < 0.01, 'progress fill ratio ' + ratio);
    ok('Progress fill animates to the recorded percentage', '28%');

    const drawerExit = await recordExit(page, 'dialog.quick-view', () => page.keyboard.press('Escape'));
    const visibleExit = drawerExit.filter(f => f.anim === 'drawer-out' && f.open);
    assert.ok(visibleExit.length > 0, 'drawer exit never played while the dialog was open: ' + JSON.stringify(drawerExit.slice(0, 6)));
    assert.ok(drawerExit.some(f => !f.open), 'drawer never actually closed');
    assert.equal(await page.locator('dialog[open][aria-label="Project quick view"]').count(), 0);
    ok('Drawer animates out while still open, then closes', visibleExit.length + ' visible exit frames');

    // Focus must come back to whatever opened the drawer.
    const focused = await page.evaluate(() => document.activeElement?.getAttribute('aria-label'));
    assert.match(focused || '', /Quick view P1042/);
    ok('Focus returns to the trigger after the exit', focused);

    // ---------- Command palette ----------
    await page.keyboard.press('Control+k');
    const palette = page.locator('dialog.command-palette[open]');
    await palette.waitFor();
    assert.equal(await palette.evaluate(el => getComputedStyle(el).animationName), 'palette-in');
    await page.waitForTimeout(400);
    const paletteExit = await recordExit(page, 'dialog.command-palette', () => page.keyboard.press('Escape'));
    assert.ok(paletteExit.some(f => f.anim === 'palette-out' && f.open), 'palette exit was not visible');
    ok('Command palette opens and closes with matched motion', 'palette-in / palette-out');

    // ---------- Notice centre ----------
    await page.getByRole('button', { name: 'Notification status' }).click();
    const notices = page.locator('dialog.notice-center[open]');
    await notices.waitFor();
    assert.equal(await notices.evaluate(el => getComputedStyle(el).animationName), 'drawer-in');
    await page.waitForTimeout(500);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(450);
    ok('Notice centre uses the same drawer motion');

    // ---------- Tab indicator ----------
    await page.goto(BASE + '/projects/P1042');
    const tabs = page.locator('.detail-tabs');
    await tabs.waitFor();
    await page.waitForTimeout(250);
    const readAttr = await tabs.getAttribute('data-ready');
    assert.equal(readAttr, 'true');
    const first = await tabs.evaluate(el => [el.style.getPropertyValue('--tab-x'), el.style.getPropertyValue('--tab-scale')]);
    await page.getByRole('tab', { name: 'Administrative Issues' }).click();
    await page.waitForTimeout(300);
    const second = await tabs.evaluate(el => [el.style.getPropertyValue('--tab-x'), el.style.getPropertyValue('--tab-scale')]);
    assert.notDeepEqual(first, second, 'tab indicator did not move');
    assert.ok(parseFloat(second[0]) > parseFloat(first[0] || '0'));
    const indicatorTransition = await tabs.evaluate(el => getComputedStyle(el, '::after').transitionDuration);
    assert.equal(indicatorTransition, '0.18s');
    ok('Tab indicator slides between tabs', `x ${first[0] || '0px'} → ${second[0]}`);

    // ---------- Row action popover ----------
    await page.goto(BASE + '/projects?search=P1042');
    await page.getByRole('button', { name: 'Actions for P1042' }).first().click();
    await page.waitForTimeout(250);
    const menu = page.locator('.row-menu-panel:popover-open');
    assert.equal(await menu.count(), 1);
    assert.equal(await menu.evaluate(el => getComputedStyle(el).opacity), '1');
    ok('Row action popover settles fully opaque');
    await page.keyboard.press('Escape');

    // ---------- Toast ----------
    await page.goto(BASE + '/projects/P1042/edit');
    await page.getByRole('button', { name: 'Save project' }).waitFor();
    await page.getByRole('button', { name: 'Save project' }).click();
    const toast = page.locator('.toast');
    await page.waitForTimeout(500);
    assert.ok(await toast.evaluate(el => el.classList.contains('visible')), 'toast never became visible');
    assert.equal(await toast.evaluate(el => getComputedStyle(el).opacity), '1');
    await toast.getByRole('button', { name: 'Dismiss notification' }).click();
    await page.waitForTimeout(80);
    const fading = await toast.evaluate(el => Number(getComputedStyle(el).opacity));
    assert.ok(fading < 1 && fading > 0, 'toast did not fade out, opacity ' + fading);
    await page.waitForTimeout(500);
    assert.equal(await toast.innerText(), '');
    ok('Toast fades in, holds, and fades out', 'mid-exit opacity ' + fading.toFixed(2));

    await page.goto(BASE + '/');
    await page.waitForTimeout(1600);
    await page.screenshot({ path: 'motion-dashboard.png', fullPage: false });

    // ================= Reduced motion =================
    const reduced = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    reduced.on('pageerror', e => errors.push('reduced: ' + e.message));
    await reduced.goto(BASE + '/');
    await reduced.locator('.stat').first().waitFor();
    await reduced.waitForTimeout(400);

    // Nothing anywhere may be animating or transitioning.
    const moving = await reduced.evaluate(() => {
      const bad = [];
      for (const el of document.querySelectorAll('*')) {
        for (const pseudo of [null, '::before', '::after']) {
          const style = getComputedStyle(el, pseudo);
          if (style.animationName !== 'none' || style.transitionDuration !== '0s') {
            bad.push((el.className || el.tagName) + (pseudo || '') + ' anim=' + style.animationName + ' trans=' + style.transitionDuration);
          }
        }
      }
      return bad.slice(0, 8);
    });
    assert.deepEqual(moving, [], 'still animating under reduced motion: ' + moving.join(' | '));
    ok('Reduced motion: no animation or transition anywhere on the page');

    // And nothing may be left invisible by a reveal that never ran.
    const hidden = await reduced.evaluate(() => {
      const bad = [];
      for (const el of document.querySelectorAll('.panel, .stat, .process-track li > *, .filter-chips .chip, .project-table tbody tr, .toast.is-present')) {
        const style = getComputedStyle(el);
        if (Number(style.opacity) < 1 || (style.transform !== 'none' && style.transform !== 'matrix(1, 0, 0, 1, 0, 0)')) {
          bad.push((el.className || el.tagName) + ' opacity=' + style.opacity + ' transform=' + style.transform);
        }
      }
      return bad;
    });
    assert.deepEqual(hidden, [], 'content hidden under reduced motion: ' + hidden.join(' | '));
    ok('Reduced motion: all revealable content is visible and untransformed');

    // The KPI counter must show the final figure immediately, not count.
    assert.equal(await reduced.locator('.stat').first().locator('strong').innerText(), '12');
    ok('Reduced motion: KPI shows its final value with no count-up');

    // Spotlight must not attach at all.
    assert.equal(await reduced.locator('.stat').first().getAttribute('data-spotlight'), null);
    ok('Reduced motion: pointer spotlight is not attached');

    // Overlays still open and close correctly with motion off.
    await reduced.goto(BASE + '/projects?search=P1042');
    await reduced.getByRole('button', { name: 'Quick view P1042' }).first().click();
    await reduced.getByRole('dialog', { name: 'Project quick view' }).waitFor();
    await reduced.keyboard.press('Escape');
    await reduced.waitForTimeout(120);
    assert.equal(await reduced.locator('dialog[open][aria-label="Project quick view"]').count(), 0, 'drawer did not close under reduced motion');
    ok('Reduced motion: overlays open and close instantly');
    await reduced.screenshot({ path: 'motion-reduced.png' });
    await reduced.close();

    // ================= Mobile =================
    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    mobile.on('pageerror', e => errors.push('mobile: ' + e.message));
    await mobile.goto(BASE + '/projects?search=P1042');
    await mobile.locator('.project-mobile-card').first().waitFor();
    await mobile.getByRole('button', { name: 'Quick view P1042' }).first().click();
    const sheet = mobile.locator('dialog.quick-view[open]');
    await sheet.waitFor();
    assert.equal(await sheet.evaluate(el => getComputedStyle(el).animationName), 'sheet-in');
    await mobile.waitForTimeout(500);
    await mobile.screenshot({ path: 'motion-mobile.png' });
    const sheetExit = await recordExit(mobile, 'dialog.quick-view', () => mobile.keyboard.press('Escape'));
    assert.ok(sheetExit.some(f => f.anim === 'sheet-out' && f.open), 'bottom sheet exit was not visible');
    ok('Mobile: drawers rise and fall as bottom sheets', 'sheet-in / sheet-out');

    await mobile.goto(BASE + '/');
    await mobile.getByRole('button', { name: 'Toggle navigation' }).click();
    const nav = mobile.locator('dialog.nav-drawer[open]');
    await nav.waitFor();
    assert.equal(await nav.evaluate(el => getComputedStyle(el).animationName), 'nav-drawer-in');
    await mobile.waitForTimeout(400);
    const navExit = await recordExit(mobile, 'dialog.nav-drawer', () => mobile.keyboard.press('Escape'));
    const navVisible = navExit.filter(f => f.anim === 'nav-drawer-out' && f.open);
    assert.ok(navVisible.length > 0, 'nav drawer exit was not visible: ' + JSON.stringify(navExit.slice(0, 6)));
    assert.ok(navExit.some(f => !f.open), 'nav drawer never closed');
    assert.equal(await mobile.locator('dialog[open][aria-label="Navigation drawer"]').count(), 0);
    ok('Mobile: navigation drawer slides in and out from the left', navVisible.length + ' visible exit frames');
    await mobile.close();

    assert.deepEqual(errors, [], 'runtime errors: ' + errors.join(' | '));
    console.log('\n' + checks.length + ' motion checks passed.');
  } finally {
    await browser.close();
  }
})().catch(e => { console.error('\nFAILED: ' + e.message); process.exit(1); });
