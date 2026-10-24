from pymongo import MongoClient, ASCENDING
from ..schemas import Workspace, Investigation
from ..run_schemas import RunSnapshot
from . import RepositoryError

class AtlasRepository:
    def __init__(self, uri: str, database: str):
        if not uri: raise RepositoryError('Atlas is configured but MONGODB_URI is missing.')
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=10000)
        self.db = self.client[database]
        try:
            self.client.admin.command('ping')
        except Exception:
            self.client.close()
            raise RepositoryError('Atlas connection failed. Check credentials, network access and cluster availability.') from None

    def seed(self, workspace: Workspace):
        doc=workspace.model_dump(mode='json')
        collections=['proteins','variants','assays','measurements','structures','evidence','investigations','reviews','workspaces','runs']
        for name in collections:
            self.db[name].create_index([('run_id' if name=='runs' else 'id',ASCENDING)],unique=True)
            self.db[name].create_index([('workspace_id',ASCENDING)])
        for name,rows in [('proteins',[doc['protein']]),('variants',doc['variants']),('assays',doc['assays']),
                          ('measurements',doc['measurements']),('structures',[doc['structure']]),('evidence',doc['evidence'])]:
            for row in rows:
                row=dict(row)
                if name=='measurements': row['id']=row['variant_id']+':'+row['assay_id']
                row['workspace_id']=workspace.id
                self.db[name].replace_one({'id':row['id']},row,upsert=True)
        meta={k:doc[k] for k in ['id','name','dataset_version','synthetic']}
        self.db.workspaces.replace_one({'id':workspace.id},meta,upsert=True)

    def workspace(self):
        meta=self.db.workspaces.find_one({'id':'workspace-demo'},{'_id':0})
        if not meta: raise RepositoryError('Atlas workspace is not seeded. Run scripts/seed.py with DATA_BACKEND=atlas.')
        def rows(name):
            docs=list(self.db[name].find({'workspace_id':'workspace-demo'},{'_id':0,'workspace_id':0}))
            if name=='measurements':
                for d in docs: d.pop('id',None)
            return docs
        proteins,structures=rows('proteins'),rows('structures')
        if not proteins or not structures: raise RepositoryError('Atlas seed is incomplete. Run the seed command again.')
        return Workspace.model_validate(dict(**meta,protein=proteins[0],structure=structures[0],
            variants=sorted(rows('variants'),key=lambda x:x['id']),assays=rows('assays'),measurements=rows('measurements'),evidence=rows('evidence')))

    def save(self, investigation: Investigation):
        self.db.investigations.replace_one({'id':investigation.id},investigation.model_dump(mode='json'),upsert=True)

    def get(self, investigation_id: str):
        doc=self.db.investigations.find_one({'id':investigation_id},{'_id':0})
        return Investigation.model_validate(doc) if doc else None

    def list(self):
        return [Investigation.model_validate(d) for d in self.db.investigations.find({'synthetic':True},{'_id':0}).sort('created_at',-1).limit(100)]

    def save_run(self, run: RunSnapshot):
        self.db.runs.replace_one({'run_id':run.run_id}, run.model_dump(mode='json'), upsert=True)

    def get_run(self, run_id: str):
        doc=self.db.runs.find_one({'run_id':run_id},{'_id':0})
        return RunSnapshot.model_validate(doc) if doc else None

    def list_runs(self):
        return [RunSnapshot.model_validate(d) for d in self.db.runs.find({},{'_id':0}).sort('created_at',-1).limit(100)]

    def close(self): self.client.close()
