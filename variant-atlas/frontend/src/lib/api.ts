import type {RunSnapshot} from '../chamber/types';
import type { Workspace, Health, Criteria, Analysis, Neighbors, Investigation, InvestigationSummary } from '../types';
const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
export async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const res=await fetch(`${BASE}/api${path}`,{...init,headers:{'Content-Type':'application/json',...init?.headers}});
  if(!res.ok){let message=`Request failed (${res.status})`;try{const data=await res.json();message=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail);}catch{/* Keep HTTP status. */}throw new Error(message);}
  return res.json();
}
export const api={
  workspace:()=>request<Workspace>('/workspace'),
  health:()=>request<Health>('/health'),
  analyze:(criteria:Criteria,signal?:AbortSignal)=>request<Analysis>('/analyze',{method:'POST',body:JSON.stringify(criteria),signal}),
  neighbors:(id:string,radius:number,signal?:AbortSignal)=>request<Neighbors>(`/variants/${encodeURIComponent(id)}/neighbors?radius=${radius}`,{signal}),
  investigations:()=>request<InvestigationSummary[]>('/investigations'),
  investigation:(id:string)=>request<Investigation>(`/investigations/${encodeURIComponent(id)}`),
  investigate:(title:string,criteria:Criteria,selected_ids:string[],explanation_mode:string,research_question:string,candidate_budget:number)=>request<Investigation>('/investigations',{method:'POST',body:JSON.stringify({title,criteria,selected_ids,explanation_mode,research_question,candidate_budget})}),
  startRun:(title:string,criteria:Criteria,selected_ids:string[],explanation_mode:string,research_question:string,candidate_budget:number)=>request<RunSnapshot>('/investigations?execution=live',{method:'POST',body:JSON.stringify({title,criteria,selected_ids,explanation_mode,research_question,candidate_budget})}),
  run:(id:string)=>request<RunSnapshot>(`/investigations/${encodeURIComponent(id)}`),
  cancelRun:(id:string)=>request<RunSnapshot>(`/investigations/${encodeURIComponent(id)}/cancel`,{method:'POST'}),
  chamberFixture:()=>request<RunSnapshot>('/chamber/fixture'),
  fixtureExportUrl:()=>`${BASE}/api/chamber/fixture/export`,
  runEventsUrl:(id:string,after:number)=>`${BASE}/api/investigations/${encodeURIComponent(id)}/events?after=${after}`,
  exportUrl:(id:string)=>`${BASE}/api/investigations/${encodeURIComponent(id)}/export`
};
export const score=(x:number|null|undefined)=>x==null?'—':x.toFixed(2);
export const mappingLabel=(x:string)=>({mapped:'Mapped',missing_coordinates:'Missing coordinates',outside_structure_coverage:'Outside coverage'}[x]||x);
