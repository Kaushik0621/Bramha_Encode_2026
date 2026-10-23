import {Component,useEffect,useMemo,useRef,useState} from 'react';
import type {ComponentRef,ReactNode,RefObject} from 'react';
import {Canvas,useFrame,useThree} from '@react-three/fiber';
import {Edges,Line,OrbitControls} from '@react-three/drei';
import * as THREE from 'three';
import type {ExecutionState,RunSnapshot} from './types';
import {kindLabel,terminal} from './types';
const POS:Record<string,[number,number,number]>={coordinator:[0,3.3,-.5],'data-retrieval':[-4.8,1,.2],'assay-analysis':[-1.6,1,-.4],'structure-mapping':[1.6,1,.4],'evidence-review':[4.8,1,-.2],'brief-synthesis':[-2.5,-1.45,.5],verification:[2.5,-1.45,-.3],'dock-store':[-7.7,-1.2,-.3],'dock-provider':[7.7,-1.2,-.3],'output-tray':[0,-3.5,.7]};
const COLORS:Record<string,string>={queued:'#557183',running:'#8cdbeb',completed:'#75cebd',failed:'#da8c80',cancelled:'#8b929a',skipped:'#7d8f9e',needs_review:'#dfb273'};
const symbol=(status:string)=>({queued:'○',running:'◉',completed:'✓',failed:'!',cancelled:'■',skipped:'–',needs_review:'△'}[status]||'○');
class Boundary extends Component<{children:ReactNode;onFail:()=>void},{failed:boolean}>{state={failed:false};static getDerivedStateFromError(){return {failed:true};}componentDidCatch(){this.props.onFail();}render(){return this.state.failed?null:this.props.children;}}
function supportsWebGL(){try{return !!document.createElement('canvas').getContext('webgl2');}catch{return false;}}
interface Props {run:RunSnapshot;state:ExecutionState;selected:string;onSelect:(id:string)=>void;onOutput:()=>void;motion:boolean;reduced:boolean}
function Scene({run,state,selected,onSelect,motion,reduced,reset,labels}:{reset:number;labels:RefObject<Map<string,HTMLButtonElement>>}&Props){
  const controls=useRef<ComponentRef<typeof OrbitControls>>(null);const {camera}=useThree();
  const meshes=useRef(new Map<string,THREE.Mesh>());
  const packet=useRef<THREE.Mesh>(null);const handoff=state.handoffs.at(-1);const packetStart=useRef(0);
  useEffect(()=>{packetStart.current=performance.now();},[handoff?.sequence]);
  useEffect(()=>{if(reset){camera.position.set(0,4.8,23);controls.current?.target.set(0,0,0);controls.current?.update();}},[reset,camera]);
  useFrame(()=>{
    for(const [id,node] of labels.current){const p=new THREE.Vector3(...POS[id]).project(camera);node.style.left=`${(p.x+1)*50}%`;node.style.top=`${(-p.y+1)*50}%`;}
    for(const [id,mesh] of meshes.current){const material=mesh.material as THREE.MeshStandardMaterial;material.emissiveIntensity=state.workers[id]?.status==='running'&&motion&&!reduced?.28+.08*Math.sin(performance.now()/350):.12;}
    if(packet.current){const from=handoff?.sender&&POS[handoff.sender],to=handoff?.recipient&&POS[handoff.recipient];const t=(performance.now()-packetStart.current)/850;packet.current.visible=!!(from&&to&&t<1&&motion&&!reduced&&!terminal(state.status));if(from&&to)packet.current.position.lerpVectors(new THREE.Vector3(...from),new THREE.Vector3(...to),Math.min(t,1));}
  });
  const edges=useMemo(()=>run.workers.flatMap(w=>w.depends_on.map(d=>({from:d,to:w.id}))),[run.workers]);
  return <>
    <ambientLight intensity={1.1}/><directionalLight position={[0,12,8]} intensity={2}/><directionalLight position={[-10,0,0]} color="#6fe3e2" intensity={.8}/>
    <mesh position={[0,0,-1.8]}><boxGeometry args={[18.7,9.2,5.8]}/><meshBasicMaterial color="#2c6876" transparent opacity={.035} depthWrite={false} side={THREE.BackSide}/><Edges color="#416f81" transparent opacity={.4}/></mesh>
    <mesh position={[0,-4.65,-.4]} rotation={[-Math.PI/2,0,0]}><planeGeometry args={[18.7,7.8]}/><meshStandardMaterial color="#12343e" transparent opacity={.3}/></mesh>
    <gridHelper args={[18,18,'#335965','#203e4b']} position={[0,-4.64,-.4]}/>
    {edges.map(e=><Line key={e.from+e.to} points={[POS[e.from],POS[e.to]]} color={selected===e.from||selected===e.to?'#86c5c3':'#355461'} lineWidth={selected===e.from||selected===e.to?1.3:.7} onClick={event=>{const handoff=state.handoffs.filter(h=>h.sender===e.from&&h.recipient===e.to).at(-1);if(handoff){event.stopPropagation();onSelect(handoff.event_id);}}} transparent opacity={selected===e.from||selected===e.to?.7:.38}/>)}
    <Line points={[POS.coordinator,POS['data-retrieval']]} color="#456f7c" lineWidth={.7} transparent opacity={.4}/>
    <Line points={[POS.verification,POS['output-tray']]} color="#486963" lineWidth={1}/>
    {Object.entries(POS).map(([id,position])=>{const ws=state.workers[id];const status=ws?.warnings.length&&ws.status==='completed'?'needs_review':ws?.status||'queued';const color=COLORS[status]||COLORS.queued;return <group key={id} position={position}><mesh ref={m=>{if(m)meshes.current.set(id,m);else meshes.current.delete(id);}} onClick={e=>{e.stopPropagation();onSelect(id);}}><boxGeometry args={[id.startsWith('dock')?1.55:id==='output-tray'?4.2:2.35,.65,.9]}/><meshStandardMaterial color={id==='output-tray'?'#194942':'#15333f'} emissive={color} emissiveIntensity={.12} metalness={.3} roughness={.45} transparent opacity={.85}/><Edges color={selected===id?'#c6f7ee':color}/></mesh><mesh position={[0,-.42,0]}><boxGeometry args={[id==='output-tray'?4.7:2.8,.06,1.25]}/><meshBasicMaterial color={color} transparent opacity={selected===id?.22:.09}/></mesh></group>;})}
    <mesh ref={packet} visible={false}><sphereGeometry args={[.095,12,8]}/><meshBasicMaterial color="#adeee1"/></mesh>
    <OrbitControls ref={controls} makeDefault enablePan={false} minDistance={18} maxDistance={30} minAzimuthAngle={-.2} maxAzimuthAngle={.2} minPolarAngle={1.2} maxPolarAngle={1.56} enableDamping={!reduced}/>
  </>;
}
export default function InvestigationChamberCanvas(props:Props){
  const [available,setAvailable]=useState(supportsWebGL);const [reset,setReset]=useState(0);const labels=useRef(new Map<string,HTMLButtonElement>());
  const artifact=props.run.artifacts.find(a=>a.id==='artifact-data'&&props.state.artifact_ids.includes(a.id));const count=artifact?.data.variants;
  return <div className="chamber-canvas-wrap"><div className="chamber-canvas-heading"><span className="eyebrow">INVESTIGATION / EXECUTION CHAMBER</span><span className="chamber-depth-label">BOUNDED WORKFLOW · ONE OPTIONAL MODEL CALL</span></div>
    {available?<Boundary onFail={()=>setAvailable(false)}><Canvas camera={{position:[0,4.8,23],fov:41,near:.1,far:100}} dpr={[1,1.5]} gl={{antialias:true}} onCreated={({gl})=>gl.domElement.addEventListener('webglcontextlost',()=>setAvailable(false),{once:true})}><Scene {...props} reset={reset} labels={labels}/></Canvas></Boundary>:<div className="chamber-no-webgl" role="status"><span>◇</span><b>3D unavailable — execution remains inspectable.</b><p>Use the worker buttons and event timeline below. The backend continues independently of this viewer.</p></div>}
    {available&&<div className="chamber-html-labels">{props.run.workers.map(w=>{const task=props.state.workers[w.id];const warning=task.warnings.length&&task.status==='completed';return <button key={w.id} ref={el=>{if(el)labels.current.set(w.id,el);else labels.current.delete(w.id);}} className={`chamber-node-label ${task.status} ${warning?'has-warning':''} ${props.selected===w.id?'active':''}`} aria-label={`Inspect ${w.name}`} onClick={()=>props.onSelect(w.id)}><small>{kindLabel(w.kind)}</small><strong><span>{symbol(warning?'needs_review':task.status)}</span>{w.name}</strong><em>{warning?'Completed · needs review':task.status.replaceAll('_',' ')}</em></button>;})}
      <button className="chamber-dock-label" ref={el=>{if(el)labels.current.set('dock-store',el);}} onClick={()=>props.onSelect('dock-store')}><small>DATA STORE</small><strong>{props.run.storage==='atlas'?'MongoDB Atlas':'Local files'}</strong><em>{typeof count==='number'?`${count} variants retrieved`:'Awaiting retrieval'}</em></button>
      <button className="chamber-dock-label" ref={el=>{if(el)labels.current.set('dock-provider',el);}} onClick={()=>props.onSelect('dock-provider')}><small>MODEL PROVIDER</small><strong>{props.run.provider==='openrouter'?'OpenRouter':props.run.provider==='mock'?'Fixture rules':'Disabled'}</strong><em>{props.run.provider==='openrouter'?'Not a worker':'No model call'}</em></button>
      <button className={`chamber-output-label ${props.state.artifact_ids.includes('artifact-brief')?'ready':''}`} ref={el=>{if(el)labels.current.set('output-tray',el);}} disabled={!props.run.result||!props.state.artifact_ids.includes('artifact-brief')} onClick={props.onOutput}><small>OUTPUT / REVIEWABLE RESULT</small><strong>{props.run.result&&props.state.artifact_ids.includes('artifact-brief')?'Open saved review brief ↗':'Waiting for verified output'}</strong></button>
    </div>}
    <div className="chamber-canvas-controls"><button onClick={()=>setReset(x=>x+1)} disabled={!available}>↺ Reset chamber</button><span>Bounded orbit · scroll to zoom</span></div>
  </div>;
}
