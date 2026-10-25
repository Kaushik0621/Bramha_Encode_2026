"""Reproducible local geometry proposals, never presented as predicted mutant folds."""
import asyncio
import io
import re
from uuid import uuid4
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.Data import CodonTable
from Bio.SeqUtils import seq3
import numpy as np
import httpx
from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from pydantic import Field
from .schemas import Model
from .ingestion.assets import AssetStore
from .research_hub import ResearchHub,now

AMINO='ACDEFGHIKLMNPQRSTVWY'
BACKBONE={'N','CA','C','O','OXT'}
class GeometryRequest(Model):
    reference_variant_id:str=Field(pattern=r'^PTEN:p\.[A-Z]\d+[A-Z]$')
    target_amino_acid:str=Field(pattern=r'^[ACDEFGHIKLMNPQRSTVWY]$')
class StructureRequest(Model):
    pdb_id:str=Field(pattern=r'^[0-9][A-Za-z0-9]{3}$')

def align_template(template, reference):
    """Least-squares rigid fit in Å; rows are xyz coordinates (no mirror reflection)."""
    x=np.asarray(template,float);y=np.asarray(reference,float)
    xc=x.mean(axis=0);yc=y.mean(axis=0)
    u,_,vt=np.linalg.svd((x-xc).T@(y-yc))
    if np.linalg.det(u@vt)<0:u[:,-1]*=-1
    rotation=u@vt
    rmsd=float(np.sqrt(np.mean(np.sum(((x-xc)@rotation+yc-y)**2,axis=1))))
    return rotation,xc,yc,rmsd

def atom_rows(cif):
    n=len(cif['_atom_site.label_atom_id']);out=[]
    def col(key,i,default):return cif.get('_atom_site.'+key,[default]*n)[i]
    for i in range(n):
        if col('pdbx_PDB_model_num',i,'1')!='1' or col('label_alt_id',i,'.') not in ('.','?','A'):continue
        if col('label_asym_id',i,'A')!='A' or col('group_PDB',i,'ATOM')!='ATOM':continue
        try:seq=int(col('auth_seq_id',i,'0'));label=int(col('label_seq_id',i,'0'))
        except ValueError:continue
        element=col('type_symbol',i,'C')
        if element in ('H','D'):continue
        out.append({'name':col('label_atom_id',i,''),'element':element,'residue':col('label_comp_id',i,''),'seq':seq,'label':label,'xyz':[float(col('Cartn_'+axis,i,'0')) for axis in 'xyz']})
    return out

def pdb_bytes(atoms):
    rows=[]
    for i,a in enumerate(atoms,1):
        x,y,z=a['xyz'];name=a['name'];name=(' '+name.ljust(3))[:4]
        rows.append(f"ATOM  {i:5d} {name:4s} {a['residue']:>3s} A{a['seq']:4d}    {x:8.3f}{y:8.3f}{z:8.3f}{1.:6.2f}{20.:6.2f}          {a['element']:>2s}")
    return ('\n'.join(rows)+'\nTER\nEND\n').encode()

