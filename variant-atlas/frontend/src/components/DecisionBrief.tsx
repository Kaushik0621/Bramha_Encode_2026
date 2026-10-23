import type {Investigation} from '../types';
import {score} from '../lib/api';
export default function DecisionBrief({investigation:inv}:{investigation:Investigation}){
  const excluded=inv.analysis.results.filter(r=>!inv.selected_ids.includes(r.variant_id));
  return <section className="decision-brief" aria-label="Research decision brief">
    <div className="decision-objective"><div><span className="eyebrow">THE DECISION WE ARE PREPARING</span><h3>{inv.research_question}</h3></div><div className="capacity-stamp"><b>{inv.selected_ids.length}<span> / {inv.candidate_budget}</span></b><small>CANDIDATE SLOTS USED</small></div></div>
    <p className="decision-boundary">Inclusion follows declared criteria and researcher curation. These notes do not establish a mechanism, rank scientific importance or estimate information gain.</p>
    {inv.decision_notes.length?<div className="decision-note-grid">{inv.decision_notes.map(note=><article className="decision-card" key={note.variant_id}>
      <div className="decision-card-title"><span className="mono">{note.variant_id}</span><span className="unverified-tag">REVIEW REQUIRED</span></div>
      <div className="decision-observations"><span className="decision-label">SUPPLIED SYNTHETIC OBSERVATIONS</span><div>{note.observations.map(m=><span key={m.assay_id}><small>{m.assay_id.replace('assay-','').replace('-demo','')}</small><b>{score(m.value)}</b></span>)}</div></div>
      <dl className="decision-reasoning"><dt>CALCULATED INCLUSION RATIONALE</dt><dd>{note.selection_reason}</dd><dt>UNRESOLVED QUESTION</dt><dd>{note.unresolved_question}</dd><dt>ALTERNATIVE EXPLANATION · UNVERIFIED</dt><dd>{note.alternative_explanation}</dd><dt>PROPOSED FOLLOW-UP · UNVERIFIED</dt><dd>{note.follow_up_approach}</dd></dl>
      <details className="decision-gaps"><summary>Missing information & limitations</summary><ul>{note.limitations.map(l=><li key={l}>{l}</li>)}</ul></details>
      <div className="decision-source-links"><span>FICTIONAL RECORDS</span>{note.evidence_ids.length?note.evidence_ids.map(e=><a key={e} href={`#snapshot-${inv.id}-${e}`}>{e} ↗</a>):<span>No linked source</span>}</div>
    </article>)}</div>:<p className="inline-note">{inv.selected_ids.length?'This older investigation predates per-variant decision notes. Rerun it to generate the expanded brief.':'No variants were included. No experimental candidates are proposed.'}</p>}
    {excluded.length>0&&<details className="excluded-decisions"><summary>Why the other {excluded.length} variants were not included</summary><ul>{excluded.map(r=><li key={r.variant_id}><b>{r.variant_id}</b><span>{r.matches?'Matches the assay filters; not included by researcher curation.':r.reasons.join(' ')}</span></li>)}</ul></details>}
    {inv.evidence_snapshot.length>0&&<div className="source-snapshots"><h4>SAVED FICTIONAL SOURCE RECORDS</h4><p className="small muted">The records below are saved with this investigation. They remain inspectable if the workspace changes.</p>{inv.evidence_snapshot.map(e=><details key={e.id} id={`snapshot-${inv.id}-${e.id}`}><summary><span className="mono">{e.id}</span> {e.title}</summary><p>{e.text}</p></details>)}</div>}
  </section>;
}
