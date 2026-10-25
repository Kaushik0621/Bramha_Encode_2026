"""Namespaced public research corpus. Explicit local/Atlas mode; no silent fallback."""
import hashlib
import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
import certifi
from pymongo import MongoClient, ReturnDocument, ReplaceOne
from gridfs import GridFS
from .ingestion.assets import AssetStore

COLLECTIONS=('studies','passages','entities','structures','relations','scenarios','ingestion_jobs','expeditions','events','tasks','searches','metadata','workspace_snapshots','measurements')

class CorpusUnavailable(RuntimeError):pass

class CorpusStore:
    def __init__(self,settings):
        self.settings=settings;self.db=None;self.client=None;self.lock=threading.RLock()
        self.root=Path(settings.local_data_dir)/'corpus';self.root.mkdir(parents=True,exist_ok=True)
        self.assets=AssetStore(self.root/'assets');self.path=self.root/'documents.sqlite3'
        if settings.corpus_backend=='atlas':
            try:
                self.client=MongoClient(settings.mongodb_uri,tlsCAFile=certifi.where(),serverSelectionTimeoutMS=8000,connectTimeoutMS=8000,socketTimeoutMS=20000)
                self.client.admin.command('ping');self.db=self.client[settings.mongodb_database];self.fs=GridFS(self.db,collection='bramha_assets')
                for name in COLLECTIONS:
                    self.collection(name).create_index('id',unique=True)
                self.collection('studies').create_index([('synthetic',1),('year',-1)])
                self.collection('studies').create_index('topics');self.collection('studies').create_index('countries')
                self.collection('passages').create_index([('study_id',1),('version',1)])
                self.collection('events').create_index([('expedition_id',1),('sequence',1)],unique=True)
                self.collection('tasks').create_index([('expedition_id',1),('id',1)])
                self.collection('expeditions').create_index([('project_id',1),('created_at',-1)])
            except Exception as exc:
                if self.client:self.client.close()
                raise CorpusUnavailable('Atlas research corpus is unavailable. Check the configured database and network access.') from None
        elif settings.corpus_backend=='local':
            with self.connect() as c:
                c.execute('PRAGMA journal_mode=WAL')
                c.execute('CREATE TABLE IF NOT EXISTS corpus (collection TEXT,id TEXT,body TEXT,PRIMARY KEY(collection,id))')
        else:raise CorpusUnavailable('CORPUS_BACKEND must be local or atlas.')
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=20)
        try:
            with c:yield c
        finally:c.close()
    def collection(self,name):
        if name not in COLLECTIONS:raise ValueError('Unknown corpus collection.')
        return self.db['bramha_'+name]
    def put(self,name,identity,body):
        if name not in COLLECTIONS:raise ValueError('Unknown corpus collection.')
        row={**body,'id':identity}
        if self.db is not None:self.collection(name).replace_one({'id':identity},row,upsert=True)
        else:
            with self.lock,self.connect() as c:c.execute('INSERT INTO corpus VALUES(?,?,?) ON CONFLICT(collection,id) DO UPDATE SET body=excluded.body',(name,identity,json.dumps(row,ensure_ascii=False)))
        return row
    def get(self,name,identity):
        if self.db is not None:return self.collection(name).find_one({'id':identity},{'_id':0})
        with self.connect() as c:r=c.execute('SELECT body FROM corpus WHERE collection=? AND id=?',(name,identity)).fetchone()
        return json.loads(r[0]) if r else None
    def put_many(self,name,rows):
        if name not in COLLECTIONS:raise ValueError('Unknown corpus collection.')
        if not rows:return
        if self.db is not None:
            self.collection(name).bulk_write([ReplaceOne({'id':row['id']},row,upsert=True) for row in rows],ordered=False)
        else:
            with self.lock,self.connect() as c:
                c.executemany('INSERT INTO corpus VALUES(?,?,?) ON CONFLICT(collection,id) DO UPDATE SET body=excluded.body',[(name,row['id'],json.dumps(row,ensure_ascii=False)) for row in rows])
    def rows(self,name,limit=5000):
        if self.db is not None:return list(self.collection(name).find({},{'_id':0,'embedding':0}).limit(limit))
        with self.connect() as c:rows=c.execute('SELECT body FROM corpus WHERE collection=? ORDER BY rowid DESC LIMIT ?',(name,limit)).fetchall()
        return [json.loads(r[0]) for r in rows]
    def expedition_page(self,project_id=None,query='',unassigned=False,offset=0,limit=50):
        # Filter and sort before paging so older records remain discoverable.
        if self.db is not None:
            match={}
            if project_id:match['project_id']=project_id
            elif unassigned:match['project_id']=None
            if query:match['question']={'$regex':re.escape(query),'$options':'i'}
            collection=self.collection('expeditions')
            total=collection.count_documents(match)
            rows=list(collection.find(match,{'_id':0}).sort([('created_at',-1),('id',1)]).skip(offset).limit(limit))
        else:
            rows=self.rows('expeditions',max(1,self.count('expeditions')))
            rows=[d for d in rows if (not project_id or d.get('project_id')==project_id) and (not unassigned or not d.get('project_id')) and query.casefold() in d.get('question','').casefold()]
            rows.sort(key=lambda d:d['id']);rows.sort(key=lambda d:d['created_at'],reverse=True)
            total=len(rows);rows=rows[offset:offset+limit]
        return {'expeditions':rows,'total':total,'next_offset':offset+len(rows) if offset+len(rows)<total else None}
    def count(self,name):
        if self.db is not None:return self.collection(name).count_documents({})
        with self.connect() as c:return c.execute('SELECT count(*) FROM corpus WHERE collection=?',(name,)).fetchone()[0]
    def mutate(self,name,identity,change):
        with self.lock:
            if self.db is not None:
                for _ in range(15):
                    old=self.get(name,identity)
                    if old is None:raise KeyError(identity)
                    new=change(json.loads(json.dumps(old)));new['revision']=old.get('revision',0)+1
                    query={'id':identity,'revision':old['revision']} if 'revision' in old else {'id':identity,'revision':{'$exists':False}}
                    if self.collection(name).replace_one(query,new).matched_count:return new
                raise CorpusUnavailable('Concurrent corpus update needs retry.')
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                raw=c.execute('SELECT body FROM corpus WHERE collection=? AND id=?',(name,identity)).fetchone()
                if not raw:raise KeyError(identity)
                old=json.loads(raw[0]);new=change(json.loads(raw[0]));new['revision']=old.get('revision',0)+1
                c.execute('UPDATE corpus SET body=? WHERE collection=? AND id=?',(json.dumps(new,ensure_ascii=False),name,identity))
                return new
    def put_asset(self,data,suffix,metadata=None):
        asset=self.assets.put(data,suffix)
        if self.db is not None and not self.fs.exists(asset['sha256']):
            self.fs.put(data,_id=asset['sha256'],filename=asset['key'],sha256=asset['sha256'],metadata=metadata or {})
        return asset
    def read_asset(self,asset):
        if self.db is not None:
            raw=self.fs.get(asset['sha256']).read()
            if hashlib.sha256(raw).hexdigest()!=asset['sha256']:raise CorpusUnavailable('Archived asset checksum mismatch.')
            return raw
        return self.assets.read(asset)
    def stats(self):
        return {'backend':self.settings.corpus_backend,'database':self.settings.mongodb_database if self.db is not None else 'local corpus','collections':{name:self.count(name) for name in COLLECTIONS},'assets':self.db.bramha_assets.files.count_documents({}) if self.db is not None else len(list((self.root/'assets').glob('*/*')))}
    def close(self):
        if self.client:self.client.close()
