import {useEffect,useRef,useState} from 'react';
import {api} from './types';
interface Props {configured:boolean;context:Record<string,unknown>;onCommand:(utterance:string,context:Record<string,unknown>)=>void}
export default function Voice({configured,context,onCommand}:Props){
 const [active,setActive]=useState(false),[status,setStatus]=useState(''),[transcripts,setTranscripts]=useState<string[]>([]);const clean=useRef<()=>void>(()=>{});
 useEffect(()=>()=>clean.current(),[]);
 // A selection or layer change invalidates the pinned spoken context.
 const signature=JSON.stringify(context);useEffect(()=>{clean.current();setActive(false);},[signature]);
 async function start(){
  setStatus('Connecting configured Google Live model…');let ws:WebSocket|undefined;let media:MediaStream|undefined;let capture:AudioContext|undefined;let output:AudioContext|undefined;let processor:ScriptProcessorNode|undefined;
  const sources=new Set<AudioBufferSourceNode>();let next=0;
  const stop=()=>{processor?.disconnect();media?.getTracks().forEach(t=>t.stop());if(capture?.state!=='closed')void capture?.close();if(output?.state!=='closed')void output?.close();ws?.close();sources.forEach(s=>{try{s.stop();}catch{}});};clean.current=stop;
  try{
   const session=await api<{websocket_path:string;model:string}>('voice/session',{});
   media=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true}});
   capture=new AudioContext({sampleRate:16000});output=new AudioContext({sampleRate:24000});await output.resume();
   ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}${session.websocket_path}`);
   ws.onopen=()=>ws?.send(JSON.stringify(context));
   ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='ready'){
     const source=capture!.createMediaStreamSource(media!);processor=capture!.createScriptProcessor(2048,1,1);source.connect(processor);processor.connect(capture!.destination);
     processor.onaudioprocess=event=>{if(ws?.readyState!==WebSocket.OPEN)return;const input=event.inputBuffer.getChannelData(0);const bytes=new Uint8Array(input.length*2);const view=new DataView(bytes.buffer);for(let i=0;i<input.length;i++)view.setInt16(i*2,Math.max(-1,Math.min(1,input[i]))*32767,true);let raw='';for(const b of bytes)raw+=String.fromCharCode(b);ws.send(JSON.stringify({type:'audio',data:btoa(raw)}));};
     setActive(true);setStatus(`Live · ${session.model} · configured session; scientific review pending`);
    }else if(m.type==='transcript')setTranscripts(t=>[...t.slice(-30),`${m.role}: ${m.text}`]);
    else if(m.type==='command')onCommand(m.utterance,m.context);
    else if(m.type==='audio'){
     const bytes=Uint8Array.from(atob(m.data),(c:string)=>c.charCodeAt(0));const values=new DataView(bytes.buffer);const buffer=output!.createBuffer(1,bytes.length/2,24000);const channel=buffer.getChannelData(0);for(let i=0;i<channel.length;i++)channel[i]=values.getInt16(i*2,true)/32768;
     const source=output!.createBufferSource();source.buffer=buffer;source.connect(output!.destination);const at=Math.max(output!.currentTime,next);source.start(at);next=at+buffer.duration;sources.add(source);source.onended=()=>sources.delete(source);
    }else if(m.type==='interrupted'){sources.forEach(s=>{try{s.stop();}catch{}});sources.clear();next=0;}
    else if(m.type==='error'){setStatus(m.message);stop();setActive(false);}
   };
   ws.onerror=()=>{setStatus('Live connection failed. Use text commands.');stop();setActive(false);};ws.onclose=()=>{stop();setActive(false);};
  }catch(e){stop();setActive(false);setStatus((e as Error).message);}
 }
 return <div className="ra-live"><button disabled={!configured} onClick={()=>{if(active){clean.current();setActive(false);setStatus('Voice stopped.');}else void start();}}>{active?'Stop live microphone':'Start configured Live voice'}</button><p>{status||(!configured?'Google Live is unavailable. Text commands work below.':'Google Live configured; account verification pending. Starting shares microphone audio for up to 3 minutes.')}</p>{transcripts.length>0&&<details open><summary>Live transcripts</summary>{transcripts.map((t,i)=><p key={i}>{t}</p>)}</details>}</div>;
}
