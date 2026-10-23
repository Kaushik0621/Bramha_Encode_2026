import type {ExecutionState,RunEvent,RunSnapshot,RunStatus,WorkerState} from './types';
const emptyWorker=():WorkerState=>({status:'queued',summary:'Waiting for declared inputs.',started_at:null,ended_at:null,warnings:[],input_refs:[],output_refs:[]});
export function initialExecution(run:RunSnapshot):ExecutionState{return {run_id:run.run_id,status:'queued',events:[],workers:Object.fromEntries(run.workers.map(w=>[w.id,emptyWorker()])),handoffs:[],artifact_ids:[],sequence:0};}
export function applyEvent(state:ExecutionState,event:RunEvent):ExecutionState{
  if(event.run_id!==state.run_id||state.events.some(e=>e.sequence===event.sequence||e.event_id===event.event_id)||event.sequence<=state.sequence)return state;
  if(['completed','failed','cancelled','needs_review'].includes(state.status))return state;
  const next={...state,events:[...state.events,event],workers:{...state.workers},sequence:event.sequence};
  if(event.type.startsWith('run.'))next.status=event.status as RunStatus;
  if(event.type==='handoff')next.handoffs=[...state.handoffs,event];
  if(event.type==='artifact.created')next.artifact_ids=[...new Set([...state.artifact_ids,...event.output_refs])];
  const old=next.workers[event.worker_id];
  if(old){
    const worker={...old,input_refs:[...new Set([...old.input_refs,...event.input_refs])],output_refs:[...new Set([...old.output_refs,...event.output_refs])]};
    if(event.type==='warning')worker.warnings=[...old.warnings,event.summary];
    if(event.type.startsWith('task.')||event.type.startsWith('tool.')){
      worker.status=event.status;worker.summary=event.summary;
      if(event.status==='running')worker.started_at=worker.started_at||event.timestamp;
      if(['completed','failed','cancelled','skipped'].includes(event.status))worker.ended_at=event.timestamp;
    }
    next.workers[event.worker_id]=worker;
  }
  return next;
}
export function rebuildExecution(run:RunSnapshot,events:RunEvent[]=run.events):ExecutionState{return [...events].sort((a,b)=>a.sequence-b.sequence).reduce(applyEvent,initialExecution(run));}
export function mergeEvents(previous:RunEvent[],incoming:RunEvent[]){return [...new Map([...previous,...incoming].map(e=>[e.event_id,e])).values()].sort((a,b)=>a.sequence-b.sequence);}
