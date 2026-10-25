"""Validated supplied-model comparison; common-CA rigid alignment, never mutant folding."""
import base64,hashlib,io,re
from copy import deepcopy
from uuid import uuid4
import numpy as np
from Bio.PDB import PDBParser,MMCIFParser,MMCIFIO
from Bio.PDB.Polypeptide import is_aa
from fastapi import APIRouter,HTTPException
from fastapi.responses import Response
from pydantic import Field
from .schemas import Model
from .structure_lab import StructureLab,align_template
from .research_hub import now

class ModelImport(Model):
    filename:str=Field(min_length=1,max_length=180)
    content_base64:str=Field(max_length=11_200_000)
    origin:str=Field(default='unspecified',pattern=r'^(experimental|predicted|unspecified)$')
    generation_method:str=Field(default='Not supplied',max_length=500)
    source_url:str=Field(default='',max_length=1500)
class Correspondence(Model):
    reference_residue:str=Field(pattern=r'^-?\d+[A-Za-z]?$')
    mobile_residue:str=Field(pattern=r'^-?\d+[A-Za-z]?$')
class ModelComparison(Model):
    reference_id:str
    mobile_id:str
    reference_chain:str=Field(min_length=1,max_length=8)
    mobile_chain:str=Field(min_length=1,max_length=8)
    correspondences:list[Correspondence]=Field(default_factory=list,max_length=5000)
    allow_identity_difference:bool=False

def parsed(raw,filename):
    text=raw.decode('utf-8-sig')
    parser=MMCIFParser(QUIET=True,auth_chains=True,auth_residues=True) if filename.lower().endswith(('.cif','.mmcif')) else PDBParser(QUIET=True)
    structure=parser.get_structure('supplied',io.StringIO(text));model=next(structure.get_models())
    atoms=list(model.get_atoms())
    if not 3<=len(atoms)<=150000:raise ValueError('Use a structure with 3–150,000 atoms.')
    if not np.isfinite(np.asarray([a.coord for a in atoms])).all():raise ValueError('Structure coordinates must be finite.')
    return structure,model

def chain_residues(chain):
    return {str(r.id[1])+r.id[2].strip():r for r in chain if is_aa(r,standard=True) and 'CA' in r and r['CA'].element=='C'}

