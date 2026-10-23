import type {Investigation,Criteria} from '../types';
export type RunStatus='queued'|'running'|'cancellation_requested'|'completed'|'needs_review'|'failed'|'cancelled';
export type WorkerKind='deterministic_tool'|'llm_call'|'database'|'output';
export interface Worker {id:string;name:string;kind:WorkerKind;depends_on:string[];description:string}
export interface RunEvent {event_id:string;run_id:string;sequence:number;timestamp:string;type:string;worker_id:string;worker_kind:WorkerKind;task_id:string;parent_task_id:string;status:string;summary:string;input_refs:string[];output_refs:string[];metrics:Record<string,unknown>;sender:string|null;recipient:string|null;mode:string}
export interface Artifact {id:string;name:string;worker_id:string;summary:string;refs:string[];data:Record<string,unknown>}
export interface RunSnapshot {run_id:string;status:RunStatus;created_at:string;updated_at:string;request:{title:string;research_question:string;candidate_budget:number;criteria:Criteria;selected_ids:string[]|null;explanation_mode:string};workers:Worker[];events:RunEvent[];artifacts:Artifact[];dataset_version:string|null;data_mode:'synthetic';execution_mode:'live'|'simulated';storage:string;provider:string;model:string|null;result_id:string|null;result:Investigation|null;error:string|null}
export interface WorkerState {status:string;summary:string;started_at:string|null;ended_at:string|null;warnings:string[];input_refs:string[];output_refs:string[]}
export interface ExecutionState {run_id:string;status:RunStatus;events:RunEvent[];workers:Record<string,WorkerState>;handoffs:RunEvent[];artifact_ids:string[];sequence:number}
export const terminal=(s:string)=>['completed','needs_review','failed','cancelled'].includes(s);
export const kindLabel=(s:WorkerKind)=>({deterministic_tool:'Deterministic tool',llm_call:'LLM call',database:'Database',output:'Output'}[s]);
