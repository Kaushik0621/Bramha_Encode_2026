import {test,expect} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomUUID} from 'node:crypto';
const artifacts='../artifacts/research-workflow-v2';
const article={id:'literature-'+'a'.repeat(24),title:'Cancer mutation evidence fixture',authors:'Fixture Research Team',year:'2025',institutions:['Fixture Laboratory'],abstract:'This fixture study reports a measured PTEN mutation. Independent validation is required.',url:'https://europepmc.org/article/MED/12345',open_access:false};
async function makeProject(page:any,method='papers'){
 const sources=await (await page.request.get('/api/portfolio/sources')).json();
 return (await page.request.post('/api/portfolio/projects',{data:{title:method==='papers'?'Mutation of cancer cells':'Structural comparison workspace',objective:method==='papers'?'Investigate mutation of cancer cells using published evidence.':'Compare measured PTEN substitutions and inspect reference coordinates.',method,area:'cancer',source_ids:method==='pten'?sources.filter((s:any)=>s.method==='pten').map((s:any)=>s.id):[]}})).json();
}

test('cancer workspace suggests searchable biological context and persists selections in both themes',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));const p=await makeProject(page);
 await page.goto('/research/'+p.id+'/workspace');
 const pool=page.getByRole('region',{name:'Biological research object pool'});
 await expect(pool.getByRole('heading',{name:'What biology are you investigating?'})).toBeVisible();
 await expect(pool.getByRole('heading',{name:'Organs & tissues',exact:true})).toBeVisible();
 await expect(pool.getByRole('heading',{name:'Cells & populations',exact:true})).toBeVisible();
 await expect(pool.getByRole('heading',{name:'Genes & proteins',exact:true})).toBeVisible();
 await expect(pool.getByRole('heading',{name:'Genetic structures',exact:true})).toBeVisible();
 await expect(pool.getByText('0 objects saved')).toBeVisible();
 await pool.getByRole('button',{name:'Organs & tissues',exact:true}).click();
 await pool.getByLabel('Search biological object pool').fill('Lung');
 await pool.locator('article').filter({has:page.getByRole('heading',{name:'Lung',exact:true})}).getByRole('button',{name:'Add to workspace',exact:false}).click();
 await expect(pool.getByLabel('Remove Lung from research scope')).toBeVisible();
 await pool.getByLabel('Search biological object pool').fill('TP53');
 await pool.getByRole('button',{name:'Genes & proteins',exact:true}).click();
 await pool.locator('article').filter({hasText:'TP53 / p53'}).getByRole('button',{name:'Add to workspace',exact:false}).click();
 await expect(pool.getByText('2 objects saved')).toBeVisible();
 await page.reload();await expect(pool.getByLabel('Remove Lung from research scope')).toBeVisible();await expect(pool.getByLabel('Remove TP53 / p53 from research scope')).toBeVisible();
 await page.screenshot({path:artifacts+'/context-light.png'});
 await page.route('**/api/hub/objects/search',async route=>{expect(route.request().postDataJSON()).toEqual({query:'KRAS',category:'gene'});await route.fulfill({json:{objects:[{id:'uniprot-fixture',category:'gene',label:'KRAS · public reference fixture',symbol:'KRAS',description:'Fixture reference contract',source_url:'https://www.uniprot.org/uniprotkb/P01116',source_type:'Live UniProt record'}]}});});
 await pool.getByRole('button',{name:'Genes & proteins',exact:true}).click();await pool.getByLabel('Search biological object pool').fill('KRAS');await pool.getByRole('button',{name:'Search public references',exact:true}).click();await expect(pool.getByRole('heading',{name:'KRAS · public reference fixture'})).toBeVisible();
 await pool.getByLabel('Remove Lung from research scope').click();await expect(pool.getByText('1 objects saved')).toBeVisible();
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>localStorage.setItem('bramha-atlas-theme','dark'));await page.reload();
 await expect(pool.getByText('1 objects saved')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:artifacts+'/context-mobile.png',animations:'disabled'});expect(errors).toEqual([]);
});

