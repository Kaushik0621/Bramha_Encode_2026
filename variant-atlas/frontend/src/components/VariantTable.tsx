import type { Analysis, Variant, Workspace } from '../types';
import {mappingLabel,score} from '../lib/api';
interface Props {workspace:Workspace;analysis:Analysis|null;selectedId:string;onSelect:(id:string)=>void;shortlist:string[];onToggle:(id:string)=>void;busy:boolean}
export default function VariantTable({workspace,analysis,selectedId,onSelect,shortlist,onToggle,busy}:Props){
  return <div className="table-scroll"><table className="variant-table"><caption className="sr-only">All eight synthetic variants. Excluded rows remain visible. Select a variant to inspect evidence.</caption><thead><tr><th scope="col"><span className="sr-only">Shortlist</span></th><th scope="col">Variant / substitution</th><th scope="col">Abundance <span>↑</span></th><th scope="col">Activity <span>↓</span></th><th scope="col">Geometry</th><th scope="col">Evidence</th><th scope="col">Criteria</th></tr></thead><tbody>{workspace.variants.map(v=>{
    const result=analysis?.results.find(r=>r.variant_id===v.id);const matches=result?.matches??false;
    return <tr key={v.id} className={`${selectedId===v.id?'selected':''} ${!matches?'excluded':''}`} data-testid={`row-${v.id}`}>
      <td><input type="checkbox" aria-label={`Include ${v.id} in shortlist`} checked={shortlist.includes(v.id)} disabled={!matches||busy} onChange={()=>onToggle(v.id)}/></td>
      <th scope="row"><button className="variant-select" onClick={()=>onSelect(v.id)} aria-pressed={selectedId===v.id}><b>{v.ref}{v.position}{v.alt}</b><span>{v.id}</span>{selectedId===v.id&&<i aria-hidden="true">↗</i>}</button></th>
      <td><div className="score-cell"><span className="score-bar"><i style={{width:`${(result?.abundance??0)*100}%`}}/></span><span>{score(result?.abundance)}</span></div></td>
      <td><div className={`score-cell activity ${result?.activity==null?'missing':''}`}><span className="score-bar"><i style={{width:`${(result?.activity??0)*100}%`}}/></span><span>{score(result?.activity)}</span></div></td>
      <td><span className={`mapping ${v.mapping_status==='mapped'?'':'warning-text'}`}><i/>{mappingLabel(v.mapping_status)}</span></td>
      <td>{v.evidence_ids.length?<span className="source-count">{v.evidence_ids.length} fictional {v.evidence_ids.length===1?'record':'records'}</span>:<span className="muted">No linked record</span>}</td>
      <td><span title={result?.reasons.join(' ')} className={`result-tag ${matches?'matches':''}`}>{busy?'Updating…':matches?'Matches':result?.activity==null?'Missing activity':'Outside filter'}</span></td>
    </tr>;
  })}</tbody></table></div>;
}
