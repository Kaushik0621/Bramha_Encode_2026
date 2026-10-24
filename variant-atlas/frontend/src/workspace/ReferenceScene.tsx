import {useEffect, useRef, useState} from 'react';
import {PluginContext} from 'molstar/lib/mol-plugin/context';
import {DefaultPluginSpec} from 'molstar/lib/mol-plugin/spec';
import {PluginConfig} from 'molstar/lib/mol-plugin/config';
import {StructureElement, StructureProperties} from 'molstar/lib/mol-model/structure';
import {MolScriptBuilder as Q} from 'molstar/lib/mol-script/language/builder';
import {Vec3} from 'molstar/lib/mol-math/linear-algebra';
import {Color} from 'molstar/lib/mol-util/color';
import {ColorThemeCategory} from 'molstar/lib/mol-theme/color/categories';
import type {ColorTheme} from 'molstar/lib/mol-theme/color';
import type {Camera} from 'molstar/lib/mol-canvas3d/camera';
import type {Variant} from '../research/types';
import type {SceneControls} from './MolecularOverview';
import {ReferenceFallback} from './MolecularOverview';

interface Props {variant:Variant;reduced:boolean;register:(controls:SceneControls|null)=>void;onReady:()=>void}
export default function ReferenceScene(props: Props) {
  const root = useRef<HTMLDivElement>(null), canvas = useRef<HTMLCanvasElement>(null);
  const current = useRef(props); current.current = props;
  const [ready,setReady] = useState(false), [error,setError] = useState('');
  useEffect(() => {
    let disposed=false, initializing=true, cleaned=false, plugin:PluginContext|undefined, observer:IntersectionObserver|undefined, resize:ResizeObserver|undefined;
    const dispose=()=>{if(plugin&&!cleaned){cleaned=true;plugin.dispose();}};
    let requestedVisible=true, onScreen=true, focus=false, progress=0;
    let camera:Camera.Snapshot|undefined;
    const abort = new AbortController();
    const subscriptions:{unsubscribe:()=>void}[]=[];
    const visibility=()=>{
      if(!plugin?.canvas3d || disposed)return;
      const visible=requestedVisible && onScreen && !document.hidden;
      if(root.current)root.current.dataset.rendering=visible?'active':'paused';
      if(visible && !plugin.animationLoop.isAnimating)plugin.animationLoop.start();
      else if(!visible && plugin.animationLoop.isAnimating)plugin.animationLoop.stop({noDraw:true});
    };
    const update = (value:number) => {
      progress=value;
      if(!plugin?.canvas3d || !camera || disposed)return;
      const p=plugin;
      const angle=current.current.reduced?0:value*.26;
      const direction=Vec3.sub(Vec3(),camera.position,camera.target);
      const rotated=Vec3.create(direction[0]*Math.cos(angle)+direction[2]*Math.sin(angle),direction[1],-direction[0]*Math.sin(angle)+direction[2]*Math.cos(angle));
      const coordinate=current.current.variant.mapping.coordinate!;
      const target=Vec3.lerp(Vec3(),camera.target,Vec3.create(coordinate.x,coordinate.y,coordinate.z),value*.18);
      p.canvas3d!.camera.setState({...camera,target,position:Vec3.add(Vec3(),target,rotated)},0);
      const selected=value>.52;
      if(selected!==focus){
        focus=selected;
        for(const s of p.managers.structure.hierarchy.current.structures)void p.managers.structure.component.updateRepresentationsTheme(s.components,{color:'overview-reference' as 'uniform'});
      }
      p.canvas3d!.requestDraw();
    };
    async function init(){
      try{
        const spec=DefaultPluginSpec();
        spec.config=[[PluginConfig.General.PixelScale,Math.min(1,1.5/window.devicePixelRatio)]];
        spec.canvas3d={transparentBackground:true,renderer:{backgroundColor:Color(0x091b28),ambientIntensity:.65,light:[{inclination:150,azimuth:35,color:Color(0xc1f2ed),intensity:.65},{inclination:40,azimuth:210,color:Color(0x40899b),intensity:.35}]},camera:{helper:{axes:{name:'off',params:{}}}},trackball:{animate:{name:'off',params:{}}}};
        const p=new PluginContext(spec);plugin=p;await p.init();
        if(disposed)return;
        // Mol* rejects a separate readiness promise when WebGL initialization fails.
        // Consume that rejection here; the visible fallback is handled below.
        void p.canvas3dInitialized.catch(()=>{});
        if(!await p.initViewerAsync(canvas.current!,root.current!))throw Error('WebGL is unavailable.');
        if(disposed)return;
        function theme(_ctx:unknown,properties:{}):ColorTheme<{}>{return {factory:theme,granularity:'group',props:properties,contextHash:focus?2:1,description:'Presentation colour on unchanged experimental reference coordinates; amber identifies the mapped reference residue, not a mutant conformation.',color:location=>{
          if(!StructureElement.Location.is(location))return Color(0x78bbb9);
          const seq=StructureProperties.residue.label_seq_id(location);
          if(seq===current.current.variant.mapping.label_seq_id)return Color(focus?0xf1bf79:0xb9d9ce);
          return Color(focus?0x426f7c:0x72b5b6);
        }};}
        p.representation.structure.themes.colorThemeRegistry.add({name:'overview-reference',label:'Reference context',category:ColorThemeCategory.Misc,factory:theme,getParams:()=>({}),defaultValues:{},isApplicable:()=>true});
        const response=await fetch('/api/structures/1D5R',{signal:abort.signal});
        if(!response.ok)throw Error('The pinned experimental structure is unavailable.');
        const data=await p.builders.data.rawData({data:await response.text(),label:'PTEN · unchanged experimental 1D5R'});
        if(disposed)return;
        const trajectory=await p.builders.structure.parseTrajectory(data,'mmcif');
        await p.builders.structure.hierarchy.applyPreset(trajectory,'default',{structure:{name:'model',params:{}},showUnitcell:false,representationPreset:'polymer-cartoon'});
        if(disposed)return;
        for(const s of p.managers.structure.hierarchy.current.structures)await p.managers.structure.component.updateRepresentationsTheme(s.components,{color:'overview-reference' as 'uniform'});
        const structure=p.managers.structure.hierarchy.current.structures[0]?.cell;
        if(!structure?.obj?.data.elementCount)throw Error('No experimental atoms were loaded.');
        const component=await p.builders.structure.tryCreateComponentFromExpression(structure,Q.struct.generator.atomGroups({'chain-test':Q.core.rel.eq([Q.struct.atomProperty.macromolecular.label_asym_id(),'A']),'residue-test':Q.core.rel.eq([Q.struct.atomProperty.macromolecular.label_seq_id(),current.current.variant.mapping.label_seq_id!])}),'overview-position',{label:'Mapped reference position; not mutant geometry'});
        if(component)await p.builders.structure.representation.addRepresentation(component,{type:'ball-and-stick',color:'uniform',colorParams:{value:Color(0xb9d9ce)},typeParams:{sizeFactor:.3}});
        p.canvas3d!.commit(true);
        p.managers.camera.orientAxes(undefined,0);
        p.managers.camera.reset(undefined,0);
        // Wait for the default framing to settle before capturing the canonical camera.
        let frames=0;
        const draw=p.canvas3d!.didDraw.subscribe(()=>{
          if(disposed||++frames<2||camera)return;
          camera=p.canvas3d!.camera.getSnapshot();
          if(root.current){root.current.dataset.rendered='true';root.current.dataset.atomCount=String(structure.obj!.data.elementCount);root.current.dataset.reference='1D5R';}
          current.current.register({progress:update,visible:value=>{requestedVisible=value;visibility();}});
          setReady(true);current.current.onReady();update(progress);visibility();
        });subscriptions.push(draw);
        observer=new IntersectionObserver(entries=>{onScreen=entries[0].isIntersecting;visibility();});observer.observe(root.current!);
        resize=new ResizeObserver(()=>{if(!disposed)p.handleResize();});resize.observe(root.current!);
        document.addEventListener('visibilitychange',visibility);
        p.canvas3d!.requestDraw();
      }catch(e){if(!disposed){setError(e instanceof Error?e.message:'Reference renderer unavailable.');plugin?.animationLoop.stop({noDraw:true});}}
    }
    const lost=(event:Event)=>{event.preventDefault();if(!disposed){setError('The graphics context was lost. A derived reference trace is shown.');plugin?.animationLoop.stop({noDraw:true});}};
    canvas.current?.addEventListener('webglcontextlost',lost);
    const canvasElement=canvas.current;
    void init().finally(()=>{initializing=false;if(disposed)dispose();});
    return()=>{disposed=true;abort.abort();current.current.register(null);observer?.disconnect();resize?.disconnect();document.removeEventListener('visibilitychange',visibility);canvasElement?.removeEventListener('webglcontextlost',lost);subscriptions.forEach(s=>s.unsubscribe());if(!initializing)dispose();};
  }, []);
  return <div className={'mo-reference '+(ready?'ready':'')}>
    <div className="mo-canvas-root" ref={root} data-testid="overview-reference" role="img" aria-label="Authentic experimental PTEN reference structure, 1D5R"><canvas ref={canvas}/></div>
    {(!ready||error)&&<ReferenceFallback status={error?`${error} Showing a derived two-dimensional reference trace.`:'Preparing the authentic PTEN structure…'}/>}
    {error&&<span className="mo-fallback-label">STATIC REFERENCE TRACE · NOT A MUTANT MODEL</span>}
  </div>;
}