class StructureLab:
    def __init__(self,app,settings):
        self.hub=ResearchHub(app,settings);self.settings=settings;self.data=app.state.science
        self.assets=AssetStore(settings.local_data_dir/'structure-lab-assets')
    async def proposal(self,pid,body):
        project=self.hub.portfolio.project(pid)
        if project['method']!='pten':raise ValueError('Open a PTEN project to propose a mapped reference-residue substitution.')
        w=self.data.workspace();variant=self.data.variant(body.reference_variant_id)
        if variant['mapping']['status']!='mapped':raise ValueError('This position has no accepted experimental coordinates. Choose a mapped position.')
        pos=variant['position'];before=w['protein']['sequence'][pos-1];target=body.target_amino_acid
        if before==target:raise ValueError('Choose an amino acid different from the reference residue.')
        component=seq3(target).upper();cache_id='ccd-'+component
        cached=self.hub.archive.get(cache_id)
        if cached:raw=self.assets.read(cached['asset'])
        else:
            async with httpx.AsyncClient(timeout=25) as client:
                response=await client.get('https://files.rcsb.org/ligands/download/'+component+'.cif');response.raise_for_status();raw=response.content
            if len(raw)>500000:raise ValueError('Chemical-component template exceeds its size limit.')
            self.hub.archive.put('template',cache_id,{'asset':self.assets.put(raw,'cif'),'source_url':'https://files.rcsb.org/ligands/download/'+component+'.cif','retrieved_at':now()})
        template=MMCIF2Dict(io.StringIO(raw.decode()))
        names=template['_chem_comp_atom.atom_id'];coords={}
        elements=template['_chem_comp_atom.type_symbol']
        for i,name in enumerate(names):
            if elements[i] in ('H','D') or name=='OXT':continue
            try:xyz=[float(template['_chem_comp_atom.pdbx_model_Cartn_'+a+'_ideal'][i]) for a in 'xyz']
            except (ValueError,KeyError):raise ValueError('The component has no usable ideal coordinates.')
            coords[name]=(elements[i],xyz)
        reference=atom_rows(MMCIF2Dict(io.StringIO(self.data.assets.read(w['structure_asset']).decode())))
        local=[a for a in reference if a['label']==variant['mapping']['label_seq_id']]
        lookup={a['name']:a for a in local}
        if not all(a in lookup and a in coords for a in ['N','CA','C']):raise ValueError('Backbone anchors are incomplete; this proposal cannot be positioned.')
        if lookup['CA']['residue']!=seq3(before).upper():raise ValueError('Observed residue identity differs from the reference. Review the construct before proposing an edit.')
        rotation,center,origin,rmsd=align_template([coords[a][1] for a in ['N','CA','C']],[lookup[a]['xyz'] for a in ['N','CA','C']])
        added=[{'name':name,'element':element,'residue':component,'seq':lookup['CA']['seq'],'label':lookup['CA']['label'],'xyz':((np.asarray(xyz)-center)@rotation+origin).tolist()} for name,(element,xyz) in coords.items() if name not in BACKBONE]
        retained=[dict(a,residue=component) for a in local if a['name'] in BACKBONE]
        candidate=[a for a in reference if a['label']!=variant['mapping']['label_seq_id']]+retained+added
        others=[a for a in reference if a['label']!=variant['mapping']['label_seq_id']]
        clashes=[];nearest=None;clash_count=0
        if added and others:
            distances=np.linalg.norm(np.asarray([a['xyz'] for a in added])[:,None,:]-np.asarray([a['xyz'] for a in others])[None,:,:],axis=2)
            nearest=float(distances.min())
            close_pairs=np.argwhere(distances<1.8)
            clash_count=len(close_pairs)
            for ai,oi in close_pairs[:20]:
                clashes.append({'candidate_atom':added[ai]['name'],'reference_residue':others[oi]['residue']+str(others[oi]['seq']),'reference_atom':others[oi]['name'],'distance_angstrom':round(float(distances[ai,oi]),3)})
        known=next((v for v in w['variants'] if v['id']==f'PTEN:p.{before}{pos}{target}'),None)
        codons=sorted(c for c,aa in CodonTable.unambiguous_dna_by_id[1].forward_table.items() if aa==target)
        eid='geometry-'+uuid4().hex
        doc={'project_id':pid,'created_at':now(),'substitution':f'p.{before}{pos}{target}','position':pos,'reference_amino_acid':before,'target_amino_acid':target,'reference_variant_id':variant['id'],'reference_accession':'P60484','reference_structure':'1D5R','reference_version':w['dataset_version'],'label_seq_id':variant['mapping']['label_seq_id'],'reference_asset':self.assets.put(pdb_bytes(reference),'pdb'),'proposal_asset':self.assets.put(pdb_bytes(sorted(candidate,key=lambda a:(a['seq'],a['name']))),'pdb'),'method':'Rigid N–CA–C least-squares alignment of an RCSB CCD ideal amino-acid template; reference backbone coordinates retained.','template_source':'https://files.rcsb.org/ligands/download/'+component+'.cif','backbone_fit_rmsd_angstrom':round(rmsd,5),'reference_sidechain_atoms':[a['name'] for a in local if a['name'] not in BACKBONE],'proposal_sidechain_atoms':[a['name'] for a in added],'closest_other_atom_angstrom':round(nearest,3) if nearest is not None else None,'clash_threshold_angstrom':1.8,'clashes':clashes,'clash_count':clash_count,'clashes_truncated':clash_count>len(clashes),'known_measurements':{'activity':known['activity'],'abundance':known['abundance'],'variant_id':known['id']} if known else None,'possible_dna_codons':codons,'codon_scope':'Genetic-code possibilities only. No transcript or genomic locus is loaded, so these are not inferred DNA edits.','status':'unrelaxed geometry proposal','limitations':['No energy minimization, molecular dynamics, docking or folding model was run.','Atom-distance screening is not an energy or functional prediction.','Observed activity/abundance are displayed only when the exact substitution exists in the loaded assay data.']}
        return self.hub.archive.put('geometry',eid,doc)
    async def import_structure(self,pid,body):
        self.hub.portfolio.raw_project(pid);pdb_id=body.pdb_id.upper()
        existing=next((s for s in self.hub.archive.list('structure') if s['project_id']==pid and s['pdb_id']==pdb_id),None)
        if existing:return existing
        async with httpx.AsyncClient(timeout=30) as client:
            async with client.stream('GET','https://files.rcsb.org/download/'+pdb_id+'.cif') as response:
                response.raise_for_status();parts=[];size=0
                async for p in response.aiter_bytes():
                    size+=len(p)
                    if size>8_000_000:raise ValueError('Structure exceeds the 8 MB comparison limit.')
                    parts.append(p)
        raw=b''.join(parts);cif=MMCIF2Dict(io.StringIO(raw.decode()));atoms=len(cif.get('_atom_site.id',[]))
        if not atoms or atoms>150000:raise ValueError('Choose a structure with 1–150,000 atoms.')
        return self.hub.archive.put('structure','structure-'+uuid4().hex,{'project_id':pid,'pdb_id':pdb_id,'asset':self.assets.put(raw,'cif'),'atom_count':atoms,'created_at':now(),'title':' '.join(cif.get('_struct.title',[pdb_id])),'source_url':'https://www.rcsb.org/structure/'+pdb_id,'scope':'Independent archived structure. Co-display does not establish binding or a physical complex.'})

