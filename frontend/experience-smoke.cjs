if (!process.env.LANDGUARD_TEST_EMAIL || !process.env.LANDGUARD_TEST_PASSWORD) throw new Error('Set LANDGUARD_TEST_EMAIL and LANDGUARD_TEST_PASSWORD to an activated test account.');
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async()=>{
 const browser = await chromium.launch({channel:'msedge',headless:true});
 const page = await browser.newPage({viewport:{width:1440,height:1050}});
 const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 const base='http://127.0.0.1:5173';
 try {
  await page.goto(base);
  const preview=page.getByRole('region',{name:'Interactive product walkthrough'});
  await preview.getByRole('button',{name:'Preview projects with pending approvals'}).click();
  assert.equal(await preview.locator('.preview-records > button').count(),2);
  await preview.getByRole('tab',{name:'Analytics',exact:true}).click();
  await preview.getByRole('button',{name:'Preview North district'}).click();
  await preview.getByRole('tab',{name:'Projects',exact:true}).click();
  await preview.getByRole('button',{name:/EX-01/}).click();
  await preview.getByRole('progressbar',{name:'Example Compensation'}).waitFor();
  assert.equal(await preview.getByRole('progressbar',{name:'Example Compensation'}).getAttribute('aria-valuenow'),'42');
  await preview.getByRole('button',{name:'Reset',exact:true}).click();
  assert.equal(await preview.locator('.preview-records > button').count(),3);
  await preview.getByRole('tab',{name:'Projects',exact:true}).press('ArrowLeft');
  assert.equal(await preview.getByRole('tab',{name:'Analytics',exact:true}).getAttribute('aria-selected'),'true');
  await page.getByRole('button',{name:'Portal administrators',exact:true}).click();
  await page.getByRole('heading',{name:'Give each person the right access.'}).waitFor();
  await page.getByRole('button',{name:'District officers',exact:true}).click();
  await page.getByRole('heading',{name:'Bring local acquisition work into focus.'}).waitFor();
  await page.getByText('Can I try it without signing in?',{exact:true}).click();
  assert.equal(await page.locator('.public-faq details').first().getAttribute('open'),'');
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:'experience-landing-smoke.png',fullPage:true});
  await page.goto(base+'/login');
  const submit=page.getByRole('button',{name:'Enter workspace'});
  assert.equal(await submit.isDisabled(),true);
  await page.getByLabel('Email',{exact:true}).fill(process.env.LANDGUARD_TEST_EMAIL);
  await page.getByLabel('Password',{exact:true}).fill(process.env.LANDGUARD_TEST_PASSWORD);
  await page.getByRole('button',{name:'Show password',exact:true}).click();
  assert.equal(await page.getByLabel('Password',{exact:true}).getAttribute('type'),'text');
  await page.getByRole('button',{name:'Hide password',exact:true}).click();
  await page.getByRole('button',{name:/Compare districts/}).click();
  await page.getByText('Explore differences in compensation, possession, and acquisition stage.').waitFor();
  await page.screenshot({path:'experience-login-smoke.png',fullPage:true});
  await page.route('**/auth/login',route=>route.fulfill({status:401,contentType:'application/json',body:'{}'}));
  await submit.click(); await page.getByRole('alert').waitFor();
  await page.unroute('**/auth/login');
  await submit.click();
  await page.getByRole('heading',{name:'Operational dashboard'}).waitFor();
  await page.waitForFunction(()=>!document.querySelector('[aria-label="Refresh project data"]')?.disabled);
  assert.equal(await page.locator('.workspace-page').evaluate(el=>getComputedStyle(el).animationName),'workspace-arrive');
  await page.getByTestId('Pending approvals').click();
  const dock=page.getByRole('complementary',{name:'Current selection'});
  await dock.getByRole('button',{name:'View results'}).click();
  await page.waitForFunction(()=>document.activeElement?.id==='project-monitor');
  await page.locator('.project-table tbody tr').first().waitFor();
  const before=await page.locator('.project-table tbody tr').count();
  await page.route('**/api/v1/projects?*',async route=>{await new Promise(r=>setTimeout(r,700));await route.continue();});
  await page.getByRole('button',{name:'Refresh project data'}).click();
  assert.equal(await page.locator('.project-table tbody tr').count(),before,'Refresh keeps current records visible');
  await page.waitForFunction(()=>!document.querySelector('[aria-label="Refresh project data"]')?.disabled);
  await page.unroute('**/api/v1/projects?*');
  await page.getByRole('button',{name:'Quick view P1042',exact:true}).first().click();
  await page.getByRole('dialog',{name:'Project quick view'}).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('dialog',{name:'Project quick view'}).waitFor({state:'hidden'});
  await page.getByRole('link',{name:'Compare in Analytics'}).click();
  await page.getByRole('heading',{name:'Acquisition analytics'}).waitFor();
  await dock.getByRole('link',{name:'Open records'}).click();
  await page.locator('.project-table tbody tr').first().waitFor();
  assert.equal(new URL(page.url()).searchParams.get('indicator'),'pending_approvals');
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await page.locator('.workspace-page').evaluate(el=>getComputedStyle(el).animationName),'none');
  for(const width of [768,390]){
   await page.setViewportSize({width,height:900});
   for(const route of ['/','/login','/dashboard?indicator=pending_approvals','/analytics?district=Pune']){
    await page.goto(base+route);
    await page.locator('h1').first().waitFor();
    if(route.startsWith('/dashboard') || route.startsWith('/analytics')) await page.waitForFunction(()=>!document.querySelector('[aria-label="Refresh project data"],[aria-label="Refresh analytics"]')?.disabled);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,route+' width '+width);
    if(width===390 && route==='/') {
      await page.getByRole('tab',{name:'Projects',exact:true}).click();
      await page.getByRole('button',{name:/EX-01/}).click();
      await page.getByRole('progressbar',{name:'Example Compensation'}).waitFor();
      await page.screenshot({path:'experience-mobile-smoke.png',fullPage:true});
    }
   }
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: interactive walkthrough, role journeys, FAQ, login controls/errors, workspace motion, selection dock, refresh continuity, drawer, scoped navigation, mobile, and reduced motion.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
