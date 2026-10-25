"""Additive Atlas backup of only the specifically approved manifest and hashes."""
import hashlib,json,sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import Settings
from app.corpus_store import CorpusStore
from app.world_research import now

manifest_path=Path(sys.argv[1]).resolve()
manifest=json.loads(manifest_path.read_text())
s=replace(Settings.from_env(),corpus_backend='atlas')
if manifest['destination_database']!=s.mongodb_database:raise ValueError('Approved destination mismatch.')
root=s.local_data_dir.resolve();verified=[];changed=[]
for entry in manifest['files']:
    path=(root/entry['path']).resolve()
    if not path.is_relative_to(root):raise ValueError('Invalid manifest path.')
    if not path.is_file():changed.append({'path':entry['path'],'reason':'missing'});continue
    raw=path.read_bytes()
    if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
        changed.append({'path':entry['path'],'reason':'changed since approval'});continue
    verified.append((entry,raw))
store=CorpusStore(s)
try:
    for entry,raw in verified:
        asset=store.put_asset(raw,'json' if entry['path'].endswith('.json') else 'bin',{'origin':'approved local research backup','path':entry['path']})
        key='local-'+hashlib.sha256((entry['path']+':'+asset['sha256']).encode()).hexdigest()[:32]
        store.put('workspace_snapshots',key,{'path':entry['path'],'asset':asset,'backed_up_at':now(),'approved_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'scope':'Exact approved snapshot; originals retained locally.'})
        if store.read_asset(asset)!=raw:raise ValueError('Backup verification failed.')
    report={'approved_files':len(manifest['files']),'verified_backups':len(verified),'verified_bytes':sum(len(raw) for _,raw in verified),'skipped':changed,'database':s.mongodb_database,'completed_at':now()}
    store.put('metadata','approved-local-backup',report)
    manifest_path.with_name('private-backup-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='skipped'},indent=2))
finally:store.close()
