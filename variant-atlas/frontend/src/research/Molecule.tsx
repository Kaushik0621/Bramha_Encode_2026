import {useEffect,useRef,useState} from 'react';
import {createPluginUI} from 'molstar/lib/mol-plugin-ui';
import {renderReact18} from 'molstar/lib/mol-plugin-ui/react18';
import {DefaultPluginUISpec} from 'molstar/lib/mol-plugin-ui/spec';
import {PluginConfig} from 'molstar/lib/mol-plugin/config';
import type {PluginUIContext} from 'molstar/lib/mol-plugin-ui/context';
import {StructureElement,StructureSelection,StructureProperties} from 'molstar/lib/mol-model/structure';
import {OrderedSet} from 'molstar/lib/mol-data/int';
import {Script} from 'molstar/lib/mol-script/script';
import {Color} from 'molstar/lib/mol-util/color';
import {ColorThemeCategory} from 'molstar/lib/mol-theme/color/categories';
import type {ColorTheme} from 'molstar/lib/mol-theme/color';
import 'molstar/build/viewer/molstar.css';
import type {Variant} from './types';
import type {SceneEvent} from './ChangeMap';
interface Props {focusIds:string[];focusVersion:number;variants:Variant[];selected:string;layer:'activity'|'abundance';picked:string[];onSelect:(id:string)=>void;onInspect?:(id:string)=>void;change?:Pick<SceneEvent,'id'|'added_ids'|'removed_ids'>}
export default function Molecule({variants,selected,layer,picked,focusIds,focusVersion,onSelect,onInspect,change}:Props){
 const zoomTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);const lastZoom=useRef(0);
 const measurement=useRef<string|null>(null);const previousSelection=useRef(selected);
 const target=useRef<HTMLDivElement>(null),plugin=useRef<PluginUIContext|null>(null);const [ready,setReady]=useState(false),[error,setError]=useState('');
 const current=useRef({variants,selected,layer,picked,onSelect,onInspect,change});current.current={variants,selected,layer,picked,onSelect,onInspect,change};
 useEffect(()=>{let disposed=false;let instance:PluginUIContext|undefined;let unsubscribe:(()=>void)|undefined;
  async function init(){try{
   const spec=DefaultPluginUISpec();spec.layout={initial:{isExpanded:false,showControls:false}};spec.components={controls:{top:'none',bottom:'none',left:'none',right:'none'}};
   spec.config=[[PluginConfig.Viewport.ShowExpand,false],[PluginConfig.Viewport.ShowSettings,false],[PluginConfig.Viewport.ShowControls,false]];
   const p=await createPluginUI({target:target.current!,render:renderReact18,spec});instance=p;if(disposed){p.dispose();return;}plugin.current=p;p.canvas3d?.setProps({renderer:{backgroundColor:Color(0x0b1926)}});
   function theme(_ctx:unknown,props:{}):ColorTheme<{}>{return {factory:theme,granularity:'group',contextHash:[...current.current.selected+current.current.layer+current.current.picked.join()+current.current.change?.id].reduce((a,c)=>(a*31+c.charCodeAt(0))|0,0),props,description:'Mean reported score across the visible subset substitutions at each mapped residue; selected substitution overrides its residue.',color:loc=>{
     if(!StructureElement.Location.is(loc))return Color(0x596979);
     const seq=StructureProperties.residue.label_seq_id(loc);const state=current.current;
     const residue=state.variants.filter(v=>v.mapping.status==='mapped'&&v.mapping.label_seq_id===seq);const added=residue.some(v=>state.change?.added_ids.includes(v.id)),removed=residue.some(v=>state.change?.removed_ids.includes(v.id));if(removed&&(added||residue.some(v=>state.picked.includes(v.id))))return Color(0xb1a2ed);if(added)return Color(0x75e4a9);if(removed)return Color(0xed9c96);
     const rows=state.variants.filter(v=>v.mapping.status==='mapped'&&v.mapping.label_seq_id===seq&&(!state.picked.length||state.picked.includes(v.id)));
     const chosen=rows.find(v=>v.id===state.selected);const values=(chosen?[chosen]:rows).map(v=>v[state.layer]).filter((v):v is number=>v!==null);
     if(!values.length)return Color(0x596979);const value=values.reduce((a,b)=>a+b,0)/values.length;
     const t=state.layer==='activity'?Math.max(0,Math.min(1,(value+3)/4)):Math.max(0,Math.min(1,value/1.5));
     return Color.interpolate(Color(0xd99358),Color(0x4ae2d2),t);
   }};}
   p.representation.structure.themes.colorThemeRegistry.add({name:'pten-assay',label:'PTEN assay',category:ColorThemeCategory.Misc,factory:theme,getParams:()=>({}),defaultValues:{},isApplicable:()=>true});
   const response=await fetch('/api/structures/1D5R');if(!response.ok)throw Error('Pinned structure unavailable. Acquire and seed real data.');
   const raw=await p.builders.data.rawData({data:await response.text(),label:'PTEN · experimental 1D5R'});
   const trajectory=await p.builders.structure.parseTrajectory(raw,'mmcif');await p.builders.structure.hierarchy.applyPreset(trajectory,'default',{structure:{name:'model',params:{}},showUnitcell:false,representationPreset:'polymer-cartoon'});
   for(const structure of p.managers.structure.hierarchy.current.structures)await p.managers.structure.component.updateRepresentationsTheme(structure.components,{color:'pten-assay' as 'uniform'});
   p.canvas3d?.commit(true);p.managers.camera.reset(undefined,0);
   const atomCount=p.managers.structure.hierarchy.current.structures[0]?.cell.obj?.data.elementCount||0;
   if(!atomCount||!p.canvas3d?.reprCount.value)throw Error('Structure parsed but no molecular representation was created.');
   if(target.current){target.current.dataset.atomCount=String(atomCount);target.current.dataset.representations=String(p.canvas3d.reprCount.value);}
   const sub=p.behaviors.interaction.click.subscribe(({current:loci})=>{
    if(!StructureElement.Loci.is(loci.loci)||!loci.loci.elements.length)return;
    const el=loci.loci.elements[0];const index=OrderedSet.getAt(el.indices,0);const loc=StructureElement.Location.create(loci.loci.structure,el.unit,el.unit.elements[index]);
    const seq=StructureProperties.residue.label_seq_id(loc);const state=current.current;const matches=state.variants.filter(v=>v.mapping.status==='mapped'&&v.mapping.label_seq_id===seq);
    if(matches.length)state.onSelect(matches.find(v=>v.id===state.selected)?.id||matches[0].id);else state.onInspect?.(state.selected);
   });unsubscribe=()=>sub.unsubscribe();
   let frames=0;const draw=p.canvas3d.didDraw.subscribe(()=>{if(++frames>=2&&p.canvas3d!.reprCount.value>0&&!disposed){if(target.current)target.current.dataset.rendered='true';setReady(true);}});const oldUnsubscribe=unsubscribe;unsubscribe=()=>{oldUnsubscribe?.();draw.unsubscribe();};p.canvas3d.requestDraw();
  }catch(e){if(!disposed)setError(e instanceof Error?e.message:'Molecular viewer unavailable. Use the linked table.');}}
  void init();return()=>{disposed=true;unsubscribe?.();if(instance)instance.dispose();plugin.current=null;};
 },[]);
 useEffect(()=>{if(!ready||!plugin.current)return;const p=plugin.current;
  void(async()=>{for(const s of p.managers.structure.hierarchy.current.structures)await p.managers.structure.component.updateRepresentationsTheme(s.components,{color:'pten-assay' as 'uniform'});})();
  const v=variants.find(v=>v.id===selected);const structure=p.managers.structure.hierarchy.current.structures[0]?.cell.obj?.data;
  p.managers.interactivity.lociSelects.deselectAll();
  if(v?.mapping.status==='mapped'&&structure){const selection=Script.getStructureSelection(Q=>Q.struct.generator.atomGroups({'residue-test':Q.core.rel.eq([Q.struct.atomProperty.macromolecular.label_seq_id(),v.mapping.label_seq_id!]),'group-by':Q.struct.atomProperty.macromolecular.residueKey()}),structure);const loci=StructureSelection.toLociWithSourceUnits(selection);p.managers.interactivity.lociSelects.select({loci});if(previousSelection.current!==selected)p.managers.camera.focusLoci(loci,{durationMs:matchMedia("(prefers-reduced-motion: reduce)").matches?0:250});previousSelection.current=selected;}
 },[ready,selected,layer,picked,variants,change]);
 useEffect(()=>{if(!ready||!plugin.current)return;const p=plugin.current;let cancelled=false;
  void(async()=>{
   if(measurement.current){await p.build().delete(measurement.current).commit();measurement.current=null;}
   const rows=picked.map(id=>variants.find(v=>v.id===id)).filter((v):v is Variant=>!!v);
   if(rows.length!==2||rows.some(v=>v.mapping.status!=='mapped')||rows[0].position===rows[1].position)return;
   const structure=p.managers.structure.hierarchy.current.structures[0]?.cell.obj?.data;if(!structure)return;
   const loci=rows.map(v=>StructureSelection.toLociWithSourceUnits(Script.getStructureSelection(Q=>Q.struct.generator.atomGroups({'atom-test':Q.core.rel.eq([Q.struct.atomProperty.macromolecular.label_atom_id(),'CA']),'residue-test':Q.core.rel.eq([Q.struct.atomProperty.macromolecular.label_seq_id(),v.mapping.label_seq_id!])}),structure)));
   if(cancelled)return;const result=await p.managers.structure.measurement.addDistance(loci[0],loci[1],{visualParams:{unitLabel:'Å'}});if(result)measurement.current=result.selection.ref;
  })();return()=>{cancelled=true;};
 },[ready,picked,variants]);
 useEffect(()=>{
  if(!ready||!focusVersion||!plugin.current)return;const p=plugin.current;const structure=p.managers.structure.hierarchy.current.structures[0]?.cell.obj?.data;if(!structure)return;
  const loci=variants.filter(v=>focusIds.includes(v.id)&&v.mapping.status==='mapped').map(v=>StructureSelection.toLociWithSourceUnits(Script.getStructureSelection(Q=>Q.struct.generator.atomGroups({'residue-test':Q.core.rel.eq([Q.struct.atomProperty.macromolecular.label_seq_id(),v.mapping.label_seq_id!])}),structure)));
  if(loci.length)p.managers.camera.focusLoci(loci,{durationMs:matchMedia('(prefers-reduced-motion: reduce)').matches?0:250});
 },[ready,focusVersion,focusIds,variants]);
 function inspectZoom(e:React.WheelEvent){if(e.deltaY>=0||Date.now()-lastZoom.current<3000)return;clearTimeout(zoomTimer.current);zoomTimer.current=setTimeout(()=>{const state=current.current;const target=plugin.current?.canvas3d?.camera.state.target;if(!target)return;const rows=state.variants.filter(v=>v.mapping.status==='mapped'&&v.mapping.coordinate);const nearest=rows.sort((a,b)=>{const dist=(v:Variant)=>{const p=v.mapping.coordinate!;return Math.hypot(p.x-target[0],p.y-target[1],p.z-target[2]);};return dist(a)-dist(b);})[0];lastZoom.current=Date.now();state.onInspect?.(nearest?.id||state.selected);},450);}
 useEffect(()=>()=>clearTimeout(zoomTimer.current),[]);
 return <section className="ra-molecule" onWheel={inspectZoom}><div ref={target} className="ra-mol-target" data-cohort={picked.join(",")}/>{!ready&&<div className="ra-view-status" role="status">{error||'Loading authentic 1D5R structure…'}</div>}<button className="ra-reset" onClick={()=>plugin.current?.managers.camera.reset(undefined,matchMedia("(prefers-reduced-motion: reduce)").matches?0:250)}>Reset molecular view</button><button className="ra-molecular-focus-chip" onClick={()=>onSelect(selected)}><span>SELECTED REFERENCE POSITION</span><b>{variants.find(v=>v.id===selected)?.protein_hgvs||selected}</b><small>Experiment options & evidence ↗</small></button><div className="ra-legend">{change&&(change.added_ids.length>0||change.removed_ids.length>0)&&<span>Change annotation: green = added to comparison · coral = removed · purple = mixed membership at one reference position. Reference atoms stay fixed.</span>}<b>{layer==='activity'?'Yeast activity enrichment':'VAMP-seq abundance score'}</b><span className="ra-gradient"/><span>{layer==='activity'?'−3':'0'} → {layer==='activity'?'1':'1.5'} · display range only; raw values retained</span><span>Grey: no measurement. {picked.length?'Colored residues: selected cohort only. Grey: outside cohort or missing measurement.':'Mean across workspace substitutions per residue.'} Selected substitution overrides. Reference geometry only.</span></div></section>;
}
