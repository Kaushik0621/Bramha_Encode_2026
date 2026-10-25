"""Deterministic reports and researcher-controlled snapshots of public-evidence work.

No model call or delivery occurs on export. Snapshots deliberately exclude project
notes, uploaded papers, prompts, credentials and raw provider responses.
"""
import hashlib
import html
import io
import json
import re
import secrets
import zipfile
from urllib.parse import urlparse
from Bio.PDB import MMCIFParser
import numpy as np
from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from .schemas import Model
from .expeditions import STOPPED
from .research_hub import now


def safe_url(value):
    return value if isinstance(value,str) and urlparse(value).scheme in ('http','https') else ''


def projection_svg(raw):
    """Orthographic PCA view of actual first-model C-alpha coordinates, not a fold prediction."""
    model=next(MMCIFParser(QUIET=True).get_structure('reference',io.StringIO(raw.decode())).get_models())
    chains=[]
    for chain in model:
        points=[atom.coord.tolist() for residue in chain if 'CA' in residue for atom in [residue['CA']]]
        if points:chains.append((chain.id,np.asarray(points,dtype=float)))
    if not chains:raise ValueError('No C-alpha coordinates are available for this reference projection.')
    xyz=np.concatenate([a for _,a in chains]);center=xyz.mean(axis=0)
    if len(xyz)<3:raise ValueError('Too few coordinates for a molecular projection.')
    _,_,basis=np.linalg.svd(xyz-center,full_matrices=False);projected=(xyz-center)@basis[:2].T
    scale=min(780/max(float(np.ptp(projected[:,0])),1),360/max(float(np.ptp(projected[:,1])),1))
    colors=['#a78bfa','#38bdf8','#fbbf24','#2dd4bf','#fb7185'];parts=[];cursor=0;legends=[]
    for i,(name,points) in enumerate(chains):
        xy=projected[cursor:cursor+len(points)];cursor+=len(points);path=[]
        for j,(x,y) in enumerate(xy):
            # Large coordinate gaps remain gaps in the trace.
            command='M' if j==0 or np.linalg.norm(points[j]-points[j-1])>8 else 'L'
            path.append(f'{command}{450+x*scale:.2f},{230-y*scale:.2f}')
        color=colors[i%len(colors)];parts.append(f'<path d="{" ".join(path)}" stroke="{color}" stroke-width="2.2" fill="none"/>')
        legends.append(f'<text x="{25+(i%5)*170}" y="{458+(i//5)*18}" fill="{color}">Chain {html.escape(name)} · {len(points)} Cα</text>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 530" role="img" aria-label="Two-dimensional projection of archived reference coordinates"><rect width="900" height="530" fill="#0b1926"/><g>'+''.join(parts)+'</g><g font-family="sans-serif" font-size="13">'+''.join(legends[:15])+'<text x="25" y="520" fill="#bad5d4">First-model Cα projection · archived coordinates · no mutation effect computed</text></g></svg>').encode()


def build_report(store,rid):
    run=store.get('expeditions',rid)
    if not run:raise KeyError(rid)
    if run['status'] not in STOPPED:raise ValueError('The expedition is still running. Finish or cancel it before exporting a final or partial report.')
    studies=[]
    for sid in run.get('study_ids',[]):
        source=store.get('studies',sid) or {}
        studies.append({k:source.get(k) for k in ['id','title','authors','year','doi','pmcid','version','coverage','licence','languages']}|{'id':sid,'url':safe_url(source.get('url',''))})
    structures=[{k:s.get(k) for k in ['id','pdb_id','title','method','resolution','atom_count','relationship','citation_matches']}|{'source_url':safe_url(s.get('source_url',''))} for s in run.get('structures',[])]
    claims=[{k:c.get(k) for k in ['id','text','study_id','passage_id','source_version','quote','worker','reviewer_status','claim_type']} for c in run.get('claims',[])]
    workers=[{k:t.get(k) for k in ['id','role','engine','status','summary','provider','model','started_at','finished_at','error']} for t in run.get('tasks',[])]
    events=[{k:e.get(k) for k in ['sequence','at','type','summary','task_id','tool','refs']} for e in run.get('events',[])]
    figures=[]
    for structure in structures[:3]:
        saved=store.get('structures',structure['id'])
        if saved and saved.get('asset'):
            try:figures.append({'pdb_id':structure.get('pdb_id'),'svg':projection_svg(store.read_asset(saved['asset'])).decode()})
            except Exception:pass
    return {'figures':figures,'schema_version':1,'id':rid,'title':run['question'],'status':run['status'],'created_at':run['created_at'],'finished_at':run.get('finished_at') or run.get('updated_at'),'generated_at':now(),'mode':run['mode'],'summary':run.get('summary') or run.get('error') or 'The expedition has no final narrative. Inspect the retained evidence and incomplete tasks.','scope':'An automatically compiled, unreviewed public-evidence research report. It is not a published paper or an independent laboratory experiment.','interpretation':'Findings describe what the acquired studies report. Source-identity checks do not establish causation, clinical benefit or a newly computed genetic or molecular structure.','studies':studies,'claims':claims,'structures':structures,'workers':workers,'events':events,'directions':run.get('directions',[]),'limitations':run.get('limitations',[]),'budget':{k:run.get('budget',{}).get(k,0) for k in ['model_requests','max_model_requests','tool_calls']}}


