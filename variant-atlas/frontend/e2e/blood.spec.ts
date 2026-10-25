import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
test('blood comparison interprets both factors, separates them, and never fabricates provider success',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('/developer/blood');
 await page.getByRole('button',{name:'Interpret comparison',exact:true}).click();const interpretation=page.getByRole('region',{name:'Interpreted blood comparison'});await expect(interpretation).toContainText('Two factors differ: ABO and RhD');
 await expect(page.getByRole('region',{name:'Synchronized illustrative cell environments'}).locator('canvas')).toHaveCount(2);
 const canvases=page.getByRole('region',{name:'Synchronized illustrative cell environments'}).locator('canvas');await expect(canvases.first()).toHaveAttribute('data-camera-position',/.+/);const initial=await canvases.first().getAttribute('data-camera-position');await canvases.first().scrollIntoViewIfNeeded();const box=await canvases.first().boundingBox();await page.mouse.move(box!.x+box!.width/2,box!.y+box!.height/2);await page.mouse.down();await page.mouse.move(box!.x+box!.width/2+70,box!.y+box!.height/2+25,{steps:8});await page.mouse.up();await expect.poll(()=>canvases.first().getAttribute('data-camera-position')).not.toBe(initial);await expect.poll(async()=>await canvases.first().getAttribute('data-camera-position')===await canvases.nth(1).getAttribute('data-camera-position')).toBe(true);
 await expect(page.getByText('Evidence-informed schematic — not a validated physical simulation.',{exact:false}).first()).toBeVisible();
 await page.getByRole('button',{name:'Start evidence investigation'}).click();await expect(page.getByRole('alert')).toContainText('No fabricated fallback');await expect(page.getByText('No verified final comparison yet.',{exact:false})).toHaveCount(0);
 await interpretation.getByText('Separate the factors',{exact:true}).click();await interpretation.getByRole('button',{name:'Compare RhD with ABO held constant'}).click();await page.getByRole('button',{name:'Interpret comparison',exact:true}).click();await expect(interpretation).toContainText('Both scenarios share ABO');await expect(interpretation).toContainText('does not establish a RhD-specific malaria difference');
 await page.getByRole('button',{name:'Molecular mechanism',exact:true}).click();await expect(page.getByText('No rosetting schematic is shown until', {exact:false})).toBeVisible();
 await page.getByLabel('Blood disease context',{exact:true}).fill('dengue');await page.getByRole('button',{name:'Interpret comparison',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Unsupported scope');expect(errors).toEqual([]);
});
test('same-group blood view and mobile sources retain limits and link back to PTEN',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/developer/blood');await page.getByLabel('Blood research question',{exact:true}).fill('Compare O positive and O positive in severe falciparum malaria.');await page.getByRole('button',{name:'Interpret comparison',exact:true}).click();await expect(page.getByRole('region',{name:'Interpreted blood comparison'})).toContainText('Same reported blood group');
 await page.getByRole('button',{name:'Research evidence',exact:true}).click();await expect(page.getByText('Study statistic:',{exact:false})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
 await page.screenshot({path:'../artifacts/blood-mobile.png',fullPage:true});await page.getByRole('link',{name:'PTEN workspace',exact:false}).click();await expect(page.getByText('PTEN · molecular workspace',{exact:true})).toBeVisible();
});
test('recorded comparative chamber inspects actual source handoffs and replays without future output',async({page})=>{
 const doc=JSON.parse(readFileSync(new URL('./fixtures/blood-scripted-run.json',import.meta.url),'utf8'));
 await page.route('**/api/blood/investigations',route=>route.fulfill({json:[doc]}));await page.goto('/developer/blood');await page.locator('.bg-history button').first().click();await expect(page.locator('.ra-tasks button')).toHaveCount(7);
 await page.locator('.ra-tasks button').filter({hasText:'scenario_a'}).click();await page.locator('.ra-task-detail summary').filter({hasText:'Blood worker report'}).click();await expect(page.locator('.ra-task-detail')).toContainText('population and assay applicability limits');
 await page.getByLabel('Replay scientific chamber').press('Home');await expect(page.locator('.ra-tasks button')).toHaveCount(1);await page.getByRole('button',{name:'Return to live state',exact:true}).click();await expect(page.locator('.ra-tasks button')).toHaveCount(7);
 await expect(page.getByRole('heading',{name:'Presenter summary',exact:true})).toBeVisible();await page.screenshot({path:'../artifacts/blood-comparison-workbench.png',fullPage:true});
});
