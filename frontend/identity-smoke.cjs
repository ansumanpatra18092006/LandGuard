// Isolated UI fixtures: this test never sends an email or creates a real account.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 const base='http://127.0.0.1:5173';
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let signedIn=false, inviteCount=0, resendCount=0, accepts=0;
 const owner={id:'00000000-0000-4000-8000-000000000001',email:'owner@example.org',display_name:'Test Owner',role:'SYSTEM_ADMIN',status:'active',project_ids:[]};
 const active={id:'00000000-0000-4000-8000-000000000002',email:'active@example.org',display_name:'Active Colleague',role:'STATE_OFFICER',status:'active',state:'Maharashtra',project_ids:[]};
 const users=[owner,active];
 const token='a'.repeat(64);
 await page.route('**/api/v1/**',async route=>{
   const req=route.request(),path=new URL(req.url()).pathname.replace('/api/v1','');
   const json=req.postDataJSON();
   const send=(body,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
   if(req.method()!=='GET') assert.equal(req.headers()['x-landguard-request'],'1');
   if(path==='/auth/me') return send(signedIn?owner:{detail:'Sign in'},signedIn?200:401);
   if(path==='/auth/login') {assert.equal(json.email,'owner@example.org');assert.equal(json.username,undefined);signedIn=true;return send({user:owner});}
   if(path==='/auth/logout'){signedIn=false;return route.fulfill({status:204});}
   if(path==='/auth/users') return send(users);
   if(path==='/auth/invitations'){
     inviteCount++;assert.equal(json.role,'DISTRICT_OFFICER');assert.equal(json.district,'Pune');
     const profile={...json,id:'00000000-0000-4000-8000-000000000003',status:'invited',invitation_delivery:'accepted_by_brevo'};
     users.push(profile);return send(profile,201);
   }
   if(path.endsWith('/resend')){resendCount++;return send(users[2]);}
   if(path==='/auth/users/'+active.id){active.status=json.status;return send(active);}
   if(path==='/auth/accept-invitation'){
     accepts++;assert.equal(json.role,undefined);assert.equal(json.token_hash,token);
     return accepts===1?send({...users[2],status:'active'}):send({code:'INVITATION_INVALID',detail:'This invitation is expired or already used. Ask your administrator to resend it.'},400);
   }
   if(path==='/review-notices') return send({items:[],total:0,page:1,page_size:20});
   throw new Error('Unexpected mocked route '+path);
 });
 try {
   await page.goto(base+'/admin/users');
   await page.waitForURL('**/login');
   await page.getByLabel('Email',{exact:true}).fill('owner@example.org');
   await page.getByLabel('Password',{exact:true}).fill('isolated-browser-passphrase');
   await page.getByRole('button',{name:'Enter workspace'}).click();
   await page.getByRole('heading',{name:'Users & access'}).waitFor();
   assert.equal(new URL(page.url()).pathname,'/admin/users');
   assert.equal(await page.evaluate(()=>localStorage.getItem('landguard:auth')),null);
   await page.reload();await page.getByRole('heading',{name:'Users & access'}).waitFor();
   await page.getByLabel('Full name',{exact:true}).fill('Invited Colleague');
   await page.getByLabel('Work email',{exact:true}).fill('invited@example.org');
   await page.getByLabel('Assigned state',{exact:true}).fill('Maharashtra');
   await page.getByLabel('Assigned district',{exact:true}).fill('Pune');
   await page.getByRole('button',{name:'Send invitation',exact:true}).click();
   await page.getByText('Invitation accepted by Brevo.',{exact:false}).waitFor();
   assert.equal(inviteCount,1);
   await page.getByRole('button',{name:'Resend invitation',exact:true}).click();
   await page.getByText('New invitation accepted by Brevo.',{exact:true}).waitFor();
   assert.equal(resendCount,1);
   await page.getByRole('button',{name:'Disable account',exact:true}).click();
   await page.getByText('Account disabled and sessions revoked.',{exact:true}).waitFor();
   assert.equal(active.status,'disabled');
   await page.getByRole('button',{name:'Enable account',exact:true}).click();
   await page.getByText('Account enabled. The user can sign in again.',{exact:true}).waitFor();
   await page.getByLabel('Search accounts').fill('invited@');
   assert.equal(await page.locator('.account-list li').count(),1);
   await page.getByLabel('Search accounts').fill('');
   await page.screenshot({path:'identity-admin-smoke.png',fullPage:true});
   await page.setViewportSize({width:390,height:844});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:'identity-admin-mobile-smoke.png',fullPage:true});
   await page.setViewportSize({width:1440,height:1000});
   await page.locator('.profile-menu summary').click();
   await page.getByRole('button',{name:'Sign out',exact:true}).click();
   await page.waitForURL('**/login');
   await page.goto(base+'/admin/users');
   await page.waitForURL('**/login');
   await page.goto(base+'/accept-invitation#token_hash='+token+'&type=invite');
   await page.getByRole('heading',{name:'Choose your password'}).waitFor();
   assert.equal(new URL(page.url()).hash,'');
   assert.equal(accepts,0);
   await page.getByLabel('New password',{exact:true}).fill('isolated-browser-passphrase');
   await page.getByLabel('Confirm password',{exact:true}).fill('not-the-same-passphrase');
   assert(await page.getByRole('button',{name:'Activate account'}).isDisabled());
   await page.getByLabel('Confirm password',{exact:true}).fill('isolated-browser-passphrase');
   await page.screenshot({path:'identity-activation-smoke.png',fullPage:true});
   await page.getByRole('button',{name:'Activate account'}).click();
   await page.getByRole('heading',{name:'Your account is active'}).waitFor();
   await page.goto(base+'/accept-invitation#token_hash='+token+'&type=invite');
   await page.getByLabel('New password',{exact:true}).fill('isolated-browser-passphrase');
   await page.getByLabel('Confirm password',{exact:true}).fill('isolated-browser-passphrase');
   await page.getByRole('button',{name:'Activate account'}).click();
   await page.getByRole('alert').filter({hasText:'expired or already used'}).waitFor();
   await page.goto(base+'/accept-invitation');
   await page.getByRole('heading',{name:'Open your invitation email'}).waitFor();
   assert.deepEqual(errors,[]);
   console.log('Identity UI passed: email login, reload session, invitations, resend, disable/enable, filtering, mobile layout, logout, activation and expired links. Provider calls were mocked.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
