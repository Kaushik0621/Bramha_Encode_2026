import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]

@dataclass
class Settings:
    app_profile: str = 'local'
    data_mode: str = 'fixture'
    asset_root: Path = ROOT / 'data/assets'
    google_api_key: str = field(default='',repr=False)
    argon_model: str = 'gemini-4-argon'
    gemini_specialist_model: str = ''
    gemini_live_model: str = ''
    google_thinking_level: str = 'medium'
    google_background: bool = True
    embedding_provider: str = 'disabled'
    embedding_model: str = ''
    voyage_api_key: str = field(default='',repr=False)
    max_concurrent_workers: int = 4
    max_spawn_depth: int = 2
    max_spawned_tasks: int = 12
    max_tool_calls: int = 40
    max_model_requests: int = 20
    max_run_seconds: int = 600
    max_run_cost_usd: float | None = None
    worker_mode: str = 'embedded'
    backend_host: str = '127.0.0.1'
    backend_port: int = 8000
    frontend_origin: str = 'http://localhost:8500'
    data_backend: str = 'local'
    local_data_dir: Path = ROOT / 'var'
    mongodb_uri: str = field(default='', repr=False)
    mongodb_database: str = 'variant_atlas'
    corpus_backend: str = 'local'
    corpus_embeddings: str = 'disabled'
    corpus_embedding_model: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    llm_provider: str = 'mock'
    llm_fallback_provider: str = 'openrouter'
    openrouter_api_key: str = field(default='', repr=False)
    openrouter_model: str = ''
    openrouter_base_url: str = 'https://openrouter.ai/api/v1'
    llm_timeout_seconds: float = 45
    llm_max_output_tokens: int = 1500
    llm_max_steps: int = 6
    cors_origins: tuple[str, ...] = ('http://localhost:8500', 'http://127.0.0.1:8500')

    @classmethod
    def from_env(cls):
        # Process environment wins. Reading files must not mutate os.environ or cause
        # test/CI fixture overrides to invoke a real, configured provider accidentally.
        env = {**dotenv_values(ROOT / '.env'), **dotenv_values(ROOT / 'backend' / '.env'), **os.environ}
        origin = str(env.get('FRONTEND_ORIGIN') or 'http://localhost:8500').rstrip('/')
        parsed = urlsplit(origin)
        origins = [origin]
        if parsed.hostname in ('localhost', '127.0.0.1'):
            alias = '127.0.0.1' if parsed.hostname == 'localhost' else 'localhost'
            port = f':{parsed.port}' if parsed.port else ''
            origins.append(urlunsplit((parsed.scheme, alias + port, '', '', '')))
        explicit = env.get('CORS_ORIGINS')
        if explicit:
            origins = [x.strip().rstrip('/') for x in explicit.split(',') if x.strip()]
        backend_port = int(env.get('BACKEND_PORT') or '8000')
        if not 1 <= backend_port <= 65535:
            raise ValueError('BACKEND_PORT must be between 1 and 65535.')
        return cls(app_profile=str(env.get('APP_PROFILE') or 'local'), data_mode=str(env.get('DATA_MODE') or 'fixture'),
            asset_root=Path(env.get('ASSET_ROOT') or ROOT/'data/assets'),
            google_api_key=str(env.get('GOOGLE_API_KEY') or env.get('GEMINI_API_KEY') or ''),
            argon_model=str(env.get('ARGON_MODEL') or 'gemini-4-argon'),
            gemini_specialist_model=str(env.get('GEMINI_SPECIALIST_MODEL') or ''),gemini_live_model=str(env.get('GEMINI_LIVE_MODEL') or ''),
            google_thinking_level=str(env.get('GOOGLE_THINKING_LEVEL') or 'medium'),google_background=str(env.get('GOOGLE_BACKGROUND','true')).lower()=='true',
            embedding_provider=str(env.get('EMBEDDING_PROVIDER') or 'disabled'),embedding_model=str(env.get('EMBEDDING_MODEL') or ''),
            voyage_api_key=str(env.get('VOYAGE_API_KEY') or ''),
            max_concurrent_workers=min(4,max(1,int(env.get('MAX_CONCURRENT_WORKERS') or '4'))),
            max_spawn_depth=min(2,max(0,int(env.get('MAX_SPAWN_DEPTH') or '2'))),max_spawned_tasks=min(12,max(0,int(env.get('MAX_SPAWNED_TASKS') or '12'))),
            max_tool_calls=min(100,max(1,int(env.get('MAX_TOOL_CALLS') or '40'))),max_model_requests=min(40,max(1,int(env.get('MAX_MODEL_REQUESTS') or '20'))),
            max_run_seconds=min(600,max(10,int(env.get('MAX_RUN_SECONDS') or '600'))),
            max_run_cost_usd=float(env['MAX_RUN_COST_USD']) if env.get('MAX_RUN_COST_USD') else None,worker_mode=str(env.get('WORKER_MODE') or 'embedded'),
            backend_host=str(env.get('BACKEND_HOST') or '127.0.0.1'),
            backend_port=backend_port, frontend_origin=origin,
            data_backend=str(env.get('DATA_BACKEND') or 'local'),
            local_data_dir=Path(env.get('LOCAL_DATA_DIR') or ROOT / 'var'),
            mongodb_uri=str(env.get('MONGODB_URI') or ''),
            mongodb_database=str(env.get('MONGODB_DATABASE') or 'variant_atlas'),
            corpus_backend=str(env.get('CORPUS_BACKEND') or 'local'),
            corpus_embeddings=str(env.get('CORPUS_EMBEDDINGS') or 'disabled'),
            corpus_embedding_model=str(env.get('CORPUS_EMBEDDING_MODEL') or 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'),
            llm_provider=str(env.get('LLM_PROVIDER') or 'mock'),
            llm_fallback_provider=str(env.get('LLM_FALLBACK_PROVIDER', 'openrouter')).lower(),
            openrouter_api_key=str(env.get('OPENROUTER_API_KEY') or ''),
            openrouter_model=str(env.get('OPENROUTER_MODEL') or ''),
            openrouter_base_url=str(env.get('OPENROUTER_BASE_URL') or 'https://openrouter.ai/api/v1').rstrip('/'),
            llm_timeout_seconds=min(max(float(env.get('LLM_TIMEOUT_SECONDS') or '45'), 1), 120),
            llm_max_output_tokens=min(max(int(env.get('LLM_MAX_OUTPUT_TOKENS') or '1500'), 256), 4000),
            llm_max_steps=min(max(int(env.get('LLM_MAX_STEPS') or '6'), 1), 6),
            cors_origins=tuple(dict.fromkeys(origins)))
