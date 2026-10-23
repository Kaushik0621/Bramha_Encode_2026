import {test,expect} from '@playwright/test';

test('live start → inspect tool → open output → reconnect saved chamber',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/');await expect(page.getByText('5 included',{exact:true})).toBeVisible();
  await page.getByLabel('Explanation',{exact:true}).selectOption('fixture');
  await page.getByLabel('Investigation title',{exact:true}).fill('Inspectable chamber run');
  await page.getByRole('button',{name:'Start investigation · 5 variants'}).click();
  const chamber=page.getByRole('region',{name:'Investigation chamber',exact:true});await expect(chamber).toBeVisible();
  await expect(chamber.getByText('Live execution',{exact:true})).toBeVisible();
  await chamber.getByRole('button',{name:'Inspect Assay analysis',exact:true}).click();
  const drawer=chamber.getByRole('complementary',{name:'Execution details'});
  await expect(drawer.getByRole('heading',{name:'Assay analysis',exact:true})).toBeVisible();
  await expect(drawer).toContainText('5 variants meet the filters');
  await drawer.getByRole('button',{name:/Assay filter results/}).click();
  await expect(drawer).toContainText('demo-v08');
  await chamber.getByRole('button',{name:'Inspect Structure mapping',exact:true}).click();
  await expect(drawer).toContainText('3 selected candidates mapped; 2 lack coordinates');
  await expect(drawer).toContainText('Unmapped candidates remain in the shortlist');
  await chamber.getByRole('button',{name:'Open saved review brief',exact:false}).last().click();
  await expect(page.getByTestId('investigation-result')).toContainText('Inspectable chamber run');
  await page.reload();
  await expect(page.getByRole('region',{name:'Investigation chamber',exact:true})).toContainText('Inspectable chamber run');
  await expect(page.getByRole('button',{name:'Inspect Assay analysis',exact:true})).toHaveCount(1);
  await chamber.scrollIntoViewIfNeeded();await page.screenshot({path:'../artifacts/investigation-chamber-live.png',fullPage:true});
  expect(errors).toEqual([]);
});

test('simulated provenance → inspect handoff → replay → linked protein selection',async({page})=>{
  await page.goto('/');await page.getByRole('button',{name:'Preview simulated chamber (no model call)'}).click();
  const chamber=page.getByRole('region',{name:'Investigation chamber',exact:true});
  await expect(chamber.getByText('Simulated workflow — synthetic data',{exact:true})).toBeVisible();
  await chamber.getByRole('button',{name:'Inspect Assay analysis',exact:true}).click();
  await chamber.getByRole('complementary',{name:'Execution details'}).getByRole('button',{name:/Assay filter results/}).click();
  await chamber.getByRole('complementary',{name:'Execution details'}).getByRole('button',{name:'demo-v05 ↗',exact:true}).click();
  await expect(chamber.getByRole('tab',{name:'Protein',exact:true})).toHaveAttribute('aria-selected','true');
  await expect(chamber.getByText(/Protein context for this run.*demo-v05/)).toBeVisible();
  await chamber.getByRole('tab',{name:'Workflow',exact:true}).click();
  await chamber.getByRole('button',{name:'Replay recorded events'}).click();
  await expect(chamber.getByText('RECORDED REPLAY',{exact:true})).toBeVisible();
  await expect(chamber.getByRole('button',{name:'Open saved review brief',exact:false})).toHaveCount(0);
  await chamber.getByRole('slider',{name:'Recorded event position'}).focus();await page.keyboard.press('End');
  await expect(chamber.getByRole('button',{name:'Open saved review brief',exact:false}).last()).toBeVisible();
  await chamber.getByRole('button',{name:'Accessible 2D execution timeline'}).click();
  await expect(chamber.locator('.execution-timeline li')).toHaveCount(41);
  await chamber.getByRole('button',{name:'Return to saved view'}).click();
  await chamber.getByRole('button',{name:'Inspect Brief synthesis',exact:true}).click();
  await expect(chamber.getByRole('complementary',{name:'Execution details'})).toContainText('Deterministic tool');
  await chamber.screenshot({path:'../artifacts/investigation-chamber.png'});
});

test('reduced-motion chamber and WebGL fallback keep worker inspection functional',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.emulateMedia({reducedMotion:'reduce'});
  await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(this:HTMLCanvasElement,type:string,...args:unknown[]){if(type.startsWith('webgl'))return null;return (original as Function).apply(this,[type,...args]);} as typeof original;});
  await page.goto('/');await page.getByRole('button',{name:'Preview simulated chamber (no model call)'}).click();
  const chamber=page.getByRole('region',{name:'Investigation chamber',exact:true});
  await expect(chamber.getByText('3D unavailable — execution remains inspectable.',{exact:true})).toBeVisible();
  await expect(chamber.getByRole('button',{name:'Motion paused'})).toBeDisabled();
  await chamber.getByRole('button',{name:'Inspect Assay analysis in timeline'}).click();
  await expect(chamber.getByRole('complementary',{name:'Execution details'})).toContainText('5 variants meet the filters');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)).toBe(false);
});