class SuppliedModels:
    def __init__(self,app,settings):self.lab=StructureLab(app,settings);self.archive=self.lab.hub.archive;self.assets=self.lab.assets
    def import_model(self,pid,body):
        self.lab.hub.portfolio.raw_project(pid)
        if body.source_url and not re.match(r'^https?://',body.source_url):raise ValueError('Source links must be HTTP(S).')
        filename=body.filename.rsplit('/',1)[-1]
        if not filename.lower().endswith(('.pdb','.cif','.mmcif')):raise ValueError('Supply a PDB or mmCIF coordinate file.')
        try:raw=base64.b64decode(body.content_base64,validate=True)
        except Exception as exc:raise ValueError('Invalid file encoding.') from exc
        if not raw or len(raw)>8_000_000:raise ValueError('Supply a nonempty coordinate file up to 8 MB.')
        try:structure,model=parsed(raw,filename)
        except Exception as exc:raise ValueError('The structure could not be parsed: '+type(exc).__name__) from exc
        chains=[]
        for c in model:
            residues=chain_residues(c)
            if residues:chains.append({'id':c.id,'observed_ca_count':len(residues),'observed_residue_ids':list(residues),'observed_sequence_3letter':[r.resname for r in residues.values()]})
        if not chains:raise ValueError('No standard protein residues with C-alpha atoms were found.')
        digest=hashlib.sha256(raw).hexdigest();identity='supplied-'+hashlib.sha256((pid+digest+filename+body.origin+body.generation_method+body.source_url).encode()).hexdigest()[:32]
        existing=self.archive.get(identity)
        if existing:return existing
        return self.archive.put('supplied_model',identity,{'project_id':pid,'filename':filename,'sha256':digest,'asset':self.assets.put(raw,'cif' if filename.lower().endswith(('.cif','.mmcif')) else 'pdb'),'origin':body.origin,'generation_method':body.generation_method,'source_url':body.source_url,'chains':chains,'atom_count':sum(1 for _ in model.get_atoms()),'model_selection':'First coordinate model only','confidence_available':False,'confidence_scope':'B factors are not interpreted as prediction confidence without documented model provenance.','created_at':now()})
    def get(self,pid,identity):
        d=self.archive.get(identity)
        if not d or d.get('project_id')!=pid or d.get('kind')!='supplied_model':raise ValueError('Supplied model is not in this project.')
        return d
    def compare(self,pid,body):
        a=self.get(pid,body.reference_id);b=self.get(pid,body.mobile_id)
        _,ref=parsed(self.assets.read(a['asset']),a['filename']);mobile_structure,mobile=parsed(self.assets.read(b['asset']),b['filename'])
        if body.reference_chain not in ref or body.mobile_chain not in mobile:raise ValueError('Selected chain is absent from the supplied model.')
        r=chain_residues(ref[body.reference_chain]);m=chain_residues(mobile[body.mobile_chain])
        pairs=[(c.reference_residue,c.mobile_residue) for c in body.correspondences] if body.correspondences else [(key,key) for key in r if key in m]
        if len({x for x,_ in pairs})!=len(pairs) or len({y for _,y in pairs})!=len(pairs):raise ValueError('Residue correspondence must be one-to-one.')
        if any(x not in r or y not in m for x,y in pairs):raise ValueError('A correspondence has no accepted C-alpha coordinate.')
        identities=[(x,y) for x,y in pairs if r[x].resname==m[y].resname]
        fraction=len(identities)/max(1,len(pairs));coverage=len(pairs)/max(1,max(len(r),len(m)))
        if len(pairs)<3 or fraction<.8 or coverage<.5:raise ValueError('Insufficient compatible correspondence: require at least three C-alpha pairs, 80% residue identity and 50% observed-chain coverage. Supply explicit correspondences for renumbered compatible structures.')
        if len(identities)!=len(pairs) and not body.allow_identity_difference:raise ValueError('Residue identities differ. Review the explicit correspondence and allow identity differences before a non-causal comparison.')
        # Identity-different sites are reported, but are excluded from the alignment atom set.
        if len(identities)<3:raise ValueError('At least three identity-matched C-alpha atoms are required for alignment.')
        xyz_ref=np.array([r[x]['CA'].coord for x,y in identities],dtype=float);xyz_mobile=np.array([m[y]['CA'].coord for x,y in identities],dtype=float)
        if np.linalg.matrix_rank(xyz_mobile-xyz_mobile.mean(axis=0))<2:raise ValueError('Alignment anchors are collinear; the rotation is underdetermined.')
        rotation,center,origin,rmsd=align_template(xyz_mobile,xyz_ref)
        displacements=[{'reference_residue':x,'mobile_residue':y,'reference_name':r[x].resname,'mobile_name':m[y].resname,'identity_matches':r[x].resname==m[y].resname,'displacement_angstrom':float(np.linalg.norm((np.asarray(m[y]['CA'].coord)-center)@rotation+origin-r[x]['CA'].coord))} for x,y in pairs]
        transformed=deepcopy(mobile)
        for atom in transformed.get_atoms():atom.coord=((np.asarray(atom.coord)-center)@rotation+origin).astype(float)
        writer=MMCIFIO();writer.set_structure(transformed);stream=io.StringIO();writer.save(stream);aligned=self.assets.put(stream.getvalue().encode(),'cif')
        return self.archive.put('structure_comparison','comparison-'+uuid4().hex,{'project_id':pid,'created_at':now(),'reference_id':a['id'],'mobile_id':b['id'],'reference_sha256':a['sha256'],'mobile_sha256':b['sha256'],'reference_chain':body.reference_chain,'mobile_chain':body.mobile_chain,'method':'Kabsch rigid-body least-squares fit over identity-matched C-alpha atom pairs; no reflection','implementation':'app.structure_lab.align_template / NumPy SVD','correspondence_basis':'Explicit supplied residue pairs' if body.correspondences else 'Same author residue identifier and insertion code; sequence identity checked','alignment_atom_count':len(identities),'rmsd_angstrom':rmsd,'coverage_fraction':coverage,'identity_fraction':fraction,'transform':{'rotation':rotation.tolist(),'mobile_center':center.tolist(),'reference_center':origin.tolist()},'per_residue':displacements,'missing_reference_residues':[x for x in r if x not in {a for a,b in pairs}],'missing_mobile_residues':[y for y in m if y not in {b for a,b in pairs}],'aligned_asset':aligned,'limitations':['Differences may reflect construct, method, conditions or conformation; mutation causation is not established.','Only the first coordinate model and selected observed protein chains are used.','The alignment transform and aligned display copy are saved separately; original coordinates remain immutable.','No folding, energy, binding or stability model was run.'],'status':'result_available'})

def router(app,settings):
    r=APIRouter(prefix='/api/analysis')
    @r.get('/projects/{pid}/models')
    def models(pid:str):
        s=SuppliedModels(app,settings);s.lab.hub.portfolio.raw_project(pid)
        return {'models':[d for d in s.archive.list('supplied_model') if d['project_id']==pid],'comparisons':[d for d in s.archive.list('structure_comparison') if d['project_id']==pid],'mutant_model_generation':{'available':False,'reason':'No rotamer-search, structural relaxation or validated mutant-fold generation engine is integrated. Existing ideal-template placement is an explicitly unrelaxed geometry exercise.'}}
    @r.post('/projects/{pid}/models')
    def upload(pid:str,body:ModelImport):
        try:return SuppliedModels(app,settings).import_model(pid,body)
        except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc
    @r.post('/projects/{pid}/structure-comparisons')
    def compare(pid:str,body:ModelComparison):
        try:return SuppliedModels(app,settings).compare(pid,body)
        except (ValueError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc
    @r.get('/projects/{pid}/models/{identity}/asset')
    def original(pid:str,identity:str):
        s=SuppliedModels(app,settings)
        try:d=s.get(pid,identity)
        except ValueError as exc:raise HTTPException(404,str(exc)) from exc
        return Response(s.assets.read(d['asset']),media_type='text/plain')
    @r.get('/projects/{pid}/structure-comparisons/{identity}/asset')
    def aligned(pid:str,identity:str):
        s=SuppliedModels(app,settings);d=s.archive.get(identity)
        if not d or d.get('project_id')!=pid or d.get('kind')!='structure_comparison':raise HTTPException(404,'Comparison is not in this project.')
        return Response(s.assets.read(d['aligned_asset']),media_type='text/plain')
    return r
