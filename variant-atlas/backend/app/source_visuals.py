"""Source-version-scoped visual evidence: content, coverage and actually saved work."""
from collections import Counter
import re
from fastapi import APIRouter,HTTPException,Query
from .portfolio import Portfolio,digest,source_id
from .papers import PaperLibrary


def source_version(run,source):
    if source['family']=='paper':
        return next((p.get('sha256') for p in run.get('paper_sources',[]) if p['id']==source['origin_id']),None)
    return next((digest(s) for s in run.get('source_manifest',[]) if s.get('id')==source['origin_id']),None)


def run_card(service,run,source):
    pid=service.project_for(run);project=service.read()['projects'].get(pid,{})
    artifacts=run.get('artifacts',[]);outcomes=Counter(a.get('data',{}).get('outcome') for a in artifacts if a.get('data',{}).get('outcome'))
    return {'id':run['run_id'],'question':run['request']['question'],'status':run['status'],'created_at':run['created_at'],'project_id':pid,'project_title':project.get('title','Unassigned research'),'source_version':source_version(run,source),'data_mode':run.get('data_mode','not recorded'),'operation_count':len(run.get('analysis_results',[])),'artifact_count':len(artifacts),'tool_outcomes':dict(outcomes),'has_baseline':bool(run.get('baseline_comparison')),'path':'/research/'+pid+'/investigations/'+run['run_id'] if pid else '/unassigned/'+run['run_id']}


def build(app,settings,sid,version=None,project_id=None):
    service=Portfolio(app,settings);current=service.source(sid);selected_version=version or current['version']
    source=current if selected_version==current['version'] else service.read()['catalogue_versions'].get(sid+'@'+selected_version)
    if not source:raise HTTPException(404,'This source version is unavailable. Current content is not substituted for a historical version.')
    if project_id:service.raw_project(project_id)
    cited=[r for r in service.runs() if service.run_cites(r,current)]
    exact=[r for r in cited if source_version(r,current)==selected_version and (not project_id or service.project_for(r)==project_id)]
    cards=[run_card(service,r,current) for r in exact[:50]]
    default=next((r['id'] for r in cards if r['has_baseline'] and r['status']=='completed_with_limitations'),None) or next((r['id'] for r in cards if r['operation_count'] and r['status']=='completed_with_limitations'),None) or (cards[0]['id'] if cards else None)
    result={'source_id':sid,'version':selected_version,'type':source['type'],'preparation':source['preparation'],'content_mode':'source evidence, not new computation','runs':cards,'total_exact_runs':len(exact),'other_version_runs':sum(source_version(r,current)!=selected_version for r in cited),'default_run_id':default,'projects':current['projects'],'molecular':None,'document':None,'checks':[{'label':'Source preparation','status':'available' if source['preparation']=='ready' else 'unavailable','reason':source['preparation']+'; preparation does not establish scientific applicability.'}],'scope':'Saved work below pins this exact source version. Operations can also use other sources pinned by the same run. Inspecting the whole reference starts no model. Focusing a position can start cached background guidance; new experiments require a separate action.'}
    science=getattr(app.state,'science',None)
    if source.get('method')=='pten' and science:
        w=science.workspace();manifest=next((s for s in w['sources'] if s['id']==source['origin_id']),None)
        if manifest and digest(manifest)==selected_version:
            mapping={m['reference_position']:m for m in w['mappings'] if isinstance(m.get('reference_position'),int) and 1<=m['reference_position']<=w['protein']['length']}
            positions=[{'position':i,'residue':aa,'status':mapping.get(i,{}).get('status','not_recorded'),'reason':mapping.get(i,{}).get('reason','No mapping audit is recorded.'),'auth_seq_id':int(mapping[i]['auth_seq_id']) if re.fullmatch(r'-?\d+',str(mapping.get(i,{}).get('auth_seq_id',''))) else None} for i,aa in enumerate(w['protein']['sequence'],1)]
            coverage=dict(Counter(p['status'] for p in positions));variants=w['variants']
            result['molecular']={'protein':w['protein'],'dataset_version':w['dataset_version'],'structure':w['structure'],'structure_url':'/api/structures/1D5R','references':[{'source_id':source_id('pten',s['id']),'title':s['title'],'version':digest(s)} for s in w['sources'] if s['id'] in ('uniprot-P60484','pdb-1D5R')],'positions':positions,'coverage':coverage,'unresolved_construct_positions':sum(m.get('reference_position') is None for m in w['mappings']),'variants':variants,'assays':w['assays'],'measurements':{'loaded_profiles':len(variants),'activity':sum(v['activity'] is not None for v in variants),'abundance':sum(v['abundance'] is not None for v in variants),'paired':sum(v['activity'] is not None and v['abundance'] is not None for v in variants)},'scope':'Loaded public PTEN substitution profiles, not patient genotypes. Assay observations and reference geometry are separate evidence. Substitution annotation does not compute a mutant structure.'}
            result['checks'] += [
                {'label':'Protein reference','status':'available','reason':str(w['protein']['length'])+' amino acids; sequence version '+str(w['protein']['sequence_version'])+'.'},
                {'label':'Experimental coordinates','status':'partial','reason':str(coverage.get('mapped',0))+' of '+str(len(positions))+' reference positions have accepted mappings; gaps remain unavailable.'},
                {'label':'DNA / participant genotype','status':'not_measured','reason':'No participant DNA allele, genome build or transcript is measured here. Protein substitutions cannot uniquely identify a DNA change.'},
                {'label':'Changed protein fold','status':'not_computed','reason':'The structure is the experimental reference. No mutant-fold prediction or physical simulation was executed by viewing this source.'},
            ]
        else:result['checks'].append({'label':'Molecular visualization','status':'unavailable','reason':'The current sequence/structure adapter does not match this historical source version. Its saved investigation artifacts remain inspectable.'})
    if source['family']=='paper':
        try:
            paper=PaperLibrary(settings).get(source['origin_id'])
            if paper['sha256']!=selected_version:raise KeyError('Version differs')
            result['document']={'status':paper['status'],'characters':paper['characters'],'chunks':[{'id':c['id'],'page':c['page'],'text':c['text']} for c in paper.get('chunks',[])[:80]],'total_chunks':len(paper.get('chunks',[])),'scope':'Original extraction preview, at most 80 passages. A readable passage is not evidence that a model has reviewed it.'}
        except (ValueError,KeyError):result['checks'].append({'label':'Original-language extraction','status':'unavailable','reason':'The original extraction for this exact source version is unavailable; frozen run passages may remain available.'})
    if not result['molecular'] and not result['document']:
        details=source.get('details',{});result['source_passage']={'text':details.get('passage') or details.get('text') or '', 'kind':details.get('passage_kind','Source metadata'),'coverage':source.get('coverage','')}
    return result


def router(app,settings):
    r=APIRouter(prefix='/api/source-visuals')
    @r.get('/{sid}')
    def visuals(sid:str,version:str|None=Query(None,max_length=160),project:str|None=Query(None,pattern=r'^project-[a-f0-9]{32}$')):
        try:return build(app,settings,sid,version,project)
        except KeyError:raise HTTPException(404,'Source or research project not found.') from None
        except ValueError:raise HTTPException(422,'This source cannot be prepared for the visual evidence view.') from None
    return r
