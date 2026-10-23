import {useEffect,useMemo,useState} from 'react';
import type {StructureViewerProps} from '../components/StructureViewer';
import StructureViewer from '../components/StructureViewer';
import type {Analysis} from '../types';
import {api} from '../lib/api';
import type {RunSnapshot} from './types';
import {terminal} from './types';
import {rebuildExecution} from './reducer';
import {useRunEvents} from './useRunEvents';
import InvestigationChamberCanvas from './InvestigationChamberCanvas';
import WorkerDetailDrawer from './WorkerDetailDrawer';
import ExecutionTimeline from './ExecutionTimeline';
import './chamber.css';
interface Props {initial:RunSnapshot;protein:StructureViewerProps;onFinish:(run:RunSnapshot)=>void;onOutput:(run:RunSnapshot)=>void}
export default function InvestigationWorkspace({initial,protein,onFinish,onOutput}:Props){
  const {run,events,connection}=useRunEvents(initial,onFinish);
  const [selected,setSelected]=useState('coordinator'),[tab,setTab]=useState<'workflow'|'protein'|'split'>('workflow');
  const [reduced,setReduced]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches),[motion,setMotion]=useState(true);
  const [replay,setReplay]=useState(false),[playing,setPlaying]=useState(false),[position,setPosition]=useState(0),[speed,setSpeed]=useState(1),[timeline,setTimeline]=useState(false);
  const [cancelling,setCancelling]=useState(false),[error,setError]=useState<string|null>(null);
  useEffect(()=>{const m=matchMedia('(prefers-reduced-motion: reduce)');const listener=()=>setReduced(m.matches);m.addEventListener('change',listener);return()=>m.removeEventListener('change',listener);},[]);
  useEffect(()=>{if(!replay||!playing)return;const timer=setInterval(()=>setPosition(p=>{if(p>=events.length){setPlaying(false);return p;}return p+1;}),650/speed);return()=>clearInterval(timer);},[replay,playing,speed,events.length]);
  const shown=replay?events.slice(0,position):events;
  const state=useMemo(()=>rebuildExecution(run,shown),[run,shown]);
  const live=run.execution_mode==='live';const done=terminal(run.status)||terminal(state.status);
  const partial=run.status==='needs_review'||state.status==='needs_review';
  const analysisArtifact=run.artifacts.find(a=>a.id==='artifact-filter-results');
  const runAnalysis=run.result?.analysis||(analysisArtifact?.data as unknown as Analysis)||protein.analysis;
  function focusVariant(id:string){protein.onSelect(id);setTab('protein');}
  async function cancel(){setCancelling(true);setError(null);try{await api.cancelRun(run.run_id);}catch(e){setError(e instanceof Error?e.message:'Cancellation request failed.');setCancelling(false);}}
  function startReplay(){setReplay(true);setPlaying(false);setPosition(0);}
  return <section className="investigation-chamber" aria-label="Investigation chamber" data-testid="investigation-chamber">
    <header className="investigation-context-header"><div><div className="execution-mode-labels"><span>Synthetic data</span><span className={live?'is-live':'is-simulated'}>{live?'Live execution':'Simulated workflow — synthetic data'}</span><span>{replay?'Recorded replay':done?'Saved provenance':'Live event stream'}</span></div><h2>{run.request.title}</h2><p className="chamber-question">{run.request.research_question}</p><div className="chamber-context-values"><span>Abundance ≥ {run.request.criteria.abundance_min.toFixed(2)}</span><span>Activity ≤ {run.request.criteria.activity_max.toFixed(2)}</span><span>{run.request.criteria.mapping} geometry</span><span>Capacity {run.request.candidate_budget}</span><span>{run.model||'No model'}</span><span>Dataset {run.dataset_version||'awaiting retrieval'}</span></div></div><div className="chamber-run-status"><span className={`execution-status ${state.status}`}>{state.status.replaceAll('_',' ')}</span><small>{connection}</small><span className="mono">{shown.length} recorded events</span></div></header>
    <div className="investigation-view-tabs"><div role="tablist" aria-label="Investigation view"><button role="tab" aria-selected={tab==='workflow'} onClick={()=>setTab('workflow')}>Workflow</button><button role="tab" aria-selected={tab==='protein'} onClick={()=>setTab('protein')}>Protein</button><button className="split-tab" role="tab" aria-selected={tab==='split'} onClick={()=>setTab('split')}>Split view</button></div><div className="run-controls"><button onClick={()=>setMotion(v=>!v)} disabled={reduced} aria-pressed={!motion||reduced}>{!motion||reduced?'Motion paused':'Pause visual motion'}</button>{done?<button onClick={()=>replay?(setReplay(false),setPlaying(false)):startReplay()}>{replay?'Return to saved view':'Replay recorded events'}</button>:<button className="cancel-run-button" onClick={cancel} disabled={cancelling||state.status==='cancellation_requested'}>{cancelling||state.status==='cancellation_requested'?'Cancellation requested':'Cancel run'}</button>}</div></div>
    {reduced&&<p className="chamber-motion-note">Reduced motion: static edges and immediate state changes. Backend execution continues.</p>}
    {replay&&<div className="replay-controls"><b>RECORDED REPLAY</b><button onClick={()=>setPlaying(v=>!v)} disabled={position>=events.length}>{playing?'Pause replay':'Play replay'}</button><button onClick={()=>{setPlaying(false);setPosition(0);}}>Restart replay</button><input aria-label="Recorded event position" type="range" min="0" max={events.length} value={position} onChange={e=>{setPlaying(false);setPosition(Number(e.target.value));}}/><span>{position} / {events.length}</span><select aria-label="Replay speed" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value=".5">0.5×</option><option value="1">1×</option><option value="2">2×</option></select><small>Playback does not execute tools or control a backend run.</small></div>}
    {error&&<p role="alert" className="error-note">{error}</p>}
    {(run.error||partial)&&<p className="chamber-run-warning" role="status">{run.error||run.result?.explanation_error||'Partial result: the explanation failed. The deterministic brief remains inspectable.'}</p>}
    <div className={`chamber-main-grid ${tab}`}><div className="chamber-viewports">{tab!=='protein'&&<InvestigationChamberCanvas run={run} state={state} selected={selected} onSelect={setSelected} onOutput={()=>onOutput(run)} motion={motion&&(!replay||playing)} reduced={reduced}/>}{tab!=='workflow'&&<div className="chamber-protein-view"><StructureViewer {...protein} analysis={runAnalysis}/><p>Protein context for this run · illustrative geometry · selected {protein.selected.id}</p></div>}</div>{tab!=='protein'&&<WorkerDetailDrawer run={run} state={state} selected={selected} onSelect={setSelected} onVariant={focusVariant}/>}</div>
    <div className="chamber-footer-strip"><span>Observed events only · no hidden reasoning</span><span>{run.storage==='atlas'?'MongoDB Atlas':'Local files'} · {run.provider} · single-process worker</span>{run.result&&state.artifact_ids.includes('artifact-brief')&&<button className="chamber-open-output" onClick={()=>onOutput(run)}>Open saved review brief ↗</button>}</div>
    {state.handoffs.length>0&&<details className="chamber-handoff-list"><summary>Inspect {state.handoffs.length} recorded handoffs</summary><div>{state.handoffs.map(e=><button key={e.event_id} onClick={()=>setSelected(e.event_id)}>{e.sender} → {e.recipient}<small>{e.output_refs.join(', ')||'Declared research context'}</small></button>)}</div></details>}
    <button className="execution-timeline-toggle" onClick={()=>setTimeline(x=>!x)} aria-expanded={timeline}>Accessible 2D execution timeline <span>{timeline?'−':'+'}</span></button>
    {/* Worker buttons stay available even when WebGL fails or the event log is collapsed. */}
    <div className={timeline?'':'timeline-log-collapsed'}><ExecutionTimeline run={run} state={state} onSelect={setSelected}/></div>
  </section>;
}
