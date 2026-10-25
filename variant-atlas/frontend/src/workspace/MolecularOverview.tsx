import {lazy, Suspense, useEffect, useRef, useState} from 'react';
import type {CSSProperties} from 'react';
import {Link} from 'react-router';
import {api} from '../research/types';
import type {Workspace, Variant} from '../research/types';
import {usePortfolio,projectPath} from './model';
import './molecular-overview.css';

const ReferenceScene = lazy(() => import('./ReferenceScene'));
export interface SceneControls {
  progress: (value: number) => void;
  visible: (value: boolean) => void;
}
const clamp = (value: number) => Math.max(0, Math.min(1, value));

export default function MolecularOverview() {
  const {data} = usePortfolio();
  const [workspace, setWorkspace] = useState<Workspace|null>(null);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const [reduced, setReduced] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  const host = useRef<HTMLElement>(null);
  const controls = useRef<SceneControls|null>(null);
  const progress = useRef(0);
  const active = useRef(true);
  const project = data?.projects.find(p => p.method === 'pten');
  const recent = data?.projects[0];
  const variant = workspace?.variants.find(v => v.id === 'PTEN:p.C124S' && v.mapping.status === 'mapped' && v.activity !== null && v.abundance !== null);
  const source = data?.sources.find(s => s.origin_id === 'mavedb-activity-scores');
  const structure = data?.sources.find(s => s.origin_id === 'pdb-1D5R');
  const intent = variant && workspace ? new URLSearchParams({variant:variant.id, reference:workspace.protein.id, dataset:workspace.dataset_version, mapping:workspace.dataset_version}).toString() : '';
  const inspect = project ? `/research/${project.id}/workspace?${intent}` : `/research?${intent}`;

  useEffect(() => {
    let alive = true;
    void api<Workspace>('workspaces/pten-real').then(w => {if (alive) setWorkspace(w);}).catch(() => {if (alive) setError('Audited PTEN data is unavailable. Sources and saved investigations remain accessible.');});
    return () => {alive = false;};
  }, []);

  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => setReduced(media.matches);
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);

  useEffect(() => {
    const el = host.current!;
    const mobile = matchMedia('(max-width: 760px)');
    let frame = 0, pointerX = 0, pointerY = 0, desiredX = 0, desiredY = 0;
    const update = () => {
      frame = 0;
      const rect = el.getBoundingClientRect();
      const travel = Math.max(1, el.offsetHeight - Math.min(690, innerHeight - 30));
      // The sole scroll progress drives layout, copy and the reference camera.
      progress.current = clamp(-rect.top / travel);
      el.style.setProperty('--overview-progress', String(progress.current));
      el.style.setProperty('--overview-motion', String(clamp(progress.current/.4)));
      el.style.setProperty('--overview-reveal', String(clamp((progress.current - .38) / .2)));
      el.dataset.progress = progress.current.toFixed(3);
      el.dataset.focus = progress.current > .52 ? 'selected-residue' : 'whole-reference';
      pointerX += (desiredX - pointerX) * .12;
      pointerY += (desiredY - pointerY) * .12;
      el.style.setProperty('--pointer-x', `${pointerX.toFixed(2)}deg`);
      el.style.setProperty('--pointer-y', `${pointerY.toFixed(2)}deg`);
      controls.current?.progress(reduced || mobile.matches ? (progress.current > .52 ? 1 : 0) : progress.current);
      if (active.current && !reduced && !mobile.matches && (Math.abs(desiredX-pointerX) + Math.abs(desiredY-pointerY) > .02)) schedule();
    };
    const schedule = () => {if (!frame && active.current) frame = requestAnimationFrame(update);};
    const pointer = (event: PointerEvent) => {
      if (reduced || mobile.matches || event.pointerType !== 'mouse') return;
      const rect = el.getBoundingClientRect();
      desiredX = Math.max(-2, Math.min(2, (event.clientY - rect.top - Math.min(690,innerHeight)/2) / 170));
      desiredY = Math.max(-3, Math.min(3, (event.clientX - rect.left - rect.width/2) / 170));
      schedule();
    };
    const leave = () => {desiredX = 0; desiredY = 0; schedule();};
    const visibility = () => {
      active.current = !document.hidden && el.getBoundingClientRect().bottom > 0 && el.getBoundingClientRect().top < innerHeight;
      el.dataset.rendering = active.current ? 'active' : 'paused';
      controls.current?.visible(active.current);
      if (active.current) schedule();
    };
    const observer = new IntersectionObserver(visibility, {threshold:0});
    observer.observe(el);
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('scroll', schedule, {passive:true});
    window.addEventListener('resize', schedule);
    el.addEventListener('pointermove', pointer);
    el.addEventListener('pointerleave', leave);
    visibility();
    return () => {observer.disconnect(); cancelAnimationFrame(frame); document.removeEventListener('visibilitychange',visibility);window.removeEventListener('scroll',schedule);window.removeEventListener('resize',schedule);el.removeEventListener('pointermove',pointer);el.removeEventListener('pointerleave',leave);};
  }, [reduced]);

  const register = (value: SceneControls|null) => {
    controls.current = value;
    value?.progress(reduced ? (progress.current > .52 ? 1 : 0) : progress.current);
    value?.visible(active.current);
  };

  return <section ref={host} className={`mo-experience ${reduced ? 'mo-reduced' : ''} ${ready ? 'mo-ready' : ''}`} aria-label="From molecular structure to inspectable evidence" style={{'--overview-progress':0,'--overview-reveal':0} as CSSProperties}>
    <div className="mo-scene-rail">
      <div className="mo-scene-pin">
        <div className="mo-scene-subject">
          <div className="mo-scene-entrance">
            {workspace && variant ? <Suspense fallback={<ReferenceFallback status="Preparing the experimental reference…"/>}>
              <ReferenceScene variant={variant} reduced={reduced} register={register} onReady={() => setReady(true)}/>
            </Suspense> : <ReferenceFallback status={error || 'Loading audited reference and measurements…'}/>}
          </div>
        </div>
        <div className="mo-structure-caption"><span>01 / PTEN · 1D5R</span><p>Experimental reference structure.<br/>Visual highlighting does not predict mutant behaviour.<br/>Amber identifies the mapped reference position C124.</p>{structure && <Link to={'/library/'+structure.id}>Structure provenance ↗</Link>}</div>
      </div>
    </div>
    <section className="mo-intro" aria-label="The molecule">
      <div className="mo-session"><span><i/> RESEARCH, WITH A RECORD</span>{recent ? <Link to={projectPath(recent)}>Resume project ↗</Link> : <Link to="/research">Your projects ↗</Link>}</div>
      <div className="mo-intro-copy">
        <p className="mo-eyebrow">COMPUTATIONAL GENOMICS · EVIDENCE-FIRST RESEARCH</p>
        <h1>See the structure.<br/><em>Investigate</em><br/>the uncertainty.</h1>
        <p className="mo-deck">Connect variant measurements, molecular context and published evidence in one inspectable research workspace.</p>
        <div className="mo-actions"><Link className="mo-primary" to={recent ? `/research/${recent.id}/workspace` : '/research'}>Open research workspace <span>↗</span></Link><a className="mo-secondary" href="#home-evidence">Explore the evidence ↓</a></div>
        <p className="mo-scope">Human PTEN reference · public assay evidence<br/>No mutant fold or clinical classification is inferred.</p>
      </div>
      <div className="mo-scroll-note"><span>SCROLL TO CONNECT THE EVIDENCE</span><i>↓</i></div>
    </section>
    <section className="mo-evidence" id="home-evidence" aria-label="The evidence">
      <div className="mo-evidence-copy">
        <p className="mo-eyebrow">02 / ONE MEASURED POSITION</p>
        <h2>A position is not<br/><em>an explanation.</em></h2>
        <p className="mo-deck">Inspect what was measured, where it maps, and what the evidence still cannot establish.</p>
        {workspace && variant ? <EvidenceCard variant={variant} workspace={workspace} sourceURL={source ? '/library/'+source.id : '/library'} inspectURL={inspect}/> : <div className="mo-measurement-card" role="status"><b>Evidence unavailable</b><p>{error || 'Waiting for audited measurements. No example scores are substituted.'}</p><Link to="/library">Inspect available sources →</Link></div>}
      </div>
    </section>
  </section>;
}
function EvidenceCard({variant,workspace,sourceURL,inspectURL}:{variant:Variant;workspace:Workspace;sourceURL:string;inspectURL:string}) {
  return <article className="mo-measurement-card">
    <div className="mo-card-head"><div><small>SELECTED SUBSTITUTION</small><Link to={inspectURL} aria-label={`Inspect ${variant.protein_hgvs} in research workspace`}>{variant.protein_hgvs} <span>↗</span></Link></div><span className="mo-mapped">● Experimental mapping</span></div>
    <dl>{(['activity','abundance'] as const).map(id => <div key={id}><dt>{workspace.assays.find(a => a.id === id)?.title || id}</dt><dd title={String(variant[id])}>{variant[id]?.toFixed(4) ?? 'Not measured'}</dd><small>{workspace.assays.find(a => a.id === id)?.scale}</small></div>)}</dl>
    <p className="mo-mapping">Canonical position {variant.position} → chain A · structure residue {variant.mapping.label_seq_id}. Reference P60484; unresolved positions are retained as gaps.</p>
    <p className="mo-limit">Separate experimental endpoints. This comparison does not explain causality or predict a changed protein shape.</p>
    <div className="mo-card-actions"><Link to={inspectURL}>Inspect evidence <span>↗</span></Link><Link to={sourceURL}>Assay source ↗</Link></div>
    <details><summary>Reference and mapping version</summary><p>{workspace.dataset_version}</p><p>{variant.mapping.mapping_id}</p></details>
  </article>;
}
export function ReferenceFallback({status}:{status:string}) {
  return <div className="mo-fallback"><img src="/reference/pten-1d5r-trace.svg" alt="Derived two-dimensional trace of accepted experimental PTEN C-alpha coordinates; gaps are unconnected"/><p role="status">{status}</p><small>Derived reference trace · display projection only</small></div>;
}
