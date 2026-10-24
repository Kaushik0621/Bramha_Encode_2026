import {test,expect} from '@playwright/test';
test('structure-first workbench edits, persists and restores the reference scene',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/developer/pten');
 await expect(page.getByText('PTEN · molecular workspace',{exact:true})).toBeVisible();await expect(page.locator('.ra-intro')).toBeHidden();
 await expect(page.locator('.ra-mol-target')).toHaveAttribute('data-rendered','true',{timeout:45000});
 await page.getByLabel('Add p.C124S',{exact:true}).click();await expect(page.locator('.ba-comparison-strip')).toContainText('p.C124S');
 await page.locator('#brain-command').fill('add G129E');await page.getByRole('button',{name:'Run instruction',exact:true}).click();await expect(page.locator('.ba-comparison-strip')).toContainText('p.G129E');
 await page.locator('.ba-comparison-strip>span').filter({hasText:'p.C124S'}).dragTo(page.locator('.ba-trash'));await expect(page.locator('.ba-comparison-strip>span').filter({hasText:'p.C124S'})).toHaveCount(0);
 await page.getByRole('button',{name:'Hide reference',exact:true}).click();await expect(page.getByRole('heading',{name:'Reference removed from scene'})).toBeVisible();
 await expect(page.locator('.ba-product-tools').getByText('All observations saved',{exact:false})).toBeVisible();await page.reload();await expect(page.getByRole('heading',{name:'Reference removed from scene'})).toBeVisible();
 await page.getByRole('button',{name:'Restore reference',exact:true}).first().click();await page.getByRole('button',{name:'Change history',exact:true}).click();await expect(page.locator('.ba-history-panel')).toBeVisible();
 await page.screenshot({path:'../artifacts/bramha-structure-workbench.png',fullPage:true});expect(errors).toEqual([]);
});
test('original-language paper upload is searchable and survives reload',async({page})=>{
 await page.goto('/developer/pten');await page.getByRole('button',{name:'Paper library',exact:true}).click();
 await page.getByLabel('Upload research paper').setInputFiles({name:'étude-française.txt',mimeType:'text/plain',buffer:Buffer.from('Étude de PTEN : les résultats sont préliminaires. 蛋白质研究。')});
 await expect(page.getByRole('heading',{name:'étude-française.txt',exact:true})).toBeVisible();await page.getByText('Page 1 · p1-c1',{exact:true}).click();await expect(page.getByText('Étude de PTEN : les résultats sont préliminaires. 蛋白质研究。',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Link paper to investigation',exact:true}).click();await expect.poll(async()=>{const sid=await page.evaluate(()=>localStorage.getItem('bramha-atlas-current-exploration'));const r=await page.request.get('/api/research/explorations/'+sid);return (await r.json()).state.paper_ids.length;}).toBe(1);await page.reload();await page.getByRole('button',{name:'Paper library',exact:true}).click();await page.getByRole('button',{name:/étude-française.txt · extracted/}).click();await expect(page.getByRole('heading',{name:'étude-française.txt',exact:true})).toBeVisible();
});
test('mobile workbench fits without horizontal page overflow',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/developer/pten');await expect(page.getByText('PTEN · molecular workspace',{exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);await expect(page.locator('.ra-mol-target')).toHaveAttribute('data-rendered','true',{timeout:45000});await page.screenshot({path:'../artifacts/bramha-workbench-mobile.png',fullPage:true});
});
