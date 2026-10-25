import {test,expect} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {randomUUID} from 'node:crypto';

test('investigation displays actual fallback provider, original request and failed attempt',async({page})=>{
 const sources=await(await page.request.get('/api/portfolio/sources')).json();const project=await(await page.request.post('/api/portfolio/projects',{data:{title:'Fallback provenance inspection',objective:'Compare reported ABO and RhD evidence independently.',method:'blood',source_ids:sources.filter((s:any)=>s.method==='blood').map((s:any)=>s.id)}})).json();
 const run=JSON.parse(readFileSync(new URL('./fixtures/blood-scripted-run.json',import.meta.url),'utf8'));run.run_id='research-'+randomUUID().replaceAll('-','');run.request.project_id=project.id;run.requested_provider='google';run.requested_model='gemini-4-argon';run.provider='openrouter';run.model='fixture-fallback';run.budget.model_requests=2;run.budget.usage=[{provider:'google',model:'gemini-4-argon',status:'failed_attempt',failure_type:'TimeoutError',cost_usd:null},{provider:'openrouter',model:'fixture-fallback',cost_usd:.001,fallback:{from_provider:'google',from_model:'gemini-4-argon',to_provider:'openrouter',to_model:'fixture-fallback',failure_type:'TimeoutError'}}];
 writeFileSync(join(tmpdir(),'variant-atlas-e2e-'+(process.env.PW_FRONTEND_PORT||'8500'),'research',run.run_id+'.json'),JSON.stringify(run));await page.request.post('/api/portfolio/projects/'+project.id+'/attach-investigation',{data:{run_id:run.run_id}});
 await page.goto('/research/'+project.id+'/investigations/'+run.run_id+'?tab=evidence');await page.getByText('Execution details & export',{exact:true}).click();await expect(page.getByText('Latest provider: openrouter / fixture-fallback.',{exact:false})).toBeVisible();await expect(page.getByText('Initially requested: google / gemini-4-argon.',{exact:true})).toBeVisible();await expect(page.getByText('Failed attempt (TimeoutError)',{exact:false})).toBeVisible();await expect(page.getByText('OpenRouter fallback after TimeoutError',{exact:false})).toBeVisible();
});
