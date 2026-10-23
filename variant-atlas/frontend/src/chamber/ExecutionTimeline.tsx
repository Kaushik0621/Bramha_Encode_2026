import type {ExecutionState,RunSnapshot} from './types';
import {kindLabel} from './types';
export default function ExecutionTimeline({run,state,onSelect}:{run:RunSnapshot;state:ExecutionState;onSelect:(id:string)=>void}){
  return <div className="execution-timeline"><div className="execution-worker-buttons">{run.workers.map(w=>{const t=state.workers[w.id];return <button key={w.id} className={t.status} onClick={()=>onSelect(w.id)} aria-label={`Inspect ${w.name} in timeline`}><span>{w.name}</span><small>{kindLabel(w.kind)} · {t.status}</small></button>;})}</div><ol>{state.events.map(e=><li key={e.event_id} className={e.status}><button onClick={()=>onSelect(e.type==='handoff'?e.event_id:e.worker_id)}><span className="event-sequence">{String(e.sequence).padStart(2,'0')}</span><time>{new Date(e.timestamp).toLocaleTimeString()}</time><span><b>{e.type.replaceAll('.',' / ')}</b>{e.summary}</span><i>{e.status.replaceAll('_',' ')}</i></button></li>)}</ol></div>;
}
