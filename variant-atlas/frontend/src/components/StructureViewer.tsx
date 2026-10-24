import { Component, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import type { ComponentRef, ReactNode, RefObject } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { Analysis, Neighbors, Variant, Workspace } from '../types';

export interface StructureViewerProps {workspace:Workspace;analysis:Analysis|null;selected:Variant;onSelect:(id:string)=>void;layer:'activity'|'abundance';neighbors:Neighbors|null;inspectNeighbors:boolean;onInspect?:()=>void}
// Adapter boundary: replace SyntheticScene with a Mol* implementation after audited mmCIF mapping.
const color=(value:number|null)=>value===null?'#778391':new THREE.Color('#efa96a').lerp(new THREE.Color('#51cecf'),value).getStyle();
function hasWebGL(){try{const c=document.createElement('canvas');return !!(c.getContext('webgl2')||c.getContext('webgl'));}catch{return false;}}
function useReducedMotion(){const [value,set]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);useEffect(()=>{const m=matchMedia('(prefers-reduced-motion: reduce)');const fn=()=>set(m.matches);m.addEventListener('change',fn);return()=>m.removeEventListener('change',fn);},[]);return value;}
class ViewerBoundary extends Component<{children:ReactNode},{failed:boolean}>{
  state={failed:false};static getDerivedStateFromError(){return {failed:true};}render(){return this.state.failed?<div className="viewer-fallback" role="status"><b>Structure viewer unavailable</b><p>WebGL could not start. Use the linked table and evidence panel to continue.</p></div>:this.props.children;}
}
function SyntheticScene({workspace,analysis,selected,onSelect,layer,neighbors,inspectNeighbors,rotation,stopRotation,reset,reduced,hover,onHover,labelRef}:{rotation:boolean;stopRotation:()=>void;reset:number;reduced:boolean;hover:string|null;onHover:(id:string|null)=>void;labelRef:RefObject<HTMLDivElement|null>}&StructureViewerProps){
  const mountedSelection=useRef(false);
  const controls=useRef<ComponentRef<typeof OrbitControls>>(null);
  const {camera,gl}=useThree();
  const target=useRef(new THREE.Vector3());const destination=useRef(new THREE.Vector3(45,24,65));const animating=useRef(false);
  const points=useMemo(()=>new Map(workspace.structure.points.map(p=>[p.position,new THREE.Vector3(p.x,p.y,p.z)])),[workspace]);
  const tubes=useMemo(()=>{
    // Do not silently bridge the deliberately unresolved position.
    const segments:THREE.Vector3[][]=[[],[]];for(const p of workspace.structure.points)segments[p.position<95?0:1].push(new THREE.Vector3(p.x,p.y,p.z));
    return segments.map(s=>new THREE.TubeGeometry(new THREE.CatmullRomCurve3(s),250,.23,10,false));
  },[workspace]);
  useEffect(()=>()=>{tubes.forEach(t=>t.dispose());},[tubes]);
  useEffect(()=>{if(!mountedSelection.current){mountedSelection.current=true;return;}const p=points.get(selected.position);if(!p)return;target.current.copy(p);destination.current.copy(p).add(new THREE.Vector3(27,16,37));animating.current=true;},[selected.id,points]);
  useEffect(()=>{if(!reset)return;target.current.set(0,0,0);destination.current.set(45,24,65);animating.current=true;},[reset]);
  useEffect(()=>{gl.domElement.style.cursor=hover?'pointer':'grab';return()=>{gl.domElement.style.cursor='';};},[hover,gl]);
  useFrame((_,dt)=>{
    if(animating.current&&controls.current){const a=reduced?1:1-Math.exp(-dt*5);camera.position.lerp(destination.current,a);controls.current.target.lerp(target.current,a);controls.current.update();if(camera.position.distanceTo(destination.current)<.03)animating.current=false;}
    const label=labelRef.current;const annotated=workspace.variants.find(v=>v.id===(hover||selected.id));const position=annotated?points.get(annotated.position):null;
    if(label){if(position){const p=position.clone().project(camera);label.style.left=`${(p.x+1)*50}%`;label.style.top=`${(-p.y+1)*50}%`;label.style.visibility=Math.abs(p.x)<.92&&Math.abs(p.y)<.85?'visible':'hidden';}else label.style.visibility='hidden';}
  });
  const matching=new Set(analysis?.matching_ids??workspace.variants.map(v=>v.id));
  const near=new Set(inspectNeighbors?neighbors?.neighbors.map(n=>n.variant_id):[]);
  return <>
    <ambientLight intensity={1.1}/><directionalLight position={[20,40,30]} intensity={2.3}/><directionalLight position={[-30,-10,-20]} color="#4c9da7" intensity={2}/>
    <group>{tubes.map((geometry,i)=><mesh key={i} geometry={geometry}><meshStandardMaterial color="#63a5b0" roughness={.5} metalness={.24}/></mesh>)}
      {workspace.structure.points.filter(p=>p.position%5===0).map(p=><mesh key={p.position} position={[p.x,p.y,p.z]}><sphereGeometry args={[.32,12,12]}/><meshStandardMaterial color="#7a9b9f" roughness={.5}/></mesh>)}
      {workspace.variants.filter(v=>v.mapping_status==='mapped').map(v=>{
        const p=points.get(v.position);if(!p)return null;const active=v.id===selected.id;
        const measure=workspace.measurements.find(m=>m.variant_id===v.id&&m.assay_id===`assay-${layer}-demo`)?.value??null;
        const excluded=!matching.has(v.id);const neighbor=near.has(v.id);
        return <group key={v.id} position={p}>
          <mesh onClick={e=>{e.stopPropagation();stopRotation();onSelect(v.id);}} onPointerOver={e=>{e.stopPropagation();onHover(v.id);}} onPointerOut={()=>onHover(null)}>
            <sphereGeometry args={[active?1.12:.85,32,24]}/><meshStandardMaterial color={color(measure)} emissive={color(measure)} emissiveIntensity={active?.3:.08} transparent opacity={excluded?.55:1} roughness={.28}/>
          </mesh>
          {(active||neighbor)&&<mesh><sphereGeometry args={[active?1.55:1.25,24,16]}/><meshBasicMaterial color={active?'#d9f4ef':'#edbc76'} wireframe transparent opacity={active?.35:.4}/></mesh>}

        </group>;
      })}
    </group>
    <OrbitControls ref={controls} makeDefault minDistance={8} maxDistance={140} enableDamping={!reduced} autoRotate={rotation&&!reduced&&!animating.current} autoRotateSpeed={.5} onStart={()=>{animating.current=false;stopRotation();}}/>
  </>;
}
export default function StructureViewer(props:StructureViewerProps){
  const reduced=useReducedMotion();const [rotation,setRotation]=useState(false);const [reset,setReset]=useState(0);const [available,setAvailable]=useState(hasWebGL);
  useEffect(()=>{if(reduced)setRotation(false);},[reduced]);
  const [contextLost,setContextLost]=useState(false);
  const [hover,setHover]=useState<string|null>(null);const labelRef=useRef<HTMLDivElement>(null);
  const annotated=props.workspace.variants.find(v=>v.id===(hover||props.selected.id))||props.selected;
  const value=props.workspace.measurements.find(m=>m.variant_id===annotated.id&&m.assay_id===`assay-${props.layer}-demo`)?.value??null;
  return <div className="structure-viewer" onWheel={e=>{if(e.deltaY<0)props.onInspect?.();}}>
    <div className="canvas-heading"><div><span className="eyebrow">SPATIAL CONTEXT</span><h2>One sequence. Different profiles.</h2></div><span className="coordinate-chip">DEMO-PROT-001 <span>/ 120 positions</span></span></div>
    <div className="viewer-controls"><button onClick={()=>{setReset(x=>x+1);setRotation(false);}} disabled={!available||contextLost} title="Reset camera to the full illustrative structure">↺ <span>Reset view</span></button><button aria-pressed={rotation} onClick={()=>setRotation(x=>!x)} disabled={reduced||!available||contextLost} title={reduced?'Idle rotation disabled by reduced-motion preference':'Toggle idle camera rotation'}>{rotation?'Ⅱ':'↻'} <span>{rotation?'Pause rotation':'Rotate slowly'}</span></button></div>
    <ViewerBoundary>{available&&!contextLost?<Suspense fallback={<div className="viewer-fallback">Preparing geometry…</div>}><Canvas camera={{position:[45,24,65],fov:43,near:.1,far:400}} dpr={[1,2]} gl={{antialias:true,alpha:true}} onCreated={({gl})=>{gl.domElement.addEventListener('webglcontextlost',()=>setContextLost(true),{once:true});}} fallback={<div className="viewer-fallback">WebGL unavailable. Continue with the table.</div>}><SyntheticScene {...props} rotation={rotation} stopRotation={()=>setRotation(false)} reset={reset} reduced={reduced} hover={hover} onHover={setHover} labelRef={labelRef}/></Canvas></Suspense>:<div className="viewer-fallback" role="status"><span className="fallback-icon">◇</span><b>Structure viewer unavailable</b><p>WebGL is unavailable on this browser. All filtering, evidence, investigations and exports remain usable through the table.</p><button onClick={()=>{setContextLost(false);setAvailable(hasWebGL());}}>Retry viewer</button></div>}</ViewerBoundary>
    {available&&!contextLost&&<div className="viewer-annotation residue-label" ref={labelRef} role="tooltip"><b>{annotated.ref}{annotated.position}{annotated.alt}</b><span>{annotated.id} · {props.layer} {value===null?'missing':value.toFixed(2)}</span>{props.analysis&&!props.analysis.matching_ids.includes(annotated.id)&&<em>Outside current filter</em>}</div>}
    <div className="synthetic-residue-jumps" role="group" aria-label="Jump to synthetic substitution">{props.workspace.variants.map(v=><button key={v.id} aria-pressed={v.id===props.selected.id} onClick={()=>props.onSelect(v.id)}>{v.ref}{v.position}{v.alt}<small>{v.mapping_status==='mapped'?'●':'○'}</small></button>)}</div>
    <div className="canvas-footnote"><span><i className="mini-dot"/> Illustrative geometry — not a biological structure.</span><span>Drag to orbit · scroll to zoom</span></div>
  </div>;
}
export { color as measurementColor };
