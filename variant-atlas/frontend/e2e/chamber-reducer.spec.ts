import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {applyEvent,initialExecution,rebuildExecution,mergeEvents} from '../src/chamber/reducer';
import type {RunSnapshot} from '../src/chamber/types';
const run=JSON.parse(readFileSync(new URL('../../data/fixtures/chamber-run.json',import.meta.url),'utf8')) as RunSnapshot;
test('recorded events rebuild the graph and reconnect without duplicate work',()=>{
  const full=rebuildExecution(run);
  const midpoint=Math.floor(run.events.length/2);
  const reconnect=mergeEvents(run.events.slice(0,midpoint),[...run.events.slice(midpoint-3),run.events[0]]);
  const rebuilt=rebuildExecution(run,reconnect.reverse());
  expect(rebuilt).toEqual(full);
  expect(full.status).toBe('completed');
  expect(full.workers['structure-mapping'].warnings.length).toBe(1);
  expect(full.handoffs.every(e=>e.sender&&e.recipient&&e.output_refs.length)).toBe(true);
  expect(new Set(full.events.map(e=>e.event_id)).size).toBe(run.events.length);
  expect(full.artifact_ids).toContain('artifact-brief');
});
test('terminal outcomes are authoritative; replay has no future artifacts',()=>{
  const initial=initialExecution(run);
  expect(initial.artifact_ids).toEqual([]);
  expect(initial.workers.verification.status).toBe('queued');
  const beforeOutput=run.events.findIndex(e=>e.output_refs.includes('artifact-brief'));
  expect(rebuildExecution(run,run.events.slice(0,beforeOutput)).artifact_ids).not.toContain('artifact-brief');
  const full=rebuildExecution(run);
  expect(applyEvent(full,{...run.events[0],sequence:999,event_id:run.run_id+':999',type:'run.started',status:'running'})).toBe(full);
  expect(applyEvent(initial,{...run.events[0],run_id:'another-run'})).toBe(initial);
});
