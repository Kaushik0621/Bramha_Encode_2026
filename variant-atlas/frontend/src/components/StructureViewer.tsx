import { Component, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import type { ComponentRef, ReactNode, RefObject } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { Analysis, Neighbors, Variant, Workspace } from '../types';

export interface StructureViewerProps {workspace:Workspace;analysis:Analysis|null;selected:Variant;onSelect:(id:string)=>void;layer:'activity'|'abundance';neighbors:Neighbors|null;inspectNeighbors:boolean}
// Adapter boundary: replace SyntheticScene with a Mol* implementation after audited mmCIF mapping.
const color=(value:number|null)=>value===null?'#6b7a90':new THREE.Color('#eabd6f').lerp(new THREE.Color('#2dd4bf'),value).getStyle();
function hasWebGL(){try{const c=document.createElement('canvas');return !!(c.getContext('webgl2')||c.getContext('webgl'));}catch{return false;}}
function useReducedMotion(){const [value,set]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);useEffect(()=>{const m=matchMedia('(prefers-reduced-motion: reduce)');const fn=()=>set(m.matches);m.addEventListener('change',fn);return()=>m.removeEventListener('change',fn);},[]);return value;}
class ViewerBoundary extends Component<{children:ReactNode},{failed:boolean}>{
  state={failed:false};static getDerivedStateFromError(){return {failed:true};}render(){return this.state.failed?<div className="viewer-fallback" role="status"><b>Structure viewer unavailable</b><p>WebGL could not start. Use the linked table and evidence panel to continue.</p></div>:this.props.children;}
}
// Glass strand look: crystalline grain, glitter inside the tube, floating dust and a translucent rim glow. The path is unchanged.
let grain:{map:THREE.Texture;sparkle:THREE.Texture}|null=null;
function strandTextures(){
  if(grain)return grain;let seed=11;const rand=()=>(seed=(seed*16807)%2147483647)/2147483647;
  const paint=(base:string,dots:(g:CanvasRenderingContext2D)=>void)=>{const c=document.createElement('canvas');c.width=512;c.height=64;const g=c.getContext('2d')!;g.fillStyle=base;g.fillRect(0,0,512,64);dots(g);const t=new THREE.CanvasTexture(c);t.wrapS=t.wrapT=THREE.RepeatWrapping;t.repeat.set(40,1);t.colorSpace=THREE.SRGBColorSpace;return t;};
  const map=paint('#f1f3f2',g=>{for(let i=0;i<5200;i++){const l=55+rand()*40;g.fillStyle=`hsla(0,0%,${l}%,${.35+rand()*.5})`;g.fillRect(rand()*512,rand()*64,1+rand()*2.2,1+rand()*2.2);}});
  const sparkle=paint('#000000',g=>{for(let i=0;i<900;i++){g.fillStyle=`rgba(255,255,255,${.2+rand()*.55})`;g.fillRect(rand()*512,rand()*64,1+rand()*1.5,1+rand()*1.5);}for(let i=0;i<70;i++){g.fillStyle='#ffffff';g.fillRect(rand()*512,rand()*64,2,2);}});
  return grain={map,sparkle};
}
const rimVertex='varying vec3 vN;varying vec3 vV;void main(){vec4 mv=modelViewMatrix*vec4(position,1.);vN=normalize(normalMatrix*normal);vV=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}';
const rimFragment='uniform vec3 glow;varying vec3 vN;varying vec3 vV;void main(){float f=pow(1.-abs(dot(vN,vV)),1.7);gl_FragColor=vec4(glow,f);}';
function RimGlow(){const uniforms=useMemo(()=>({glow:{value:new THREE.Color('#a5f3fc')}}),[]);return <shaderMaterial vertexShader={rimVertex} fragmentShader={rimFragment} uniforms={uniforms} transparent depthWrite={false} blending={THREE.AdditiveBlending}/>;}
// Colouring by sequence position (start deep teal to end bright aqua); colour only, geometry unchanged.
const sequenceStops=['#0e7490','#06b6d4','#22d3ee','#2dd4bf','#5eead4'].map(c=>new THREE.Color(c));
function sequenceColor(t:number){const x=Math.min(Math.max(t,0),1)*(sequenceStops.length-1),i=Math.min(Math.floor(x),sequenceStops.length-2);return sequenceStops[i].clone().lerp(sequenceStops[i+1],x-i);}
function paintSequence(tubes:THREE.TubeGeometry[],workspace:Workspace){
  const all=workspace.structure.points.map(p=>p.position),lo=Math.min(...all),hi=Math.max(...all);
  const ranges=[all.filter(p=>p<95),all.filter(p=>p>=95)].map(r=>[Math.min(...r),Math.max(...r)]);
  tubes.forEach((tube,i)=>{const uv=tube.getAttribute('uv'),colors=new Float32Array(uv.count*3),[first,last]=ranges[i];
    for(let k=0;k<uv.count;k++){const c=sequenceColor((first+(last-first)*uv.getX(k)-lo)/(hi-lo));colors.set([c.r,c.g,c.b],k*3);}
    tube.setAttribute('color',new THREE.BufferAttribute(colors,3));});
}
let dotTexture:THREE.Texture|null=null;
function softDot(){if(dotTexture)return dotTexture;const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d')!;const r=g.createRadialGradient(32,32,0,32,32,32);r.addColorStop(0,'rgba(255,255,255,1)');r.addColorStop(.3,'rgba(255,255,255,.6)');r.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=r;g.fillRect(0,0,64,64);return dotTexture=new THREE.CanvasTexture(c);}
const glitterColors=['#bef264','#a3e635','#84cc16','#d9f99d','#ecfccb'].map(c=>new THREE.Color(c));
const dustColors=['#67e8f9','#22d3ee','#5eead4','#a5f3fc','#2dd4bf'].map(c=>new THREE.Color(c));
// Particles scattered around the strand path: inside the glass (minRadius 0) or as dust floating outside it.
function strandParticles(tubes:THREE.TubeGeometry[],perUnit:number,minRadius:number,maxRadius:number,seed:number,palette:THREE.Color[]){
  const rand=()=>(seed=(seed*16807)%2147483647)/2147483647;const pos:number[]=[],col:number[]=[];
  for(const tube of tubes){const path=tube.parameters.path,n=Math.round(path.getLength()*perUnit),frames=tube.tangents.length-1;
    for(let i=0;i<n;i++){const u=rand(),k=Math.round(u*frames),a=rand()*Math.PI*2,r=minRadius+Math.sqrt(rand())*(maxRadius-minRadius);
      const p=path.getPointAt(u).addScaledVector(tube.normals[k],Math.cos(a)*r).addScaledVector(tube.binormals[k],Math.sin(a)*r);
      const c=palette[Math.floor(rand()*palette.length)];pos.push(p.x,p.y,p.z);col.push(c.r,c.g,c.b);}}
  const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));g.setAttribute('color',new THREE.Float32BufferAttribute(col,3));return g;
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
    return segments.map(s=>new THREE.TubeGeometry(new THREE.CatmullRomCurve3(s),250,.62,24,false));
  },[workspace]);
  const glitter=useMemo(()=>strandParticles(tubes,22,0,.5,3,glitterColors),[tubes]);
  const dust=useMemo(()=>strandParticles(tubes,3,1.2,6,9,dustColors),[tubes]);
  const dustRef=useRef<THREE.Points>(null);
  useEffect(()=>()=>{glitter.dispose();dust.dispose();},[glitter,dust]);
  useMemo(()=>paintSequence(tubes,workspace),[tubes,workspace]);
  useEffect(()=>()=>{tubes.forEach(t=>t.dispose());},[tubes]);
  useEffect(()=>{if(!mountedSelection.current){mountedSelection.current=true;return;}const p=points.get(selected.position);if(!p)return;target.current.copy(p);destination.current.copy(p).add(new THREE.Vector3(27,16,37));animating.current=true;},[selected.id,points]);
  useEffect(()=>{if(!reset)return;target.current.set(0,0,0);destination.current.set(45,24,65);animating.current=true;},[reset]);
  useEffect(()=>{gl.domElement.style.cursor=hover?'pointer':'grab';return()=>{gl.domElement.style.cursor='';};},[hover,gl]);
  useFrame((_,dt)=>{
    if(dustRef.current&&!reduced)dustRef.current.rotation.y=Math.sin(performance.now()/9000)*.03;
    if(animating.current&&controls.current){const a=reduced?1:1-Math.exp(-dt*5);camera.position.lerp(destination.current,a);controls.current.target.lerp(target.current,a);controls.current.update();if(camera.position.distanceTo(destination.current)<.03)animating.current=false;}
    const label=labelRef.current;const annotated=workspace.variants.find(v=>v.id===(hover||selected.id));const position=annotated?points.get(annotated.position):null;
    if(label){if(position){const p=position.clone().project(camera);label.style.left=`${(p.x+1)*50}%`;label.style.top=`${(-p.y+1)*50}%`;label.style.visibility=Math.abs(p.x)<.92&&Math.abs(p.y)<.85?'visible':'hidden';}else label.style.visibility='hidden';}
  });
  const matching=new Set(analysis?.matching_ids??workspace.variants.map(v=>v.id));
  const near=new Set(inspectNeighbors?neighbors?.neighbors.map(n=>n.variant_id):[]);
  return <>
    <ambientLight intensity={1.1} color="#a5f3fc"/><directionalLight position={[20,40,30]} intensity={2.3} color="#ecfeff"/><directionalLight position={[-30,-10,-20]} color="#14b8a6" intensity={2}/>
    <group>{tubes.map((geometry,i)=><group key={i}>
        <mesh geometry={geometry}><meshPhysicalMaterial color="#ffffff" vertexColors map={strandTextures().map} bumpMap={strandTextures().map} bumpScale={1.5} emissive="#22d3ee" emissiveMap={strandTextures().sparkle} emissiveIntensity={2.4} roughness={.18} metalness={.1} clearcoat={1} clearcoatRoughness={.15} transparent opacity={.5} depthWrite={false}/></mesh>
        <mesh geometry={geometry} raycast={()=>null}><RimGlow/></mesh>
      </group>)}
      <points geometry={glitter} raycast={()=>null}><pointsMaterial map={softDot()} size={.42} vertexColors transparent opacity={.95} depthWrite={false} blending={THREE.AdditiveBlending} sizeAttenuation/></points>
      <points ref={dustRef} geometry={dust} raycast={()=>null}><pointsMaterial map={softDot()} size={.5} vertexColors transparent opacity={.55} depthWrite={false} blending={THREE.AdditiveBlending} sizeAttenuation/></points>
      {workspace.structure.points.filter(p=>p.position%5===0).map(p=><mesh key={p.position} position={[p.x,p.y,p.z]}><sphereGeometry args={[.32,12,12]}/><meshStandardMaterial color="#ecfeff" emissive="#22d3ee" emissiveIntensity={.9} roughness={.5}/></mesh>)}
      {workspace.variants.filter(v=>v.mapping_status==='mapped').map(v=>{
        const p=points.get(v.position);if(!p)return null;const active=v.id===selected.id;
        const measure=workspace.measurements.find(m=>m.variant_id===v.id&&m.assay_id===`assay-${layer}-demo`)?.value??null;
        const excluded=!matching.has(v.id);const neighbor=near.has(v.id);
        return <group key={v.id} position={p}>
          <mesh onClick={e=>{e.stopPropagation();stopRotation();onSelect(v.id);}} onPointerOver={e=>{e.stopPropagation();onHover(v.id);}} onPointerOut={()=>onHover(null)}>
            <sphereGeometry args={[active?1.12:.85,32,24]}/><meshStandardMaterial color={color(measure)} emissive={color(measure)} emissiveIntensity={active?.3:.08} transparent opacity={excluded?.55:1} roughness={.28}/>
          </mesh>
          {(active||neighbor)&&<mesh><sphereGeometry args={[active?1.55:1.25,24,16]}/><meshBasicMaterial color={active?'#ffffff':'#f472b6'} wireframe transparent opacity={active?.35:.4}/></mesh>}

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
  return <div className="structure-viewer">
    <div className="canvas-heading"><div><span className="eyebrow">SPATIAL CONTEXT</span><h2>One sequence. Different profiles.</h2></div><span className="coordinate-chip">DEMO-PROT-001 <span>/ 120 positions</span></span></div>
    <div className="viewer-controls"><button onClick={()=>{setReset(x=>x+1);setRotation(false);}} disabled={!available||contextLost} title="Reset camera to the full illustrative structure">↺ <span>Reset view</span></button><button aria-pressed={rotation} onClick={()=>setRotation(x=>!x)} disabled={reduced||!available||contextLost} title={reduced?'Idle rotation disabled by reduced-motion preference':'Toggle idle camera rotation'}>{rotation?'Ⅱ':'↻'} <span>{rotation?'Pause rotation':'Rotate slowly'}</span></button></div>
    <ViewerBoundary>{available&&!contextLost?<Suspense fallback={<div className="viewer-fallback">Preparing geometry…</div>}><Canvas camera={{position:[45,24,65],fov:43,near:.1,far:400}} dpr={[1,2]} gl={{antialias:true,alpha:true}} onCreated={({gl})=>{gl.domElement.addEventListener('webglcontextlost',()=>setContextLost(true),{once:true});}} fallback={<div className="viewer-fallback">WebGL unavailable. Continue with the table.</div>}><SyntheticScene {...props} rotation={rotation} stopRotation={()=>setRotation(false)} reset={reset} reduced={reduced} hover={hover} onHover={setHover} labelRef={labelRef}/></Canvas></Suspense>:<div className="viewer-fallback" role="status"><span className="fallback-icon">◇</span><b>Structure viewer unavailable</b><p>WebGL is unavailable on this browser. All filtering, evidence, investigations and exports remain usable through the table.</p><button onClick={()=>{setContextLost(false);setAvailable(hasWebGL());}}>Retry viewer</button></div>}</ViewerBoundary>
    {available&&!contextLost&&<div className="viewer-annotation residue-label" ref={labelRef} role="tooltip"><b>{annotated.ref}{annotated.position}{annotated.alt}</b><span>{annotated.id} · {props.layer} {value===null?'missing':value.toFixed(2)}</span>{props.analysis&&!props.analysis.matching_ids.includes(annotated.id)&&<em>Outside current filter</em>}</div>}
    <div className="synthetic-residue-jumps" role="group" aria-label="Jump to synthetic substitution">{props.workspace.variants.map(v=><button key={v.id} aria-pressed={v.id===props.selected.id} onClick={()=>props.onSelect(v.id)}>{v.ref}{v.position}{v.alt}<small>{v.mapping_status==='mapped'?'●':'○'}</small></button>)}</div>
    <div className="canvas-footnote"><span><i className="mini-dot"/> Illustrative geometry — not a biological structure.</span><span className="sequence-legend">Strand colour: sequence position <i/> start → end</span><span>Drag to orbit · scroll to zoom</span></div>
  </div>;
}
export { color as measurementColor };