def activity_svg(report):
    values=[('Public studies',len(report['studies'])),('Saved observations',len(report['claims'])),('Coordinate references',len(report['structures'])),('Completed workers',sum(t['status']=='completed' for t in report['workers'])),('Tool operations',report['budget']['tool_calls'])]
    highest=max(1,*[v for _,v in values]);bars=[]
    for i,(label,value) in enumerate(values):
        y=42+i*42
        bars.append(f'<text x="16" y="{y+15}">{label}</text><rect x="190" y="{y}" width="{340*value/highest:.2f}" height="22" rx="3" fill="#277a70"/><text x="{205+340*value/highest:.2f}" y="{y+15}">{value}</text>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 280" role="img" aria-label="Recorded research output counts"><rect width="620" height="280" fill="#f4f7f4"/><g fill="#23413e" font-family="sans-serif" font-size="13">'+''.join(bars)+'<text x="16" y="266">Execution counts, not biological effect sizes</text></g></svg>').encode()


def markdown(report):
    r=report;lines=['# '+r['title'],'','Bramha Atlas · Research report · '+r['status'].replace('_',' '),'',r['scope'],'','## Abstract',r['summary'],'','## Research question and methods',r['title'],'','Execution: '+r['mode']+'. Public literature acquisition, source passage review, coordinate tracing and recorded verification; inspect worker outcomes below.','',r['interpretation'],'','## Results and their meaning']
    for i,c in enumerate(r['claims'],1):
        lines += [f'### Observation {i}',c.get('text') or '',f"Evidence type: {c.get('claim_type')} · reviewer status: {c.get('reviewer_status')}",'','> '+(c.get('quote') or '').replace('\n','\n> '),f"Source: {c.get('study_id')} · passage {c.get('passage_id')} · version {c.get('source_version')}",'']
    if not r['claims']:lines+=['No source-checked observations were retained. Absence of findings is not evidence of no biological effect.','']
    lines += ['## Molecular and genetic context']
    for s in r['structures']:
        lines += [f"### {s.get('pdb_id')}: {s.get('title')}",f"Relationship: {s.get('relationship')}. Method: {', '.join(s.get('method') or [])}.",s.get('source_url') or '', 'This is an acquired coordinate reference. Its presence does not establish a mutation effect, binding change or new genome.','']
    if not r['structures']:lines+=['No structural coordinates were acquired. A molecular effect or sequence was not invented.','']
    lines+=['## Discussion and research implications',r['interpretation'],'Further experiments should be designed against the specific study system, original methods and evidence gaps below. This compilation does not estimate an effect beyond the supplied measurements.','','## Limitations and incomplete work']
    lines+=['- '+str(l) for l in r['limitations']]
    lines+=['- '+t['role']+': '+t['status']+'; '+str(t.get('error') or t.get('summary') or 'No saved output') for t in r['workers'] if t['status']!='completed']
    lines+=['','## Agent methods and execution']
    for t in r['workers']:lines += ['- '+t['role']+' · '+t['status']+' · '+str(t.get('engine'))+(' · '+t['provider']+' / '+str(t.get('model')) if t.get('provider') else '')+': '+str(t.get('summary') or t.get('error') or 'No task summary recorded')]
    lines+=['','## Research paths and possible follow-up']
    for direction in r.get('directions',[]):lines += ['- '+str(direction.get('title'))+' · '+str(direction.get('status'))+': '+str(direction.get('last_reason') or direction.get('why') or '')]
    lines+=['','## References']
    for i,s in enumerate(r['studies'],1):lines += [f"{i}. {s.get('authors') or 'Author metadata unavailable'} ({s.get('year') or 'Year unavailable'}). {s.get('title') or s['id']}. {s.get('url') or ''}",f"   Actual coverage: {s.get('coverage')}. Original source licence: {s.get('licence') or 'Inspect original source'}. Version: {s.get('version')}."]
    lines+=['','## Reproducibility',f"Run: {r['id']}",f"Started: {r['created_at']} · stopped: {r['finished_at']} · report: {r['generated_at']}",f"Model attempts: {r['budget']['model_requests']} / {r['budget']['max_model_requests']}; tool operations: {r['budget']['tool_calls']}.",'Reports omit project notes, uploaded private papers, prompts, credentials and raw model responses.','']
    return '\n'.join(lines)