test('online evidence leads to selected passages, enabled start and visible reviewer results',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));const p=await makeProject(page);let source:any;
 await page.route('**/api/hub/discover',r=>r.fulfill({json:{results:[article],hit_count:1,query:'cancer mutation',model_called:false}}));
 await page.route('**/api/hub/evidence',async r=>{
  source=await (await page.request.post('/api/portfolio/sources/import',{data:{filename:'Cancer-evidence-fixture.txt',content_base64:Buffer.from(article.abstract).toString('base64')}})).json();
  await page.request.post('/api/portfolio/projects/'+p.id+'/sources',{data:{source_id:source.id}});await page.request.post('/api/portfolio/projects/'+p.id+'/sources',{data:{source_id:source.id,action:'include'}});
  await r.fulfill({json:{source,coverage:'abstract',included:true}});
 });
 await page.route('**/api/capabilities',async r=>{const response=await r.fetch();const body=await response.json();body.openrouter.configured=true;await r.fulfill({json:body});});
 await page.goto('/research/'+p.id+'/workspace');
 await page.getByRole('button',{name:'Find published studies',exact:true}).click();await expect(page.getByRole('heading',{name:'Cancer mutation evidence fixture ↗'})).toBeVisible();
 await page.getByRole('button',{name:'Save & include in this research',exact:true}).click();await expect(page.getByLabel('Workspace source')).toBeVisible();await expect(page.locator('.ex-paper-pages')).toContainText(article.abstract);
 await page.getByRole('link',{name:'Review investigation →',exact:true}).last().click();await expect(page.getByLabel('Review passage p1-c1')).toBeChecked();await expect(page.getByLabel('Investigation paper')).toHaveValue(source.id);
 await page.getByRole('button',{name:'Comparative',exact:false}).click();await page.getByLabel('Confirm reviewed investigation inputs').check();await expect(page.getByRole('button',{name:'Start investigation',exact:true})).toBeEnabled();
 await page.screenshot({path:artifacts+'/ready-investigation.png'});
 await page.route('**/api/portfolio/projects/'+p.id+'/investigations',async route=>{
  const input=route.request().postDataJSON();expect(input.paper.depth).toBe('standard');expect(input.paper.chunk_ids).toEqual(['p1-c1']);expect(input.paper.max_seconds).toBe(300);
  const rid='research-'+randomUUID().replaceAll('-','');const at=new Date().toISOString();const paper=await (await page.request.get('/api/research/papers/'+source.origin_id)).json();
  const doc={run_id:rid,workspace_id:'paper-review',status:'completed_with_limitations',created_at:at,revision:1,request:{...input.paper,project_id:p.id},provider:'fixture',model:'scripted',dataset_version:source.version,data_mode:'original-language passages',storage_mode:'local',source_manifest:[],paper_sources:[paper],events:[{event_id:'fixture-event',sequence:1,timestamp:at,type:'review_saved',summary:'Fixture reviewer and quotation checks completed.'}],tasks:[{id:'reviewer-0',role:'source reviewer',status:'completed',engine:'language model',question:'Fixture paper',parent_task_id:null,allowed_tools:[],input_artifact_ids:[]},{id:'quote-verifier',role:'quotation verifier',status:'completed',engine:'deterministic',question:'Verify exact quotations',parent_task_id:null,allowed_tools:[],input_artifact_ids:[]}],artifacts:[],findings:[{id:'finding-1',text:'Independent validation is required.',claim_type:'reported observation',reviewer_status:'unreviewed',evidence_refs:[source.origin_id+'#p1-c1'],variant_ids:[],limitations:['Scripted browser fixture.']}],budget:{model_requests:1,tool_calls:2,cost_status:'fixture'},reading:{reading:{summary:'Fixture reading summary.',limitations:['Fixture only.']},covered_chunk_ids:['p1-c1'],total_chunks:1},source_coverage:[{paper_id:paper.id,title:paper.filename,covered_chunk_ids:['p1-c1'],selected_chunks:1}],comparison_summary:{studies:1,reviewers:1,verified_quotations:1,method:'Fixture contract'}};
  const dir=join(tmpdir(),'variant-atlas-e2e-'+process.env.PW_FRONTEND_PORT,'research');mkdirSync(dir,{recursive:true});writeFileSync(join(dir,rid+'.json'),JSON.stringify(doc));
  const attached=await page.request.post('/api/portfolio/projects/'+p.id+'/attach-investigation',{data:{run_id:rid}});expect(attached.ok()).toBeTruthy();await route.fulfill({json:{run_id:rid}});
 });
 await page.getByRole('button',{name:'Start investigation',exact:true}).click();await expect(page).toHaveURL(/\/investigations\/research-/);await expect(page.getByRole('region',{name:'Investigation execution monitor'})).toContainText('quotation verifier');await expect(page.getByText('Independent validation is required.',{exact:true})).toBeVisible();
 await page.screenshot({path:artifacts+'/reviewer-result.png'});
 await page.getByRole('button',{name:'Bramha Assistant',exact:false}).click();await page.getByLabel('Question for Bramha Assistant').fill('What evidence is missing?');
 await page.route('**/api/hub/assistant',r=>r.fulfill({json:{id:'guide-fixture',question:'What evidence is missing?',answer:'The saved source calls for independent validation.',claims:[{text:'Validation is required.',citation_id:'fixture-citation',quote:'Independent validation is required.'}],citations:[{citation_id:'fixture-citation',title:source.title,url:'/library/'+source.id+'?project='+p.id}],limitations:['Fixture only.'],next_questions:[],retrieval:{method:'BM25 fixture',count:1},provider:{provider:'fixture',model:'scripted'}}}));
 await page.getByRole('button',{name:'Ask Bramha Assistant',exact:true}).click();await expect(page.getByRole('region',{name:'Bramha Assistant'})).toContainText('The saved source calls for independent validation.');await page.screenshot({path:artifacts+'/cited-guide.png'});expect(errors).toEqual([]);
});

test('molecular viewport survives view switches and wheel does not invent a selected residue',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));const p=await makeProject(page,'pten');
 await page.goto('/research/'+p.id+'/workspace');await expect(page.locator('.ra-mol-target')).toHaveAttribute('data-rendered','true',{timeout:45000});
 const before=await page.locator('.ra-molecular-focus-chip b').innerText();await page.locator('.ra-mol-target').hover();await page.mouse.wheel(0,-180);await page.waitForTimeout(250);expect(await page.locator('.ra-molecular-focus-chip b').innerText()).toBe(before);
 const legend=await page.locator('.ra-legend').boundingBox(),viewport=await page.locator('.ra-mol-viewport').boundingBox();expect(legend!.y).toBeGreaterThanOrEqual(viewport!.y+viewport!.height-1);
 await page.getByLabel('Find draggable substitution').fill('R172H');await page.getByRole('button',{name:'p.R172H',exact:true}).click();await page.getByRole('button',{name:'Build a 3D residue proposal',exact:true}).click();await expect(page.getByRole('heading',{name:'Design a structural comparison'})).toBeVisible();await expect(page.getByLabel('Experiment reference position')).toHaveValue('PTEN:p.R172H');
 await page.getByRole('button',{name:'Structure',exact:true}).click();await expect(page.locator('.ra-mol-target')).toHaveAttribute('data-rendered','true',{timeout:45000});
 await page.screenshot({path:artifacts+'/molecular-workspace.png',animations:'disabled'});expect(errors).toEqual([]);
});
