const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
 const browser = await chromium.launch({channel:'msedge',headless:true});
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 try {
  await page.goto('http://127.0.0.1:5173/projects?search=P1042');
  await page.getByRole('button',{name:'Quick view P1042'}).first().click();
  const quick = page.getByRole('dialog',{name:'Project quick view'});
  await quick.waitFor();
  await page.waitForTimeout(600);
  const progress = quick.locator('.progress').first();
  const ratio = await progress.evaluate(el => el.querySelector('.progress-track i').getBoundingClientRect().width / el.querySelector('.progress-track').getBoundingClientRect().width);
  assert.ok(Math.abs(ratio - .28) < .01);
  assert.equal(await progress.getByRole('progressbar').getAttribute('value'),'28');
  await page.screenshot({path:'interaction-drawer-smoke.png'});
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await progress.locator('.progress-track i').evaluate(el => getComputedStyle(el).animationName),'none');
  await page.keyboard.press('Escape');
  await page.goto('http://127.0.0.1:5173/projects?page=2');
  await page.getByText('Page 2 of',{exact:false}).waitFor();
  await page.locator('.project-table .project-link').first().click();
  await page.getByRole('link',{name:'Back to results'}).click();
  assert.equal(new URL(page.url()).searchParams.get('page'),'2');
  await page.getByText('Page 2 of',{exact:false}).waitFor();
  console.log('PASS: progress reaches the recorded percentage, reduced motion disables animation, and return navigation restores page 2.');
 } finally {await browser.close();}
})().catch(e => {console.error(e);process.exit(1);});