def router(app,settings):
    r=APIRouter(prefix='/api/hub')
    def lab():return StructureLab(app,settings)
    @r.get('/projects/{pid}/experiments')
    def experiments(pid:str):
        l=lab();l.hub.portfolio.raw_project(pid)
        return {'geometries':[d for d in l.hub.archive.list('geometry') if d['project_id']==pid],'structures':[d for d in l.hub.archive.list('structure') if d['project_id']==pid]}
    @r.post('/projects/{pid}/geometry')
    async def proposal(pid:str,body:GeometryRequest):
        try:return await lab().proposal(pid,body)
        except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc
        except httpx.HTTPError as exc:raise HTTPException(502,'The RCSB template service is unavailable. Saved structures are retained.') from exc
    @r.post('/projects/{pid}/structures')
    async def structure(pid:str,body:StructureRequest):
        try:return await lab().import_structure(pid,body)
        except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc
        except httpx.HTTPError as exc:raise HTTPException(502,'The public structure could not be acquired. Check the PDB identifier or retry.') from exc
    @r.get('/assets/{identity}/{view}')
    def asset(identity:str,view:str):
        l=lab();doc=l.hub.archive.get(identity)
        if not doc or doc['kind'] not in ('geometry','structure'):raise HTTPException(404,'Saved structure not found.')
        key={'reference':'reference_asset','proposal':'proposal_asset','structure':'asset'}.get(view)
        if key not in doc:raise HTTPException(404,'Structure view not found.')
        return Response(l.assets.read(doc[key]),media_type='text/plain',headers={'Cache-Control':'public,max-age=31536000,immutable'})
    return r
