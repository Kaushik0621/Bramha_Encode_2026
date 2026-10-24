import {createContext,useCallback,useContext,useEffect,useRef,useState} from 'react';
import type {ReactNode} from 'react';
import {api} from '../research/types';
export interface Source {id:string;origin_id:string;aliases?:string[];family:string;title:string;type:string;version:string;method:'pten'|'blood'|null;preparation:string;scientific_eligibility:string;origin:string;url:string|null;added_at:string|null;licence:string;coverage:string;details:Record<string,unknown>;projects:{id:string;title:string}[];citing_investigations:string[];cited_version?:string;versions?:Source[]}
export interface Project {id:string;title:string;description:string;objective:string;method:'pten'|'blood';context:string;revision:number;readiness:string;created_at:string;updated_at:string;sources:Record<string,{version:string;included:boolean;source:Source;current_version:string;version_changed:boolean}>;missing_required_source_ids:string[];method_info:{title:string;scope:string;context:string;available?:boolean};exploration_state:Record<string,unknown>;journey_id:string|null;journey_ids?:string[];run_ids:string[];activity:{at:string;kind:string;text:string}[]}
export interface RunSummary {id:string;question:string;method:'pten'|'blood';project_id:string|null;project_title:string;status:string;created_at:string;provider:string;model:string;has_result:boolean}
export interface Note {id:string;project_id:string;at:string;text:string;kind:string;authorship:string;run_id:string|null;source_id:string|null}
export interface Bootstrap {methods:Record<'pten'|'blood',{title:string;scope:string;context:string;available?:boolean}>;projects:Project[];sources:Source[];investigations:RunSummary[];notes:Note[];search_method:string}
interface Value {data:Bootstrap|null;error:string;reload:()=>Promise<void>}
const Context=createContext<Value>({data:null,error:'',reload:async()=>{}});
export function PortfolioProvider({children}:{children:ReactNode}){const [data,setData]=useState<Bootstrap|null>(null),[error,setError]=useState('');const token=useRef(0);const reload=useCallback(async()=>{const id=++token.current;try{const d=await api<Bootstrap>('portfolio/bootstrap');if(id===token.current){setData(d);setError('');}}catch(e){if(id===token.current)setError((e as Error).message);}},[]);useEffect(()=>{void reload();},[reload]);return <Context.Provider value={{data,error,reload}}>{children}</Context.Provider>;}
export const usePortfolio=()=>useContext(Context);
export const terminal=(status:string)=>['completed_with_limitations','abstained','failed','cancelled','interrupted'].includes(status);
export const statusLabel=(status:string)=>status.replaceAll('_',' ');
export const date=(value:string|null)=>value?new Date(value).toLocaleString():'Not recorded';
export async function uploadSource(file:File){if(file.size>8_000_000)throw Error('Maximum supported file size is 8 MB.');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));return api<Source>('portfolio/sources/import',{filename:file.name,content_base64:btoa(binary)});}
