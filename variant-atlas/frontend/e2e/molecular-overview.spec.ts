import {test,expect} from '@playwright/test';

async function project(page:any){
 const sources=await (await page.request.get('/api/portfolio/sources')).json();
 const response=await page.request.post('/api/portfolio/projects',{data:{title:'Molecular overview entry',objective:'Inspect measured PTEN evidence from the molecular overview.',method:'pten',source_ids:sources.filter((s:any)=>s.method==='pten'&&!s.coverage.startsWith('Historical')).map((s:any)=>s.id)}});
 expect(response.ok()).toBe(true);return response.json();
}
function watchModels(page:any){const calls:string[]=[];page.on('request',(r:any)=>{if(r.method()==='POST'&&(/\/api\/(?:research|blood)\/investigations$|\/api\/portfolio\/projects\/[^/]+\/investigations$|\/papers\/[^/]+\/read$/.test(r.url())||r.postData()?.includes('"use_model":true')))calls.push(r.url());});return calls;}

test('one authentic reference scene reverses with scroll and opens the exact measured project context',async({page})=>{
 const p=await project(page);const calls=watchModels(page),errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 const before=await (await page.request.get('/api/workspaces/pten-real')).json();const variant=before.variants.find((v:any)=>v.id==='PTEN:p.C124S');
 await page.goto('/');await expect(page.getByRole('heading',{level:1})).toContainText('See the structure.');await expect(page.getByRole('link',{name:'Resume project',exact:false})).toBeVisible();
 const scene=page.getByTestId('overview-reference');await expect(scene).toHaveAttribute('data-rendered','true',{timeout:45000});expect(Number(await scene.getAttribute('data-atom-count'))).toBeGreaterThan(1000);await scene.evaluate(el=>el.setAttribute('data-test-instance','same'));
 const start=(await page.locator('.mo-scene-subject').boundingBox())!;await page.screenshot({path:'../artifacts/molecular-overview-desktop.png',animations:'disabled'});
 await page.evaluate(()=>{const host=document.querySelector<HTMLElement>('.mo-experience')!,pin=document.querySelector<HTMLElement>('.mo-scene-pin')!;scrollTo(0,scrollY+host.getBoundingClientRect().top+(host.offsetHeight-pin.offsetHeight)*.85);});
 await expect(page.locator('.mo-experience')).toHaveAttribute('data-focus','selected-residue');await expect(scene).toHaveAttribute('data-test-instance','same');expect((await page.locator('.mo-scene-subject').boundingBox())!.x).toBeLessThan(start.x-150);
 await expect(page.locator('.mo-measurement-card')).toContainText(variant.activity.toFixed(4));await expect(page.locator('.mo-measurement-card')).toContainText(variant.abundance.toFixed(4));await expect(page.locator('.mo-measurement-card')).toContainText('original scale');
 await page.screenshot({path:'../artifacts/molecular-overview-evidence.png',animations:'disabled'});
 await page.evaluate(()=>scrollTo(0,0));await expect(page.locator('.mo-experience')).toHaveAttribute('data-progress','0.000');expect(Math.abs((await page.locator('.mo-scene-subject').boundingBox())!.x-start.x)).toBeLessThan(2);
 await page.evaluate(()=>scrollTo(0,document.documentElement.scrollHeight));await expect(scene).toHaveAttribute('data-rendering','paused');await page.evaluate(()=>scrollTo(0,0));await expect(scene).toHaveAttribute('data-rendering','active');
 await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>true});document.dispatchEvent(new Event('visibilitychange'));});await expect(scene).toHaveAttribute('data-rendering','paused');await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});document.dispatchEvent(new Event('visibilitychange'));});await expect(scene).toHaveAttribute('data-rendering','active');
 const unchanged=await (await page.request.get('/api/workspaces/pten-real')).json();expect(unchanged.variants.map((v:any)=>v.mapping)).toEqual(before.variants.map((v:any)=>v.mapping));
 await page.locator('.mo-measurement-card').getByRole('link',{name:'Inspect evidence',exact:false}).click();await expect(page).toHaveURL(new RegExp('/research/'+p.id+'/workspace\\?'));const url=new URL(page.url());expect(url.searchParams.get('variant')).toBe(variant.id);expect(url.searchParams.get('dataset')).toBe(before.dataset_version);expect(url.searchParams.get('mapping')).toBe(before.dataset_version);expect(url.searchParams.get('reference')).toBe('P60484');
 await expect(page.locator('.ba-live-inspector h2')).toHaveText('p.C124S',{timeout:45000});await expect(page.getByRole('region',{name:'Residue research assistant'})).toBeVisible();await expect(page.getByRole('checkbox',{name:'Focus-aware brain suggestions',exact:false})).toHaveCount(0);expect(calls).toEqual([]);expect(errors).toEqual([]);
});

