import json
import os
import re
import tempfile
from pathlib import Path
from ..schemas import Workspace, Investigation
from ..run_schemas import RunSnapshot
from ..fixtures import load_fixture
from . import RepositoryError

class LocalRepository:
    def __init__(self, root: Path):
        self.root = root
        self.folder = root / 'investigations'
        self.folder.mkdir(parents=True,exist_ok=True)
        if not (root/'workspace.json').exists(): self.seed(load_fixture())

    @staticmethod
    def atomic_write(path: Path, payload: dict):
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as f:
                tmp=f.name
                json.dump(payload,f,indent=2,allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp,path)
        finally:
            if tmp and os.path.exists(tmp): os.unlink(tmp)

    def seed(self, workspace: Workspace):
        self.atomic_write(self.root/'workspace.json',workspace.model_dump(mode='json'))

    def workspace(self):
        return Workspace.model_validate_json((self.root/'workspace.json').read_text())

    def save(self, investigation: Investigation):
        self.atomic_write(self.folder/f'{investigation.id}.json',investigation.model_dump(mode='json'))

    def get(self, investigation_id: str):
        if not re.fullmatch(r'inv-[0-9a-f]{32}', investigation_id): return None
        path = self.folder/f'{investigation_id}.json'
        return Investigation.model_validate_json(path.read_text()) if path.exists() else None

    def list(self):
        return sorted([Investigation.model_validate_json(p.read_text()) for p in self.folder.glob('inv-*.json')],key=lambda x:x.created_at,reverse=True)

    def save_run(self, run: RunSnapshot):
        directory = self.root / 'runs'
        directory.mkdir(parents=True, exist_ok=True)
        self.atomic_write(directory / f'{run.run_id}.json', run.model_dump(mode='json'))

    def get_run(self, run_id: str):
        if not re.fullmatch(r'run-[0-9a-f]{32}', run_id): return None
        path = self.root / 'runs' / f'{run_id}.json'
        return RunSnapshot.model_validate_json(path.read_text()) if path.exists() else None

    def list_runs(self):
        return [RunSnapshot.model_validate_json(p.read_text()) for p in (self.root / 'runs').glob('run-*.json')]

    def close(self): pass