def report_html(report):
    r=report;e=lambda x:html.escape(str(x or ''));blocks=[]
    for line in markdown(r).splitlines():
        if line.startswith('### '):blocks.append('<h3>'+e(line[4:])+'</h3>')
        elif line.startswith('## '):blocks.append('<h2>'+e(line[3:])+'</h2>')
        elif line.startswith('# '):blocks.append('<h1>'+e(line[2:])+'</h1>')
        elif line.startswith('> '):blocks.append('<blockquote>'+e(line[2:])+'</blockquote>')
        elif line.strip():blocks.append('<p>'+e(line)+'</p>')
    at=next((i+1 for i,b in enumerate(blocks) if b=='<h2>Molecular and genetic context</h2>'),len(blocks))
    for figure in reversed(r.get('figures',[])):
        blocks.insert(at,'<figure>'+figure['svg']+'<figcaption>Reference geometry: '+e(figure.get('pdb_id'))+'. Two-dimensional projection of acquired first-model coordinates; no mutation effect computed.</figcaption></figure>')
    at=next((i+1 for i,b in enumerate(blocks) if b=='<h2>Results and their meaning</h2>'),6)
    figure=activity_svg(r).decode();blocks.insert(at,'<figure>'+figure+'<figcaption>Figure 1. Counts from the saved execution record.</figcaption></figure>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+e(r['title'])+'</title><style>body{margin:0;background:#eeeae2;color:#183d39;font:17px/1.8 Georgia,serif}main{max-width:860px;margin:35px auto;background:#fffefb;padding:55px 65px;box-shadow:0 4px 35px #0001}h1{font-size:34px;line-height:1.3}h2{font-size:23px;margin:35px 0 15px;border-bottom:1px solid #ccd8d2;padding-bottom:8px}h3{font-size:19px;margin-top:26px}p,blockquote{overflow-wrap:anywhere}blockquote{border-left:3px solid #277a70;padding-left:18px;color:#526963;font-size:15px}svg{width:100%;max-height:280px}figcaption{font:12px/1.6 system-ui,sans-serif;color:#526963}header{display:flex;justify-content:space-between;gap:12px;font:13px system-ui,sans-serif;margin-bottom:30px}button{padding:10px 16px;background:#245e56;color:white;border:0;border-radius:6px;cursor:pointer}@media(max-width:700px){main{margin:0;padding:25px}h1{font-size:26px}}@media print{body{background:white}main{margin:0;padding:0;box-shadow:none}button{display:none}h2,h3{break-after:avoid}blockquote,figure{break-inside:avoid}}</style><main><header><b>BRAMHA ATLAS · RESEARCH REPORT</b><button onclick="window.print()">Print / Save PDF</button></header>'+''.join(blocks)+'</main></html>').encode()


def bundle(store,report):
    stream=io.BytesIO();assets=[];written=set()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('research-report.md',markdown(report));z.writestr('research-report.html',report_html(report));z.writestr('research-record.json',json.dumps(report,ensure_ascii=False,indent=2));z.writestr('figures/execution-counts.svg',activity_svg(report))
        for s in report['structures']:
            stored=store.get('structures',s['id']);entry={'id':s['id'],'pdb_id':s.get('pdb_id'),'available':False}
            if stored and stored.get('asset'):
                try:
                    raw=store.read_asset(stored['asset']);name=re.sub('[^A-Za-z0-9_-]','_',str(s.get('pdb_id') or s['id']))
                    path='structures/'+name+'.cif'
                    if path not in written:z.writestr(path,raw);written.add(path)
                    entry.update(available=True,path=path,sha256=hashlib.sha256(raw).hexdigest())
                    try:
                        image_path='figures/'+name+'-reference-projection.svg'
                        if image_path not in written:z.writestr(image_path,projection_svg(raw));written.add(image_path)
                    except (ValueError,KeyError,StopIteration):pass
                except Exception:entry['error']='Archived coordinate asset unavailable; inspect the original public reference.'
            assets.append(entry)
        z.writestr('manifest.json',json.dumps({'run_id':report['id'],'structures':assets,'scope':'Archived coordinate files are references, not computed mutation outcomes. Source licences remain applicable.'},indent=2))
    return stream.getvalue()


class ShareRequest(Model):
    consent:bool=False


def router(app):
    r=APIRouter(prefix='/api/observatory')
    def store():
        if not getattr(app.state,'corpus_store',None):raise HTTPException(503,'Research corpus unavailable.')
        return app.state.corpus_store
    def report(rid):
        try:return build_report(store(),rid)
        except KeyError:raise HTTPException(404,'Saved research record not found.')
        except ValueError as exc:raise HTTPException(409,str(exc))
    @r.get('/structures/{sid}/projection.svg')
    def projection(sid:str):
        source=store().get('structures',sid)
        if not source or not source.get('asset'):raise HTTPException(404,'Saved coordinates unavailable.')
        try:return Response(projection_svg(store().read_asset(source['asset'])),media_type='image/svg+xml',headers={'Cache-Control':'private,max-age=86400'})
        except Exception:raise HTTPException(422,'A C-alpha projection could not be generated for this coordinate file.')
    @r.get('/expeditions/{rid}/report')
    def data(rid:str):return report(rid)
    @r.get('/expeditions/{rid}/export/{format}')
    def export(rid:str,format:str):
        if format not in ['html','md','json','zip']:raise HTTPException(422,'Choose html, md, json or zip.')
        result=report(rid)
        content={'html':lambda:report_html(result),'md':lambda:markdown(result).encode(),'json':lambda:json.dumps(result,ensure_ascii=False,indent=2).encode(),'zip':lambda:bundle(store(),result)}[format]()
        mime={'html':'text/html; charset=utf-8','md':'text/markdown; charset=utf-8','json':'application/json','zip':'application/zip'}[format]
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
        if format!='html':headers['Content-Disposition']=f'attachment; filename="bramha-{rid}.{format}"'
        return Response(content,media_type=mime,headers=headers)
    @r.get('/expeditions/{rid}/sharing')
    def sharing(rid:str):
        if not store().get('expeditions',rid):raise HTTPException(404,'Saved research record not found.')
        return {'shares':[{'token':s['token'],'created_at':s['created_at'],'revoked':s.get('revoked',False)} for s in store().rows('searches',max(1,store().count('searches'))) if s.get('kind')=='expedition_report_share' and s.get('run_id')==rid]}
    @r.post('/expeditions/{rid}/share')
    def share(rid:str,body:ShareRequest):
        if not body.consent:raise HTTPException(422,'Choose to share the report before creating a link.')
        result=report(rid);token=secrets.token_urlsafe(24)
        store().put('searches','report-share-'+token,{'kind':'expedition_report_share','run_id':rid,'token':token,'created_at':now(),'report':result,'revoked':False})
        return {'token':token,'path':'/api/observatory/shared/'+token,'scope':'An explicit report snapshot, accessible to anyone holding this link while the server is reachable.'}
    @r.post('/expeditions/{rid}/share/{token}/revoke')
    def revoke(rid:str,token:str):
        source=store().get('searches','report-share-'+token)
        if not source or source.get('run_id')!=rid:raise HTTPException(404,'Share record not found.')
        store().put('searches',source['id'],{**source,'revoked':True,'revoked_at':now()});return {'revoked':True}
    @r.get('/shared/{token}')
    def shared(token:str):
        source=store().get('searches','report-share-'+token)
        if not source or source.get('kind')!='expedition_report_share' or source.get('revoked'):raise HTTPException(404,'This shared report is unavailable or its link was revoked.')
        return Response(report_html(source['report']),media_type='text/html; charset=utf-8',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Robots-Tag':'noindex, nofollow','X-Content-Type-Options':'nosniff'})
    return r
