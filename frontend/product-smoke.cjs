if (!process.env.LANDGUARD_TEST_EMAIL || !process.env.LANDGUARD_TEST_PASSWORD) throw new Error('Set LANDGUARD_TEST_EMAIL and LANDGUARD_TEST_PASSWORD to an activated test account.');
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const errors = [];
  const publicRequests = [];
  let publicPhase = true;
  page.on('pageerror',e => errors.push(e.message));
  page.on('request',r => { if (publicPhase && r.url().includes('/api/')) publicRequests.push(r.url()); });
  const base = 'http://127.0.0.1:5173';
  try {
    await page.goto(base);
    await page.getByRole('heading',{name:/See the blockers/}).waitFor();
    assert.equal(await page.locator('.app-shell').count(),0);
    assert.deepEqual(publicRequests,[]);
    await page.screenshot({path:'landing-desktop-smoke.png',fullPage:true});
    await page.getByRole('link',{name:'Who it serves',exact:true}).click();
    await page.waitForFunction(() => Math.abs(document.querySelector('#users').getBoundingClientRect().top) < 160);
    await page.getByRole('link',{name:'Access guidance',exact:true}).click();
    await page.getByRole('heading',{name:'Access starts with authorization.'}).waitFor();
    assert.equal(await page.locator('form').count(),0);
    await page.getByRole('link',{name:'Go to sign in'}).click();
    assert.equal(await page.getByLabel('Email',{exact:true}).inputValue(),'');
    assert.equal(await page.getByLabel('Password',{exact:true}).inputValue(),'');
    publicPhase = false;
    await page.goto(base + '/analytics?district=Pune&state=Maharashtra');
    await page.waitForURL('**/login');
    await page.getByLabel('Email',{exact:true}).fill(process.env.LANDGUARD_TEST_EMAIL);
    await page.getByLabel('Password',{exact:true}).fill(process.env.LANDGUARD_TEST_PASSWORD);
    await page.getByRole('button',{name:'Enter workspace'}).click();
    await page.getByRole('heading',{name:'Acquisition analytics'}).waitFor();
    assert.equal(new URL(page.url()).searchParams.get('district'),'Pune');
    await page.getByRole('heading',{name:'Compensation vs. possession'}).waitFor();
    assert.equal(await page.locator('.project-table').count(),0);
    assert.equal(await page.getByTestId('Pending approvals').count(),0);
    await page.getByRole('link',{name:'Explore matching projects'}).click();
    await page.locator('.project-table tbody tr').first().waitFor();
    assert.equal(new URL(page.url()).searchParams.get('district'),'Pune');
    await page.locator('.project-table .project-link').first().click();
    await page.getByRole('link',{name:'Back to results'}).click();
    assert.equal(new URL(page.url()).searchParams.get('district'),'Pune');
    await page.getByRole('link',{name:'Dashboard',exact:true}).click();
    await page.getByRole('heading',{name:'Operational dashboard'}).waitFor();
    await page.getByTestId('Pending approvals').click();
    await page.getByTestId('Pending approvals').waitFor();
    assert.equal(new URL(page.url()).searchParams.get('indicator'),'pending_approvals');
    assert.equal(await page.locator('.recharts-wrapper').count(),0);
    await page.getByRole('link',{name:'Compare in Analytics'}).click();
    await page.getByRole('heading',{name:'Compensation vs. possession'}).waitFor();
    assert.equal(new URL(page.url()).searchParams.get('indicator'),'pending_approvals');
    await page.screenshot({path:'analytics-separated-smoke.png',fullPage:true});
    for (const width of [1440,768,390]) {
      await page.setViewportSize({width,height:900});
      for (const route of ['/','/access','/login','/dashboard','/analytics']) {
        await page.goto(base + route);
        if (['/dashboard','/analytics'].includes(route)) await page.waitForFunction(() => !document.querySelector('[aria-label="Refresh project data"],[aria-label="Refresh analytics"]')?.disabled);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true,route + ' overflows at ' + width);
        if (width === 390 && route === '/') await page.screenshot({path:'landing-mobile-smoke.png',fullPage:true});
      }
    }
    assert.deepEqual(errors,[]);
    console.log('PASS: public landing/access pages, no public data fetch, blank login, authenticated deep-link restoration, distinct dashboard/analytics, scoped drilldowns/back navigation, and desktop/tablet/mobile layouts.');
  } finally {await browser.close();}
})().catch(e => {console.error(e);process.exit(1);});
