import {useEffect,useRef,useState} from 'react';
import {api} from '../lib/api';
import {mergeEvents} from './reducer';
import {terminal} from './types';
import type {RunEvent,RunSnapshot} from './types';
export function useRunEvents(initial:RunSnapshot,onFinish:(run:RunSnapshot)=>void){
  const [run,setRun]=useState(initial),[events,setEvents]=useState(initial.events),[connection,setConnection]=useState('Connecting');
  const finishRef=useRef(onFinish);finishRef.current=onFinish;
  useEffect(()=>{
    let disposed=false;let source:EventSource|null=null;let refresh:ReturnType<typeof setTimeout>|undefined;
    if(terminal(initial.status)){setConnection(initial.execution_mode==='simulated'?'Simulated recording':'Saved provenance');finishRef.current(initial);return;}
    source=new EventSource(api.runEventsUrl(initial.run_id,initial.events.at(-1)?.sequence||0));
    source.onopen=()=>{if(!disposed)setConnection('Connected');};
    source.addEventListener('run-event',event=>{
      if(disposed)return;let value:RunEvent;try{value=JSON.parse((event as MessageEvent).data);}catch{setConnection('Invalid event received');return;}
      setEvents(old=>mergeEvents(old,[value]));
      if(value.type==='artifact.created'){clearTimeout(refresh);refresh=setTimeout(()=>api.run(initial.run_id).then(s=>{if(!disposed)setRun(s);}).catch(()=>{}),50);}
      if(value.type.startsWith('run.')&&terminal(value.status)){
        source?.close();setConnection('Saved provenance');
        api.run(initial.run_id).then(snapshot=>{if(!disposed){setRun(snapshot);setEvents(old=>mergeEvents(old,snapshot.events));finishRef.current(snapshot);}}).catch(()=>{if(!disposed)setConnection('Output snapshot unavailable — refresh to retry');});
      }
    });
    source.onerror=()=>{if(!disposed)setConnection('Reconnecting — saved events will resume');};
    return()=>{disposed=true;clearTimeout(refresh);source?.close();};
  },[initial.run_id]);
  return {run,events,connection};
}