test('mobile reduced-motion overview keeps evidence and navigation accessible without overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});const calls=watchModels(page);await page.goto('/');await expect(page.locator('.mo-experience')).toHaveClass(/mo-reduced/);await expect(page.getByRole('link',{name:'Open research workspace',exact:false})).toBeVisible();
 await expect(page.locator('.mo-measurement-card')).toContainText('p.C124S');await page.screenshot({path:'../artifacts/molecular-overview-mobile.png',animations:'disabled'});await page.locator('.mo-evidence').scrollIntoViewIfNeeded();await expect(page.locator('.mo-evidence-copy')).toHaveCSS('opacity','1');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await page.screenshot({path:'../artifacts/molecular-overview-mobile-evidence.png',animations:'disabled'});
 await page.getByRole('link',{name:'Assay source',exact:false}).click();await expect(page).toHaveURL(/\/library\/source-/);await expect(page.getByRole('heading',{name:'Source provenance',exact:true})).toBeVisible();await expect(page.getByTestId('overview-reference')).toHaveCount(0);expect(calls).toEqual([]);
});

test('WebGL failure presents a labelled authentic-coordinate fallback and usable source links',async({page})=>{
 await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(this:HTMLCanvasElement,type:string,...args:unknown[]){if(type.toLowerCase().includes('webgl'))return null;return (original as Function).apply(this,[type,...args]);} as typeof original;});
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));const calls=watchModels(page);await page.goto('/');await expect(page.locator('.mo-fallback-label')).toContainText('STATIC REFERENCE TRACE',{timeout:45000});await expect(page.getByRole('heading',{level:1})).toContainText('Investigate');await expect(page.locator('.mo-fallback img')).toBeVisible();await expect(page.locator('.mo-measurement-card')).toContainText('p.C124S');await page.screenshot({path:'../artifacts/molecular-overview-fallback.png',animations:'disabled'});await page.getByRole('link',{name:'Assay source',exact:false}).click();await expect(page.getByRole('heading',{name:'Source provenance',exact:true})).toBeVisible();expect(calls).toEqual([]);expect(errors).toEqual([]);
});


test('an overview selection survives the project picker and explicit project creation',async({page})=>{
 let hideProjects=true;
 await page.route('**/api/portfolio/bootstrap',async route=>{const response=await route.fetch();const data=await response.json();if(hideProjects)data.projects=[];await route.fulfill({json:data});});
 const calls=watchModels(page);await page.goto('/');await page.locator('.mo-measurement-card').getByRole('link',{name:'Inspect evidence',exact:false}).click();await expect(page).toHaveURL(/\/research\?variant=/);await page.getByRole('link',{name:'Start research',exact:false}).first().click();await page.getByLabel('Research question',{exact:true}).fill('Inspect the selected PTEN substitution and its original experimental evidence.');await page.getByRole('button',{name:'Review supported setup',exact:false}).click();await page.getByLabel('Research title',{exact:true}).fill('Overview-created PTEN project');hideProjects=false;await page.getByRole('button',{name:'Create research & open workspace',exact:false}).click();await expect(page).toHaveURL(/\/research\/project-[a-f0-9]+\/workspace\?variant=/);await expect(page.getByRole('region',{name:'Residue research assistant'})).toContainText('p.C124S',{timeout:45000});expect(calls).toEqual([]);
});

test('missing audited data stays explicit and never substitutes example measurements',async({page})=>{
 await page.route('**/api/workspaces/pten-real',route=>route.fulfill({status:503,json:{detail:'Reference data unavailable for this test.'}}));const calls=watchModels(page);await page.goto('/');await expect(page.locator('.mo-measurement-card')).toContainText('Evidence unavailable');await expect(page.locator('.mo-measurement-card')).not.toContainText('-4.8956');await expect(page.getByTestId('overview-reference')).toHaveCount(0);await page.getByRole('link',{name:'Inspect available sources',exact:false}).click();await expect(page.getByRole('heading',{name:'Library',exact:true})).toBeVisible();expect(calls).toEqual([]);
});
