// One control for moving between the audited PTEN workspace and the synthetic demo; used in both page headers.
export default function WorkspaceSwitcher({current}:{current:'real'|'fixture'}){
  return <label className="workspace-switcher"><span className="sr-only">Workspace</span>
    <select value={current} onChange={e=>{location.href=e.target.value==='fixture'?'/?workspace=fixture':'/';}}>
      <option value="real">Real PTEN workspace</option>
      <option value="fixture">Synthetic demo workspace</option>
    </select>
  </label>;
}
